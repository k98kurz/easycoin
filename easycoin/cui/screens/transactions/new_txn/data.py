from dataclasses import dataclass, field
from easycoin.models import Coin, Output, Txn
from tapescript import Script


@dataclass
class Witness:
    lock_type: str = field(default='Unknown')
    generated: Script = field(default_factory=lambda: Script('', b''))
    custom: Script = field(default_factory=lambda: Script('', b''))
    scriptspend: bool = field(default=False)

    def full(self) -> Script:
        if self.lock_type in ("P2GR", "P2GT", "P2PK", "P2PKH"):
            return self.generated
        return self.custom + self.generated


@dataclass
class TransactionData:
    """Shared transaction state across all steps."""
    available_inputs: list[Output] = field(default_factory=list)
    selected_inputs: list[Output] = field(default_factory=list)
    new_output_coins: list[Coin] = field(default_factory=list)
    witnesses: dict[str, Witness] = field(default_factory=dict)
    fee: int = 0
    txn: Txn = field(default_factory=Txn)
