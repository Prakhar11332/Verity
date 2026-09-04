"""Unit tests for the Exception Engine and Root-Cause Classification (Phase 2).

Tests:
1. One test per exception type from DATA_MODEL.md (all 9 types) asserting:
   - right exception_type
   - right root_cause
   - right routing tier (AUTO_RESOLVE / REVIEW_REQUIRED / UNRESOLVED)
2. Invariant: UNKNOWN exceptions NEVER receive AUTO_RESOLVE.
3. Database persistence with foreign keys to source_records.
4. Initial audit-log entry format ("Exception classified as X, confidence Y%, evidence: [...]").
"""

import json
import os
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters import BankAdapter, LedgerAdapter, RazorpayAdapter, SettlementAdapter
from app.database import Base
from app.exceptions.classifier import ExceptionClassifierService, RoutingThresholds
from app.exceptions.repository import ExceptionRepository
from app.exceptions.types import ExceptionType, ResolutionStatus
from app.models.audit_log import AuditLogModel
from app.models.exception import ExceptionModel
from app.models.source_record import SourceRecordModel
from app.reconciliation.engine import ReconciliationEngine
from app.schemas.record import Record

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@pytest.fixture(scope="module")
def dataset():
    """Load all 4 source records and ground truth."""
    gt_path = os.path.join(DATA_DIR, "ground_truth.json")
    if not os.path.exists(gt_path):
        pytest.skip("Synthetic data not generated.")

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
def classifier():
    return ExceptionClassifierService()


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing persistence."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


# -----------------------------------------------------------------------------
# 1. Test FEE_MISMATCH
# -----------------------------------------------------------------------------
def test_fee_mismatch_exception(dataset, classifier):
    ground_truth, sources = dataset
    fee_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "FEE_MISMATCH"]
    assert len(fee_pids) > 0

    target_pid = fee_pids[0]
    bank_rec = next(b for b in sources["bank"] if b.payment_id == target_pid)
    ledger_rec = next(rec for rec in sources["ledger"] if rec.payment_id == target_pid)

    # In FEE_MISMATCH, ledger retained gross amount while bank received net
    exc = classifier.classify(
        record_a=ledger_rec,
        record_b=bank_rec,
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.FEE_MISMATCH.value
    assert exc.root_cause == "Settlement fee/tax deducted from gross amount"
    assert exc.resolution_status == ResolutionStatus.AUTO_RESOLVE.value
    assert exc.confidence >= 0.95
    assert exc.financial_impact > Decimal("0.00")
    assert len(exc.evidence) >= 1


# -----------------------------------------------------------------------------
# 2. Test SETTLEMENT_TIMING
# -----------------------------------------------------------------------------
def test_settlement_timing_exception(dataset, classifier):
    ground_truth, sources = dataset
    timing_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "SETTLEMENT_TIMING"]
    assert len(timing_pids) > 0

    target_pid = timing_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    bank_rec = next(b for b in sources["bank"] if b.payment_id == target_pid)

    exc = classifier.classify(
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
# 3. Test DUPLICATE_TRANSACTION
# -----------------------------------------------------------------------------
def test_duplicate_transaction_exception(dataset, classifier):
    ground_truth, sources = dataset
    dup_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "DUPLICATE_TRANSACTION"]
    assert len(dup_pids) > 0

    target_pid = dup_pids[0]
    dups = [r for r in sources["razorpay"] if r.payment_id == target_pid]
    assert len(dups) >= 2

    exc = classifier.classify(
        record_a=dups[0],
        duplicate_records=dups,
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.DUPLICATE_TRANSACTION.value
    assert exc.root_cause == "Duplicate transaction"
    assert exc.resolution_status == ResolutionStatus.AUTO_RESOLVE.value
    assert exc.confidence >= 0.95
    assert exc.financial_impact == dups[0].amount


# -----------------------------------------------------------------------------
# 4. Test MISSING_IN_BANK
# -----------------------------------------------------------------------------
def test_missing_in_bank_exception(dataset, classifier):
    ground_truth, sources = dataset
    missing_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "MISSING_IN_BANK"]
    assert len(missing_pids) > 0

    target_pid = missing_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)

    exc = classifier.classify(
        record_a=rzp_rec,
        record_b=None,
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.MISSING_IN_BANK.value
    assert exc.root_cause == "Pending or missing settlement"
    assert exc.resolution_status == ResolutionStatus.AUTO_RESOLVE.value
    assert exc.confidence >= 0.95
    assert exc.financial_impact == rzp_rec.amount


# -----------------------------------------------------------------------------
# 5. Test MISSING_IN_LEDGER
# -----------------------------------------------------------------------------
def test_missing_in_ledger_exception(dataset, classifier):
    ground_truth, sources = dataset
    missing_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "MISSING_IN_LEDGER"]
    assert len(missing_pids) > 0

    target_pid = missing_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    bank_rec = next(b for b in sources["bank"] if b.payment_id == target_pid)

    exc = classifier.classify(
        record_a=rzp_rec,
        record_b=bank_rec,
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.MISSING_IN_LEDGER.value
    assert exc.root_cause == "Ledger synchronization gap"
    assert exc.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
    assert 0.80 <= exc.confidence < 0.95
    assert exc.financial_impact == rzp_rec.amount


# -----------------------------------------------------------------------------
# 6. Test REFUND_MISMATCH
# -----------------------------------------------------------------------------
def test_refund_mismatch_exception(dataset, classifier):
    ground_truth, sources = dataset
    refund_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "REFUND_MISMATCH"]
    assert len(refund_pids) > 0

    target_pid = refund_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    assert rzp_rec.transaction_type == "refund"

    exc = classifier.classify(
        record_a=rzp_rec,
        record_b=None,
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.REFUND_MISMATCH.value
    assert exc.root_cause == "Ledger refund synchronization gap"
    assert exc.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
    assert 0.80 <= exc.confidence < 0.95
    assert exc.financial_impact == rzp_rec.amount


# -----------------------------------------------------------------------------
# 7. Test WRONG_REFERENCE
# -----------------------------------------------------------------------------
def test_wrong_reference_exception(dataset, classifier):
    ground_truth, sources = dataset
    wrong_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "WRONG_REFERENCE"]
    assert len(wrong_pids) > 0

    target_pid = wrong_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    bank_rec = next(b for b in sources["bank"] if b.transaction_id == f"bank_txn_{target_pid}")

    exc = classifier.classify(
        record_a=rzp_rec,
        record_b=bank_rec,
        match_level="LEVEL_4_FUZZY_REFERENCE",
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.WRONG_REFERENCE.value
    assert exc.root_cause == "Reference ID mismatch (likely transcription error)"
    assert exc.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
    assert 0.80 <= exc.confidence < 0.95


# -----------------------------------------------------------------------------
# 8. Test PARTIAL_SETTLEMENT
# -----------------------------------------------------------------------------
def test_partial_settlement_exception(dataset, classifier):
    ground_truth, sources = dataset
    partial_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "PARTIAL_SETTLEMENT"]
    assert len(partial_pids) > 0

    target_pid = partial_pids[0]
    rzp_rec = next(r for r in sources["razorpay"] if r.payment_id == target_pid)
    split_banks = [b for b in sources["bank"] if b.payment_id == target_pid]

    exc = classifier.classify(
        record_a=rzp_rec,
        record_b=split_banks[0],
        split_records=split_banks,
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.PARTIAL_SETTLEMENT.value
    assert exc.root_cause == "Split/partial settlement"
    assert exc.resolution_status == ResolutionStatus.AUTO_RESOLVE.value
    assert exc.confidence >= 0.95
    # Financial impact is 0 if sum reconciles exactly (ENGINE_SPEC.md)
    assert exc.financial_impact == Decimal("0.00")


# -----------------------------------------------------------------------------
# 9. Test UNKNOWN
# -----------------------------------------------------------------------------
def test_unknown_exception(dataset, classifier):
    ground_truth, sources = dataset
    unknown_pids = [pid for pid, info in ground_truth.items() if info["exception_type"] == "UNKNOWN"]
    assert len(unknown_pids) > 0

    # Pick an unknown bank transaction
    unknown_banks = [b for b in sources["bank"] if (b.bank_reference or "").startswith("UNKN_")]
    assert len(unknown_banks) > 0

    target_bank = unknown_banks[0]
    exc = classifier.classify(
        record_a=target_bank,
        record_b=None,
        all_sources=sources,
    )

    assert exc.exception_type == ExceptionType.UNKNOWN.value
    assert exc.root_cause is None  # Root cause must be None per spec
    assert exc.resolution_status == ResolutionStatus.UNRESOLVED.value
    assert exc.confidence < 0.80


# -----------------------------------------------------------------------------
# 10. Invariant: UNKNOWN never gets AUTO_RESOLVE
# -----------------------------------------------------------------------------
def test_unknown_never_auto_resolves(classifier):
    """Assert UNKNOWN-type exceptions NEVER get AUTO_RESOLVE routing even with threshold overrides."""
    # Force auto-resolve threshold very low
    permissive_classifier = ExceptionClassifierService(
        routing_thresholds=RoutingThresholds(auto_resolve_min_confidence=0.10)
    )

    unknown_record = Record(
        transaction_id="bank_unkn_test",
        source_name="bank",
        amount=Decimal("5000.00"),
        transaction_date=None,
        transaction_type="payment",
        status="success",
        description="Unknown credit",
        merchant_id="MERCH_001",
        bank_reference="UNKN_99999999",
    )

    exc = permissive_classifier.classify(record_a=unknown_record)
    assert exc.exception_type == "UNKNOWN"
    assert exc.resolution_status == ResolutionStatus.UNRESOLVED.value
    assert exc.resolution_status != ResolutionStatus.AUTO_RESOLVE.value


# -----------------------------------------------------------------------------
# 11. Database Persistence and Audit Trail
# -----------------------------------------------------------------------------
def test_database_persistence_and_audit_log(test_db, dataset, classifier):
    _, sources = dataset
    repo = ExceptionRepository(test_db)

    # 1. Save source records first (to satisfy foreign keys)
    sample_records = sources["razorpay"][:5] + sources["bank"][:5]
    repo.save_source_records(sample_records)

    # Check source_records table
    stored_sources = test_db.query(SourceRecordModel).all()
    assert len(stored_sources) >= 5

    # 2. Classify and save an exception
    exc = classifier.classify(
        record_a=sample_records[0],
        record_b=sample_records[1],
        all_sources=sources,
        exception_id="exc_test_001",
    )
    repo.save_exception(exc)

    # Verify exception in DB
    db_exc = test_db.query(ExceptionModel).filter_by(id="exc_test_001").first()
    assert db_exc is not None
    assert db_exc.exception_type == exc.exception_type
    assert db_exc.source_record_id == sample_records[0].transaction_id

    # 3. Verify audit log entry format
    # "Exception classified as X, confidence Y%, evidence: [...]"
    audit_entry = test_db.query(AuditLogModel).filter_by(exception_id="exc_test_001").first()
    assert audit_entry is not None
    assert audit_entry.event_type == "EXCEPTION_CLASSIFIED"
    assert audit_entry.actor == "SYSTEM_DETERMINISTIC"
    assert f"Exception classified as {exc.exception_type}, confidence {exc.confidence * 100:.1f}%, evidence: [" in audit_entry.details


# -----------------------------------------------------------------------------
# 11. End-to-End Test: WRONG_REFERENCE from actual generator output
# -----------------------------------------------------------------------------
def test_wrong_reference_end_to_end_from_generator(dataset):
    """Assert WRONG_REFERENCE records produced by generate_synthetic_data.py
    route through Level 4 fuzzy matching and classify as WRONG_REFERENCE."""
    ground_truth, sources = dataset
    wrong_pids = [
        pid for pid, info in ground_truth.items()
        if info["exception_type"] == "WRONG_REFERENCE"
    ]
    assert len(wrong_pids) == 3, f"Expected 3 seeded WRONG_REFERENCE records, got {len(wrong_pids)}"

    # Run full reconciliation engine
    engine = ReconciliationEngine()
    summary = engine.reconcile(sources)

    # Verify each WRONG_REFERENCE transaction matched at Level 4
    for pid in wrong_pids:
        r = next(
            (res for res in summary.results if res.record_a.payment_id == pid),
            None,
        )
        assert r is not None, f"No reconciliation result found for {pid}"
        assert r.record_b is not None, f"No bank match found for {pid}"
        assert r.match_level == "LEVEL_4_FUZZY_REFERENCE", (
            f"{pid} expected LEVEL_4_FUZZY_REFERENCE, got {r.match_level}"
        )
        assert r.classification == "LIKELY_MATCH", (
            f"{pid} expected LIKELY_MATCH, got {r.classification}"
        )

    # Run full exception classifier
    classifier = ExceptionClassifierService()
    exceptions = classifier.classify_all_exceptions(summary, sources)

    # Verify all 3 exceptions are produced with correct root cause and routing tier
    classified_wrong_refs = [
        e for e in exceptions
        if e.exception_type == ExceptionType.WRONG_REFERENCE.value
    ]
    assert len(classified_wrong_refs) == 3, (
        f"Expected 3 WRONG_REFERENCE exceptions, got {len(classified_wrong_refs)}"
    )

    for e in classified_wrong_refs:
        assert e.root_cause == "Reference ID mismatch (likely transcription error)"
        assert e.resolution_status == ResolutionStatus.REVIEW_REQUIRED.value
        assert 0.80 <= e.confidence < 0.95
        ref_evidence = next(
            (ev for ev in e.evidence if ev.get("field") == "reference_comparison"),
            None,
        )
        assert ref_evidence is not None, f"Missing reference_comparison in evidence for {e.id}"

