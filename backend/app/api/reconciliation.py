"""Reconciliation API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.adapters import (
    BankAdapter,
    LedgerAdapter,
    RazorpayAdapter,
    SettlementAdapter,
)
from app.database import get_db
from app.exceptions.classifier import ExceptionClassifierService
from app.exceptions.repository import ExceptionRepository
from app.models.audit_log import AuditLogModel
from app.models.reconciliation import ReconciliationRecordModel, ReconciliationRunModel
from app.models.source_record import SourceRecordModel
from app.reconciliation.engine import ReconciliationEngine
from app.schemas.api import ReconciliationRecordItem, ReconciliationSummaryResponse

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post("/run", response_model=ReconciliationSummaryResponse)
def run_reconciliation(db: Session = Depends(get_db)):
    """Trigger complete ingestion from all 4 sources, run 5-level matching,

    classify exceptions, persist to database, and log audit trail.
    """
    now_utc = datetime.now(UTC)
    run_id = f"run_{int(now_utc.timestamp() * 1000)}"

    # 1. Ingest records from all 4 source adapters
    sources = {
        "razorpay": RazorpayAdapter().fetch_records(),
        "bank": BankAdapter().fetch_records(),
        "ledger": LedgerAdapter().fetch_records(),
        "settlement": SettlementAdapter().fetch_records(),
    }

    # 2. Persist source records
    repo = ExceptionRepository(db)
    all_records = []
    for record_list in sources.values():
        all_records.extend(record_list)
    repo.save_source_records(all_records)

    # 3. Execute 5-level reconciliation engine
    engine = ReconciliationEngine()
    summary = engine.reconcile(sources)

    # 4. Save reconciliation run model
    run_model = ReconciliationRunModel(
        id=run_id,
        created_at=now_utc,
        total_records=summary.total_records,
        matched_count=summary.matched_count,
        likely_match_count=summary.likely_match_count,
        exception_count=summary.exception_count,
        unresolved_count=summary.unresolved_count,
        match_rate=round(summary.match_rate, 4),
        total_processed_value=summary.total_processed_value,
        matched_value=summary.matched_value,
        exception_value=summary.exception_value,
        unresolved_value=summary.unresolved_value,
        status="COMPLETED",
    )
    db.add(run_model)

    # 5. Save reconciliation records
    for idx, r in enumerate(summary.results):
        rec_model = ReconciliationRecordModel(
            id=f"rec_{run_id}_{idx}",
            run_id=run_id,
            record_a_id=r.record_a.transaction_id,
            record_b_id=r.record_b.transaction_id if r.record_b else None,
            match_score=r.match_score,
            match_level=r.match_level,
            classification=r.classification,
            score_components=r.score_components,
            created_at=now_utc,
        )
        db.add(rec_model)

    # Log run in audit trail
    audit_run = AuditLogModel(
        id=f"aud_{run_id}_{int(now_utc.timestamp() * 1000)}",
        timestamp=now_utc,
        event_type="RECONCILIATION_RUN_COMPLETED",
        transaction_id=None,
        exception_id=None,
        action="RUN_RECONCILIATION",
        actor="SYSTEM_DETERMINISTIC",
        evidence={
            "total_records": summary.total_records,
            "match_rate": summary.match_rate,
            "matched_count": summary.matched_count,
            "exception_count": summary.exception_count + summary.likely_match_count,
            "unresolved_count": summary.unresolved_count,
        },
        details=f"Reconciliation run {run_id} completed: {summary.total_records} processed, match rate {summary.match_rate:.1%}",
    )
    db.add(audit_run)
    db.commit()

    # 6. Classify exceptions and persist with initial audit logs
    classifier = ExceptionClassifierService()
    exceptions = classifier.classify_all_exceptions(summary, sources)
    repo.save_all_exceptions(exceptions)

    return ReconciliationSummaryResponse(
        run_id=run_model.id,
        created_at=run_model.created_at,
        total_records=run_model.total_records,
        matched_count=run_model.matched_count,
        likely_match_count=run_model.likely_match_count,
        exception_count=run_model.exception_count,
        unresolved_count=run_model.unresolved_count,
        match_rate=run_model.match_rate,
        total_processed_value=run_model.total_processed_value,
        matched_value=run_model.matched_value,
        exception_value=run_model.exception_value,
        unresolved_value=run_model.unresolved_value,
        status=run_model.status,
    )


@router.get("/summary", response_model=ReconciliationSummaryResponse)
def get_reconciliation_summary(db: Session = Depends(get_db)):
    """Retrieve the latest reconciliation run summary."""
    latest_run = (
        db.query(ReconciliationRunModel)
        .order_by(ReconciliationRunModel.created_at.desc())
        .first()
    )
    if not latest_run:
        # If no run exists in DB yet, execute one automatically
        return run_reconciliation(db)

    return ReconciliationSummaryResponse(
        run_id=latest_run.id,
        created_at=latest_run.created_at,
        total_records=latest_run.total_records,
        matched_count=latest_run.matched_count,
        likely_match_count=latest_run.likely_match_count,
        exception_count=latest_run.exception_count,
        unresolved_count=latest_run.unresolved_count,
        match_rate=latest_run.match_rate,
        total_processed_value=latest_run.total_processed_value,
        matched_value=latest_run.matched_value,
        exception_value=latest_run.exception_value,
        unresolved_value=latest_run.unresolved_value,
        status=latest_run.status,
    )


@router.get("/records", response_model=list[ReconciliationRecordItem])
def get_reconciliation_records(
    classification: str | None = Query(None, description="Filter by MATCHED, LIKELY_MATCH, EXCEPTION, UNRESOLVED"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve matched and exception candidate records from the latest reconciliation run."""
    latest_run = (
        db.query(ReconciliationRunModel)
        .order_by(ReconciliationRunModel.created_at.desc())
        .first()
    )
    if not latest_run:
        run_reconciliation(db)
        latest_run = (
            db.query(ReconciliationRunModel)
            .order_by(ReconciliationRunModel.created_at.desc())
            .first()
        )

    query = db.query(ReconciliationRecordModel).filter_by(run_id=latest_run.id)
    if classification:
        query = query.filter(ReconciliationRecordModel.classification == classification.upper())

    records = query.offset(offset).limit(limit).all()

    # Enrich with source record details
    output = []
    for r in records:
        src_a = db.query(SourceRecordModel).filter_by(transaction_id=r.record_a_id).first()
        src_b = (
            db.query(SourceRecordModel).filter_by(transaction_id=r.record_b_id).first()
            if r.record_b_id
            else None
        )

        diff = None
        if src_a and src_b and src_a.amount is not None and src_b.amount is not None:
            diff = abs(src_a.amount - src_b.amount)

        output.append(
            ReconciliationRecordItem(
                id=r.id,
                run_id=r.run_id,
                record_a_id=r.record_a_id,
                record_b_id=r.record_b_id,
                match_score=r.match_score,
                match_level=r.match_level,
                classification=r.classification,
                score_components=r.score_components,
                created_at=r.created_at,
                record_a_amount=src_a.amount if src_a else None,
                record_a_source=src_a.source_name if src_a else None,
                record_b_amount=src_b.amount if src_b else None,
                record_b_source=src_b.source_name if src_b else None,
                difference=diff,
            )
        )

    return output
