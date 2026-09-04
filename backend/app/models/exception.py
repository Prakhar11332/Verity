from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ExceptionModel(Base):
    """SQLAlchemy model representing a classified reconciliation exception."""
    __tablename__ = "exceptions"

    id = Column(String(64), primary_key=True, index=True)
    exception_type = Column(String(64), nullable=False, index=True)
    root_cause = Column(Text, nullable=True)  # Null for UNKNOWN exceptions
    financial_impact = Column(Numeric(12, 2), nullable=False, default=0.0)
    confidence = Column(Float, nullable=False)
    evidence = Column(JSON, nullable=False)
    recommended_action = Column(Text, nullable=False)
    resolution_status = Column(String(32), nullable=False, index=True)  # AUTO_RESOLVE | REVIEW_REQUIRED | UNRESOLVED

    # Foreign keys referencing source records
    source_record_id = Column(String(64), ForeignKey("source_records.transaction_id"), nullable=False, index=True)
    matched_record_id = Column(String(64), ForeignKey("source_records.transaction_id"), nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    source_record = relationship("SourceRecordModel", foreign_keys=[source_record_id])
    matched_record = relationship("SourceRecordModel", foreign_keys=[matched_record_id])
