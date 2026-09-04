"""AI Service: LLM boundary for natural-language explanations.

Per ENGINE_SPEC.md, the LLM is called ONLY for:
  - turning a resolved exception's structured fields into a one-paragraph
    natural-language explanation for the audit log
  - suggesting recommended_action text shown to the operator
  - writing a short natural-language summary of a cluster

For every call:
  - Input: exact structured record(s) already computed — never raw source rows.
  - Output: structured JSON, validated server-side, with numeric-claim checks.
  - Fallback: template-based explanation with no LLM call.
  - Audit: log which source (LLM vs template) was used.
"""

from __future__ import annotations

import json
import logging
import os
import re
from decimal import Decimal
from typing import Any

try:
    from google import genai as _genai_module
    from google.genai import types as _genai_types
except ImportError:
    _genai_module = None  # type: ignore[assignment]
    _genai_types = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class ExplanationResult:
    """Immutable result returned by both the LLM and template paths."""

    __slots__ = ("action_text", "explanation", "source")

    def __init__(self, explanation: str, action_text: str, source: str):
        self.explanation = explanation
        self.action_text = action_text
        self.source = source  # "LLM" | "TEMPLATE"

    def to_dict(self) -> dict[str, str]:
        return {
            "explanation": self.explanation,
            "action_text": self.action_text,
            "source": self.source,
        }


class ClusterSummaryResult:
    """Immutable result for cluster-level natural-language summaries."""

    __slots__ = ("source", "summary")

    def __init__(self, summary: str, source: str):
        self.summary = summary
        self.source = source

    def to_dict(self) -> dict[str, str]:
        return {"summary": self.summary, "source": self.source}


# ---------------------------------------------------------------------------
# Template fallback — zero external dependencies, always available
# ---------------------------------------------------------------------------

_IMPACT_FORMAT = "₹{:,.2f}"

_EXCEPTION_TEMPLATES: dict[str, str] = {
    "DUPLICATE_TRANSACTION": (
        "A duplicate transaction was detected: payment {source_record_id} "
        "appears more than once within the same data source. "
        "The duplicate entry carries a financial impact of {impact}. "
        "Confidence in this classification is {confidence} based on "
        "exact reference matching across rows. {evidence_summary}"
    ),
    "FEE_MISMATCH": (
        "A fee/tax mismatch was identified for payment {source_record_id}. "
        "The difference between the gateway amount and the bank settlement "
        "amount is {impact}, which corresponds to the deducted processing "
        "fee and applicable tax. Confidence is {confidence} because the "
        "discrepancy exactly matches the fee + tax breakdown. {evidence_summary}"
    ),
    "AMOUNT_MISMATCH": (
        "An unexplained amount discrepancy of {impact} was found for payment "
        "{source_record_id}. The difference does not align with known fee or "
        "tax deductions. Confidence is {confidence}. {evidence_summary}"
    ),
    "MISSING_IN_BANK": (
        "Payment {source_record_id} was processed through the payment gateway "
        "but has no corresponding deposit in the bank statement within the "
        "expected settlement window. The outstanding amount is {impact}. "
        "Confidence is {confidence}. {evidence_summary}"
    ),
    "MISSING_IN_RAZORPAY": (
        "A bank credit of {impact} was received but has no corresponding "
        "transaction record in the payment gateway. The unidentified deposit "
        "requires manual investigation. Confidence is {confidence}. "
        "{evidence_summary}"
    ),
    "MISSING_IN_LEDGER": (
        "Payment {source_record_id} is confirmed in both the payment gateway "
        "and bank statement but is absent from the merchant ledger. The "
        "unrecorded amount is {impact}. This indicates a ledger "
        "synchronization gap. Confidence is {confidence}. {evidence_summary}"
    ),
    "SETTLEMENT_TIMING": (
        "Payment {source_record_id} settled later than the expected T+N "
        "window. The transaction was eventually credited in full, so the "
        "net financial impact is {impact} with risk limited to cash-flow "
        "timing. Confidence is {confidence}. {evidence_summary}"
    ),
    "REFUND_MISMATCH": (
        "A refund of {impact} was issued through the payment gateway for "
        "payment {source_record_id} but is not yet reflected in the merchant "
        "ledger. This represents a ledger refund synchronization gap. "
        "Confidence is {confidence}. {evidence_summary}"
    ),
    "PARTIAL_SETTLEMENT": (
        "Payment {source_record_id} was settled across multiple bank "
        "transactions whose combined amount matches the original gateway "
        "record. The financial impact is {impact} (zero if the parts sum "
        "correctly). Confidence is {confidence}. {evidence_summary}"
    ),
    "WRONG_REFERENCE": (
        "Payment {source_record_id} was matched to a bank transaction via "
        "fuzzy reference matching (Level 4). The reference IDs differ by a "
        "minor character transposition, suggesting a data-entry typo rather "
        "than a genuine mismatch. Financial impact is {impact}. Confidence "
        "is {confidence}. {evidence_summary}"
    ),
    "UNKNOWN": (
        "Payment {source_record_id} could not be classified under any known "
        "exception rule. The amount of {impact} remains unreconciled and "
        "requires manual investigation. No automated resolution is "
        "recommended. {evidence_summary}"
    ),
}

_ACTION_TEMPLATES: dict[str, str] = {
    "DUPLICATE_TRANSACTION": "Remove or void the duplicate entry and verify the original transaction is correctly recorded.",
    "FEE_MISMATCH": "Verify the fee schedule with the payment processor and adjust the ledger entry to reflect the net settlement amount.",
    "AMOUNT_MISMATCH": "Investigate the root cause of the amount difference and reconcile manually with the payment processor.",
    "MISSING_IN_BANK": "Confirm settlement status with the payment processor; escalate if the deposit is overdue beyond the SLA.",
    "MISSING_IN_RAZORPAY": "Identify the source of the bank credit and create the corresponding gateway transaction record.",
    "MISSING_IN_LEDGER": "Synchronize the ledger with the confirmed gateway and bank records to close the gap.",
    "SETTLEMENT_TIMING": "Monitor settlement timing trends; no financial action required if the amount settled correctly.",
    "REFUND_MISMATCH": "Post the refund entry to the merchant ledger and verify the customer's refund status.",
    "PARTIAL_SETTLEMENT": "Verify that all split settlement parts are accounted for and linked to the parent transaction.",
    "WRONG_REFERENCE": "Correct the reference ID in the bank statement to match the gateway's UTR/settlement reference.",
    "UNKNOWN": "Manually investigate this transaction — no automated rule could classify it.",
}


def _summarise_evidence(evidence: list[dict[str, Any]]) -> str:
    """Build a brief human-readable summary of the evidence array."""
    if not evidence:
        return ""
    parts: list[str] = []
    for ev in evidence[:3]:  # Cap at 3 items
        desc = ev.get("description", "")
        val = ev.get("value", "")
        if desc:
            parts.append(desc)
        elif val:
            parts.append(str(val))
    if parts:
        return "Evidence: " + "; ".join(parts) + "."
    return ""


def generate_template_explanation(
    exception_type: str,
    root_cause: str | None,
    financial_impact: Decimal | float | str,
    confidence: float,
    evidence: list[dict[str, Any]],
    source_record_id: str,
    matched_record_id: str | None = None,
    **kwargs: Any,
) -> ExplanationResult:
    """Build a readable explanation from the structured fields — no LLM call.

    This is the fallback that always works, even without an API key.
    """
    impact = Decimal(str(financial_impact))
    impact_str = _IMPACT_FORMAT.format(impact)
    conf_str = f"{confidence * 100:.1f}%"
    evidence_summary = _summarise_evidence(evidence)

    template = _EXCEPTION_TEMPLATES.get(exception_type, _EXCEPTION_TEMPLATES["UNKNOWN"])
    explanation = template.format(
        source_record_id=source_record_id,
        impact=impact_str,
        confidence=conf_str,
        evidence_summary=evidence_summary,
    )

    action_text = _ACTION_TEMPLATES.get(exception_type, _ACTION_TEMPLATES["UNKNOWN"])

    return ExplanationResult(
        explanation=explanation.strip(),
        action_text=action_text,
        source="TEMPLATE",
    )


# ---------------------------------------------------------------------------
# LLM-powered explanation via Anthropic API
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a financial reconciliation analyst explaining an already-classified \
payment exception to a non-technical finance operator.

RULES — read carefully:
1. You receive the COMPLETE structured classification (type, root_cause, \
financial_impact, confidence, evidence). The deterministic engine has already \
done all the analysis. Your job is ONLY to turn these facts into clear prose.
2. You MUST use the EXACT numbers provided (financial_impact, confidence). \
Do not round, approximate, or invent numbers. If financial_impact is 0 or \
0.00 (such as in timing variances or clean split settlements), explicitly \
frame it as a timing/grouping variance with zero money lost; do NOT invent a \
nonzero 'at risk' or loss claim.
3. Keep your explanation to ONE concise paragraph (3-5 sentences).
4. Use plain, professional language. Avoid jargon or hedging.
5. The action_text should be a single actionable sentence.
6. Respond with ONLY the JSON object — no markdown fences, no commentary.\
"""

_USER_PROMPT_TEMPLATE = """\
Generate a natural-language explanation and recommended action for this \
reconciliation exception.

Exception data:
{exception_json}

Respond with a JSON object matching this schema exactly:
{{
  "explanation": "<one paragraph, 3-5 sentences>",
  "action_text": "<one actionable sentence>"
}}
"""


def _extract_numbers(text: str) -> set[str]:
    """Extract all number-like tokens from text for validation.

    Matches integers (1234), decimals (12.34), and comma-separated (1,234.56).
    Does NOT match a trailing period at end of sentence (e.g. '00042.').
    """
    return set(re.findall(r"\d[\d,]*(?:\.\d+)?", text))


def _validate_llm_response(
    parsed: dict[str, str],
    financial_impact: Decimal | float | str,
    confidence: float,
    source_record_id: str = "",
    matched_record_id: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> bool:
    """Validate that any numeric claims in the LLM text match our ground truth.

    Per ENGINE_SPEC.md: "if any numeric-looking claim in the text doesn't match
    a number you already computed, discard the LLM text."
    """
    if "explanation" not in parsed or "action_text" not in parsed:
        return False
    if not isinstance(parsed["explanation"], str) or not isinstance(parsed["action_text"], str):
        return False
    if len(parsed["explanation"].strip()) < 20:
        return False

    # Build set of "acceptable" number representations
    impact = Decimal(str(financial_impact))
    acceptable: set[str] = set()

    # Various formats of the financial impact
    acceptable.add(str(impact))
    acceptable.add(f"{impact:,.2f}")
    acceptable.add(f"{impact:.2f}")
    # Strip trailing zeros
    normalized = str(impact.normalize())
    acceptable.add(normalized)
    # Integer form if it's a whole number
    if impact == impact.to_integral_value():
        acceptable.add(str(int(impact)))

    # Confidence representations
    conf_pct = confidence * 100
    acceptable.add(f"{conf_pct:.1f}")
    acceptable.add(f"{conf_pct:.0f}")
    acceptable.add(f"{confidence:.2f}")
    acceptable.add(f"{confidence:.4f}")

    # Extract numbers from input fields (record IDs, evidence, etc.)
    # so we don't reject numbers the LLM copied verbatim from our own data
    input_texts = [source_record_id or "", matched_record_id or ""]
    for ev in (evidence or []):
        input_texts.append(str(ev.get("value", "")))
        input_texts.append(str(ev.get("description", "")))
    for txt in input_texts:
        for num in _extract_numbers(txt):
            acceptable.add(num.replace(",", ""))

    # Check every number in the LLM text
    explanation_numbers = _extract_numbers(parsed["explanation"])
    for num_str in explanation_numbers:
        clean = num_str.replace(",", "")
        if clean in {n.replace(",", "") for n in acceptable}:
            continue
        # Allow small numbers (≤ 10) that might be counts, ordinals, or sentences
        try:
            val = float(clean)
            if val <= 10:
                continue
        except ValueError:
            continue
        # A non-trivial invented number — discard
        logger.warning(
            "LLM produced unrecognised number '%s' in explanation; "
            "discarding response and falling back to template",
            num_str,
        )
        return False

    return True


async def generate_llm_explanation(
    exception_type: str,
    root_cause: str | None,
    financial_impact: Decimal | float | str,
    confidence: float,
    evidence: list[dict[str, Any]],
    source_record_id: str,
    matched_record_id: str | None = None,
    api_key: str | None = None,
    model: str = "gemini-3.5-flash",
    **kwargs: Any,
) -> ExplanationResult:
    """Call the Gemini API for a natural-language explanation.

    Raises on any failure — the caller (the API route) catches this and
    falls back to the template.
    """
    if _genai_module is None:
        raise RuntimeError("google-genai package is not installed")

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("No GEMINI_API_KEY configured")

    # Build the structured input for the prompt
    exception_data = {
        "exception_type": exception_type,
        "root_cause": root_cause,
        "financial_impact": str(financial_impact),
        "confidence": round(confidence, 4),
        "evidence": evidence,
        "source_record_id": source_record_id,
        "matched_record_id": matched_record_id,
    }
    exception_json = json.dumps(exception_data, indent=2, default=str)

    client = _genai_module.Client(api_key=key)

    config = (
        _genai_types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=2048,
        )
        if _genai_types
        else None
    )

    prompt = _USER_PROMPT_TEMPLATE.format(exception_json=exception_json)

    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except Exception as exc:
        if "503" in str(exc) and model != "gemini-3.1-flash-lite":
            logger.warning("Model %s returned 503, retrying with gemini-3.1-flash-lite", model)
            response = await client.aio.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=config,
            )
        else:
            raise

    raw_text = (response.text or "").strip()

    # Strip markdown fences if the model wraps them anyway
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    parsed = json.loads(raw_text)

    # Validate: discard if numeric claims don't match our ground truth
    if not _validate_llm_response(
        parsed,
        financial_impact,
        confidence,
        source_record_id=source_record_id,
        matched_record_id=matched_record_id,
        evidence=evidence,
    ):
        raise ValueError(
            f"LLM response failed numeric validation: {raw_text[:200]}"
        )

    return ExplanationResult(
        explanation=parsed["explanation"].strip(),
        action_text=parsed["action_text"].strip(),
        source="LLM",
    )


# ---------------------------------------------------------------------------
# Cluster summary — template and LLM variants
# ---------------------------------------------------------------------------

def generate_template_cluster_summary(
    exception_type: str,
    root_cause: str | None,
    record_count: int,
    total_financial_impact: Decimal | float | str,
    pct_of_all_exceptions: float,
    avg_confidence: float,
    recommended_action: str,
    **kwargs: Any,
) -> ClusterSummaryResult:
    """Build a readable cluster summary from structured fields — no LLM call."""
    impact = Decimal(str(total_financial_impact))
    impact_str = _IMPACT_FORMAT.format(impact)

    root_str = f" due to \"{root_cause}\"" if root_cause else ""
    summary = (
        f"This cluster contains {record_count} {exception_type.replace('_', ' ').lower()} "
        f"exceptions{root_str}, representing {pct_of_all_exceptions:.1f}% of all "
        f"exceptions with a combined financial impact of {impact_str}. "
        f"Average classification confidence is {avg_confidence * 100:.1f}%. "
        f"Recommended action: {recommended_action}"
    )

    return ClusterSummaryResult(summary=summary.strip(), source="TEMPLATE")


async def generate_llm_cluster_summary(
    exception_type: str,
    root_cause: str | None,
    record_count: int,
    total_financial_impact: Decimal | float | str,
    pct_of_all_exceptions: float,
    avg_confidence: float,
    recommended_action: str,
    api_key: str | None = None,
    model: str = "gemini-3.5-flash",
    **kwargs: Any,
) -> ClusterSummaryResult:
    """Call the Gemini API for a cluster summary. Raises on failure."""
    if _genai_module is None:
        raise RuntimeError("google-genai package is not installed")

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("No GEMINI_API_KEY configured")

    cluster_data = {
        "exception_type": exception_type,
        "root_cause": root_cause,
        "record_count": record_count,
        "total_financial_impact": str(total_financial_impact),
        "pct_of_all_exceptions": pct_of_all_exceptions,
        "avg_confidence": avg_confidence,
        "recommended_action": recommended_action,
    }

    client = _genai_module.Client(api_key=key)

    system_inst = (
        "You summarise patterns of financial reconciliation exceptions for "
        "a finance operator. Use the EXACT numbers provided. Write ONE "
        "concise paragraph explaining what the pattern means and why it "
        "matters. Respond with ONLY a JSON object: {\"summary\": \"...\"}"
    )

    config = (
        _genai_types.GenerateContentConfig(
            system_instruction=system_inst,
            response_mime_type="application/json",
            max_output_tokens=2048,
        )
        if _genai_types
        else None
    )

    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=json.dumps(cluster_data, indent=2, default=str),
            config=config,
        )
    except Exception as exc:
        if "503" in str(exc) and model != "gemini-3.1-flash-lite":
            logger.warning("Model %s returned 503, retrying with gemini-3.1-flash-lite", model)
            response = await client.aio.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=json.dumps(cluster_data, indent=2, default=str),
                config=config,
            )
        else:
            raise

    raw_text = (response.text or "").strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    parsed = json.loads(raw_text)
    if "summary" not in parsed or not isinstance(parsed["summary"], str):
        raise ValueError("LLM cluster summary missing 'summary' field")

    return ClusterSummaryResult(summary=parsed["summary"].strip(), source="LLM")
