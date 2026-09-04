"""Tests for the AI Service module: template fallback, LLM mock, API endpoint,
and audit-trail logging.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai_service.service import (
    ExplanationResult,
    _validate_llm_response,
    generate_llm_explanation,
    generate_template_cluster_summary,
    generate_template_explanation,
)

# ---------------------------------------------------------------------------
# Template tests (no network, no API key needed)
# ---------------------------------------------------------------------------


class TestTemplateExplanation:
    """Verify the template fallback produces correct, complete explanations."""

    def _make_fields(self, exc_type: str = "FEE_MISMATCH") -> dict:
        return {
            "exception_type": exc_type,
            "root_cause": "Settlement fee/tax deducted from gross amount",
            "financial_impact": Decimal("153.41"),
            "confidence": 0.99,
            "evidence": [
                {
                    "field": "amount_difference",
                    "value": "₹153.41",
                    "description": "Difference matches fee (₹130.40) + tax (₹23.01) exactly",
                }
            ],
            "source_record_id": "rzp_txn_00042",
            "matched_record_id": "bank_txn_pay_00042",
        }

    def test_fee_mismatch_template(self):
        result = generate_template_explanation(**self._make_fields("FEE_MISMATCH"))
        assert result.source == "TEMPLATE"
        assert "₹153.41" in result.explanation
        assert "99.0%" in result.explanation
        assert "fee" in result.explanation.lower()
        assert len(result.action_text) > 10

    def test_unknown_template(self):
        fields = self._make_fields("UNKNOWN")
        fields["root_cause"] = None
        fields["confidence"] = 0.20
        result = generate_template_explanation(**fields)
        assert result.source == "TEMPLATE"
        assert "manual investigation" in result.explanation.lower()

    def test_all_exception_types_produce_output(self):
        types = [
            "DUPLICATE_TRANSACTION", "FEE_MISMATCH", "AMOUNT_MISMATCH",
            "MISSING_IN_BANK", "MISSING_IN_RAZORPAY", "MISSING_IN_LEDGER",
            "SETTLEMENT_TIMING", "REFUND_MISMATCH", "PARTIAL_SETTLEMENT",
            "WRONG_REFERENCE", "UNKNOWN",
        ]
        for exc_type in types:
            fields = self._make_fields(exc_type)
            result = generate_template_explanation(**fields)
            assert result.source == "TEMPLATE", f"Failed for {exc_type}"
            assert len(result.explanation) > 50, f"Too short for {exc_type}"
            assert len(result.action_text) > 10, f"No action for {exc_type}"


class TestTemplateClusterSummary:
    """Verify the cluster summary template."""

    def test_cluster_summary(self):
        result = generate_template_cluster_summary(
            exception_type="FEE_MISMATCH",
            root_cause="Settlement fee/tax deducted from gross amount",
            record_count=9,
            total_financial_impact=Decimal("7103.11"),
            pct_of_all_exceptions=18.4,
            avg_confidence=0.99,
            recommended_action="Verify fee schedule",
        )
        assert result.source == "TEMPLATE"
        assert "9" in result.summary
        assert "₹7,103.11" in result.summary
        assert "18.4%" in result.summary


# ---------------------------------------------------------------------------
# Numeric validation tests
# ---------------------------------------------------------------------------


class TestNumericValidation:
    def test_valid_response_passes(self):
        parsed = {
            "explanation": "The difference of ₹153.41 at 99.0% confidence is due to fees.",
            "action_text": "Verify the fee schedule.",
        }
        assert _validate_llm_response(
            parsed, Decimal("153.41"), 0.99,
            source_record_id="rzp_txn_00042",
        ) is True

    def test_invented_number_fails(self):
        parsed = {
            "explanation": "The difference of ₹999.99 is suspicious.",
            "action_text": "Investigate.",
        }
        assert _validate_llm_response(parsed, Decimal("153.41"), 0.99) is False

    def test_missing_explanation_fails(self):
        assert _validate_llm_response({"action_text": "ok"}, Decimal(0), 0.5) is False

    def test_empty_explanation_fails(self):
        assert _validate_llm_response(
            {"explanation": "short", "action_text": "ok"},
            Decimal(0), 0.5,
        ) is False


# ---------------------------------------------------------------------------
# LLM function tests (mocked — no real API calls)
# ---------------------------------------------------------------------------


class TestLLMExplanation:
    """Test the LLM path with a mocked Gemini client."""

    @pytest.mark.asyncio
    async def test_llm_success_returns_llm_source(self):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "explanation": (
                "A fee mismatch of ₹153.41 was detected for payment rzp_txn_00042. "
                "The discrepancy corresponds exactly to the processing fee and tax "
                "deductions applied during settlement. Classification confidence is "
                "99.0%, confirmed by arithmetic proof."
            ),
            "action_text": "Verify the fee schedule with the payment processor.",
        })

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("app.ai_service.service._genai_module") as mock_genai:
            mock_genai.Client.return_value = mock_client
            result = await generate_llm_explanation(
                exception_type="FEE_MISMATCH",
                root_cause="Settlement fee/tax deducted from gross amount",
                financial_impact=Decimal("153.41"),
                confidence=0.99,
                evidence=[],
                source_record_id="rzp_txn_00042",
                api_key="gemini-test-key",
            )

        assert result.source == "LLM"
        assert "153.41" in result.explanation
        assert len(result.action_text) > 10

    @pytest.mark.asyncio
    async def test_llm_no_api_key_raises(self):
        with pytest.raises(RuntimeError, match="No GEMINI_API_KEY"):
            await generate_llm_explanation(
                exception_type="FEE_MISMATCH",
                root_cause="test",
                financial_impact=Decimal(0),
                confidence=0.5,
                evidence=[],
                source_record_id="test",
                api_key="",
            )

    @pytest.mark.asyncio
    async def test_llm_invented_number_raises(self):
        """If the LLM invents a number, validation should reject it."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "explanation": "The total loss is ₹50,000.00 which is very concerning.",
            "action_text": "Escalate immediately.",
        })

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("app.ai_service.service._genai_module") as mock_genai:
            mock_genai.Client.return_value = mock_client
            with pytest.raises(ValueError, match="numeric validation"):
                await generate_llm_explanation(
                    exception_type="FEE_MISMATCH",
                    root_cause="test",
                    financial_impact=Decimal("153.41"),
                    confidence=0.99,
                    evidence=[],
                    source_record_id="test",
                    api_key="gemini-test-key",
                )


# ---------------------------------------------------------------------------
# API endpoint tests (template path, no real API key)
# ---------------------------------------------------------------------------


class TestExplainEndpoint:
    """Test the /api/exceptions/{id}/explain endpoint using the template path."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    def test_explain_returns_template_without_api_key(self, monkeypatch):
        """With no API key, the endpoint should return a template explanation
        with no errors and source='TEMPLATE'."""
        from app.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", "")

        # Get an exception ID (data will auto-load on first request)
        exceptions_resp = self.client.get("/api/exceptions?limit=1")
        assert exceptions_resp.status_code == 200
        exc_list = exceptions_resp.json()
        assert len(exc_list) > 0
        exc_id = exc_list[0]["id"]

        # Hit the explain endpoint
        resp = self.client.get(f"/api/exceptions/{exc_id}/explain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["exception_id"] == exc_id
        assert body["source"] == "TEMPLATE"
        assert len(body["explanation"]) > 50
        assert len(body["action_text"]) > 10

    def test_explain_writes_audit_log(self, monkeypatch):
        """The explain endpoint should write an audit log entry."""
        from app.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", "")

        exceptions_resp = self.client.get("/api/exceptions?limit=1")
        exc_id = exceptions_resp.json()[0]["id"]

        self.client.get(f"/api/exceptions/{exc_id}/explain")

        # Check audit log
        audit_resp = self.client.get(f"/api/audit-log?exception_id={exc_id}")
        assert audit_resp.status_code == 200
        audit_entries = audit_resp.json()
        explain_entries = [
            e for e in audit_entries
            if e["event_type"] == "EXPLANATION_GENERATED"
        ]
        assert len(explain_entries) >= 1
        latest = explain_entries[-1]
        assert "TEMPLATE" in latest["action"]
        assert latest["actor"] == "SYSTEM_TEMPLATE"
        assert latest["action"] == "GENERATE_EXPLANATION_TEMPLATE_NO_KEY"

    def test_cluster_summary_fallback_without_api_key(self, monkeypatch):
        """Cluster summary with no API key should return 200, source='TEMPLATE',
        coherent grounded text, and write audit log."""
        from app.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", "")

        clusters_resp = self.client.get("/api/exception-clusters")
        assert clusters_resp.status_code == 200
        clusters = clusters_resp.json()
        assert len(clusters) > 0
        cl_id = clusters[0]["cluster_id"]

        resp = self.client.get(f"/api/exception-clusters/{cl_id}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cluster_id"] == cl_id
        assert body["source"] == "TEMPLATE"
        assert "N/A" not in body["summary"]
        assert len(body["summary"]) > 30

        # Check audit log
        audit_resp = self.client.get("/api/audit-log?event_type=CLUSTER_SUMMARY_GENERATED")
        assert audit_resp.status_code == 200
        entries = audit_resp.json()
        assert len(entries) >= 1
        latest = entries[-1]
        assert latest["actor"] == "SYSTEM_TEMPLATE"
        assert latest["action"] == "GENERATE_CLUSTER_SUMMARY_TEMPLATE_NO_KEY"

    def test_explain_fallback_on_malformed_llm_json(self, monkeypatch):
        """When LLM returns malformed JSON, endpoint must fall back to template
        with 200 OK, source='TEMPLATE', and distinct audit action."""
        from app.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", "test-key-configured")

        exceptions_resp = self.client.get("/api/exceptions?limit=1")
        exc_id = exceptions_resp.json()[0]["id"]

        with patch("app.api.ai_explanations.generate_llm_explanation", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = json.JSONDecodeError("Expecting value", "invalid json", 0)

            resp = self.client.get(f"/api/exceptions/{exc_id}/explain")
            assert resp.status_code == 200
            body = resp.json()
            assert body["source"] == "TEMPLATE"
            assert "N/A" not in body["explanation"]
            assert len(body["explanation"]) > 30

        audit_resp = self.client.get(f"/api/audit-log?exception_id={exc_id}")
        assert audit_resp.status_code == 200
        explain_entries = [
            e for e in audit_resp.json()
            if e["event_type"] == "EXPLANATION_GENERATED"
        ]
        latest = explain_entries[-1]
        assert latest["actor"] == "SYSTEM_TEMPLATE_FALLBACK"
        assert latest["action"] == "GENERATE_EXPLANATION_TEMPLATE_FALLBACK"
        assert "Expecting value" in latest["details"]

    def test_explain_fallback_on_llm_numeric_validation_failure(self, monkeypatch):
        """When LLM returns an ungrounded invented number, endpoint must reject
        and fall back to template with 200 OK and distinct audit action."""
        from app.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", "test-key-configured")

        exceptions_resp = self.client.get("/api/exceptions?limit=1")
        exc_id = exceptions_resp.json()[0]["id"]

        with patch("app.api.ai_explanations.generate_llm_explanation", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = ValueError("LLM response failed numeric validation: invented number 99999999")

            resp = self.client.get(f"/api/exceptions/{exc_id}/explain")
            assert resp.status_code == 200
            body = resp.json()
            assert body["source"] == "TEMPLATE"
            assert "N/A" not in body["explanation"]

        audit_resp = self.client.get(f"/api/audit-log?exception_id={exc_id}")
        assert audit_resp.status_code == 200
        explain_entries = [
            e for e in audit_resp.json()
            if e["event_type"] == "EXPLANATION_GENERATED"
        ]
        latest = explain_entries[-1]
        assert latest["actor"] == "SYSTEM_TEMPLATE_FALLBACK"
        assert latest["action"] == "GENERATE_EXPLANATION_TEMPLATE_VALIDATION_FAILED"
        assert "numeric validation" in latest["details"]

    def test_explain_successful_llm_audit_distinction(self, monkeypatch):
        """Successful LLM response produces source='LLM' and SYSTEM_AI_SERVICE audit log."""
        from app.config import settings
        monkeypatch.setattr(settings, "gemini_api_key", "test-key-configured")

        exceptions_resp = self.client.get("/api/exceptions?limit=1")
        exc_id = exceptions_resp.json()[0]["id"]

        with patch("app.api.ai_explanations.generate_llm_explanation", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ExplanationResult(
                explanation="Validated LLM explanation with exact numbers.",
                action_text="Take verified operator action.",
                source="LLM",
            )

            resp = self.client.get(f"/api/exceptions/{exc_id}/explain")
            assert resp.status_code == 200
            body = resp.json()
            assert body["source"] == "LLM"
            assert body["explanation"] == "Validated LLM explanation with exact numbers."

        audit_resp = self.client.get(f"/api/audit-log?exception_id={exc_id}")
        assert audit_resp.status_code == 200
        explain_entries = [
            e for e in audit_resp.json()
            if e["event_type"] == "EXPLANATION_GENERATED"
        ]
        latest = explain_entries[-1]
        assert latest["actor"] == "SYSTEM_AI_SERVICE"
        assert latest["action"] == "GENERATE_EXPLANATION_LLM"

    def test_explain_404_for_missing_exception(self):
        resp = self.client.get("/api/exceptions/nonexistent_id/explain")
        assert resp.status_code == 404

