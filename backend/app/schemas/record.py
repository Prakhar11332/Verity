"""Pydantic schemas and enums for the normalized record format and reconciliation results.

All fields match DATA_MODEL.md exactly.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TransactionType(enum.StrEnum):
    PAYMENT = "payment"
    REFUND = "refund"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


class PaymentMethod(enum.StrEnum):
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMI = "emi"


class TransactionStatus(enum.StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REVERSED = "reversed"


class SourceName(enum.StrEnum):
    RAZORPAY = "razorpay"
    BANK = "bank"
    LEDGER = "ledger"
    SETTLEMENT = "settlement"


class MatchStatus(enum.StrEnum):
    MATCHED = "MATCHED"
    LIKELY_MATCH = "LIKELY_MATCH"
    EXCEPTION = "EXCEPTION"
    UNRESOLVED = "UNRESOLVED"


class MatchLevel(enum.StrEnum):
    """Which pipeline level produced this match."""
    LEVEL_1_EXACT_ID = "LEVEL_1_EXACT_ID"
    LEVEL_2_EXACT_AMOUNT_DATE = "LEVEL_2_EXACT_AMOUNT_DATE"
    LEVEL_3_TOLERANT_AMOUNT = "LEVEL_3_TOLERANT_AMOUNT"
    LEVEL_4_FUZZY_REFERENCE = "LEVEL_4_FUZZY_REFERENCE"
    LEVEL_5_COMPOSITE = "LEVEL_5_COMPOSITE"
    NONE = "NONE"


# ---------------------------------------------------------------------------
# Normalized Record — the single shape the engine sees
# ---------------------------------------------------------------------------

@dataclass
class Record:
    """Normalized record from any financial source.

    The reconciliation engine operates only on this shape; adapters are
    responsible for mapping their raw data into it.
    """
    transaction_id: str
    source_name: str  # "razorpay" | "bank" | "ledger" | "settlement"
    amount: Decimal
    transaction_date: date
    transaction_type: str  # TransactionType value
    status: str  # TransactionStatus value
    description: str
    merchant_id: str
    currency: str = "INR"
    payment_id: str | None = None
    order_id: str | None = None
    settlement_id: str | None = None
    settlement_utr: str | None = None
    settlement_date: date | None = None
    fee: Decimal | None = None
    tax: Decimal | None = None
    net_amount: Decimal | None = None
    payment_method: str | None = None  # PaymentMethod value
    bank_reference: str | None = None


# ---------------------------------------------------------------------------
# Reconciliation Result
# ---------------------------------------------------------------------------

@dataclass
class ReconciliationResult:
    """Outcome of matching a single record (or pair) through the pipeline."""
    record_a: Record                         # primary record (usually Razorpay)
    record_b: Record | None = None        # matched counterpart, if any
    match_score: float = 0.0
    match_level: str = MatchLevel.NONE.value
    classification: str = MatchStatus.UNRESOLVED.value
    score_components: dict = field(default_factory=dict)


@dataclass
class ReconciliationSummary:
    """Aggregate output of a full reconciliation run."""
    results: list[ReconciliationResult] = field(default_factory=list)
    total_records: int = 0
    matched_count: int = 0
    likely_match_count: int = 0
    exception_count: int = 0
    unresolved_count: int = 0
    match_rate: float = 0.0
    total_processed_value: Decimal = Decimal(0)
    matched_value: Decimal = Decimal(0)
    exception_value: Decimal = Decimal(0)
    unresolved_value: Decimal = Decimal(0)
