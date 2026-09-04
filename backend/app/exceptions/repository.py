"""Repository for persisting source records, exceptions, and initial audit logs.

Handles database transactions, foreign key integrity, and audit logging.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.exceptions.types import ClassifiedException
from app.models.audit_log import AuditLogModel
from app.models.exception import ExceptionModel
from app.models.source_record import SourceRecordModel
from app.schemas.record import Record


class ExceptionRepository:
    """Handles database persistence for source records, exceptions, and audit trails."""

    def __init__(self, db: Session):
        self.db = db

    def save_source_records(self, records: list[Record]) -> None:
        """Upsert/insert normalized source records into the source_records table."""
        for r in records:
            existing = self.db.query(SourceRecordModel).filter_by(transaction_id=r.transaction_id).first()
            if not existing:
                model = SourceRecordModel(
                    transaction_id=r.transaction_id,
                    source_name=r.source_name,
                    amount=r.amount,
                    currency=r.currency or "INR",
                    transaction_date=r.transaction_date,
                    settlement_date=r.settlement_date,
                    transaction_type=r.transaction_type,
                    status=r.status,
                    description=r.description,
                    merchant_id=r.merchant_id,
                    payment_id=r.payment_id,
                    order_id=r.order_id,
                    settlement_id=r.settlement_id,
                    settlement_utr=r.settlement_utr,
                    fee=r.fee,
                    tax=r.tax,
                    net_amount=r.net_amount,
                    payment_method=r.payment_method,
                    bank_reference=r.bank_reference,
                )
                self.db.add(model)
        self.db.commit()

    def save_exception(self, exception: ClassifiedException) -> ExceptionModel:
        """Persist a ClassifiedException and record its initial audit log entry."""
        # Check existing exception
        existing = self.db.query(ExceptionModel).filter_by(id=exception.id).first()
        if existing:
            existing.exception_type = exception.exception_type
            existing.root_cause = exception.root_cause
            existing.financial_impact = exception.financial_impact
            existing.confidence = exception.confidence
            existing.evidence = exception.evidence
            existing.recommended_action = exception.recommended_action
            existing.resolution_status = exception.resolution_status
            existing.updated_at = datetime.now(UTC)
            model = existing
        else:
            model = ExceptionModel(
                id=exception.id,
                exception_type=exception.exception_type,
                root_cause=exception.root_cause,
                financial_impact=exception.financial_impact,
                confidence=exception.confidence,
                evidence=exception.evidence,
                recommended_action=exception.recommended_action,
                resolution_status=exception.resolution_status,
                source_record_id=exception.source_record_id,
                matched_record_id=exception.matched_record_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.db.add(model)

        self.db.flush()

        # Write initial audit log entry per requirement:
        # "Exception classified as X, confidence Y%, evidence: [...]"
        evidence_str = json.dumps(exception.evidence, default=str)
        now_utc = datetime.now(UTC)
        audit_entry = AuditLogModel(
            id=f"aud_{exception.id}_{int(now_utc.timestamp() * 1000)}",
            timestamp=now_utc,
            event_type="EXCEPTION_CLASSIFIED",
            transaction_id=exception.source_record_id,
            exception_id=model.id,
            action="CLASSIFY_EXCEPTION",
            actor="SYSTEM_DETERMINISTIC",
            evidence=exception.evidence,
            details=f"Exception classified as {exception.exception_type}, confidence {exception.confidence * 100:.1f}%, evidence: {evidence_str}",
        )
        self.db.add(audit_entry)
        self.db.commit()

        return model

    def save_all_exceptions(self, exceptions: list[ClassifiedException]) -> list[ExceptionModel]:
        """Batch save exceptions and their corresponding audit logs."""
        saved_models = []
        for exc in exceptions:
            saved_models.append(self.save_exception(exc))
        return saved_models
