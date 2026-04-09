from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static
from easycoin.config import ConfigManager
from easycoin.cui.state import StateManager
from easycoin.cui.screens.dashboard import DashboardScreen
from easycoin.cui.screens.wallet.main_screen import WalletListScreen
from easycoin.cui.screens.coins.coins_screen import CoinsScreen
from easycoin.cui.screens.transactions.txn_screen import TransactionsScreen
from easycoin.cui.screens.stamps.stamp_templates_screen import StampTemplatesScreen
from easycoin.cui.screens.network.placeholder import NetworkScreen
from easycoin.cui.screens.trustnet.placeholder import TrustNetScreen
from easycoin.cui.screens.repl.repl_modal import ReplModal
from easycoin.cui.screens.event_log_modal import EventLogModal
from easycoin.cui.screens.welcome import WelcomeScreen
from easycoin.cui.screens.settings.settings_screen import SettingsScreen
import logging


class EasyCoinApp(App):
    """Main EasyCoin CUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "EasyCoin"
    SUB_TITLE = "Cryptographic Asset Manager"

    SCREENS = {
        "dashboard": DashboardScreen,
        "wallet": WalletListScreen,
        "coins": CoinsScreen,
        "transactions": TransactionsScreen,
        "stamp_templates": StampTemplatesScreen,
        "network": NetworkScreen,
        "trustnet": TrustNetScreen,
        "settings": SettingsScreen,
        "repl": ReplModal,
        "event_log": EventLogModal,
        "welcome": WelcomeScreen,
    }

    BINDINGS = [
        ("0", "open_repl", "REPL"),
        ("1", "switch_to_dashboard", "Dashboard"),
        ("2", "switch_to_wallet", "Identity/Wallet"),
        ("3", "switch_to_coins", "Coins"),
        ("4", "switch_to_transactions", "Transactions"),
        ("5", "switch_to_stamp_templates", "Stamp Templates"),
        ("9", "switch_to_settings", "Settings"),
        ("ctrl+e", "open_event_log", "Event Log"),
        ("ctrl+q", "quit", "Quit"),
        ("?", "open_welcome", "Welcome"),
    ]

    network_connected = reactive(False)
    active_trustnet_id = reactive(None)
    active_trustnet_state = reactive(None)
    sidebar_visible = reactive(False)
    wallet = reactive(None)

    def __init__(self):
        """Initialize the application."""
        super().__init__()
        self.config = ConfigManager("easycoin")
        self.state = StateManager(self)
        self.logger = logging.getLogger("easycoin")
        self._setup_file_logging()

    def _setup_file_logging(self) -> None:
        """Setup file-based logging for all log levels."""
        log_file = self.config.get_log_path()
        self.logger.setLevel(logging.DEBUG)

        if self.logger.handlers:
            self.logger.handlers.clear()

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        yield Static(id="screen_placeholder", classes="screen-placeholder")

    def on_mount(self) -> None:
        """Initialize application on mount."""
        try:
            self.config.load()

            self.active_trustnet_id = self.config.get("active_trustnet_id")
            self.sidebar_visible = self.config.get("sidebar_visible")

            self.log_event("EasyCoin CUI started", "INFO")

            if not self.config.get("welcome_shown"):
                self.call_later(self.action_open_welcome)

            self.push_screen("dashboard")

        except Exception as e:
            self.logger.error(f"Failed to initialize app: {e}")
            self.notify(f"Initialization error: {e}", severity="error")

    def watch_active_trustnet_id(
            self, old_value: str | None, new_value: str | None
        ) -> None:
        """Watch `active_trustnet_id` for changes."""
        pass

    def watch_sidebar_visible(self, old_value: bool, new_value: bool) -> None:
        """Watch `sidebar_visible` for changes and persist to config."""
        self.config.set("sidebar_visible", new_value)
        self.config.save()

    def action_switch_to_dashboard(self) -> None:
        """Switch to dashboard screen."""
        self.switch_screen("dashboard")

    def action_switch_to_wallet(self) -> None:
        """Switch to wallet screen."""
        self.switch_screen("wallet")

    def action_switch_to_coins(self) -> None:
        """Switch to coins screen."""
        self.switch_screen("coins")

    def action_switch_to_transactions(self) -> None:
        """Switch to transactions screen."""
        self.switch_screen("transactions")

    def action_switch_to_stamp_templates(self) -> None:
        """Switch to stamp templates screen."""
        self.switch_screen("stamp_templates")

    def action_switch_to_settings(self) -> None:
        """Switch to settings screen."""
        self.switch_screen("settings")

    def action_open_repl(self) -> None:
        """Open REPL modal for Python code execution."""
        self.push_screen("repl")

    def action_open_event_log(self) -> None:
        """Open event log modal for viewing and managing logs."""
        self.push_screen("event_log")

    def action_open_welcome(self) -> None:
        """Open welcome screen."""
        self.config.set("welcome_shown", True)
        self.config.save()
        self.push_screen("welcome")

    def log_event(self, message: str, level: str = "INFO") -> None:
        """Append log entry to state. Args:
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        self.logger.log(log_levels[level], message)
        self.state.add_log_entry(message, level)
