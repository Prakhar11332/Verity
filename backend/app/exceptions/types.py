from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class ExceptionType(enum.StrEnum):
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    FEE_MISMATCH = "FEE_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_IN_BANK = "MISSING_IN_BANK"
    MISSING_IN_RAZORPAY = "MISSING_IN_RAZORPAY"
    MISSING_IN_LEDGER = "MISSING_IN_LEDGER"
    SETTLEMENT_TIMING = "SETTLEMENT_TIMING"
    REFUND_MISMATCH = "REFUND_MISMATCH"
    PARTIAL_SETTLEMENT = "PARTIAL_SETTLEMENT"
    WRONG_REFERENCE = "WRONG_REFERENCE"
    UNKNOWN = "UNKNOWN"


class ResolutionStatus(enum.StrEnum):
    AUTO_RESOLVE = "AUTO_RESOLVE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class ClassifiedException:
    """Structured exception object per PRD and ENGINE_SPEC."""
    id: str
    exception_type: str
    root_cause: str | None  # None for UNKNOWN
    financial_impact: Decimal
    confidence: float
    evidence: list[dict[str, Any]]
    recommended_action: str
    resolution_status: str
    source_record_id: str
    matched_record_id: str | None = None
    rule_number: int = 11
