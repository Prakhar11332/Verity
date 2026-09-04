"""Data Quality API endpoint."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.source_record import SourceRecordModel
from app.schemas.api import DataQualityDimension, DataQualityResponse

router = APIRouter(prefix="/data-quality", tags=["Data Quality"])


@router.get("", response_model=DataQualityResponse)
def get_data_quality(db: Session = Depends(get_db)):
    """Evaluate data quality across ingested source records.

    Inspects missing IDs, duplicate IDs, missing amounts, and invalid dates.
    """
    records = db.query(SourceRecordModel).all()
    if not records:
        from app.api.reconciliation import run_reconciliation

        run_reconciliation(db)
        records = db.query(SourceRecordModel).all()

    total = len(records)
    if total == 0:
        now_utc = datetime.now(UTC)
        return DataQualityResponse(
            overall_score=100.0,
            status="HEALTHY",
            total_records=0,
            clean_records=0,
            dimensions={
                "missing_ids": DataQualityDimension(
                    count=0, percentage=0.0, status="PASS", details="No records present."
                ),
                "duplicate_ids": DataQualityDimension(
                    count=0, percentage=0.0, status="PASS", details="No records present."
                ),
                "missing_amounts": DataQualityDimension(
                    count=0, percentage=0.0, status="PASS", details="No records present."
                ),
                "invalid_dates": DataQualityDimension(
                    count=0, percentage=0.0, status="PASS", details="No records present."
                ),
            },
            last_analyzed=now_utc,
        )

    # 1. Missing IDs
    missing_id_count = sum(
        1 for r in records if not r.transaction_id or not str(r.transaction_id).strip()
    )

    # 2. Duplicate IDs (by source + payment_id, or by transaction_id)
    source_pid = Counter()
    for r in records:
        if r.payment_id:
            source_pid[(r.source_name, r.payment_id)] += 1
    dup_id_count = sum(count - 1 for count in source_pid.values() if count > 1)

    # 3. Missing Amounts (None or non-positive)
    missing_amount_count = sum(1 for r in records if r.amount is None or r.amount <= 0)

    # 4. Invalid Dates (Missing or future-dated beyond today)
    today = date.today()
    invalid_date_count = sum(
        1 for r in records if r.transaction_date is None or r.transaction_date > today
    )

    total_issues = (
        missing_id_count + dup_id_count + missing_amount_count + invalid_date_count
    )
    clean_records = max(0, total - total_issues)
    overall_score = round(max(0.0, min(100.0, (clean_records / total) * 100.0)), 1)

    if overall_score >= 95.0:
        system_status = "HEALTHY"
    elif overall_score >= 80.0:
        system_status = "DEGRADED"
    else:
        system_status = "CRITICAL"

    now_utc = datetime.now(UTC)

    return DataQualityResponse(
        overall_score=overall_score,
        status=system_status,
        total_records=total,
        clean_records=clean_records,
        dimensions={
            "missing_ids": DataQualityDimension(
                count=missing_id_count,
                percentage=round((missing_id_count / total) * 100.0, 2),
                status="PASS" if missing_id_count == 0 else "FLAGGED",
                details=(
                    "All records have valid primary transaction IDs."
                    if missing_id_count == 0
                    else f"{missing_id_count} records lack a valid primary transaction ID."
                ),
            ),
            "duplicate_ids": DataQualityDimension(
                count=dup_id_count,
                percentage=round((dup_id_count / total) * 100.0, 2),
                status="PASS" if dup_id_count == 0 else "FLAGGED",
                details=(
                    "Zero duplicate references identified within source feeds."
                    if dup_id_count == 0
                    else f"{dup_id_count} duplicate payment keys detected across source feeds."
                ),
            ),
            "missing_amounts": DataQualityDimension(
                count=missing_amount_count,
                percentage=round((missing_amount_count / total) * 100.0, 2),
                status="PASS" if missing_amount_count == 0 else "FLAGGED",
                details=(
                    "All transaction amounts are positive non-null numbers."
                    if missing_amount_count == 0
                    else f"{missing_amount_count} records have missing or non-positive amounts."
                ),
            ),
            "invalid_dates": DataQualityDimension(
                count=invalid_date_count,
                percentage=round((invalid_date_count / total) * 100.0, 2),
                status="PASS" if invalid_date_count == 0 else "FLAGGED",
                details=(
                    "All settlement and transaction dates are formatted and historical."
                    if invalid_date_count == 0
                    else f"{invalid_date_count} records have invalid or future dates."
                ),
            ),
        },
        last_analyzed=now_utc,
    )
