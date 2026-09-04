"""Deterministic 11-rule root-cause engine per ENGINE_SPEC.md.

Rules are evaluated in strict order (1 to 11).
Rule 11 (UNKNOWN) is the explicit fallback — no catch-all guess.
No LLM calls anywhere in this module.
"""

from __future__ import annotations

import difflib
from decimal import Decimal
from typing import Any

from app.exceptions.types import ClassifiedException, ExceptionType, ResolutionStatus
from app.schemas.record import Record


def evaluate_rules(
    record_a: Record,
    record_b: Record | None = None,
    match_level: str | None = None,
    all_sources: dict[str, list[Record]] | None = None,
    split_records: list[Record] | None = None,
    duplicate_records: list[Record] | None = None,
    exception_id: str | None = None,
) -> ClassifiedException:
    """Evaluate the 11 root-cause rules in order and return a ClassifiedException."""
    eid = exception_id or f"exc_{record_a.transaction_id}"

    # -------------------------------------------------------------------------
    # Rule 1: Same reference in 2+ rows within one source
    # -------------------------------------------------------------------------
    rule_1_match, r1_evidence = _check_rule_1_duplicate(record_a, all_sources, duplicate_records)
    if rule_1_match:
        confidence = 0.98
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.DUPLICATE_TRANSACTION.value,
            root_cause="Duplicate transaction",
            financial_impact=record_a.amount or Decimal("0.00"),
            confidence=confidence,
            evidence=r1_evidence,
            recommended_action="Void or reverse duplicate entry in payment gateway/ledger",
            resolution_status=ResolutionStatus.AUTO_RESOLVE.value,  # Rule 1 + 98% >= 95%
            source_record_id=record_a.transaction_id,
            matched_record_id=record_b.transaction_id if record_b else None,
            rule_number=1,
        )

    # -------------------------------------------------------------------------
    # Rule 2: Reference matched, amounts differ, |diff - (fee + tax)| < ₹1
    # -------------------------------------------------------------------------
    rule_2_match, r2_evidence, r2_impact = _check_rule_2_fee_mismatch(record_a, record_b, all_sources)
    if rule_2_match:
        confidence = 0.99
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.FEE_MISMATCH.value,
            root_cause="Settlement fee/tax deducted from gross amount",
            financial_impact=r2_impact,
            confidence=confidence,
            evidence=r2_evidence,
            recommended_action="Record settlement fee and GST tax journal entry in merchant ledger",
            resolution_status=ResolutionStatus.AUTO_RESOLVE.value,  # Rule 2 + 99% >= 95%
            source_record_id=record_a.transaction_id,
            matched_record_id=record_b.transaction_id if record_b else None,
            rule_number=2,
        )

    # -------------------------------------------------------------------------
    # Rule 3: Reference matched, amounts differ, diff doesn't match fee+tax, |diff| < ₹1 rounding
    # -------------------------------------------------------------------------
    rule_3_match, r3_evidence, r3_impact = _check_rule_3_amount_mismatch(
        record_a, record_b, split_records=split_records, all_sources=all_sources
    )
    if rule_3_match:
        confidence = 0.85
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.AMOUNT_MISMATCH.value,
            root_cause="Unexplained amount difference",
            financial_impact=r3_impact,
            confidence=confidence,
            evidence=r3_evidence,
            recommended_action="Investigate unexplained amount difference with payment provider",
            resolution_status=ResolutionStatus.REVIEW_REQUIRED.value,  # 80-94%
            source_record_id=record_a.transaction_id,
            matched_record_id=record_b.transaction_id if record_b else None,
            rule_number=3,
        )

    # -------------------------------------------------------------------------
    # Rule 4: Exists in Razorpay, no bank row within settlement window
    # -------------------------------------------------------------------------
    rule_4_match, r4_evidence = _check_rule_4_missing_in_bank(record_a, record_b, all_sources)
    if rule_4_match:
        confidence = 0.95
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.MISSING_IN_BANK.value,
            root_cause="Pending or missing settlement",
            financial_impact=record_a.amount or Decimal("0.00"),
            confidence=confidence,
            evidence=r4_evidence,
            recommended_action="Check settlement batch status with Razorpay",
            resolution_status=ResolutionStatus.AUTO_RESOLVE.value,  # Rule 4 + 95% >= 95%
            source_record_id=record_a.transaction_id,
            matched_record_id=None,
            rule_number=4,
        )

    # -------------------------------------------------------------------------
    # Rule 5: Exists in bank, no Razorpay row at all
    # -------------------------------------------------------------------------
    rule_5_match, r5_evidence = _check_rule_5_missing_in_razorpay(record_a, record_b, all_sources)
    if rule_5_match:
        confidence = 0.85
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.MISSING_IN_RAZORPAY.value,
            root_cause="Unidentified bank transaction",
            financial_impact=record_a.amount or Decimal("0.00"),
            confidence=confidence,
            evidence=r5_evidence,
            recommended_action="Identify origin of bank credit/debit and create merchant transaction",
            resolution_status=ResolutionStatus.REVIEW_REQUIRED.value,  # Not in auto-resolve list
            source_record_id=record_a.transaction_id,
            matched_record_id=None,
            rule_number=5,
        )

    # -------------------------------------------------------------------------
    # Rule 6: Exists in Razorpay + bank, missing from ledger
    # -------------------------------------------------------------------------
    rule_6_match, r6_evidence = _check_rule_6_missing_in_ledger(record_a, record_b, all_sources)
    if rule_6_match:
        confidence = 0.92
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.MISSING_IN_LEDGER.value,
            root_cause="Ledger synchronization gap",
            financial_impact=record_a.amount or Decimal("0.00"),
            confidence=confidence,
            evidence=r6_evidence,
            recommended_action="Post missing transaction to merchant ledger",
            resolution_status=ResolutionStatus.REVIEW_REQUIRED.value,  # Not in auto-resolve list
            source_record_id=record_a.transaction_id,
            matched_record_id=record_b.transaction_id if record_b else None,
            rule_number=6,
        )

    # -------------------------------------------------------------------------
    # Rule 7: Amount matches, dates differ but within acceptable T+N window
    # -------------------------------------------------------------------------
    rule_7_match, r7_evidence = _check_rule_7_settlement_timing(record_a, record_b)
    if rule_7_match:
        # Lower confidence (88%) per ENGINE_SPEC because window is a judgment call
        confidence = 0.88
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.SETTLEMENT_TIMING.value,
            root_cause="Settlement timing difference",
            financial_impact=Decimal("0.00"),  # Timing variance, no money lost
            confidence=confidence,
            evidence=r7_evidence,
            recommended_action="Accept timing variance; adjust settlement schedule",
            resolution_status=ResolutionStatus.REVIEW_REQUIRED.value,  # 80-94%
            source_record_id=record_a.transaction_id,
            matched_record_id=record_b.transaction_id if record_b else None,
            rule_number=7,
        )

    # -------------------------------------------------------------------------
    # Rule 8: transaction_type == refund, exists in Razorpay, missing in ledger
    # -------------------------------------------------------------------------
    rule_8_match, r8_evidence = _check_rule_8_refund_mismatch(record_a, all_sources)
    if rule_8_match:
        confidence = 0.90
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.REFUND_MISMATCH.value,
            root_cause="Ledger refund synchronization gap",
            financial_impact=record_a.amount or Decimal("0.00"),
            confidence=confidence,
            evidence=r8_evidence,
            recommended_action="Post refund entry to merchant ledger",
            resolution_status=ResolutionStatus.REVIEW_REQUIRED.value,
            source_record_id=record_a.transaction_id,
            matched_record_id=record_b.transaction_id if record_b else None,
            rule_number=8,
        )

    # -------------------------------------------------------------------------
    # Rule 9: One source has 1 record, another has 2-3 whose amounts sum to it (± ₹1)
    # -------------------------------------------------------------------------
    rule_9_match, r9_evidence, r9_matched_id = _check_rule_9_partial_settlement(
        record_a, record_b, all_sources, split_records
    )
    if rule_9_match:
        confidence = 0.96
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
            root_cause="Split/partial settlement",
            financial_impact=Decimal("0.00"),  # Exact sum matches: timing/grouping, not money lost
            confidence=confidence,
            evidence=r9_evidence,
            recommended_action="Group split settlements against parent transaction",
            resolution_status=ResolutionStatus.AUTO_RESOLVE.value,  # Rule 9 + 96% >= 95%
            source_record_id=record_a.transaction_id,
            matched_record_id=r9_matched_id or (record_b.transaction_id if record_b else None),
            rule_number=9,
        )

    # -------------------------------------------------------------------------
    # Rule 10: Fuzzy reference match only (Level 4), no exact ID
    # -------------------------------------------------------------------------
    rule_10_match, r10_evidence = _check_rule_10_wrong_reference(record_a, record_b, match_level)
    if rule_10_match:
        confidence = 0.85
        impact = abs((record_a.amount or Decimal(0)) - (record_b.amount if record_b and record_b.amount else Decimal(0)))
        return ClassifiedException(
            id=eid,
            exception_type=ExceptionType.WRONG_REFERENCE.value,
            root_cause="Reference ID mismatch (likely transcription error)",
            financial_impact=impact,
            confidence=confidence,
            evidence=r10_evidence,
            recommended_action="Update bank reference with verified settlement UTR",
            resolution_status=ResolutionStatus.REVIEW_REQUIRED.value,  # 80-94%
            source_record_id=record_a.transaction_id,
            matched_record_id=record_b.transaction_id if record_b else None,
            rule_number=10,
        )

    # -------------------------------------------------------------------------
    # Rule 11: Nothing above applies → UNKNOWN
    # -------------------------------------------------------------------------
    return ClassifiedException(
        id=eid,
        exception_type=ExceptionType.UNKNOWN.value,
        root_cause=None,  # Root cause is null per spec
        financial_impact=record_a.amount or Decimal("0.00"),
        confidence=0.20,
        evidence=[
            {
                "field": "classification",
                "value": "UNKNOWN",
                "description": "No deterministic rule matched this record; preserved as unexplained exception",
            }
        ],
        recommended_action="Manual investigation required",
        resolution_status=ResolutionStatus.UNRESOLVED.value,  # UNKNOWN is ALWAYS UNRESOLVED
        source_record_id=record_a.transaction_id,
        matched_record_id=record_b.transaction_id if record_b else None,
        rule_number=11,
    )


# =============================================================================
# Helper Rule Checkers
# =============================================================================

def _check_rule_1_duplicate(
    record: Record,
    all_sources: dict[str, list[Record]] | None,
    duplicate_records: list[Record] | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Rule 1: Same reference in 2+ rows within one source."""
    if duplicate_records and len(duplicate_records) > 1:
        evidence = [
            {
                "field": "duplicate_count",
                "value": len(duplicate_records),
                "description": f"Found {len(duplicate_records)} records sharing reference within source {record.source_name}",
            },
            {
                "field": "transaction_ids",
                "value": [r.transaction_id for r in duplicate_records],
                "description": "Duplicate transaction IDs identified",
            },
        ]
        return True, evidence

    if all_sources and record.source_name in all_sources:
        source_list = all_sources[record.source_name]
        refs = {record.payment_id, record.settlement_utr, record.bank_reference} - {None, ""}
        if refs:
            matching_dups = [
                r for r in source_list
                if (r.payment_id in refs or r.settlement_utr in refs or r.bank_reference in refs)
            ]
            if len(matching_dups) >= 2:
                evidence = [
                    {
                        "field": "duplicate_count",
                        "value": len(matching_dups),
                        "description": f"Found {len(matching_dups)} records sharing reference '{next(iter(refs))}' in {record.source_name}",
                    },
                    {
                        "field": "duplicate_ids",
                        "value": [r.transaction_id for r in matching_dups],
                        "description": "Records with identical reference key",
                    }
                ]
                return True, evidence

    return False, []


def _check_rule_2_fee_mismatch(
    record_a: Record,
    record_b: Record | None,
    all_sources: dict[str, list[Record]] | None,
) -> tuple[bool, list[dict[str, Any]], Decimal]:
    """Rule 2: Reference matched, amounts differ, |diff - (fee + tax)| < ₹1.
    
    A fee mismatch occurs when one source (e.g. ledger) retains the gross amount
    while another (bank) has fees deducted, or when net amount received differs
    from expected due to fee/tax deduction.
    """
    # 1. If record_a is ledger and record_b is bank:
    # Ledger shows gross, bank shows net: this is the textbook FEE_MISMATCH from DATA_MODEL.md.
    if record_b is not None and record_a.amount is not None and record_b.amount is not None:
        # Check if record_a is ledger or if amounts differ and net_amount doesn't explain it
        if record_a.source_name == "ledger" or record_b.source_name == "ledger":
            diff = abs(record_a.amount - record_b.amount)
            fee = record_a.fee or (record_b.fee if record_b else None) or Decimal("0.00")
            tax = record_a.tax or (record_b.tax if record_b else None) or Decimal("0.00")
            fee_tax = fee + tax
            if fee_tax > Decimal("0.00") and abs(diff - fee_tax) < Decimal("1.00"):
                evidence = [
                    {
                        "field": "amount_comparison",
                        "value": f"ledger: ₹{record_a.amount}, bank: ₹{record_b.amount}",
                        "description": f"Ledger retained gross amount ₹{record_a.amount}; bank received net ₹{record_b.amount}",
                    },
                    {
                        "field": "fee_tax_deduction",
                        "value": f"fee: ₹{fee}, tax: ₹{tax}, total: ₹{fee_tax}",
                        "description": f"Difference matches fee+tax deduction within ₹{abs(diff - fee_tax)}",
                    },
                ]
                return True, evidence, diff

        # If comparing Razorpay and Bank:
        # If Razorpay net_amount matches bank amount, they agree on net settlement!
        # It is only a fee mismatch if ledger still shows gross, or if net doesn't match bank.
        if record_a.source_name == "razorpay" and record_b.source_name == "bank":
            if record_a.net_amount is not None and record_a.net_amount == record_b.amount:
                # Razorpay and Bank agree! Check if merchant ledger for this txn shows gross
                if all_sources:
                    ledger_list = all_sources.get("ledger", [])
                    ref = record_a.payment_id or record_a.settlement_utr
                    ledger_rec = next((led for led in ledger_list if led.payment_id == ref or led.settlement_utr == ref), None)
                    if ledger_rec and ledger_rec.amount and ledger_rec.amount != record_b.amount:
                        diff = abs(ledger_rec.amount - record_b.amount)
                        fee = record_a.fee or Decimal("0.00")
                        tax = record_a.tax or Decimal("0.00")
                        fee_tax = fee + tax
                        if fee_tax > Decimal("0.00") and abs(diff - fee_tax) < Decimal("1.00"):
                            evidence = [
                                {
                                    "field": "ledger_variance",
                                    "value": f"ledger: ₹{ledger_rec.amount}, bank: ₹{record_b.amount}",
                                    "description": "Ledger recorded gross; bank shows net deposit after fee/tax deduction",
                                },
                                {
                                    "field": "fee_tax_proof",
                                    "value": f"fee: ₹{fee} + tax: ₹{tax} = ₹{fee_tax}",
                                    "description": "Gross-net difference equals gateway fee + GST tax",
                                }
                            ]
                            return True, evidence, diff
                # Otherwise, Razorpay-Bank net amounts match cleanly: not a fee mismatch
                return False, [], Decimal("0.00")

            # Razorpay net doesn't match bank amount: check if difference matches fee+tax
            diff = abs(record_a.amount - record_b.amount)
            fee = record_a.fee or Decimal("0.00")
            tax = record_a.tax or Decimal("0.00")
            fee_tax = fee + tax
            if fee_tax > Decimal("0.00") and abs(diff - fee_tax) < Decimal("1.00"):
                evidence = [
                    {
                        "field": "amount_comparison",
                        "value": f"Razorpay: ₹{record_a.amount}, Bank: ₹{record_b.amount}",
                        "description": f"Difference of ₹{diff} matches fee+tax deduction ₹{fee_tax}",
                    }
                ]
                return True, evidence, diff

    return False, [], Decimal("0.00")


def _check_rule_3_amount_mismatch(
    record_a: Record,
    record_b: Record | None,
    split_records: list[Record] | None = None,
    all_sources: dict[str, list[Record]] | None = None,
) -> tuple[bool, list[dict[str, Any]], Decimal]:
    """Rule 3: Reference matched, amounts differ, diff doesn't match fee+tax."""
    # If this is a partial/split settlement, rule 9 handles it, not rule 3
    if split_records and len(split_records) >= 2:
        return False, [], Decimal("0.00")

    if all_sources and record_a.source_name == "razorpay":
        ref = record_a.payment_id or record_a.settlement_utr
        bank_list = all_sources.get("bank", [])
        if ref and len([b for b in bank_list if b.payment_id == ref or (ref in (b.description or ""))]) >= 2:
            return False, [], Decimal("0.00")

    if record_b is not None and record_a.amount is not None and record_b.amount is not None:
        target = record_a.net_amount if (record_a.source_name == "razorpay" and record_b.source_name == "bank" and record_a.net_amount is not None) else record_a.amount
        diff = abs(target - record_b.amount)
        if diff > Decimal("0.01"):
            fee = record_a.fee or Decimal("0.00")
            tax = record_a.tax or Decimal("0.00")
            fee_tax = fee + tax
            if abs(diff - fee_tax) >= Decimal("1.00"):
                evidence = [
                    {
                        "field": "amount_difference",
                        "value": f"Record A: ₹{target}, Record B: ₹{record_b.amount}",
                        "description": f"Unexplained difference of ₹{diff} (does not match fee+tax ₹{fee_tax})",
                    }
                ]
                return True, evidence, diff
    return False, [], Decimal("0.00")


def _check_rule_4_missing_in_bank(
    record_a: Record,
    record_b: Record | None,
    all_sources: dict[str, list[Record]] | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Rule 4: Exists in Razorpay, no bank row within settlement window."""
    if record_a.source_name == "razorpay" and (record_b is None or record_b.source_name != "bank"):
        # Cross-check bank records in all_sources
        if all_sources:
            bank_list = all_sources.get("bank", [])
            ref = record_a.settlement_utr or record_a.payment_id
            has_bank = any(b.bank_reference == ref or b.settlement_utr == ref or b.payment_id == ref for b in bank_list)
            if not has_bank:
                evidence = [
                    {
                        "field": "razorpay_transaction",
                        "value": record_a.transaction_id,
                        "description": f"Transaction of ₹{record_a.amount} recorded on {record_a.transaction_date}",
                    },
                    {
                        "field": "bank_statement_lookup",
                        "value": "NOT_FOUND",
                        "description": "No corresponding bank settlement credit within window",
                    }
                ]
                return True, evidence
        else:
            if record_b is None:
                evidence = [
                    {
                        "field": "source",
                        "value": "razorpay",
                        "description": f"Razorpay transaction {record_a.transaction_id} has no matching bank deposit",
                    }
                ]
                return True, evidence
    return False, []


def _check_rule_5_missing_in_razorpay(
    record_a: Record,
    record_b: Record | None,
    all_sources: dict[str, list[Record]] | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Rule 5: Exists in bank, no Razorpay row at all (and not completely unidentifiable UNKNOWN)."""
    if record_a.source_name == "bank" and (record_b is None or record_b.source_name != "razorpay"):
        # Make sure this isn't an explicit synthetic UNKNOWN record
        ref = record_a.bank_reference or ""
        if not ref.startswith("UNKN_") and all_sources:
            rzp_list = all_sources.get("razorpay", [])
            has_rzp = any(r.settlement_utr == ref or r.payment_id == ref or r.bank_reference == ref for r in rzp_list)
            if not has_rzp:
                evidence = [
                    {
                        "field": "bank_credit",
                        "value": f"₹{record_a.amount} on {record_a.transaction_date}",
                        "description": f"Bank credit with reference '{ref}' has no matching Razorpay gateway record",
                    }
                ]
                return True, evidence
    return False, []


def _check_rule_6_missing_in_ledger(
    record_a: Record,
    record_b: Record | None,
    all_sources: dict[str, list[Record]] | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Rule 6: Exists in Razorpay + bank, missing from ledger."""
    if all_sources:
        rzp_list = all_sources.get("razorpay", [])
        bank_list = all_sources.get("bank", [])
        ledger_list = all_sources.get("ledger", [])

        ref = record_a.payment_id or record_a.settlement_utr
        if ref and record_a.transaction_type != "refund":
            in_rzp = any(r.payment_id == ref or r.settlement_utr == ref for r in rzp_list)
            in_bank = any(b.payment_id == ref or b.bank_reference == ref or b.settlement_utr == ref for b in bank_list)
            in_ledger = any(led.payment_id == ref or led.settlement_utr == ref for led in ledger_list)

            if in_rzp and in_bank and not in_ledger:
                evidence = [
                    {
                        "field": "gateway_status",
                        "value": "CONFIRMED",
                        "description": "Verified in Razorpay gateway",
                    },
                    {
                        "field": "bank_status",
                        "value": "CONFIRMED",
                        "description": "Verified in bank statement",
                    },
                    {
                        "field": "ledger_status",
                        "value": "MISSING",
                        "description": "Entry missing from merchant accounting ledger",
                    }
                ]
                return True, evidence
    return False, []


def _check_rule_7_settlement_timing(
    record_a: Record,
    record_b: Record | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Rule 7: Amount matches, dates differ but within acceptable T+N window."""
    if record_b is not None and record_a.amount is not None and record_b.amount is not None:
        # Check amount match (exact or gross vs net)
        diff = abs(record_a.amount - record_b.amount)
        amounts_match = (diff == Decimal("0.00")) or (record_a.net_amount is not None and record_a.net_amount == record_b.amount)
        if amounts_match:
            # Expected settlement date for record_a vs actual bank date
            expected_date = record_a.settlement_date or record_a.transaction_date
            actual_date = record_b.transaction_date or record_b.settlement_date
            if expected_date and actual_date:
                delay_days = (actual_date - expected_date).days
                # An abnormal timing delay is when the bank deposit is 3 or more days after expected settlement
                if delay_days >= 3 and delay_days <= 20:
                    evidence = [
                        {
                            "field": "amount_reconciled",
                            "value": f"₹{record_b.amount}",
                            "description": "Amounts match cleanly across source and bank",
                        },
                        {
                            "field": "date_variance",
                            "value": f"{delay_days} days delay",
                            "description": f"Expected settlement on {expected_date}, actually credited on {actual_date} ({delay_days} days late)",
                        }
                    ]
                    return True, evidence
    return False, []


def _check_rule_8_refund_mismatch(
    record_a: Record,
    all_sources: dict[str, list[Record]] | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Rule 8: transaction_type == refund, exists in Razorpay, missing in ledger."""
    if record_a.transaction_type == "refund" and record_a.source_name == "razorpay":
        if all_sources:
            ledger_list = all_sources.get("ledger", [])
            ref = record_a.payment_id or record_a.order_id
            in_ledger = any(led.payment_id == ref or led.order_id == ref for led in ledger_list)
            if not in_ledger:
                evidence = [
                    {
                        "field": "transaction_type",
                        "value": "refund",
                        "description": "Refund processed in Razorpay gateway",
                    },
                    {
                        "field": "ledger_refund_entry",
                        "value": "MISSING",
                        "description": "Refund credit/debit adjustment not reflected in ledger",
                    }
                ]
                return True, evidence
        else:
            return True, [
                {
                    "field": "refund_status",
                    "value": "refund",
                    "description": "Refund exists in Razorpay but missing in accounting ledger",
                }
            ]
    return False, []


def _check_rule_9_partial_settlement(
    record_a: Record,
    record_b: Record | None,
    all_sources: dict[str, list[Record]] | None,
    split_records: list[Record] | None,
) -> tuple[bool, list[dict[str, Any]], str | None]:
    """Rule 9: One source has 1 record, another has 2-3 whose amounts sum to it (± ₹1)."""
    # If explicit split records passed
    if split_records and len(split_records) >= 2:
        split_sum = sum((r.amount or Decimal("0.00") for r in split_records), Decimal("0.00"))
        target = record_a.net_amount if record_a.net_amount is not None else record_a.amount
        if target is not None and abs(split_sum - target) <= Decimal("1.00"):
            evidence = [
                {
                    "field": "parent_amount",
                    "value": f"₹{target}",
                    "description": f"Parent transaction {record_a.transaction_id}",
                },
                {
                    "field": "split_components",
                    "value": [f"₹{r.amount}" for r in split_records],
                    "description": f"{len(split_records)} split entries sum to ₹{split_sum} (diff: ₹{abs(split_sum - target)})",
                },
                {
                    "field": "financial_risk",
                    "value": "₹0.00",
                    "description": "Sum reconciles exactly; timing/grouping difference, not financial loss",
                }
            ]
            return True, evidence, split_records[0].transaction_id

    # Check all_sources for split bank records
    if all_sources and record_a.source_name == "razorpay":
        bank_list = all_sources.get("bank", [])
        ref = record_a.payment_id or record_a.settlement_utr
        if ref:
            # Find partial credits matching this reference or payment_id in description
            matching_banks = [
                b for b in bank_list
                if (b.payment_id == ref or (ref in (b.description or "")) or (b.bank_reference == ref))
            ]
            if len(matching_banks) >= 2:
                split_sum = sum((b.amount or Decimal("0.00") for b in matching_banks), Decimal("0.00"))
                target = record_a.net_amount if record_a.net_amount is not None else record_a.amount
                if target is not None and abs(split_sum - target) <= Decimal("1.00"):
                    evidence = [
                        {
                            "field": "parent_transaction",
                            "value": f"₹{target}",
                            "description": f"Razorpay settlement batch total: ₹{target}",
                        },
                        {
                            "field": "split_credits",
                            "value": [f"₹{b.amount} ({b.transaction_id})" for b in matching_banks],
                            "description": f"Received as {len(matching_banks)} partial deposits summing to ₹{split_sum}",
                        },
                        {
                            "field": "split_transaction_ids",
                            "value": [b.transaction_id for b in matching_banks],
                            "description": f"All {len(matching_banks)} bank deposit transaction IDs in this partial settlement group",
                        },
                        {
                            "field": "financial_risk",
                            "value": "₹0.00",
                            "description": "Sum reconciles within ₹1.00; grouping variance, no money lost",
                        }
                    ]
                    return True, evidence, matching_banks[0].transaction_id

    return False, [], None


def _check_rule_10_wrong_reference(
    record_a: Record,
    record_b: Record | None,
    match_level: str | None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Rule 10: Fuzzy reference match only (Level 4), no exact ID."""
    if record_b is not None:
        ref_a = record_a.settlement_utr or record_a.bank_reference or record_a.payment_id
        ref_b = record_b.bank_reference or record_b.settlement_utr or record_b.payment_id
        if ref_a and ref_b and ref_a != ref_b:
            sim = difflib.SequenceMatcher(None, ref_a, ref_b).ratio()
            if sim >= 0.80 or match_level == "LEVEL_4_FUZZY_REFERENCE":
                evidence = [
                    {
                        "field": "reference_comparison",
                        "value": f"Expected: '{ref_a}' vs Bank: '{ref_b}'",
                        "description": f"Similarity ratio: {sim:.2%}. Character transposition or typo detected",
                    }
                ]
                return True, evidence
    return False, []
