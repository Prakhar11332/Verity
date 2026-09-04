"""Matching score computation functions for the reconciliation engine.

Each function computes one signal in the composite score from ENGINE_SPEC.md.
All math is deterministic Python — no LLM calls.
"""

from __future__ import annotations

import difflib

from app.reconciliation.config import ReconciliationConfig, default_config
from app.schemas.record import Record


def compute_reference_similarity(a: Record, b: Record) -> float:
    """Compute reference match score between two records.

    Returns 1.0 for exact match on payment_id, settlement_utr, or bank_reference.
    For non-exact matches, returns fuzzy similarity ratio using SequenceMatcher.
    Returns 0.0 if no reference fields are present.
    """
    # Exact match on any reference field
    pairs = [
        (a.payment_id, b.payment_id),
        (a.settlement_utr, b.settlement_utr),
        (a.bank_reference, b.bank_reference),
        (a.settlement_utr, b.bank_reference),
        (a.bank_reference, b.settlement_utr),
        (a.payment_id, b.bank_reference),
        (a.bank_reference, b.payment_id),
    ]
    for va, vb in pairs:
        if va and vb and va == vb:
            return 1.0

    # Fuzzy match: compare the best available reference strings
    ref_a = _best_reference(a)
    ref_b = _best_reference(b)
    if ref_a and ref_b:
        ratio = difflib.SequenceMatcher(None, ref_a, ref_b).ratio()
        # Noise floor: random 12-15 char alphanumeric strings share 3-5 chars by pure chance (ratio 0.20-0.35).
        # Ratios below 0.60 represent zero semantic similarity and must not contribute match points.
        return ratio if ratio >= 0.60 else 0.0

    return 0.0


def _best_reference(r: Record) -> str | None:
    """Pick the most specific reference string from a record."""
    return r.settlement_utr or r.bank_reference or r.payment_id


def has_exact_id_match(a: Record, b: Record) -> bool:
    """Level 1: Check if any ID field matches exactly across two records."""
    pairs = [
        (a.payment_id, b.payment_id),
        (a.settlement_utr, b.settlement_utr),
        (a.bank_reference, b.bank_reference),
        (a.settlement_utr, b.bank_reference),
        (a.bank_reference, b.settlement_utr),
    ]
    return any(va and vb and va == vb for va, vb in pairs)


def _best_amount_diff(a: Record, b: Record) -> float:
    """Find the smallest absolute difference across amount permutations.

    Cross-source comparison needs to handle Razorpay (gross in amount, net in
    net_amount) vs Bank (net in amount). We check:
      - amount vs amount
      - net_amount vs amount (a's net vs b's amount)
      - amount vs net_amount (a's amount vs b's net)
      - net_amount vs net_amount
    and return the smallest difference found.
    """
    candidates: list[float] = []
    pairs = [
        (a.amount, b.amount),
        (a.net_amount, b.amount),
        (a.amount, b.net_amount),
        (a.net_amount, b.net_amount),
    ]
    for va, vb in pairs:
        if va is not None and vb is not None:
            candidates.append(abs(float(va) - float(vb)))
    return min(candidates) if candidates else float("inf")


def _best_max_amount(a: Record, b: Record) -> float:
    """Return max of the amounts being compared for normalization."""
    amounts = [
        v for v in [a.amount, a.net_amount, b.amount, b.net_amount]
        if v is not None
    ]
    return max(abs(float(v)) for v in amounts) if amounts else 0.0


def compute_amount_match(a: Record, b: Record) -> float:
    """Compute amount match score.

    1.0 if best amount comparison is exactly equal.
    Decays with |difference| / max(amounts).
    Considers net_amount vs amount cross-matching for Razorpay-Bank pairs.
    """
    diff = _best_amount_diff(a, b)
    if diff == float("inf"):
        return 0.0
    if diff == 0.0:
        return 1.0
    max_amt = _best_max_amount(a, b)
    if max_amt == 0:
        return 0.0
    return max(0.0, 1.0 - diff / max_amt)


def amounts_match_exactly(a: Record, b: Record) -> bool:
    """Check if any amount permutation matches exactly."""
    return _best_amount_diff(a, b) == 0.0


def amounts_within_tolerance(a: Record, b: Record, tolerance: float = 1.0) -> bool:
    """Check if best amount comparison is within tolerance (default ₹1)."""
    return _best_amount_diff(a, b) <= tolerance


def _best_date_diff_days(a: Record, b: Record) -> int:
    """Find the smallest date difference across all date field permutations.

    Cross-source comparison: Razorpay stores transaction_date, bank may store
    the settlement_date as its transaction_date. Check all permutations to
    find the closest date pair.
    """
    min_diff = None
    date_pairs = [
        (a.transaction_date, b.transaction_date),
        (a.transaction_date, b.settlement_date),
        (a.settlement_date, b.transaction_date),
        (a.settlement_date, b.settlement_date),
    ]
    for da, db in date_pairs:
        if da is not None and db is not None:
            diff = abs((da - db).days)
            if min_diff is None or diff < min_diff:
                min_diff = diff
    return min_diff if min_diff is not None else 999


def compute_date_proximity(a: Record, b: Record, window_days: int = 7) -> float:
    """Compute date proximity score.

    1.0 if same day, decays linearly to 0.0 at window edge.
    Checks all date field permutations to find the closest pair.
    """
    diff_days = _best_date_diff_days(a, b)
    if diff_days >= window_days:
        return 0.0
    return 1.0 - (diff_days / window_days)


def dates_within_window(a: Record, b: Record, window_days: int = 3) -> bool:
    """Check if the closest date pair is within a given day window."""
    return _best_date_diff_days(a, b) <= window_days


def compute_transaction_type_match(a: Record, b: Record) -> float:
    """1.0 if transaction types are equal, 0.0 otherwise."""
    if a.transaction_type and b.transaction_type:
        return 1.0 if a.transaction_type == b.transaction_type else 0.0
    return 0.0


def compute_merchant_match(a: Record, b: Record) -> float:
    """1.0 if merchant IDs are equal, 0.0 otherwise."""
    if a.merchant_id and b.merchant_id:
        return 1.0 if a.merchant_id == b.merchant_id else 0.0
    return 0.0


def compute_description_similarity(a: Record, b: Record) -> float:
    """Compute description similarity via token overlap.

    Returns the Jaccard similarity of word tokens.
    """
    if not a.description or not b.description:
        return 0.0
    tokens_a = set(a.description.lower().split())
    tokens_b = set(b.description.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def compute_composite_score(
    a: Record,
    b: Record,
    config: ReconciliationConfig = default_config,
) -> tuple[float, dict[str, float]]:
    """Compute the Level 5 composite score per ENGINE_SPEC.md formula.

    Returns (total_score, component_scores_dict).
    """
    w = config.weights
    window = config.date_windows.wide_date

    ref = compute_reference_similarity(a, b)
    amt = compute_amount_match(a, b)
    dt = compute_date_proximity(a, b, window_days=window)
    txn_type = compute_transaction_type_match(a, b)
    merch = compute_merchant_match(a, b)
    desc = compute_description_similarity(a, b)

    score = (
        w.reference_match * ref
        + w.amount_match * amt
        + w.date_proximity * dt
        + w.transaction_type_match * txn_type
        + w.merchant_match * merch
        + w.description_similarity * desc
    )

    components = {
        "reference_match": ref,
        "amount_match": amt,
        "date_proximity": dt,
        "transaction_type_match": txn_type,
        "merchant_match": merch,
        "description_similarity": desc,
    }

    return score, components


def classify_score(score: float, config: ReconciliationConfig = default_config) -> str:
    """Classify a match score into MATCHED / LIKELY_MATCH / EXCEPTION / UNRESOLVED."""
    t = config.thresholds
    if score >= t.matched:
        return "MATCHED"
    elif score >= t.likely_match:
        return "LIKELY_MATCH"
    elif score >= t.exception:
        return "EXCEPTION"
    else:
        return "UNRESOLVED"
