"""EasyCoin CUI screens package."""

from .dashboard import DashboardScreen
from .wallet.wallet_list import WalletListScreen
from .wallet.wallet_screen import WalletScreen

__all__ = [
    "DashboardScreen",
    "WalletListScreen",
    "WalletScreen",
]
