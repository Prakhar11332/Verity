from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ReconciliationRunModel(Base):
    """SQLAlchemy model representing a full reconciliation execution run."""
    __tablename__ = "reconciliation_runs"

    id = Column(String(64), primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    total_records = Column(Integer, nullable=False, default=0)
    matched_count = Column(Integer, nullable=False, default=0)
    likely_match_count = Column(Integer, nullable=False, default=0)
    exception_count = Column(Integer, nullable=False, default=0)
    unresolved_count = Column(Integer, nullable=False, default=0)
    match_rate = Column(Float, nullable=False, default=0.0)
    total_processed_value = Column(Numeric(14, 2), nullable=False, default=0.0)
    matched_value = Column(Numeric(14, 2), nullable=False, default=0.0)
    exception_value = Column(Numeric(14, 2), nullable=False, default=0.0)
    unresolved_value = Column(Numeric(14, 2), nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="COMPLETED")

    # Relationships
    records = relationship("ReconciliationRecordModel", back_populates="run", cascade="all, delete-orphan")


class ReconciliationRecordModel(Base):
    """SQLAlchemy model representing a pair or record outcome from a reconciliation run."""
    __tablename__ = "reconciliation_records"

    id = Column(String(64), primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("reconciliation_runs.id"), nullable=False, index=True)
    record_a_id = Column(String(64), ForeignKey("source_records.transaction_id"), nullable=False, index=True)
    record_b_id = Column(String(64), ForeignKey("source_records.transaction_id"), nullable=True, index=True)
    match_score = Column(Float, nullable=False, default=0.0)
    match_level = Column(String(64), nullable=False)
    classification = Column(String(32), nullable=False, index=True)
    score_components = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    # Relationships
    run = relationship("ReconciliationRunModel", back_populates="records")
    record_a = relationship("SourceRecordModel", foreign_keys=[record_a_id])
    record_b = relationship("SourceRecordModel", foreign_keys=[record_b_id])
