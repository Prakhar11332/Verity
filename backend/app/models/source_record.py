from sqlalchemy import Column, Date, Numeric, String, Text

from app.database import Base


class SourceRecordModel(Base):
    """SQLAlchemy model representing an ingested financial source record."""
    __tablename__ = "source_records"

    transaction_id = Column(String(64), primary_key=True, index=True)
    source_name = Column(String(32), nullable=False, index=True)  # razorpay, bank, ledger, settlement
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="INR")
    transaction_date = Column(Date, nullable=False, index=True)
    settlement_date = Column(Date, nullable=True)
    transaction_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    description = Column(Text, nullable=True)
    merchant_id = Column(String(64), nullable=True, index=True)
    payment_id = Column(String(64), nullable=True, index=True)
    order_id = Column(String(64), nullable=True, index=True)
    settlement_id = Column(String(64), nullable=True, index=True)
    settlement_utr = Column(String(64), nullable=True, index=True)
    fee = Column(Numeric(12, 2), nullable=True)
    tax = Column(Numeric(12, 2), nullable=True)
    net_amount = Column(Numeric(12, 2), nullable=True)
    payment_method = Column(String(32), nullable=True)
    bank_reference = Column(String(64), nullable=True, index=True)
