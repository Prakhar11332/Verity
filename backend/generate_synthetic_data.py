#!/usr/bin/env python3
"""generate_synthetic_data.py — Deterministic synthetic dataset generator.

Produces ~150 base transactions and derives 4 source files (Razorpay, Bank,
Ledger, Settlement) with intentional divergence per DATA_MODEL.md's exception
distribution. Also outputs ground_truth.json for regression testing.

Usage:
    cd backend && python generate_synthetic_data.py

Seed: 42 (deterministic — re-running produces identical output).
"""

import copy
import json
import os
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

SEED = 42
NUM_BASE = 150
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ---- Exception distribution (DATA_MODEL.md) ----
# 65% clean = 98, 25% resolvable = 37, 10% unresolved = 15
EXCEPTION_PLAN = [
    # (type, count)
    ("FEE_MISMATCH", 9),
    ("SETTLEMENT_TIMING", 7),
    ("DUPLICATE_TRANSACTION", 3),
    ("MISSING_IN_BANK", 4),
    ("MISSING_IN_LEDGER", 3),
    ("REFUND_MISMATCH", 3),
    ("WRONG_REFERENCE", 3),
    ("PARTIAL_SETTLEMENT", 2),
    ("UNKNOWN", 15),
]
# Sum of exception records: 9+7+3+4+3+3+3+2+15 = 49; clean = 150 - 49 = 101 (~67%)
# Close enough to 65/25/10 split, biased toward more exceptions for clustering

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet", "emi"]
MERCHANT_IDS = ["MERCH_001", "MERCH_002", "MERCH_003", "MERCH_004", "MERCH_005"]
BASE_DATE = date(2024, 6, 1)
DATE_RANGE_DAYS = 60  # Transactions spread over 2 months


def _decimal(val: float) -> Decimal:
    """Round to 2 decimal places."""
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _random_amount(rng: random.Random) -> Decimal:
    """Generate a realistic transaction amount between ₹100 and ₹50,000."""
    return _decimal(rng.uniform(100, 50000))


def _random_date(rng: random.Random) -> date:
    """Random date within the generation window."""
    return BASE_DATE + timedelta(days=rng.randint(0, DATE_RANGE_DAYS))


def _generate_utr(rng: random.Random) -> str:
    """Generate a realistic UTR-like reference string."""
    return f"UTR{rng.randint(100000000000, 999999999999)}"


def _transpose_digit(s: str, rng: random.Random) -> str:
    """Transpose two adjacent digits in a string to simulate a typo."""
    digits_positions = [i for i, c in enumerate(s) if c.isdigit()]
    if len(digits_positions) < 2:
        return s
    # Pick a random pair of adjacent digit positions
    idx = rng.randint(0, len(digits_positions) - 2)
    p1, p2 = digits_positions[idx], digits_positions[idx + 1]
    chars = list(s)
    chars[p1], chars[p2] = chars[p2], chars[p1]
    # Ensure it's actually different
    if "".join(chars) == s and len(digits_positions) >= 3:
        p1, p2 = digits_positions[idx + 1], digits_positions[idx + 2]
        chars = list(s)
        chars[p1], chars[p2] = chars[p2], chars[p1]
    return "".join(chars)


def _make_base_record(idx: int, rng: random.Random, txn_type: str = "payment") -> dict:
    """Create a single base Razorpay transaction record."""
    payment_id = f"pay_{idx:05d}"
    order_id = f"order_{idx:05d}"
    settlement_id = f"setl_{(idx // 10):04d}"
    utr = _generate_utr(rng)
    txn_date = _random_date(rng)
    amount = _random_amount(rng)
    fee_rate = Decimal(str(rng.choice([0.02, 0.018, 0.025, 0.03])))
    fee = (amount * fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # 18% GST
    net = amount - fee - tax
    settlement_date = txn_date + timedelta(days=rng.choice([1, 2, 3]))  # T+1 to T+3

    return {
        "transaction_id": f"rzp_txn_{idx:05d}",
        "payment_id": payment_id,
        "order_id": order_id,
        "settlement_id": settlement_id,
        "settlement_utr": utr,
        "transaction_type": txn_type,
        "transaction_date": txn_date.isoformat(),
        "settlement_date": settlement_date.isoformat(),
        "amount": str(amount),
        "fee": str(fee),
        "tax": str(tax),
        "net_amount": str(net),
        "currency": "INR",
        "payment_method": rng.choice(PAYMENT_METHODS),
        "merchant_id": rng.choice(MERCHANT_IDS),
        "bank_reference": utr,  # bank_reference matches settlement_utr for clean matches
        "status": "success",
        "description": f"Payment for order {order_id}",
        "source_name": "razorpay",
    }


def _derive_bank(base: dict) -> dict:
    """Derive a bank statement record from a base Razorpay transaction."""
    net = Decimal(base["net_amount"])
    return {
        "transaction_id": f"bank_txn_{base['payment_id']}",
        "payment_id": base["payment_id"],
        "order_id": None,
        "settlement_id": base["settlement_id"],
        "settlement_utr": base["settlement_utr"],
        "transaction_type": base["transaction_type"],
        "transaction_date": base["settlement_date"],  # bank sees it on settlement date
        "settlement_date": base["settlement_date"],
        "amount": str(net),  # bank receives net amount
        "fee": None,
        "tax": None,
        "net_amount": str(net),
        "currency": "INR",
        "payment_method": base["payment_method"],
        "merchant_id": base["merchant_id"],
        "bank_reference": base["settlement_utr"],
        "status": "success",
        "description": f"Credit {base['settlement_utr']}",
        "source_name": "bank",
    }


def _derive_ledger(base: dict) -> dict:
    """Derive a merchant ledger entry from a base Razorpay transaction."""
    return {
        "transaction_id": f"ledger_txn_{base['payment_id']}",
        "payment_id": base["payment_id"],
        "order_id": base["order_id"],
        "settlement_id": base["settlement_id"],
        "settlement_utr": base["settlement_utr"],
        "transaction_type": base["transaction_type"],
        "transaction_date": base["transaction_date"],
        "settlement_date": base["settlement_date"],
        "amount": base["net_amount"],  # ledger records net amount received
        "fee": base["fee"],
        "tax": base["tax"],
        "net_amount": base["net_amount"],
        "currency": "INR",
        "payment_method": base["payment_method"],
        "merchant_id": base["merchant_id"],
        "bank_reference": base["settlement_utr"],
        "status": "success",
        "description": f"Revenue {base['order_id']}",
        "source_name": "ledger",
    }


def _derive_settlement(base: dict) -> dict:
    """Derive a settlement report entry from a base Razorpay transaction."""
    return {
        "transaction_id": f"setl_txn_{base['payment_id']}",
        "payment_id": base["payment_id"],
        "order_id": base["order_id"],
        "settlement_id": base["settlement_id"],
        "settlement_utr": base["settlement_utr"],
        "transaction_type": base["transaction_type"],
        "transaction_date": base["transaction_date"],
        "settlement_date": base["settlement_date"],
        "amount": base["amount"],  # settlement shows gross
        "fee": base["fee"],
        "tax": base["tax"],
        "net_amount": base["net_amount"],
        "currency": "INR",
        "payment_method": base["payment_method"],
        "merchant_id": base["merchant_id"],
        "bank_reference": base["settlement_utr"],
        "status": "success",
        "description": f"Settlement batch {base['settlement_id']}",
        "source_name": "settlement",
    }


def generate():
    rng = random.Random(SEED)

    # Build the assignment list: which indices get which exception type
    exception_indices: dict[int, str] = {}
    available_indices = list(range(NUM_BASE))
    rng.shuffle(available_indices)

    offset = 0
    for exc_type, count in EXCEPTION_PLAN:
        for _ in range(count):
            exception_indices[available_indices[offset]] = exc_type
            offset += 1

    # Generate base records
    base_records: list[dict] = []
    for idx in range(NUM_BASE):
        exc_type = exception_indices.get(idx)
        if exc_type == "REFUND_MISMATCH":
            base = _make_base_record(idx, rng, txn_type="refund")
        else:
            base = _make_base_record(idx, rng)
        base_records.append(base)

    # Derive source records with intentional exceptions
    razorpay_records: list[dict] = []
    bank_records: list[dict] = []
    ledger_records: list[dict] = []
    settlement_records: list[dict] = []
    ground_truth: dict[str, dict] = {}

    for idx, base in enumerate(base_records):
        exc_type = exception_indices.get(idx, "CLEAN_MATCH")
        payment_id = base["payment_id"]

        razorpay_rec = copy.deepcopy(base)
        bank_rec = _derive_bank(base)
        ledger_rec = _derive_ledger(base)
        settlement_rec = _derive_settlement(base)

        if exc_type == "CLEAN_MATCH":
            # All four sources agree
            razorpay_records.append(razorpay_rec)
            bank_records.append(bank_rec)
            ledger_records.append(ledger_rec)
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "CLEAN_MATCH",
                "description": "All sources match cleanly",
            }

        elif exc_type == "FEE_MISMATCH":
            # Bank amount = net (gross - fee - tax), but ledger still shows GROSS amount.
            # So ledger.amount != bank.amount.
            ledger_rec["amount"] = base["amount"]  # ledger keeps gross
            ledger_rec["net_amount"] = base["amount"]  # and net_amount shows gross too
            razorpay_records.append(razorpay_rec)
            bank_records.append(bank_rec)
            ledger_records.append(ledger_rec)
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "FEE_MISMATCH",
                "description": f"Ledger shows gross {base['amount']}, bank shows net {base['net_amount']}",
            }

        elif exc_type == "SETTLEMENT_TIMING":
            # Settlement date shifted 2-5 days beyond normal T+N window
            extra_days = rng.randint(4, 8)
            orig_settlement = date.fromisoformat(base["settlement_date"])
            delayed_settlement = orig_settlement + timedelta(days=extra_days)
            bank_rec["transaction_date"] = delayed_settlement.isoformat()
            bank_rec["settlement_date"] = delayed_settlement.isoformat()
            razorpay_records.append(razorpay_rec)
            bank_records.append(bank_rec)
            ledger_records.append(ledger_rec)
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "SETTLEMENT_TIMING",
                "description": f"Settlement delayed by {extra_days} extra days",
            }

        elif exc_type == "DUPLICATE_TRANSACTION":
            # Same payment_id appears twice in razorpay (duplicate)
            dup = copy.deepcopy(razorpay_rec)
            dup["transaction_id"] = f"rzp_txn_{idx:05d}_dup"
            razorpay_records.append(razorpay_rec)
            razorpay_records.append(dup)
            bank_records.append(bank_rec)
            ledger_records.append(ledger_rec)
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "DUPLICATE_TRANSACTION",
                "description": "Duplicate record in razorpay source",
            }

        elif exc_type == "MISSING_IN_BANK":
            # Exists in Razorpay, no bank row
            razorpay_records.append(razorpay_rec)
            # bank_rec is NOT appended
            ledger_records.append(ledger_rec)
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "MISSING_IN_BANK",
                "description": "No bank statement entry for this transaction",
            }

        elif exc_type == "MISSING_IN_LEDGER":
            # Exists in Razorpay + bank, missing from ledger
            razorpay_records.append(razorpay_rec)
            bank_records.append(bank_rec)
            # ledger_rec is NOT appended
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "MISSING_IN_LEDGER",
                "description": "No ledger entry for this transaction",
            }

        elif exc_type == "REFUND_MISMATCH":
            # Refund in Razorpay, not reflected in ledger
            razorpay_records.append(razorpay_rec)
            bank_records.append(bank_rec)
            # ledger_rec omitted — refund not reflected
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "REFUND_MISMATCH",
                "description": "Refund exists in Razorpay but not in ledger",
            }

        elif exc_type == "WRONG_REFERENCE":
            # bank_reference has a transposed digit vs settlement_utr
            original_utr = base["settlement_utr"]
            typo_utr = _transpose_digit(original_utr, rng)
            # Bank statement has typo'd reference and lacks internal gateway payment_id
            bank_rec["bank_reference"] = typo_utr
            bank_rec["settlement_utr"] = typo_utr
            bank_rec["payment_id"] = None
            bank_rec["order_id"] = None
            bank_rec["description"] = f"Credit {typo_utr}"
            razorpay_records.append(razorpay_rec)
            bank_records.append(bank_rec)
            ledger_records.append(ledger_rec)
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "WRONG_REFERENCE",
                "description": f"Bank reference {typo_utr} vs UTR {original_utr}",
            }

        elif exc_type == "PARTIAL_SETTLEMENT":
            # One Razorpay record maps to 2-3 bank records whose amounts sum
            net = Decimal(base["net_amount"])
            num_parts = rng.choice([2, 3])
            parts: list[Decimal] = []
            remaining = net
            for _ in range(num_parts - 1):
                part = (remaining * Decimal(str(rng.uniform(0.2, 0.6)))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                parts.append(part)
                remaining -= part
            parts.append(remaining)

            razorpay_records.append(razorpay_rec)
            # Create split bank records instead of single
            for pi, part_amount in enumerate(parts):
                part_bank = copy.deepcopy(bank_rec)
                part_bank["transaction_id"] = f"bank_txn_{payment_id}_part{pi}"
                part_bank["amount"] = str(part_amount)
                part_bank["net_amount"] = str(part_amount)
                part_bank["description"] = f"Partial credit {pi+1}/{num_parts} {base['settlement_utr']}"
                bank_records.append(part_bank)

            ledger_records.append(ledger_rec)
            settlement_records.append(settlement_rec)
            ground_truth[payment_id] = {
                "exception_type": "PARTIAL_SETTLEMENT",
                "description": f"Split into {num_parts} bank entries summing to {net}",
            }

        elif exc_type == "UNKNOWN":
            # Bank-only transaction with no Razorpay match at all
            # Do NOT add a Razorpay record — create only a bank record with a unique reference
            unknown_bank = {
                "transaction_id": f"bank_unknown_{idx:05d}",
                "payment_id": None,
                "order_id": None,
                "settlement_id": None,
                "settlement_utr": None,
                "transaction_type": rng.choice(["payment", "transfer", "adjustment"]),
                "transaction_date": _random_date(rng).isoformat(),
                "settlement_date": None,
                "amount": str(_random_amount(rng)),
                "fee": None,
                "tax": None,
                "net_amount": str(_random_amount(rng)),
                "currency": "INR",
                "payment_method": rng.choice(PAYMENT_METHODS),
                "merchant_id": rng.choice(MERCHANT_IDS),
                "bank_reference": f"UNKN_{rng.randint(10000000, 99999999)}",
                "status": "success",
                "description": f"Unknown bank debit/credit ref {idx}",
                "source_name": "bank",
            }
            bank_records.append(unknown_bank)
            # DO NOT add razorpay/ledger/settlement — genuinely orphaned bank record
            ground_truth[payment_id] = {
                "exception_type": "UNKNOWN",
                "description": "Bank-only transaction with no plausible match",
            }

    # Write output files
    os.makedirs(DATA_DIR, exist_ok=True)

    def _write_json(filename: str, data: list[dict]):
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  Written {len(data)} records to {filepath}")

    _write_json("razorpay_transactions.json", razorpay_records)
    _write_json("bank_statements.json", bank_records)
    _write_json("ledger_entries.json", ledger_records)
    _write_json("settlement_reports.json", settlement_records)

    gt_path = os.path.join(DATA_DIR, "ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"  Written ground truth for {len(ground_truth)} transactions to {gt_path}")

    # Summary
    from collections import Counter
    exc_counts = Counter(v["exception_type"] for v in ground_truth.values())
    print("\nDataset Summary:")
    print(f"  Total base transactions: {NUM_BASE}")
    print(f"  Razorpay records: {len(razorpay_records)}")
    print(f"  Bank records: {len(bank_records)}")
    print(f"  Ledger records: {len(ledger_records)}")
    print(f"  Settlement records: {len(settlement_records)}")
    print("\n  Exception distribution:")
    for exc_type, count in sorted(exc_counts.items()):
        print(f"    {exc_type}: {count}")


if __name__ == "__main__":
    print("Generating synthetic data (seed=42)...")
    generate()
    print("\nDone.")
