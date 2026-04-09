from .english import wordlist
from .gameset import create_gameset, calculate_gameset_hash, apply_gameset
from .misc import microbench, calc_microbench_offset
from .models import (
    Coin, Txn, Input, Output, Address, Wallet, StampTemplate, StampType,
    TrustNet, TrustNetFeature, Attestation, Confirmation, Snapshot,
    set_connection_info, get_migrations, publish_migrations, automigrate,
)
from .UTXOSet import UTXOSet


__version__ = '0.0.1'

def version() -> str:
    """Returns the version of the bookchain package."""
    return __version__


