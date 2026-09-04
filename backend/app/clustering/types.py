from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PriorityWeights:
    """Configurable weights for investigation priority scoring per ENGINE_SPEC.md.

    priority_score = w1*impact_norm + w2*(1-confidence) + w3*count_norm + w4*age_norm
    """
    w_impact: float = 0.40
    w_confidence: float = 0.30
    w_count: float = 0.20
    w_age: float = 0.10


@dataclass
class ExceptionCluster:
    """Grouped exception cluster by (exception_type, root_cause) signature."""
    cluster_id: str
    exception_type: str
    root_cause: str | None
    record_count: int
    total_financial_impact: Decimal
    pct_of_all_exceptions: float
    avg_confidence: float
    recommended_action: str
    exception_ids: list[str]
    priority_score: float = 0.0
