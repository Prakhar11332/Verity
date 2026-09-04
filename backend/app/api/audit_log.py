"""Audit Log API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLogModel
from app.schemas.api import AuditLogEntryResponse

router = APIRouter(tags=["Audit Log"])


@router.get("/audit-log", response_model=list[AuditLogEntryResponse])
def get_audit_log(
    transaction_id: str | None = Query(None, description="Filter audit events by transaction ID"),
    exception_id: str | None = Query(None, description="Filter audit events by exception ID"),
    event_type: str | None = Query(None, description="Filter by event type (e.g. EXCEPTION_CLASSIFIED, RESOLUTION_APPROVED)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Query immutable audit log entries in chronological order with timestamps."""
    query = db.query(AuditLogModel)

    if transaction_id:
        query = query.filter(AuditLogModel.transaction_id == transaction_id)
    if exception_id:
        query = query.filter(AuditLogModel.exception_id == exception_id)
    if event_type:
        query = query.filter(AuditLogModel.event_type == event_type.upper())

    # Return in strict chronological order per ENGINE_SPEC.md requirement
    entries = query.order_by(AuditLogModel.timestamp.asc()).offset(offset).limit(limit).all()

    return entries
