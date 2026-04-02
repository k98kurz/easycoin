from .english import wordlist
from .misc import microbench, calc_microbench_offset
from .models import (
    Coin, Txn, Input, Output, Address, Wallet,
    TrustNet, TrustNetFeature, Attestation, Confirmation, Snapshot,
    set_connection_info, get_migrations, publish_migrations, automigrate,
)
from .UTXOSet import UTXOSet


__version__ = '0.0.1'

def version() -> str:
    """Returns the version of the bookchain package."""
    return __version__


