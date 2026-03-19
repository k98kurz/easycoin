from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Static
from easycoin.cui.config import ConfigManager
from easycoin.cui.state import StateManager
from easycoin.cui.widgets.event_log import EventLog, LogLevel
import logging


class EasyCoinApp(App):
    """Main EasyCoin CUI application."""

    CSS_PATH = "cui/styles.tcss"
    TITLE = "EasyCoin"
    SUB_TITLE = "Cryptographic Asset Manager"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("ctrl+r", "toggle_right_sidebar", "Toggle Sidebar"),
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
        self.config = ConfigManager("easycoin")
        self.state = StateManager(self)
        self._sidebar_visible = True

    def compose(self) -> ComposeResult:
        """Compose the main application layout."""
        with Horizontal(id="main_layout"):
            with Vertical(id="main_content"):
                yield Static("EasyCoin CUI - Main Content", id="placeholder")

    def on_mount(self) -> None:
        """Initialize application on mount."""
        self.config.load()
        self.current_wallet_id = self.config.get_current_wallet_id()
        self.active_trustnet_id = self.config.get_active_trustnet_id()
        self.log_event("EasyCoin CUI started", "INFO", persistent=True)
        self.push_screen("dashboard")

    def action_toggle_right_sidebar(self) -> None:
        """Toggle event log sidebar visibility."""
        self._sidebar_visible = not self._sidebar_visible

        try:
            sidebar = self.query_one("#right_sidebar")
            if self._sidebar_visible:
                sidebar.remove_class("hidden")
            else:
                sidebar.add_class("hidden")
        except NoMatches:
            pass

    def ensure_wallet_unlocked(self) -> bool:
        """Check if wallet is unlocked; show unlock modal if not.
        Returns:
            True if wallet is unlocked, False otherwise.
        """
        if not self.wallet_locked:
            return True

        self.log_event("Wallet is locked - unlock required", "WARNING")
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
        self.log_event("Refreshing screen", "INFO")

    def log_event(
            self, message: str, level: str = "INFO",
            persistent: bool = False
        ) -> None:
        """Log an event to the event log. Args:
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            persistent: Whether to persist to file
            Raises:
            KeyError: If an invalid log level is provided
        """
        try:
            log_widget = self.query_one("#event_log", EventLog)
            log_widget.write_log(message, LogLevel[level], persistent)
        except KeyError:
            raise
        except NoMatches:
            pass
        except Exception as e:
            logger = logging.getLogger("easycoin")
            logger.error(f"Error logging event: {e}")


NodeApp = EasyCoinApp
