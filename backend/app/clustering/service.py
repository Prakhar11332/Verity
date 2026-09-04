"""Exception clustering and investigation priority scoring service per ENGINE_SPEC.md."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal

from app.clustering.types import ExceptionCluster, PriorityWeights
from app.exceptions.types import ClassifiedException
from app.models.exception import ExceptionModel


def _slugify(text: str) -> str:
    """Create a URL-safe lowercase cluster ID."""
    clean = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)


class ClusterService:
    """Groups exceptions by (exception_type, root_cause) signature and computes priority scores."""

    def __init__(self, weights: PriorityWeights | None = None):
        self.weights = weights or PriorityWeights()

    def build_clusters(
        self,
        exceptions: list[ClassifiedException | ExceptionModel],
    ) -> list[ExceptionCluster]:
        """Group exceptions by (exception_type, root_cause) signature and rank by priority score."""
        if not exceptions:
            return []

        total_exceptions_count = len(exceptions)

        # 1. Group by (exception_type, root_cause)
        grouped: dict[tuple[str, str], list[ClassifiedException | ExceptionModel]] = defaultdict(list)
        for exc in exceptions:
            sig = (exc.exception_type, exc.root_cause or "unexplained")
            grouped[sig].append(exc)

        raw_clusters: list[ExceptionCluster] = []

        # 2. Compute aggregate metrics per cluster
        for (exc_type, _root_cause_str), exc_list in grouped.items():
            record_count = len(exc_list)
            total_impact = sum(
                (Decimal(str(e.financial_impact or 0)) for e in exc_list),
                Decimal("0.00"),
            )
            avg_conf = sum(float(e.confidence or 0.0) for e in exc_list) / record_count
            pct = round((record_count / total_exceptions_count) * 100.0, 2)

            # Majority recommended_action
            actions = [e.recommended_action for e in exc_list if e.recommended_action]
            majority_action = Counter(actions).most_common(1)[0][0] if actions else "Manual investigation required"

            # Actual root_cause (None if UNKNOWN)
            actual_root_cause = exc_list[0].root_cause

            cluster_id = f"cl_{_slugify(exc_type)}"
            if actual_root_cause:
                cluster_id += f"_{_slugify(actual_root_cause)[:20]}"

            raw_clusters.append(
                ExceptionCluster(
                    cluster_id=cluster_id,
                    exception_type=exc_type,
                    root_cause=actual_root_cause,
                    record_count=record_count,
                    total_financial_impact=total_impact,
                    pct_of_all_exceptions=pct,
                    avg_confidence=round(avg_conf, 4),
                    recommended_action=majority_action,
                    exception_ids=[e.id for e in exc_list],
                    priority_score=0.0,
                )
            )

        # 3. Compute investigation priority score
        # priority_score = w1*impact_norm + w2*(1-confidence) + w3*count_norm + w4*age_norm
        max_impact = max((c.total_financial_impact for c in raw_clusters), default=Decimal("0.00"))
        max_count = max((c.record_count for c in raw_clusters), default=1)

        w = self.weights

        for cluster in raw_clusters:
            impact_norm = float(cluster.total_financial_impact / max_impact) if max_impact > 0 else 0.0
            confidence_component = max(0.0, 1.0 - cluster.avg_confidence)
            count_norm = cluster.record_count / max_count if max_count > 0 else 0.0
            age_norm = 0.0  # Normalized age (batch runs within same window)

            score = (
                w.w_impact * impact_norm
                + w.w_confidence * confidence_component
                + w.w_count * count_norm
                + w.w_age * age_norm
            )
            cluster.priority_score = round(score, 4)

        # 4. Sort descending by priority_score
        raw_clusters.sort(key=lambda c: (c.priority_score, c.total_financial_impact), reverse=True)
        return raw_clusters
