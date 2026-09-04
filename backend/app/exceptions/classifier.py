"""Exception classification service and confidence-routing engine.

Evaluates candidate exceptions through the 11-rule engine, computes financial
impact, confidence scores, and determines the routing status.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.exceptions.rules import evaluate_rules
from app.exceptions.types import ClassifiedException, ExceptionType, ResolutionStatus
from app.schemas.record import ReconciliationSummary, Record


@dataclass
class RoutingThresholds:
    """Configurable routing thresholds from ENGINE_SPEC.md."""
    auto_resolve_min_confidence: float = 0.95
    review_required_min_confidence: float = 0.80
    auto_resolvable_rules: set[int] = field(default_factory=lambda: {1, 2, 4, 7, 9})


class ExceptionClassifierService:
    """Classifies reconciliation exceptions and assigns routing tiers."""

    def __init__(self, routing_thresholds: RoutingThresholds | None = None):
        self.thresholds = routing_thresholds or RoutingThresholds()

    def route_confidence(self, rule_number: int, confidence: float, exception_type: str) -> str:
        """Route an exception to AUTO_RESOLVE / REVIEW_REQUIRED / UNRESOLVED.

        Rules from ENGINE_SPEC.md:
        - >= 95% AND a deterministic rule matched (rules 1,2,4,7,9) → AUTO_RESOLVE
        - 80-94%, or a rule matched with partial evidence → REVIEW_REQUIRED
        - < 80%, or UNKNOWN → UNRESOLVED
        Hard rule: UNKNOWN must NEVER receive AUTO_RESOLVE!
        """
        if exception_type == ExceptionType.UNKNOWN.value:
            return ResolutionStatus.UNRESOLVED.value

        if (
            rule_number in self.thresholds.auto_resolvable_rules
            and confidence >= self.thresholds.auto_resolve_min_confidence
        ):
            return ResolutionStatus.AUTO_RESOLVE.value
        elif confidence >= self.thresholds.review_required_min_confidence:
            return ResolutionStatus.REVIEW_REQUIRED.value
        else:
            return ResolutionStatus.UNRESOLVED.value

    def classify(
        self,
        record_a: Record,
        record_b: Record | None = None,
        match_level: str | None = None,
        all_sources: dict[str, list[Record]] | None = None,
        split_records: list[Record] | None = None,
        duplicate_records: list[Record] | None = None,
        exception_id: str | None = None,
    ) -> ClassifiedException:
        """Classify a single exception pair or orphan record."""
        classified = evaluate_rules(
            record_a=record_a,
            record_b=record_b,
            match_level=match_level,
            all_sources=all_sources,
            split_records=split_records,
            duplicate_records=duplicate_records,
            exception_id=exception_id,
        )

        # Enforce configurable routing thresholds
        classified.resolution_status = self.route_confidence(
            rule_number=classified.rule_number,
            confidence=classified.confidence,
            exception_type=classified.exception_type,
        )

        return classified

    def classify_all_exceptions(
        self,
        reconciliation_summary: ReconciliationSummary,
        all_sources: dict[str, list[Record]],
    ) -> list[ClassifiedException]:
        """Classify all exceptions from a reconciliation run and all 4 sources.

        Takes:
        1. Non-MATCHED results (LIKELY_MATCH, EXCEPTION, UNRESOLVED) from reconciliation
        2. Cross-source discrepancies (e.g. missing in ledger, refund gaps, fee mismatches)
        """
        classified_exceptions: list[ClassifiedException] = []
        seen_pairs: set[str] = set()
        consumed_record_ids: set[str] = set()

        # 1. Non-MATCHED results from primary reconciliation
        for result in reconciliation_summary.results:
            if result.classification != "MATCHED":
                # If this record was already consumed as part of a partial settlement group, skip
                if result.record_a.transaction_id in consumed_record_ids:
                    continue

                pair_key = f"{result.record_a.transaction_id}:{result.record_b.transaction_id if result.record_b else 'none'}"
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                exc = self.classify(
                    record_a=result.record_a,
                    record_b=result.record_b,
                    match_level=result.match_level,
                    all_sources=all_sources,
                )

                # If this is a PARTIAL_SETTLEMENT, mark all split bank parts as consumed
                if exc.exception_type == ExceptionType.PARTIAL_SETTLEMENT.value:
                    for ev in exc.evidence:
                        if ev.get("field") == "split_transaction_ids":
                            for tid in ev.get("value", []):
                                consumed_record_ids.add(tid)
                        elif ev.get("field") == "split_credits":
                            import re
                            for desc in ev.get("value", []):
                                m = re.search(r"\((bank_txn_[^\)]+)\)", str(desc))
                                if m:
                                    consumed_record_ids.add(m.group(1))

                classified_exceptions.append(exc)

        # 2. Cross-source check on MATCHED pairs for ledger or settlement discrepancies
        # (e.g., MISSING_IN_LEDGER, REFUND_MISMATCH, FEE_MISMATCH across ledger/bank)
        ledger_list = all_sources.get("ledger", [])
        ledger_by_ref = {
            r.payment_id: r for r in ledger_list if r.payment_id
        }
        ledger_by_utr = {
            r.settlement_utr: r for r in ledger_list if r.settlement_utr
        }

        for result in reconciliation_summary.results:
            if result.classification == "MATCHED" and result.record_a.source_name == "razorpay":
                ref = result.record_a.payment_id
                utr = result.record_a.settlement_utr
                ledger_rec = ledger_by_ref.get(ref) or ledger_by_utr.get(utr)

                # Check refund mismatch
                if (result.record_a.transaction_type == "refund" and not ledger_rec) or not ledger_rec:
                    exc = self.classify(
                        record_a=result.record_a,
                        record_b=result.record_b,
                        all_sources=all_sources,
                    )
                    classified_exceptions.append(exc)
                # Check fee mismatch between ledger gross and bank net
                elif result.record_b and ledger_rec:
                    if ledger_rec.amount != result.record_b.amount:
                        exc = self.classify(
                            record_a=ledger_rec,
                            record_b=result.record_b,
                            all_sources=all_sources,
                        )
                        classified_exceptions.append(exc)

        return classified_exceptions
