"""API endpoints for AI-generated explanations (LLM boundary).

Per ENGINE_SPEC.md: try the LLM version, catch any failure or malformed
response, fall back to the template. Log which one was used in the audit trail.
If no ANTHROPIC_API_KEY is configured, the template path is used everywhere
with no visible errors.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.ai_service import (
    generate_llm_cluster_summary,
    generate_llm_explanation,
    generate_template_cluster_summary,
    generate_template_explanation,
)
from app.clustering import ClusterService
from app.config import settings
from app.database import get_db
from app.models.audit_log import AuditLogModel
from app.models.exception import ExceptionModel
from app.schemas.api import ClusterSummaryResponse, ExplanationResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Explanations"])


def _ensure_data_loaded(db: Session):
    """Ensure at least one reconciliation run and exception set exists in DB."""
    count = db.query(ExceptionModel).count()
    if count == 0:
        from app.api.reconciliation import run_reconciliation
        run_reconciliation(db)


@router.get("/exceptions/{id}/explain", response_model=ExplanationResponse)
async def explain_exception(
    id: str = Path(..., description="Exception ID (e.g. exc_...)"),
    db: Session = Depends(get_db),
):
    """Generate a natural-language explanation for an exception.

    Tries the LLM (Anthropic API) first. If the API key is missing, the call
    fails, or the response fails numeric validation, falls back to the
    deterministic template. Which source was used is logged in the audit trail.
    """
    _ensure_data_loaded(db)

    exc = db.query(ExceptionModel).filter_by(id=id).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception with ID '{id}' not found")

    # Build the kwargs that both functions accept
    fields = {
        "exception_type": exc.exception_type,
        "root_cause": exc.root_cause,
        "financial_impact": exc.financial_impact,
        "confidence": exc.confidence,
        "evidence": exc.evidence or [],
        "source_record_id": exc.source_record_id,
        "matched_record_id": exc.matched_record_id,
    }

    result = None
    llm_error: str | None = None

    # --- Attempt LLM path (only if API key is configured) ---
    if settings.gemini_api_key:
        try:
            result = await generate_llm_explanation(
                **fields,
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
            )
            logger.info(
                "LLM explanation generated for exception %s", id
            )
        except Exception as e:
            llm_error = str(e)
            logger.warning(
                "LLM explanation failed for exception %s, falling back to "
                "template: %s",
                id, llm_error,
            )
    else:
        llm_error = "No GEMINI_API_KEY configured"
        logger.debug("No API key configured; using template fallback for %s", id)

    # --- Fallback to template ---
    if result is None:
        result = generate_template_explanation(**fields)

    # --- Write to audit trail ---
    now_utc = datetime.now(UTC)
    audit_id = f"aud_explain_{exc.id}_{int(now_utc.timestamp() * 1000)}"

    if result.source == "LLM":
        actor = "SYSTEM_AI_SERVICE"
        action = "GENERATE_EXPLANATION_LLM"
        details = (
            f"LLM-generated explanation for exception {exc.id} "
            f"({exc.exception_type}): {result.explanation[:200]}"
        )
    elif llm_error == "No GEMINI_API_KEY configured":
        actor = "SYSTEM_TEMPLATE"
        action = "GENERATE_EXPLANATION_TEMPLATE_NO_KEY"
        details = (
            f"Template-generated explanation for exception {exc.id} "
            f"({exc.exception_type}). Reason: {llm_error}"
        )
    else:
        actor = "SYSTEM_TEMPLATE_FALLBACK"
        if "numeric validation" in (llm_error or "").lower():
            action = "GENERATE_EXPLANATION_TEMPLATE_VALIDATION_FAILED"
        else:
            action = "GENERATE_EXPLANATION_TEMPLATE_FALLBACK"
        details = (
            f"Template-generated explanation for exception {exc.id} "
            f"({exc.exception_type}). Reason: {llm_error}"
        )

    audit_entry = AuditLogModel(
        id=audit_id,
        timestamp=now_utc,
        event_type="EXPLANATION_GENERATED",
        transaction_id=exc.source_record_id,
        exception_id=exc.id,
        action=action,
        actor=actor,
        evidence={"source": result.source, "reason": llm_error or "SUCCESS"},
        details=details,
    )
    db.add(audit_entry)
    db.commit()

    return ExplanationResponse(
        exception_id=exc.id,
        explanation=result.explanation,
        action_text=result.action_text,
        source=result.source,
    )


@router.get(
    "/exception-clusters/{cluster_id}/summary",
    response_model=ClusterSummaryResponse,
)
async def summarise_cluster(
    cluster_id: str = Path(..., description="Cluster ID (e.g. cl_fee_mismatch_...)"),
    db: Session = Depends(get_db),
):
    """Generate a natural-language summary for an exception cluster.

    Same LLM-first / template-fallback / audit-trail pattern as the
    single-exception endpoint.
    """
    _ensure_data_loaded(db)

    # Build clusters from current exception set
    exceptions = db.query(ExceptionModel).all()
    cluster_service = ClusterService()
    clusters = cluster_service.build_clusters(exceptions)

    target = next((c for c in clusters if c.cluster_id == cluster_id), None)
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"Cluster with ID '{cluster_id}' not found",
        )

    fields = {
        "exception_type": target.exception_type,
        "root_cause": target.root_cause,
        "record_count": target.record_count,
        "total_financial_impact": target.total_financial_impact,
        "pct_of_all_exceptions": target.pct_of_all_exceptions,
        "avg_confidence": target.avg_confidence,
        "recommended_action": target.recommended_action,
    }

    result = None
    llm_error: str | None = None

    if settings.gemini_api_key:
        try:
            result = await generate_llm_cluster_summary(
                **fields,
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
            )
            logger.info("LLM cluster summary generated for %s", cluster_id)
        except Exception as e:
            llm_error = str(e)
            logger.warning(
                "LLM cluster summary failed for %s, falling back: %s",
                cluster_id, llm_error,
            )
    else:
        llm_error = "No GEMINI_API_KEY configured"

    if result is None:
        result = generate_template_cluster_summary(**fields)

    # --- Write to audit trail ---
    now_utc = datetime.now(UTC)
    audit_id = f"aud_cluster_{cluster_id}_{int(now_utc.timestamp() * 1000)}"

    if result.source == "LLM":
        cl_actor = "SYSTEM_AI_SERVICE"
        cl_action = "GENERATE_CLUSTER_SUMMARY_LLM"
        cl_details = f"LLM-generated summary for cluster {cluster_id}: {result.summary[:200]}"
    elif llm_error == "No GEMINI_API_KEY configured":
        cl_actor = "SYSTEM_TEMPLATE"
        cl_action = "GENERATE_CLUSTER_SUMMARY_TEMPLATE_NO_KEY"
        cl_details = f"Template-generated summary for cluster {cluster_id}. Reason: {llm_error}"
    else:
        cl_actor = "SYSTEM_TEMPLATE_FALLBACK"
        cl_action = "GENERATE_CLUSTER_SUMMARY_TEMPLATE_FALLBACK"
        cl_details = f"Template-generated summary for cluster {cluster_id}. Reason: {llm_error}"

    audit_entry = AuditLogModel(
        id=audit_id,
        timestamp=now_utc,
        event_type="CLUSTER_SUMMARY_GENERATED",
        transaction_id=None,
        exception_id=None,
        action=cl_action,
        actor=cl_actor,
        evidence={"cluster_id": cluster_id, "source": result.source, "reason": llm_error or "SUCCESS"},
        details=cl_details,
    )
    db.add(audit_entry)
    db.commit()

    return ClusterSummaryResponse(
        cluster_id=cluster_id,
        summary=result.summary,
        source=result.source,
    )
