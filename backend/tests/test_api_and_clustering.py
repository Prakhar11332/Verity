"""Comprehensive tests for Phase 3: Clustering, Priority Scoring, and REST API Endpoints."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.adapters import BankAdapter, LedgerAdapter, RazorpayAdapter, SettlementAdapter
from app.clustering.service import ClusterService
from app.clustering.types import PriorityWeights
from app.exceptions.classifier import ExceptionClassifierService
from app.main import app
from app.reconciliation.engine import ReconciliationEngine


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def initialized_data():
    """Load sources, run reconciliation, and classify exceptions."""
    sources = {
        "razorpay": RazorpayAdapter().fetch_records(),
        "bank": BankAdapter().fetch_records(),
        "ledger": LedgerAdapter().fetch_records(),
        "settlement": SettlementAdapter().fetch_records(),
    }
    engine = ReconciliationEngine()
    summary = engine.reconcile(sources)
    classifier = ExceptionClassifierService()
    exceptions = classifier.classify_all_exceptions(summary, sources)
    return sources, summary, exceptions


# =============================================================================
# 1. Clustering & Priority Scoring Tests
# =============================================================================

def test_clustering_produces_handful_of_clusters_not_individual_rows(initialized_data):
    """Assert clustering produces a concise handful of clusters (e.g. 7-9), not 30+ individual rows."""
    _, _, exceptions = initialized_data
    assert len(exceptions) >= 20, f"Expected at least 20 raw exceptions, got {len(exceptions)}"

    cluster_service = ClusterService()
    clusters = cluster_service.build_clusters(exceptions)

    # Must be a handful of clusters (between 5 and 12), NOT 30+ rows!
    assert 4 <= len(clusters) <= 12, (
        f"Expected a handful of clusters (4-12), got {len(clusters)} from {len(exceptions)} exceptions"
    )

    # Verify every cluster has all required properties per ENGINE_SPEC.md
    for c in clusters:
        assert c.cluster_id.startswith("cl_")
        assert c.exception_type
        assert c.record_count >= 1
        assert c.total_financial_impact >= Decimal("0.00")
        assert 0.0 < c.pct_of_all_exceptions <= 100.0
        assert 0.0 <= c.avg_confidence <= 1.0
        assert c.recommended_action
        assert len(c.exception_ids) == c.record_count
        assert 0.0 <= c.priority_score <= 1.0


def test_clustering_metrics_and_priority_sorting(initialized_data):
    """Assert percentage sum reconciles, and clusters are sorted descending by priority score."""
    _, _, exceptions = initialized_data
    cluster_service = ClusterService(weights=PriorityWeights(w_impact=0.4, w_confidence=0.3, w_count=0.2, w_age=0.1))
    clusters = cluster_service.build_clusters(exceptions)

    # Total records across clusters equals total exceptions
    total_clustered_records = sum(c.record_count for c in clusters)
    assert total_clustered_records == len(exceptions)

    # Total percentages sum to approximately 100%
    pct_sum = sum(c.pct_of_all_exceptions for c in clusters)
    assert 99.0 <= pct_sum <= 101.0

    # Clusters must be sorted descending by priority score
    scores = [c.priority_score for c in clusters]
    assert scores == sorted(scores, reverse=True), f"Clusters not sorted descending by priority: {scores}"


# =============================================================================
# 2. REST API Endpoints Tests
# =============================================================================

def test_api_reconciliation_run(client):
    """Test POST /api/reconciliation/run."""
    response = client.post("/api/reconciliation/run")
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["total_records"] >= 140
    assert data["status"] == "COMPLETED"
    assert 0.5 <= data["match_rate"] <= 0.95


def test_api_reconciliation_summary(client):
    """Test GET /api/reconciliation/summary."""
    response = client.get("/api/reconciliation/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] > 0
    assert "match_rate" in data
    assert "matched_value" in data
    assert "exception_value" in data


def test_api_reconciliation_records(client):
    """Test GET /api/reconciliation/records with filtering."""
    response = client.get("/api/reconciliation/records?limit=50")
    assert response.status_code == 200
    records = response.json()
    assert len(records) > 0

    # Filter by MATCHED
    resp_matched = client.get("/api/reconciliation/records?classification=MATCHED&limit=10")
    assert resp_matched.status_code == 200
    for r in resp_matched.json():
        assert r["classification"] == "MATCHED"


def test_api_exceptions_list_and_detail(client):
    """Test GET /api/exceptions and GET /api/exceptions/{id}."""
    response = client.get("/api/exceptions?limit=100")
    assert response.status_code == 200
    exceptions = response.json()
    assert len(exceptions) > 0

    first_exc = exceptions[0]
    exc_id = first_exc["id"]

    # Detail query
    detail_resp = client.get(f"/api/exceptions/{exc_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == exc_id
    assert "evidence" in detail
    assert "confidence" in detail
    assert "audit_trail" in detail
    assert len(detail["audit_trail"]) >= 1
    assert detail["source_record"] is not None


def test_api_exception_clusters(client):
    """Test GET /api/exception-clusters."""
    response = client.get("/api/exception-clusters")
    assert response.status_code == 200
    clusters = response.json()
    assert 4 <= len(clusters) <= 12

    # Check top cluster properties
    top = clusters[0]
    assert "cluster_id" in top
    assert "record_count" in top
    assert "priority_score" in top
    assert "exception_ids" in top
    assert len(top["exception_ids"]) == top["record_count"]


def test_api_approve_and_reject_write_to_audit_log(client):
    """Assert POST /api/exceptions/{id}/approve and /reject write to audit log."""
    # Fetch an exception to test
    resp = client.get("/api/exceptions?limit=2")
    exceptions = resp.json()
    assert len(exceptions) >= 2

    exc1_id = exceptions[0]["id"]
    exc2_id = exceptions[1]["id"]

    # 1. Test APPROVE
    appr_resp = client.post(
        f"/api/exceptions/{exc1_id}/approve",
        json={"actor": "LEAD_AUDITOR", "notes": "Verified against bank wire confirmation"},
    )
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()
    assert appr_data["success"] is True
    assert appr_data["new_status"] == "APPROVED"
    assert "audit_log_id" in appr_data

    # Verify audit log recorded the approval
    audit_resp = client.get(f"/api/audit-log?exception_id={exc1_id}")
    assert audit_resp.status_code == 200
    audit_entries = audit_resp.json()
    assert len(audit_entries) >= 2  # initial classification + approval
    latest_event = audit_entries[-1]
    assert latest_event["event_type"] == "RESOLUTION_APPROVED"
    assert latest_event["actor"] == "LEAD_AUDITOR"
    assert "Verified against bank wire confirmation" in latest_event["details"]

    # 2. Test REJECT
    rej_resp = client.post(
        f"/api/exceptions/{exc2_id}/reject",
        json={"actor": "RISK_OPS", "notes": "Mismatched UTR requires provider ticketing"},
    )
    assert rej_resp.status_code == 200
    rej_data = rej_resp.json()
    assert rej_data["success"] is True
    assert rej_data["new_status"] == "REJECTED"

    # Verify audit log recorded the rejection
    audit_resp2 = client.get(f"/api/audit-log?exception_id={exc2_id}")
    assert audit_resp2.status_code == 200
    audit_entries2 = audit_resp2.json()
    latest_rej = audit_entries2[-1]
    assert latest_rej["event_type"] == "RESOLUTION_REJECTED"
    assert latest_rej["actor"] == "RISK_OPS"
    # 3. Test UNRESOLVE
    unres_resp = client.post(
        f"/api/exceptions/{exc1_id}/unresolve",
        json={"actor": "LEAD_AUDITOR", "notes": "Reopening for further inquiry"},
    )
    assert unres_resp.status_code == 200
    unres_data = unres_resp.json()
    assert unres_data["success"] is True
    assert unres_data["new_status"] == "UNRESOLVED"

    audit_resp3 = client.get(f"/api/audit-log?exception_id={exc1_id}")
    assert audit_resp3.status_code == 200
    latest_unres = audit_resp3.json()[-1]
    assert latest_unres["event_type"] == "RESOLUTION_UNRESOLVED"
    assert latest_unres["action"] == "UNRESOLVE_EXCEPTION"


def test_api_audit_log_chronological_ordering(client):
    """Assert GET /api/audit-log returns events in chronological order with timestamps."""
    resp = client.get("/api/audit-log?limit=50")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) > 0

    timestamps = [e["timestamp"] for e in entries]
    assert timestamps == sorted(timestamps), "Audit log entries not in chronological order"
