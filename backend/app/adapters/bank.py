"""BankAdapter — Bank statement records."""


from app.adapters.base import BaseSourceAdapter
from app.adapters.synthetic import SyntheticDataAdapter
from app.schemas.record import Record


class BankAdapter(BaseSourceAdapter):
    """Fetches normalized records from the bank statement source."""

    def __init__(self, data_dir: str | None = None):
        kwargs = {"data_dir": data_dir} if data_dir else {}
        self._backend = SyntheticDataAdapter(**kwargs)

    def fetch_records(self) -> list[Record]:
        return self._backend.fetch_records("bank")
