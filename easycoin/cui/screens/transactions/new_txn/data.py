from dataclasses import dataclass, field
from easycoin.models import Output, Txn


@dataclass
class TransactionData:
    """Shared transaction state across all steps."""
    selected_outputs: list[Output] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)
    witness_scripts: dict[bytes, bytes] = field(default_factory=dict)
    available_outputs: list[Output] = field(default_factory=list)
    fee: int = 0
    txn: Txn = field(default_factory=Txn)
