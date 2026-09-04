"""Exception Center and Pattern Insights API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.clustering import ClusterService
from app.database import get_db
from app.models.audit_log import AuditLogModel
from app.models.exception import ExceptionModel
from app.models.source_record import SourceRecordModel
from app.schemas.api import (
    ActionRequest,
    ActionResponse,
    AuditLogEntryResponse,
    ExceptionClusterResponse,
    ExceptionDetailResponse,
    ExceptionListItem,
    SourceRecordDetail,
)

router = APIRouter(tags=["Exceptions"])


def _ensure_data_loaded(db: Session):
    """Ensure at least one reconciliation run and exception set exists in DB."""
    count = db.query(ExceptionModel).count()
    if count == 0:
        from app.api.reconciliation import run_reconciliation
        run_reconciliation(db)


@router.get("/exceptions", response_model=list[ExceptionListItem])
def list_exceptions(
    status: str | None = Query(None, description="Filter by resolution_status: AUTO_RESOLVE, REVIEW_REQUIRED, UNRESOLVED, APPROVED, REJECTED"),
    exception_type: str | None = Query(None, description="Filter by exception_type (e.g. FEE_MISMATCH, SETTLEMENT_TIMING)"),
    min_impact: float | None = Query(None, description="Minimum financial impact threshold"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List exceptions with optional filters for status, type, and impact."""
    _ensure_data_loaded(db)

    query = db.query(ExceptionModel)

    if status:
        query = query.filter(ExceptionModel.resolution_status == status.upper())
    if exception_type:
        query = query.filter(ExceptionModel.exception_type == exception_type.upper())
    if min_impact is not None:
        query = query.filter(ExceptionModel.financial_impact >= min_impact)

    exceptions = (
        query.order_by(ExceptionModel.financial_impact.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return exceptions


@router.get("/exceptions/{id}", response_model=ExceptionDetailResponse)
def get_exception_detail(
    id: str = Path(..., description="Exception ID (e.g. exc_...)"),
    db: Session = Depends(get_db),
):
    """Retrieve full exception detail including side-by-side source records and decision audit trail."""
    _ensure_data_loaded(db)

    exc = db.query(ExceptionModel).filter_by(id=id).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception with ID '{id}' not found")

    # Fetch source record and matched counterpart
    src_rec = db.query(SourceRecordModel).filter_by(transaction_id=exc.source_record_id).first()
    matched_rec = (
        db.query(SourceRecordModel).filter_by(transaction_id=exc.matched_record_id).first()
        if exc.matched_record_id
        else None
    )

    # Fetch related audit log entries
    audit_entries = (
        db.query(AuditLogModel)
        .filter(
            (AuditLogModel.exception_id == exc.id)
            | (AuditLogModel.transaction_id == exc.source_record_id)
        )
        .order_by(AuditLogModel.timestamp.asc())
        .all()
    )

    return ExceptionDetailResponse(
        id=exc.id,
        exception_type=exc.exception_type,
        root_cause=exc.root_cause,
        financial_impact=exc.financial_impact,
        confidence=exc.confidence,
        evidence=exc.evidence,
        recommended_action=exc.recommended_action,
        resolution_status=exc.resolution_status,
        source_record_id=exc.source_record_id,
        matched_record_id=exc.matched_record_id,
        created_at=exc.created_at,
        updated_at=exc.updated_at,
        source_record=SourceRecordDetail.model_validate(src_rec) if src_rec else None,
        matched_record=SourceRecordDetail.model_validate(matched_rec) if matched_rec else None,
        audit_trail=[AuditLogEntryResponse.model_validate(a) for a in audit_entries],
    )


@router.post("/exceptions/{id}/approve", response_model=ActionResponse)
def approve_exception(
    id: str = Path(..., description="Exception ID to approve"),
    request: ActionRequest | None = None,
    db: Session = Depends(get_db),
):
    """Approve an exception resolution action and record an immutable audit trail entry."""
    req = request or ActionRequest()
    _ensure_data_loaded(db)

    exc = db.query(ExceptionModel).filter_by(id=id).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception with ID '{id}' not found")

    now_utc = datetime.now(UTC)
    exc.resolution_status = "APPROVED"
    exc.updated_at = now_utc

    # Write approval to audit log
    audit_id = f"aud_appr_{exc.id}_{int(now_utc.timestamp() * 1000)}"
    audit_entry = AuditLogModel(
        id=audit_id,
        timestamp=now_utc,
        event_type="RESOLUTION_APPROVED",
        transaction_id=exc.source_record_id,
        exception_id=exc.id,
        action="APPROVE_RESOLUTION",
        actor=req.actor or "OPERATOR",
        evidence=exc.evidence,
        details=f"Operator approved resolution for exception {exc.id} ({exc.exception_type}): {exc.recommended_action}. Notes: {req.notes or 'None'}",
    )
    db.add(audit_entry)
    db.commit()

    return ActionResponse(
        success=True,
        exception_id=exc.id,
        new_status="APPROVED",
        message=f"Exception {exc.id} resolution successfully approved",
        audit_log_id=audit_id,
    )


@router.post("/exceptions/{id}/reject", response_model=ActionResponse)
def reject_exception(
    id: str = Path(..., description="Exception ID to reject"),
    request: ActionRequest | None = None,
    db: Session = Depends(get_db),
):
    """Reject an exception resolution action and record an immutable audit trail entry."""
    req = request or ActionRequest()
    _ensure_data_loaded(db)

    exc = db.query(ExceptionModel).filter_by(id=id).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception with ID '{id}' not found")

    now_utc = datetime.now(UTC)
    exc.resolution_status = "REJECTED"
    exc.updated_at = now_utc

    # Write rejection to audit log
    audit_id = f"aud_rej_{exc.id}_{int(now_utc.timestamp() * 1000)}"
    audit_entry = AuditLogModel(
        id=audit_id,
        timestamp=now_utc,
        event_type="RESOLUTION_REJECTED",
        transaction_id=exc.source_record_id,
        exception_id=exc.id,
        action="REJECT_RESOLUTION",
        actor=req.actor or "OPERATOR",
        evidence=exc.evidence,
        details=f"Operator rejected resolution for exception {exc.id} ({exc.exception_type}). Reason: {req.notes or 'No reason provided'}",
    )
    db.add(audit_entry)
    db.commit()

    return ActionResponse(
        success=True,
        exception_id=exc.id,
        new_status="REJECTED",
        message=f"Exception {exc.id} resolution rejected",
        audit_log_id=audit_id,
    )


@router.post("/exceptions/{id}/unresolve", response_model=ActionResponse)
def unresolve_exception(
    id: str = Path(..., description="Exception ID to mark as unresolved"),
    request: ActionRequest | None = None,
    db: Session = Depends(get_db),
):
    """Mark an exception resolution as UNRESOLVED and record an immutable audit trail entry."""
    req = request or ActionRequest()
    _ensure_data_loaded(db)

    exc = db.query(ExceptionModel).filter_by(id=id).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception with ID '{id}' not found")

    now_utc = datetime.now(UTC)
    exc.resolution_status = "UNRESOLVED"
    exc.updated_at = now_utc

    audit_id = f"aud_unres_{exc.id}_{int(now_utc.timestamp() * 1000)}"
    audit_entry = AuditLogModel(
        id=audit_id,
        timestamp=now_utc,
        event_type="RESOLUTION_UNRESOLVED",
        transaction_id=exc.source_record_id,
        exception_id=exc.id,
        action="UNRESOLVE_EXCEPTION",
        actor=req.actor or "OPERATOR",
        evidence=exc.evidence,
        details=f"Operator marked exception {exc.id} ({exc.exception_type}) as UNRESOLVED. Reason: {req.notes or 'No reason provided'}",
    )
    db.add(audit_entry)
    db.commit()

    return ActionResponse(
        success=True,
        exception_id=exc.id,
        new_status="UNRESOLVED",
        message=f"Exception {exc.id} marked as unresolved",
        audit_log_id=audit_id,
    )



@router.get("/exception-clusters", response_model=list[ExceptionClusterResponse])
def get_exception_clusters(db: Session = Depends(get_db)):
    """Retrieve exception clusters grouped by (exception_type, root_cause) signature,

    ranked by investigation priority score in descending order.
    """
    _ensure_data_loaded(db)

    exceptions = db.query(ExceptionModel).all()
    cluster_service = ClusterService()
    clusters = cluster_service.build_clusters(exceptions)

    return [
        ExceptionClusterResponse(
            cluster_id=c.cluster_id,
            exception_type=c.exception_type,
            root_cause=c.root_cause,
            record_count=c.record_count,
            total_financial_impact=c.total_financial_impact,
            pct_of_all_exceptions=c.pct_of_all_exceptions,
            avg_confidence=c.avg_confidence,
            recommended_action=c.recommended_action,
            exception_ids=c.exception_ids,
            priority_score=c.priority_score,
        )
        for c in clusters
    ]


@router.get("/exception-clusters/{id}", response_model=ExceptionClusterResponse)
def get_exception_cluster_detail(
    id: str = Path(..., description="Cluster ID (e.g. cl_fee_mismatch_...)"),
    db: Session = Depends(get_db),
):
    """Retrieve a single exception cluster by its cluster ID."""
    _ensure_data_loaded(db)

    exceptions = db.query(ExceptionModel).all()
    cluster_service = ClusterService()
    clusters = cluster_service.build_clusters(exceptions)

    target = next((c for c in clusters if c.cluster_id == id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Cluster with ID '{id}' not found")

    return ExceptionClusterResponse(
        cluster_id=target.cluster_id,
        exception_type=target.exception_type,
        root_cause=target.root_cause,
        record_count=target.record_count,
        total_financial_impact=target.total_financial_impact,
        pct_of_all_exceptions=target.pct_of_all_exceptions,
        avg_confidence=target.avg_confidence,
        recommended_action=target.recommended_action,
        exception_ids=target.exception_ids,
        priority_score=target.priority_score,
    )

