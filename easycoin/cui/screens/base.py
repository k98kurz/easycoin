from textual.screen import Screen
from textual.css.query import NoMatches
from easycoin.cui.widgets.event_log import EventLog, LogLevel
from easycoin.models.Coin import Coin


class BaseScreen(Screen):
    """Base screen with common functionality for all EasyCoin CUI screens."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+r", "app.toggle_right_sidebar", "Toggle Sidebar"),
    ]

    # Subclasses should override this to specify their tab ID
    TAB_ID: str | None = None

    def __init__(self, **kwargs):
        """Initialize BaseScreen."""
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        """Subscribe to state manager when screen is mounted."""
        if hasattr(self.app, 'state'):
            self.app.state.subscribe(self)
        self._update_active_tab()

    def on_unmount(self) -> None:
        """Unsubscribe from state manager when screen is unmounted."""
        if hasattr(self.app, 'state'):
            self.app.state.unsubscribe(self)

    def _update_active_tab(self) -> None:
        """Update top tabs to highlight the current screen."""
        if self.TAB_ID is None:
            return
        try:
            tabs = self.query_one("#top_tabs")
            tabs.active = self.TAB_ID
        except NoMatches:
            pass

    def on_wallet_info_changed(self, wallet_info: dict) -> None:
        """Handle wallet info updates.

        Override in subclasses that need to react to wallet changes.
        """
        pass

    def on_mining_status_changed(self, active: bool, progress: int) -> None:
        """Handle mining status updates.

        Override in subclasses that need to react to mining changes.
        """
        pass

    def on_network_status_changed(self, height: int, peers: int) -> None:
        """Handle network status updates.

        Override in subclasses that need to react to network changes.
        """
        pass

    def on_txn_validated(self, result) -> None:
        """Handle transaction validation result.

        Override in subclasses that need to react to validation results.
        """
        pass

    def on_coins_mined(self, coins: list[Coin | Exception]) -> None:
        """Handle newly mined coins or mining errors.

        Override in subclasses that need to react to new coins.
        """
        pass

    def log_event(self, message: str, level: str = "INFO") -> None:
        """Log an event to the app's event log.

        Args:
            message: Log message
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        try:
            if hasattr(self.app, 'query_one'):
                log_widget = self.app.query_one("#event_log", EventLog)
                log_widget.write_log(message, LogLevel[level], persistent=False)
        except Exception:
            pass

    def refresh_data(self) -> None:
        """Refresh screen data.

        Override in subclasses to implement screen-specific refresh logic.
        """
        self.log_event("Refreshing screen data", "INFO")
        pass

    def ensure_wallet_unlocked(self) -> bool:
        """Check if wallet is unlocked; prompt if not.

        Returns:
            True if wallet is unlocked, False otherwise.
        """
        if hasattr(self.app, 'ensure_wallet_unlocked'):
            return self.app.ensure_wallet_unlocked()
        return False
