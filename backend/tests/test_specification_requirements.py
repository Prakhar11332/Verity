"""Automated tests explicitly validating the core specification requirements:
1. Exact matching (Level 1/2/3)
2. Fuzzy matching (Level 4, similarity >= 0.85)
3. Amount mismatch (Rule 3)
4. Fee mismatch (Rule 2)
5. Duplicate detection (Rule 1)
6. Missing transaction both directions (Rule 4: missing in bank; Rule 5: missing in Razorpay)
7. Timing mismatch (Rule 7)
8. Refund mismatch (Rule 8)
9. Partial settlement (Rule 9)
10. Unresolved / UNKNOWN (Rule 11)
11. Financial totals reconciliation (matched_value + exception_value == total_processed_value)
"""

import json
import os
from datetime import date
from decimal import Decimal

import pytest

from app.adapters import BankAdapter, LedgerAdapter, RazorpayAdapter, SettlementAdapter
from app.exceptions.classifier import ExceptionClassifierService
from app.exceptions.types import ExceptionType, ResolutionStatus
from app.reconciliation.engine import ReconciliationEngine
from app.schemas.record import Record

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@pytest.fixture(scope="module")
def dataset():
    """Load all 4 source records and ground truth."""
    gt_path = os.path.join(DATA_DIR, "ground_truth.json")
    if not os.path.exists(gt_path):
        pytest.skip("Synthetic data not generated. Run generate_synthetic_data.py first.")

    with open(gt_path) as f:
        ground_truth = json.load(f)

    sources = {
        "razorpay": RazorpayAdapter(data_dir=DATA_DIR).fetch_records(),
        "bank": BankAdapter(data_dir=DATA_DIR).fetch_records(),
        "ledger": LedgerAdapter(data_dir=DATA_DIR).fetch_records(),
        "settlement": SettlementAdapter(data_dir=DATA_DIR).fetch_records(),
    }
    return ground_truth, sources


@pytest.fixture(scope="module")
def reconciliation_engine():
    return ReconciliationEngine()


@pytest.fixture(scope="module")
def exception_classifier():
    return ExceptionClassifierService()


@pytest.fixture(scope="module")
def reconciliation_summary(reconciliation_engine, dataset):
    _, sources = dataset
    return reconciliation_engine.reconcile(sources)


# -----------------------------------------------------------------------------
# 1. Exact Matching
# -----------------------------------------------------------------------------
def test_exact_matching(reconciliation_summary, dataset):
    """Verify clean 1:1 transactions match on exact reference and amount with score 1.0."""
    ground_truth, _ = dataset
    clean_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "CLEAN_MATCH"
    ]
    assert len(clean_pids) > 0

    results_by_pid = {
        r.record_a.payment_id: r
        for r in reconciliation_summary.results
        if r.record_a.payment_id
    }

    for pid in clean_pids:
        r = results_by_pid.get(pid)
        assert r is not None, f"Clean match transaction {pid} missing from results"
        assert r.classification == "MATCHED", f"Transaction {pid} expected MATCHED, got {r.classification}"
        assert r.match_score >= 0.95, f"Transaction {pid} expected high confidence score, got {r.match_score}"
        assert r.record_b is not None, f"Clean match transaction {pid} has no matched record_b"


# -----------------------------------------------------------------------------
# 2. Fuzzy Matching
# -----------------------------------------------------------------------------
def test_fuzzy_matching(reconciliation_summary, dataset):
    """Verify records with reference typos/transcriptions match via Level 4 fuzzy similarity."""
    ground_truth, _ = dataset
    wrong_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "WRONG_REFERENCE"
    ]
    assert len(wrong_pids) > 0

    results_by_pid = {
        r.record_a.payment_id: r
        for r in reconciliation_summary.results
        if r.record_a.payment_id
    }

    for pid in wrong_pids:
        r = results_by_pid.get(pid)
        assert r is not None, f"Fuzzy candidate {pid} missing from results"
        assert r.match_level == "LEVEL_4_FUZZY_REFERENCE", f"{pid} expected LEVEL_4_FUZZY_REFERENCE, got {r.match_level}"
        assert r.classification == "LIKELY_MATCH", f"{pid} expected LIKELY_MATCH, got {r.classification}"
        assert 0.80 <= r.match_score < 0.95, f"{pid} fuzzy score {r.match_score} outside [0.80, 0.95)"


# -----------------------------------------------------------------------------
# 3. Amount Mismatch
# -----------------------------------------------------------------------------
def test_amount_mismatch(exception_classifier):
    """Verify amount mismatch where reference matches but difference cannot be explained by fees."""
    rec_a = Record(
        transaction_id="rzp_amt_001",
        source_name="razorpay",
        amount=Decimal("10000.00"),
        net_amount=Decimal("10000.00"),
        fee=Decimal("0.00"),
        tax=Decimal("0.00"),
        payment_id="pay_amt_mismatch_001",
        transaction_date=date(2026, 3, 1),
        transaction_type="payment",
        status="captured",
        description="Razorpay transaction for amount mismatch test",
        merchant_id="MERCH_TEST",
    )
    rec_b = Record(
        transaction_id="bank_amt_001",
        source_name="bank",
        amount=Decimal("9450.00"),  # ₹550 difference, unexplained
        payment_id="pay_amt_mismatch_001",
        bank_reference="pay_amt_mismatch_001",
        transaction_date=date(2026, 3, 1),
        transaction_type="credit",
        status="success",
        description="Bank credit for amount mismatch test",
        merchant_id="MERCH_TEST",
    )

    exc = exception_classifier.classify(record_a=rec_a, record_b=rec_b)
    assert exc.exception_type == ExceptionType.AMOUNT_MISMATCH.value
    assert exc.root_cause == "Unexplained amount difference"
    assert exc.financial_impact == Decimal("550.00")
    assert exc.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
    assert 0.80 <= exc.confidence < 0.95


# -----------------------------------------------------------------------------
# 4. Fee Mismatch
# -----------------------------------------------------------------------------
def test_fee_mismatch(dataset, exception_classifier):
    """Verify fee mismatch where gross ledger matches net bank plus fee & tax."""
    ground_truth, sources = dataset
    fee_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "FEE_MISMATCH"
    ]
    assert len(fee_pids) > 0

    target_pid = fee_pids[0]
    bank_rec = next(b for b in sources["bank"] if b.payment_id == target_pid)
    ledger_rec = next(rec for rec in sources["ledger"] if rec.payment_id == target_pid)

    exc = exception_classifier.classify(
        record_a=ledger_rec,
        record_b=bank_rec,
        all_sources=sources,
    )
    assert exc.exception_type == ExceptionType.FEE_MISMATCH.value
    assert exc.root_cause == "Settlement fee/tax deducted from gross amount"
    assert exc.resolution_status == ResolutionStatus.AUTO_RESOLVE.value
    assert exc.confidence >= 0.95
    assert exc.financial_impact > Decimal("0.00")


# -----------------------------------------------------------------------------
# 5. Duplicate Detection
# -----------------------------------------------------------------------------
def test_duplicate_detection(dataset, reconciliation_summary, exception_classifier):
    """Verify duplicate transactions are detected both in matching and exception engine."""
    ground_truth, sources = dataset
    dup_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "DUPLICATE_TRANSACTION"
    ]
    assert len(dup_pids) > 0

    target_pid = dup_pids[0]
    matching_results = [
        r for r in reconciliation_summary.results
        if r.record_a.payment_id == target_pid
    ]
    assert len(matching_results) == 2, f"Expected 2 results for duplicate {target_pid}"

    # Exception classification check
    dups = [r for r in sources["razorpay"] if r.payment_id == target_pid]
    exc = exception_classifier.classify(
        record_a=dups[0],
        duplicate_records=dups,
        all_sources=sources,
    )
    assert exc.exception_type == ExceptionType.DUPLICATE_TRANSACTION.value
    assert exc.root_cause == "Duplicate transaction"
    assert exc.resolution_status == ResolutionStatus.AUTO_RESOLVE.value
    assert exc.confidence >= 0.95


# -----------------------------------------------------------------------------
# 6. Missing Transaction (Both Directions)
# -----------------------------------------------------------------------------
def test_missing_transaction_direction_razorpay_missing_in_bank(dataset, exception_classifier):
    """Direction 1: Exists in Razorpay, no bank credit found within settlement window."""
    ground_truth, sources = dataset
    missing_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "MISSING_IN_BANK"
    ]
    assert len(missing_pids) > 0

    target_pid = missing_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)

    exc = exception_classifier.classify(
        record_a=rzp_rec,
        record_b=None,
        all_sources=sources,
    )
    assert exc.exception_type == ExceptionType.MISSING_IN_BANK.value
    assert exc.root_cause == "Pending or missing settlement"
    assert exc.financial_impact == rzp_rec.amount


def test_missing_transaction_direction_bank_missing_in_razorpay(exception_classifier):
    """Direction 2: Direct bank credit exists with reference, but no matching Razorpay gateway record."""
    bank_rec = Record(
        transaction_id="bank_direct_dep_100",
        source_name="bank",
        amount=Decimal("4500.00"),
        transaction_date="2026-03-01",
        transaction_type="credit",
        status="success",
        bank_reference="DIRECT_NEFT_987654",
        description="Direct NEFT credit from customer",
        merchant_id="MERCH_TEST",
    )

    empty_sources = {"razorpay": [], "bank": [bank_rec], "ledger": [], "settlement": []}

    exc = exception_classifier.classify(
        record_a=bank_rec,
        record_b=None,
        all_sources=empty_sources,
    )
    assert exc.exception_type == ExceptionType.MISSING_IN_RAZORPAY.value
    assert exc.root_cause == "Unidentified bank transaction"
    assert exc.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
    assert exc.financial_impact == Decimal("4500.00")


# -----------------------------------------------------------------------------
# 7. Timing Mismatch
# -----------------------------------------------------------------------------
def test_timing_mismatch(dataset, exception_classifier):
    """Verify settlement timing difference across window/midnight."""
    ground_truth, sources = dataset
    timing_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "SETTLEMENT_TIMING"
    ]
    assert len(timing_pids) > 0

    target_pid = timing_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    bank_rec = next(b for b in sources["bank"] if b.payment_id == target_pid)

    exc = exception_classifier.classify(
        record_a=rzp_rec,
        record_b=bank_rec,
        all_sources=sources,
    )
    assert exc.exception_type == ExceptionType.SETTLEMENT_TIMING.value
    assert exc.root_cause == "Settlement timing difference"
    assert exc.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
    assert 0.80 <= exc.confidence < 0.95
    assert exc.financial_impact == Decimal("0.00")  # No capital loss


# -----------------------------------------------------------------------------
# 8. Refund Mismatch
# -----------------------------------------------------------------------------
def test_refund_mismatch(dataset, exception_classifier):
    """Verify refund transaction present in gateway but missing/desynchronized in ledger."""
    ground_truth, sources = dataset
    refund_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "REFUND_MISMATCH"
    ]
    assert len(refund_pids) > 0

    target_pid = refund_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    assert rzp_rec.transaction_type == "refund"

    exc = exception_classifier.classify(
        record_a=rzp_rec,
        record_b=None,
        all_sources=sources,
    )
    assert exc.exception_type == ExceptionType.REFUND_MISMATCH.value
    assert exc.root_cause == "Ledger refund synchronization gap"
    assert exc.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
    assert exc.financial_impact == rzp_rec.amount


# -----------------------------------------------------------------------------
# 9. Partial Settlement
# -----------------------------------------------------------------------------
def test_partial_settlement(dataset, exception_classifier):
    """Verify gateway transaction split across multiple partial bank deposits."""
    ground_truth, sources = dataset
    partial_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "PARTIAL_SETTLEMENT"
    ]
    assert len(partial_pids) > 0

    target_pid = partial_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    split_banks = [b for b in sources["bank"] if b.payment_id == target_pid]

    exc = exception_classifier.classify(
        record_a=rzp_rec,
        record_b=split_banks[0],
        split_records=split_banks,
        all_sources=sources,
    )
    assert exc.exception_type == ExceptionType.PARTIAL_SETTLEMENT.value
    assert exc.root_cause == "Split/partial settlement"
    assert exc.resolution_status == ResolutionStatus.AUTO_RESOLVE.value
    assert exc.financial_impact == Decimal("0.00")


# -----------------------------------------------------------------------------
# 10. Unresolved / UNKNOWN
# -----------------------------------------------------------------------------
def test_unresolved_unknown(dataset, exception_classifier):
    """Verify UNKNOWN records are never auto-resolved, root_cause is None, status is UNRESOLVED."""
    ground_truth, sources = dataset
    unknown_pids = [
        pid for pid, info in ground_truth.items()
        if info.get("exception_type") == "UNKNOWN"
    ]
    assert len(unknown_pids) > 0

    unknown_banks = [b for b in sources["bank"] if (b.bank_reference or "").startswith("UNKN_")]
    assert len(unknown_banks) > 0

    exc = exception_classifier.classify(
        record_a=unknown_banks[0],
        record_b=None,
        all_sources=sources,
    )
    assert exc.exception_type == ExceptionType.UNKNOWN.value
    assert exc.root_cause is None  # Spec requirement: null root cause
    assert exc.resolution_status == ResolutionStatus.UNRESOLVED.value
    assert exc.confidence < 0.80


# -----------------------------------------------------------------------------
# 11. Financial Totals Reconciliation Test
# -----------------------------------------------------------------------------
def test_financial_totals_reconciliation(reconciliation_summary):
    """Assert financial-totals reconciliation: matched_value + exception_value == total_processed_value.

    All non-matched value (exception_value + unresolved_value) represents the total exception pool.
    """
    s = reconciliation_summary
    total_exception_pool = s.exception_value + s.unresolved_value

    assert s.matched_value + total_exception_pool == s.total_processed_value, (
        f"Financial totals mismatch: matched ₹{s.matched_value} + exceptions ₹{total_exception_pool} "
        f"!= total ₹{s.total_processed_value}"
    )
