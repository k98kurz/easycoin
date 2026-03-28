from dataclasses import dataclass, field
from easycoin.models import Coin, Output, Txn
from tapescript import Script


@dataclass
class TransactionData:
    """Shared transaction state across all steps."""
    available_inputs: list[Output] = field(default_factory=list)
    selected_inputs: list[Output] = field(default_factory=list)
    new_output_coins: list[Coin] = field(default_factory=list)
    witness_scripts: dict[str, Script] = field(default_factory=dict)
    fee: int = 0
    txn: Txn = field(default_factory=Txn)
