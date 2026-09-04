from abc import ABC, abstractmethod

from app.schemas.record import Record


class BaseSourceAdapter(ABC):
    """Abstract interface for all financial source adapters.

    All source adapters (RazorpayAdapter, BankAdapter, LedgerAdapter, SettlementAdapter)
    implement this interface, producing normalized Record objects.
    The reconciliation engine only ever sees Record — never raw source data.
    """

    @abstractmethod
    def fetch_records(self) -> list[Record]:
        """Fetch and normalize records from the source into the common Record format."""
        ...
