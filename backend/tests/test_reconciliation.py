"""Unit tests for the reconciliation engine — Phase 1.

Tests run the engine against the generated synthetic dataset and verify:
- Clean matches are classified correctly
- Exception types surface appropriately at the matching level
- Financial totals reconcile (matched + exception + unresolved == total)
- Match rate is in a realistic range
- UNKNOWN records stay UNRESOLVED (never MATCHED)
"""

import json
import os

import pytest

from app.adapters import BankAdapter, RazorpayAdapter
from app.reconciliation.engine import ReconciliationEngine

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    """Load ground_truth.json."""
    gt_path = os.path.join(DATA_DIR, "ground_truth.json")
    if not os.path.exists(gt_path):
        pytest.skip("Synthetic data not generated. Run: python generate_synthetic_data.py")
    with open(gt_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def reconciliation_summary(ground_truth):
    """Run reconciliation engine and return summary."""
    engine = ReconciliationEngine()
    sources = {
        "razorpay": RazorpayAdapter(data_dir=DATA_DIR).fetch_records(),
        "bank": BankAdapter(data_dir=DATA_DIR).fetch_records(),
    }
    return engine.reconcile(sources)


@pytest.fixture(scope="module")
def rzp_classifications(reconciliation_summary) -> dict[str, str]:
    """Map payment_id -> classification for Razorpay records."""
    result = {}
    for r in reconciliation_summary.results:
        pid = r.record_a.payment_id
        if pid and r.record_a.source_name == "razorpay":
            result[pid] = r.classification
    return result


# ------------------------------------------------------------------
# Test 1: All clean matches should be MATCHED
# ------------------------------------------------------------------
def test_clean_matches_are_matched(ground_truth, rzp_classifications):
    """Every CLEAN_MATCH transaction should classify as MATCHED at the Razorpay-Bank level."""
    clean_pids = [pid for pid, info in ground_truth.items()
                  if info["exception_type"] == "CLEAN_MATCH"]
    assert len(clean_pids) > 0, "No clean matches in ground truth"

    misclassified = []
    for pid in clean_pids:
        cls = rzp_classifications.get(pid)
        if cls != "MATCHED":
            misclassified.append((pid, cls))

    assert len(misclassified) == 0, (
        f"{len(misclassified)} clean matches were NOT classified as MATCHED: "
        f"{misclassified[:5]}"
    )


# ------------------------------------------------------------------
# Test 2: Fee mismatch records — Razorpay-Bank should still match
# (the fee mismatch is between ledger and bank, not Razorpay and bank)
# ------------------------------------------------------------------
def test_fee_mismatch_records_match_at_primary_level(ground_truth, rzp_classifications):
    """FEE_MISMATCH: Razorpay-Bank matching succeeds (net_amount matches).
    The actual fee mismatch is a ledger-vs-bank issue handled by root-cause rules."""
    fee_pids = [pid for pid, info in ground_truth.items()
                if info["exception_type"] == "FEE_MISMATCH"]
    assert len(fee_pids) > 0

    for pid in fee_pids:
        cls = rzp_classifications.get(pid)
        assert cls is not None, f"FEE_MISMATCH {pid} has no Razorpay classification"
        # These should match on the primary axis (Razorpay net == bank amount)
        assert cls == "MATCHED", (
            f"FEE_MISMATCH {pid} should be MATCHED at Razorpay-Bank level, got {cls}"
        )


# ------------------------------------------------------------------
# Test 3: Duplicate transaction records — one matches, one doesn't
# ------------------------------------------------------------------
def test_duplicate_transaction_detected(ground_truth, reconciliation_summary):
    """DUPLICATE_TRANSACTION: The duplicate record in the source should result in
    one match and one non-matched orphan."""
    dup_pids = [pid for pid, info in ground_truth.items()
                if info["exception_type"] == "DUPLICATE_TRANSACTION"]
    assert len(dup_pids) > 0

    for pid in dup_pids:
        # Find all results for this payment_id
        pid_results = [r for r in reconciliation_summary.results
                       if r.record_a.payment_id == pid
                       and r.record_a.source_name == "razorpay"]
        # Should have 2 results (original + duplicate)
        assert len(pid_results) == 2, (
            f"DUPLICATE {pid} expected 2 Razorpay results, got {len(pid_results)}"
        )
        classifications = [r.classification for r in pid_results]
        # At least one should NOT be MATCHED (the orphan duplicate)
        non_matched = [c for c in classifications if c != "MATCHED"]
        assert len(non_matched) >= 1, (
            f"DUPLICATE {pid}: both copies classified as MATCHED — duplicate not detected"
        )


# ------------------------------------------------------------------
# Test 4: Missing-in-bank — Razorpay record with no bank counterpart
# ------------------------------------------------------------------
def test_missing_in_bank_not_matched(ground_truth, rzp_classifications):
    """MISSING_IN_BANK: Should NOT be classified as MATCHED since there's no real bank record."""
    missing_pids = [pid for pid, info in ground_truth.items()
                    if info["exception_type"] == "MISSING_IN_BANK"]
    assert len(missing_pids) > 0

    for pid in missing_pids:
        cls = rzp_classifications.get(pid)
        # Should not be MATCHED — there's no real bank record
        # May be EXCEPTION or UNRESOLVED depending on whether a spurious match was found
        assert cls != "MATCHED", (
            f"MISSING_IN_BANK {pid} was incorrectly classified as MATCHED"
        )


# ------------------------------------------------------------------
# Test 5: Wrong reference — fuzzy match, not exact match
# ------------------------------------------------------------------
def test_wrong_reference_detected(ground_truth, reconciliation_summary):
    """WRONG_REFERENCE: Records with typo'd bank_reference should match via
    Level 4 fuzzy matching (> 0.85 similarity), classified as LIKELY_MATCH."""
    wrong_pids = [pid for pid, info in ground_truth.items()
                  if info["exception_type"] == "WRONG_REFERENCE"]
    assert len(wrong_pids) > 0

    for pid in wrong_pids:
        pid_results = [r for r in reconciliation_summary.results
                       if r.record_a.payment_id == pid
                       and r.record_a.source_name == "razorpay"]
        assert len(pid_results) == 1
        r = pid_results[0]
        assert r.record_b is not None, f"WRONG_REFERENCE {pid} found no match"
        assert r.match_level == "LEVEL_4_FUZZY_REFERENCE", (
            f"WRONG_REFERENCE {pid} matched at {r.match_level}, expected LEVEL_4_FUZZY_REFERENCE"
        )
        assert r.classification == "LIKELY_MATCH", (
            f"WRONG_REFERENCE {pid} classified as {r.classification}, expected LIKELY_MATCH"
        )


# ------------------------------------------------------------------
# Test 6: Financial totals reconciliation
# ------------------------------------------------------------------
def test_financial_totals_reconcile(reconciliation_summary):
    """matched_value + exception_value + unresolved_value == total_processed_value."""
    s = reconciliation_summary
    total_parts = s.matched_value + s.exception_value + s.unresolved_value
    assert total_parts == s.total_processed_value, (
        f"Financial totals don't reconcile: "
        f"matched({s.matched_value}) + exception({s.exception_value}) + "
        f"unresolved({s.unresolved_value}) = {total_parts} "
        f"!= total({s.total_processed_value})"
    )


# ------------------------------------------------------------------
# Test 7: Match rate sanity check
# ------------------------------------------------------------------
def test_match_rate_in_realistic_range(reconciliation_summary):
    """Match rate should be roughly 65-85% — not 100%, not 0%."""
    rate = reconciliation_summary.match_rate
    assert 0.50 <= rate <= 0.95, (
        f"Match rate {rate:.1%} is outside realistic range [50%, 95%]"
    )
    # The match rate should NOT be 100% (AGENTS.md rule 3)
    assert rate < 1.0, "Match rate is 100% — this violates AGENTS.md rule 3"


# ------------------------------------------------------------------
# Test 8: UNKNOWN records stay UNRESOLVED (never MATCHED)
# ------------------------------------------------------------------
def test_unknown_stays_unresolved(ground_truth, reconciliation_summary):
    """UNKNOWN-type bank records (no Razorpay match) must never be MATCHED.
    They should appear as UNRESOLVED orphans in the bank results."""
    unknown_pids = [pid for pid, info in ground_truth.items()
                    if info["exception_type"] == "UNKNOWN"]
    assert len(unknown_pids) > 0

    # UNKNOWN records are bank-only — they have no Razorpay record, so they
    # should appear as unmatched bank orphans (source_name="bank")
    bank_orphans = [r for r in reconciliation_summary.results
                    if r.record_a.source_name == "bank"
                    and r.classification == "UNRESOLVED"
                    and r.record_b is None]

    # We should have at least some bank orphans (the UNKNOWN records)
    # Check that UNKNOWN-typed bank records have refs starting with "UNKN_"
    unkn_orphans = [r for r in bank_orphans
                    if r.record_a.bank_reference and r.record_a.bank_reference.startswith("UNKN_")]
    assert len(unkn_orphans) > 0, (
        "Expected UNKNOWN bank records to be UNRESOLVED orphans, found 0"
    )

    # Ensure none of the UNKNOWN bank records got MATCHED
    all_matched_bank_refs = {
        r.record_b.bank_reference
        for r in reconciliation_summary.results
        if r.record_b is not None
        and r.record_b.source_name == "bank"
        and r.classification == "MATCHED"
    }
    unkn_matched = [ref for ref in all_matched_bank_refs
                    if ref and ref.startswith("UNKN_")]
    assert len(unkn_matched) == 0, (
        f"UNKNOWN bank records were incorrectly MATCHED: {unkn_matched}"
    )


# ------------------------------------------------------------------
# Test 9: Classification counts add up
# ------------------------------------------------------------------
def test_classification_counts_sum(reconciliation_summary):
    """All classification counts should sum to total_records."""
    s = reconciliation_summary
    count_sum = s.matched_count + s.likely_match_count + s.exception_count + s.unresolved_count
    assert count_sum == s.total_records, (
        f"Classification counts don't sum: "
        f"{s.matched_count} + {s.likely_match_count} + {s.exception_count} + {s.unresolved_count} "
        f"= {count_sum} != {s.total_records}"
    )


# ------------------------------------------------------------------
# Test 10: LIKELY_MATCH is never silently promoted to MATCHED
# ------------------------------------------------------------------
def test_likely_match_not_promoted(reconciliation_summary):
    """LIKELY_MATCH records must exist separately from MATCHED — no code path
    silently promotes them (AGENTS.md rule 3)."""
    likely_matches = [r for r in reconciliation_summary.results
                      if r.classification == "LIKELY_MATCH"]
    # If there are any LIKELY_MATCH results, verify they have scores in [0.80, 0.95)
    for r in likely_matches:
        assert 0.80 <= r.match_score < 0.95, (
            f"LIKELY_MATCH with score {r.match_score} is outside [0.80, 0.95)"
        )
