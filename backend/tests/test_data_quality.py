from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_data_quality_endpoint():
    """Assert GET /api/data-quality returns valid overall score and 4 dimensions."""
    response = client.get("/api/data-quality")
    assert response.status_code == 200
    data = response.json()

    assert "overall_score" in data
    assert 0.0 <= data["overall_score"] <= 100.0
    assert data["status"] in ("HEALTHY", "DEGRADED", "CRITICAL")
    assert data["total_records"] >= 0
    assert data["clean_records"] >= 0

    dimensions = data["dimensions"]
    for key in ("missing_ids", "duplicate_ids", "missing_amounts", "invalid_dates"):
        assert key in dimensions
        dim = dimensions[key]
        assert "count" in dim
        assert "percentage" in dim
        assert dim["status"] in ("PASS", "FLAGGED")
        assert "details" in dim
