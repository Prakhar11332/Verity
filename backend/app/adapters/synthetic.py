"""SyntheticDataAdapter — reads generated JSON files and produces normalized Records.

This is the backing store for all four source adapters during the hackathon.
A real adapter (e.g. RazorpayAPIAdapter) can replace this without touching the engine.
"""

import json
import os
from datetime import date
from decimal import Decimal

from app.schemas.record import Record

# Default data directory relative to the backend root
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _parse_date(val: str | None) -> date | None:
    if val is None:
        return None
    return date.fromisoformat(val)


def _parse_decimal(val) -> Decimal | None:
    if val is None:
        return None
    return Decimal(str(val))


def _load_records_from_file(filepath: str) -> list[Record]:
    """Load a JSON array of raw record dicts and convert to Record objects."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Synthetic data file not found: {filepath}")

    with open(filepath) as f:
        raw_records = json.load(f)

    records: list[Record] = []
    for r in raw_records:
        records.append(Record(
            transaction_id=r["transaction_id"],
            source_name=r["source_name"],
            amount=_parse_decimal(r["amount"]),
            transaction_date=_parse_date(r["transaction_date"]),
            transaction_type=r["transaction_type"],
            status=r["status"],
            description=r.get("description", ""),
            merchant_id=r.get("merchant_id", ""),
            currency=r.get("currency", "INR"),
            payment_id=r.get("payment_id"),
            order_id=r.get("order_id"),
            settlement_id=r.get("settlement_id"),
            settlement_utr=r.get("settlement_utr"),
            settlement_date=_parse_date(r.get("settlement_date")),
            fee=_parse_decimal(r.get("fee")),
            tax=_parse_decimal(r.get("tax")),
            net_amount=_parse_decimal(r.get("net_amount")),
            payment_method=r.get("payment_method"),
            bank_reference=r.get("bank_reference"),
        ))
    return records


class SyntheticDataAdapter:
    """Reads pre-generated JSON files from the data/ directory."""

    def __init__(self, data_dir: str = _DATA_DIR):
        self.data_dir = data_dir

    def fetch_records(self, source_name: str) -> list[Record]:
        """Fetch records for a specific source from its JSON file."""
        file_map = {
            "razorpay": "razorpay_transactions.json",
            "bank": "bank_statements.json",
            "ledger": "ledger_entries.json",
            "settlement": "settlement_reports.json",
        }
        filename = file_map.get(source_name)
        if filename is None:
            raise ValueError(f"Unknown source: {source_name}")
        filepath = os.path.join(self.data_dir, filename)
        return _load_records_from_file(filepath)
