from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static
from easycoin.cui.config import ConfigManager
from easycoin.cui.state import StateManager
from typing import Callable
from easycoin.cui.screens.dashboard import DashboardScreen
from easycoin.cui.screens.wallet.placeholder import WalletScreen
from easycoin.cui.screens.coins.placeholder import CoinsScreen
from easycoin.cui.screens.transactions.placeholder import TransactionsScreen
from easycoin.cui.screens.network.placeholder import NetworkScreen
from easycoin.cui.screens.trustnet.placeholder import TrustNetScreen
import logging


class EasyCoinApp(App):
    """Main EasyCoin CUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "EasyCoin"
    SUB_TITLE = "Cryptographic Asset Manager"

    SCREENS = {
        "dashboard": DashboardScreen,
        "wallet": WalletScreen,
        "coins": CoinsScreen,
        "transactions": TransactionsScreen,
        "network": NetworkScreen,
        "trustnet": TrustNetScreen,
    }

    BINDINGS = [
        ("ctrl+1", "switch_to_dashboard", "Dashboard"),
        ("ctrl+2", "switch_to_wallet", "Identity/Wallet"),
        ("ctrl+3", "switch_to_coins", "Coins"),
        ("ctrl+4", "switch_to_transactions", "Transactions"),
        ("f5", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    current_wallet_id = reactive(None)
    wallet_locked = reactive(True)
    network_connected = reactive(False)
    active_trustnet_id = reactive(None)
    active_trustnet_state = reactive(None)

    def __init__(self):
        """Initialize the application."""
        super().__init__()
        self.logger = logging.getLogger("easycoin")
        self.config = ConfigManager("easycoin")
        self.state = StateManager(self)
        self._lock_change_callbacks = []

    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Static(id="screen_placeholder", classes="screen-placeholder")

    def on_mount(self) -> None:
        """Initialize application on mount."""
        self.config.load()
        self.current_wallet_id = self.config.get_current_wallet_id()
        self.active_trustnet_id = self.config.get_active_trustnet_id()

        self.notify("EasyCoin CUI started")
        self.push_screen("dashboard")

    def watch_current_wallet_id(self, old_value: str | None, new_value: str | None) -> None:
        """Watch current_wallet_id for changes."""
        pass

    def watch_active_trustnet_id(self, old_value: str | None, new_value: str | None) -> None:
        """Watch active_trustnet_id for changes."""
        pass

    def watch_wallet_locked(self, old_value: bool, new_value: bool) -> None:
        """Call all registered callbacks when wallet lock state changes."""
        self.notify(f"Wallet {'unlocked' if not new_value else 'locked'}")
        for callback in self._lock_change_callbacks:
            try:
                callback(new_value)
            except Exception as e:
                self.logger.warning(f"Lock change callback failed: {e}")

    def register_lock_change_callback(self, callback: Callable[[bool], None]) -> None:
        """Register callback to be called when wallet lock state changes."""
        self._lock_change_callbacks.append(callback)

    def unregister_lock_change_callback(self, callback: Callable[[bool], None]) -> None:
        """Unregister a previously registered lock change callback."""
        try:
            self._lock_change_callbacks.remove(callback)
        except ValueError:
            pass

    def ensure_wallet_unlocked(self) -> bool:
        """Check if wallet is unlocked; show unlock modal if not.
        Returns:
            True if wallet is unlocked, False otherwise.
        """
        if not self.wallet_locked:
            return True

        self.notify("Wallet is locked - unlock required", severity="warning")
        return False

    def action_switch_to_dashboard(self) -> None:
        """Switch to dashboard screen."""
        self.push_screen("dashboard")

    def action_switch_to_wallet(self) -> None:
        """Switch to wallet screen."""
        self.push_screen("wallet")

    def action_switch_to_coins(self) -> None:
        """Switch to coins screen."""
        self.push_screen("coins")

    def action_switch_to_transactions(self) -> None:
        """Switch to transactions screen."""
        self.push_screen("transactions")

    def action_refresh(self) -> None:
        """Refresh current screen."""
        self.notify("Refreshing screen", severity="information")

    def action_command_palette(self) -> None:
        """Show command palette (placeholder for now)."""
        self.notify("Command palette not yet implemented", severity="information")
