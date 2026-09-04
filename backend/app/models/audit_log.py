from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLogModel(Base):
    """SQLAlchemy model for the immutable audit trail of reconciliation actions and decisions."""
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    event_type = Column(String(64), nullable=False, index=True)  # e.g. EXCEPTION_CLASSIFIED, RESOLUTION_APPROVED
    transaction_id = Column(String(64), ForeignKey("source_records.transaction_id"), nullable=True, index=True)
    exception_id = Column(String(64), ForeignKey("exceptions.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    actor = Column(String(64), nullable=False, default="SYSTEM_DETERMINISTIC")
    evidence = Column(JSON, nullable=True)
    details = Column(Text, nullable=False)

    # Relationships
    transaction = relationship("SourceRecordModel", foreign_keys=[transaction_id])
    exception = relationship("ExceptionModel", foreign_keys=[exception_id])
