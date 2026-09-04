"""ReconciliationEngine — 5-level matching pipeline per ENGINE_SPEC.md.

Run in order, stop at first confident match per record.
All math is deterministic Python — no LLM calls.
"""

from __future__ import annotations

from decimal import Decimal

from app.reconciliation.config import ReconciliationConfig, default_config
from app.reconciliation.matcher import (
    _best_date_diff_days,
    amounts_match_exactly,
    amounts_within_tolerance,
    classify_score,
    compute_amount_match,
    compute_composite_score,
    compute_reference_similarity,
    dates_within_window,
    has_exact_id_match,
)
from app.schemas.record import (
    MatchLevel,
    MatchStatus,
    ReconciliationResult,
    ReconciliationSummary,
    Record,
)


class ReconciliationEngine:
    """Deterministic multi-level reconciliation engine.

    Primary axis: Razorpay records vs Bank records (did money move?).
    Each record is consumed by the first level that matches it.
    LIKELY_MATCH is never silently promoted to MATCHED.
    """

    def __init__(self, config: ReconciliationConfig | None = None):
        self.config = config or default_config

    def reconcile(self, sources: dict[str, list[Record]]) -> ReconciliationSummary:
        """Run the full 5-level pipeline and return aggregated results.

        Args:
            sources: dict mapping source_name → list of Records.
                     Expected keys: "razorpay", "bank", (optionally "ledger", "settlement")
        """
        razorpay = list(sources.get("razorpay", []))
        bank = list(sources.get("bank", []))

        # Track which records have been consumed (matched)
        matched_rzp: set[str] = set()      # transaction_id
        matched_bank: set[str] = set()     # transaction_id
        results: list[ReconciliationResult] = []

        # ===== Level 1: Exact ID match =====
        self._level_1_exact_id(razorpay, bank, matched_rzp, matched_bank, results)

        # ===== Level 2: Exact amount + date within 3 days =====
        self._level_2_exact_amount_date(razorpay, bank, matched_rzp, matched_bank, results)

        # ===== Level 3: Amount within ₹1 + same type + date within 7 days =====
        self._level_3_tolerant_amount(razorpay, bank, matched_rzp, matched_bank, results)

        # ===== Level 4: Fuzzy reference match (similarity > 0.85) =====
        self._level_4_fuzzy_reference(razorpay, bank, matched_rzp, matched_bank, results)

        # ===== Level 5: Composite score for remaining pairs =====
        self._level_5_composite(razorpay, bank, matched_rzp, matched_bank, results)

        # ===== Orphans: unmatched records =====
        self._collect_orphans(razorpay, bank, matched_rzp, matched_bank, results)

        return self._build_summary(results)

    # ------------------------------------------------------------------
    # Level 1: Exact ID match
    # ------------------------------------------------------------------
    def _level_1_exact_id(
        self,
        razorpay: list[Record],
        bank: list[Record],
        matched_rzp: set[str],
        matched_bank: set[str],
        results: list[ReconciliationResult],
    ) -> None:
        for rzp in razorpay:
            if rzp.transaction_id in matched_rzp:
                continue

            # Find all candidate bank records matching by exact ID
            candidates = [
                b for b in bank
                if b.transaction_id not in matched_bank and has_exact_id_match(rzp, b)
            ]
            if not candidates:
                continue

            # Check 1-to-many partial settlement: multiple bank records summing to parent
            if len(candidates) > 1:
                cand_sum = sum(b.amount for b in candidates)
                target_amt = rzp.net_amount if rzp.net_amount is not None else rzp.amount
                if target_amt is not None and abs(cand_sum - target_amt) <= Decimal("1.00"):
                    # Consume ALL candidates into the single partial settlement group
                    score, components = compute_composite_score(rzp, candidates[0], self.config)
                    classification = MatchStatus.LIKELY_MATCH.value
                    components["partial_settlement"] = 1.0
                    components["split_ids"] = [b.transaction_id for b in candidates]
                    results.append(ReconciliationResult(
                        record_a=rzp,
                        record_b=candidates[0],
                        match_score=score,
                        match_level=MatchLevel.LEVEL_1_EXACT_ID.value,
                        classification=classification,
                        score_components=components,
                    ))
                    matched_rzp.add(rzp.transaction_id)
                    for b in candidates:
                        matched_bank.add(b.transaction_id)
                    continue

            # Standard 1-to-1 exact ID match
            bnk = candidates[0]
            score, components = compute_composite_score(rzp, bnk, self.config)
            classification = classify_score(score, self.config)
            results.append(ReconciliationResult(
                record_a=rzp,
                record_b=bnk,
                match_score=score,
                match_level=MatchLevel.LEVEL_1_EXACT_ID.value,
                classification=classification,
                score_components=components,
            ))
            matched_rzp.add(rzp.transaction_id)
            matched_bank.add(bnk.transaction_id)

    # ------------------------------------------------------------------
    # Level 2: Exact amount + date within narrow window
    # ------------------------------------------------------------------
    def _level_2_exact_amount_date(
        self,
        razorpay: list[Record],
        bank: list[Record],
        matched_rzp: set[str],
        matched_bank: set[str],
        results: list[ReconciliationResult],
    ) -> None:
        window = self.config.date_windows.exact_date
        for rzp in razorpay:
            if rzp.transaction_id in matched_rzp:
                continue
            best_match: tuple[Record, float, dict] | None = None
            best_score = -1.0
            for bnk in bank:
                if bnk.transaction_id in matched_bank:
                    continue
                # If records have fuzzy reference similarity >= min_similarity, defer to Level 4
                if compute_reference_similarity(rzp, bnk) >= self.config.fuzzy_match.min_similarity:
                    continue
                if amounts_match_exactly(rzp, bnk) and dates_within_window(rzp, bnk, window):
                    score, components = compute_composite_score(rzp, bnk, self.config)
                    if score > best_score:
                        best_score = score
                        best_match = (bnk, score, components)
            if best_match:
                bnk, score, components = best_match
                classification = classify_score(score, self.config)
                results.append(ReconciliationResult(
                    record_a=rzp,
                    record_b=bnk,
                    match_score=score,
                    match_level=MatchLevel.LEVEL_2_EXACT_AMOUNT_DATE.value,
                    classification=classification,
                    score_components=components,
                ))
                matched_rzp.add(rzp.transaction_id)
                matched_bank.add(bnk.transaction_id)

    # ------------------------------------------------------------------
    # Level 3: Amount within tolerance + same type + wider date window
    # ------------------------------------------------------------------
    def _level_3_tolerant_amount(
        self,
        razorpay: list[Record],
        bank: list[Record],
        matched_rzp: set[str],
        matched_bank: set[str],
        results: list[ReconciliationResult],
    ) -> None:
        tolerance = self.config.amount_tolerance.small
        window = self.config.date_windows.wide_date
        for rzp in razorpay:
            if rzp.transaction_id in matched_rzp:
                continue
            best_match: tuple[Record, float, dict] | None = None
            best_score = -1.0
            for bnk in bank:
                if bnk.transaction_id in matched_bank:
                    continue
                # If records have fuzzy reference similarity >= min_similarity, defer to Level 4
                if compute_reference_similarity(rzp, bnk) >= self.config.fuzzy_match.min_similarity:
                    continue
                if (
                    amounts_within_tolerance(rzp, bnk, tolerance)
                    and rzp.transaction_type == bnk.transaction_type
                    and dates_within_window(rzp, bnk, window)
                ):
                    score, components = compute_composite_score(rzp, bnk, self.config)
                    if score > best_score:
                        best_score = score
                        best_match = (bnk, score, components)
            if best_match:
                bnk, score, components = best_match
                classification = classify_score(score, self.config)
                results.append(ReconciliationResult(
                    record_a=rzp,
                    record_b=bnk,
                    match_score=score,
                    match_level=MatchLevel.LEVEL_3_TOLERANT_AMOUNT.value,
                    classification=classification,
                    score_components=components,
                ))
                matched_rzp.add(rzp.transaction_id)
                matched_bank.add(bnk.transaction_id)

    # ------------------------------------------------------------------
    # Level 4: Fuzzy reference match (SequenceMatcher > 0.85)
    # ------------------------------------------------------------------
    def _level_4_fuzzy_reference(
        self,
        razorpay: list[Record],
        bank: list[Record],
        matched_rzp: set[str],
        matched_bank: set[str],
        results: list[ReconciliationResult],
    ) -> None:
        min_sim = self.config.fuzzy_match.min_similarity
        for rzp in razorpay:
            if rzp.transaction_id in matched_rzp:
                continue
            best_match: tuple[Record, float, dict, float] | None = None
            best_sim = -1.0
            for bnk in bank:
                if bnk.transaction_id in matched_bank:
                    continue
                sim = compute_reference_similarity(rzp, bnk)
                # Must be above threshold but NOT exact (exact was caught in L1)
                if sim >= min_sim and sim < 1.0:
                    score, components = compute_composite_score(rzp, bnk, self.config)
                    if sim > best_sim:
                        best_sim = sim
                        best_match = (bnk, score, components, sim)
            if best_match:
                bnk, score, components, sim = best_match
                classification = classify_score(score, self.config)
                results.append(ReconciliationResult(
                    record_a=rzp,
                    record_b=bnk,
                    match_score=score,
                    match_level=MatchLevel.LEVEL_4_FUZZY_REFERENCE.value,
                    classification=classification,
                    score_components=components,
                ))
                matched_rzp.add(rzp.transaction_id)
                matched_bank.add(bnk.transaction_id)

    # ------------------------------------------------------------------
    # Level 5: Composite score for any remaining candidate pairs
    # ------------------------------------------------------------------
    def _level_5_composite(
        self,
        razorpay: list[Record],
        bank: list[Record],
        matched_rzp: set[str],
        matched_bank: set[str],
        results: list[ReconciliationResult],
    ) -> None:
        threshold = self.config.thresholds.exception  # minimum score to be a candidate
        for rzp in razorpay:
            if rzp.transaction_id in matched_rzp:
                continue
            best_match: tuple[Record, float, dict] | None = None
            best_score = -1.0
            for bnk in bank:
                if bnk.transaction_id in matched_bank:
                    continue

                # Pre-filter 1: Bounded date window (<= 14 days)
                # Wildly separated dates are never candidate matches
                if _best_date_diff_days(rzp, bnk) > 14:
                    continue

                # Pre-filter 2: Financial anchor requirement
                # A candidate pair cannot be matched purely on non-discriminating metadata
                # (transaction_type + merchant_id). If reference similarity is 0.0,
                # amount must match closely (amount_match >= 0.95).
                ref_sim = compute_reference_similarity(rzp, bnk)
                amt_match = compute_amount_match(rzp, bnk)
                if ref_sim == 0.0 and amt_match < 0.95:
                    continue

                score, components = compute_composite_score(rzp, bnk, self.config)
                if score >= threshold and score > best_score:
                    best_score = score
                    best_match = (bnk, score, components)
            if best_match:
                bnk, score, components = best_match
                classification = classify_score(score, self.config)
                results.append(ReconciliationResult(
                    record_a=rzp,
                    record_b=bnk,
                    match_score=score,
                    match_level=MatchLevel.LEVEL_5_COMPOSITE.value,
                    classification=classification,
                    score_components=components,
                ))
                matched_rzp.add(rzp.transaction_id)
                matched_bank.add(bnk.transaction_id)

    # ------------------------------------------------------------------
    # Orphans — records that matched nothing
    # ------------------------------------------------------------------
    def _collect_orphans(
        self,
        razorpay: list[Record],
        bank: list[Record],
        matched_rzp: set[str],
        matched_bank: set[str],
        results: list[ReconciliationResult],
    ) -> None:
        # Unmatched Razorpay records
        for rzp in razorpay:
            if rzp.transaction_id not in matched_rzp:
                results.append(ReconciliationResult(
                    record_a=rzp,
                    record_b=None,
                    match_score=0.0,
                    match_level=MatchLevel.NONE.value,
                    classification=MatchStatus.UNRESOLVED.value,
                ))

        # Unmatched Bank records
        for bnk in bank:
            if bnk.transaction_id not in matched_bank:
                results.append(ReconciliationResult(
                    record_a=bnk,
                    record_b=None,
                    match_score=0.0,
                    match_level=MatchLevel.NONE.value,
                    classification=MatchStatus.UNRESOLVED.value,
                ))

    # ------------------------------------------------------------------
    # Summary aggregation
    # ------------------------------------------------------------------
    def _build_summary(self, results: list[ReconciliationResult]) -> ReconciliationSummary:
        """Aggregate results into a ReconciliationSummary."""
        summary = ReconciliationSummary(results=results)

        # Count unique primary records (record_a) for totals
        seen_primary: set[str] = set()
        for r in results:
            tid = r.record_a.transaction_id
            if tid in seen_primary:
                continue
            seen_primary.add(tid)
            summary.total_records += 1
            amount = r.record_a.amount or Decimal(0)
            summary.total_processed_value += amount

            if r.classification == MatchStatus.MATCHED.value:
                summary.matched_count += 1
                summary.matched_value += amount
            elif r.classification == MatchStatus.LIKELY_MATCH.value:
                summary.likely_match_count += 1
                summary.exception_value += amount
            elif r.classification == MatchStatus.EXCEPTION.value:
                summary.exception_count += 1
                summary.exception_value += amount
            elif r.classification == MatchStatus.UNRESOLVED.value:
                summary.unresolved_count += 1
                summary.unresolved_value += amount

        if summary.total_records > 0:
            summary.match_rate = summary.matched_count / summary.total_records

        return summary
