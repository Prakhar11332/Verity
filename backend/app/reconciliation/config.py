"""Reconciliation engine configuration — weights, thresholds, and windows.

All configurable parameters live here in one place, per ENGINE_SPEC.md:
"Weights live in one config object (MatchingWeights), not scattered constants."
"""

from dataclasses import dataclass


@dataclass
class MatchingWeights:
    """Composite score weights from ENGINE_SPEC.md."""
    reference_match: float = 0.35
    amount_match: float = 0.25
    date_proximity: float = 0.15
    transaction_type_match: float = 0.10
    merchant_match: float = 0.10
    description_similarity: float = 0.05


@dataclass
class ClassificationThresholds:
    """Score thresholds for match classification."""
    matched: float = 0.95       # >= 0.95 → MATCHED
    likely_match: float = 0.80  # 0.80 - 0.949 → LIKELY_MATCH
    exception: float = 0.50     # 0.50 - 0.799 → EXCEPTION
    # < 0.50 or no candidate → UNRESOLVED


@dataclass
class DateWindows:
    """Date tolerance windows in days."""
    exact_date: int = 3    # Level 2: exact amount + date within 3 days
    wide_date: int = 7     # Level 3: tolerant amount + wider date window


@dataclass
class AmountTolerance:
    """Amount tolerance in currency units (₹)."""
    small: float = 1.0  # Level 3: ₹1 tolerance for rounding


@dataclass
class FuzzyMatchConfig:
    """Fuzzy string matching configuration."""
    min_similarity: float = 0.85  # Level 4: minimum similarity for fuzzy reference match


@dataclass
class ReconciliationConfig:
    """Top-level reconciliation configuration grouping all settings."""
    weights: MatchingWeights = None
    thresholds: ClassificationThresholds = None
    date_windows: DateWindows = None
    amount_tolerance: AmountTolerance = None
    fuzzy_match: FuzzyMatchConfig = None

    def __post_init__(self):
        if self.weights is None:
            self.weights = MatchingWeights()
        if self.thresholds is None:
            self.thresholds = ClassificationThresholds()
        if self.date_windows is None:
            self.date_windows = DateWindows()
        if self.amount_tolerance is None:
            self.amount_tolerance = AmountTolerance()
        if self.fuzzy_match is None:
            self.fuzzy_match = FuzzyMatchConfig()


# Default configuration instance
default_config = ReconciliationConfig()
