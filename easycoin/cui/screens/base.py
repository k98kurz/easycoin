from textual.screen import Screen
from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.containers import Horizontal
from textual.widgets import Footer
from easycoin.cui.widgets.event_log import EventLog, LogLevel
from easycoin.cui.widgets.top_tabs import TopTabs
from easycoin.models.Coin import Coin
from easycoin.cui.widgets.right_sidebar import RightSidebar
from easycoin.config import ConfigManager


class BaseScreen(Screen):
    """Base screen with common functionality for all EasyCoin CUI
        screens.
    """

    BINDINGS = [
        ("ctrl+r", "toggle_right_sidebar", "Toggle Sidebar"),
    ]

    # Subclasses should override this to specify their tab ID
    TAB_ID: str | None = None

    def __init__(self, **kwargs):
        """Initialize BaseScreen."""
        super().__init__(**kwargs)
        self.config = ConfigManager("easycoin")

    def compose(self) -> ComposeResult:
        """Compose screen with top tabs, main content and sidebar."""
        yield TopTabs(id="top_tabs")

        with Horizontal(id="screen_layout"):
            with Horizontal(id="screen_content"):
                yield from self._compose_content()

            log_file = self.config.get_log_path()
            sidebar = RightSidebar(log_file=log_file, id="right_sidebar")
            if not self.app.sidebar_visible:
                sidebar.add_class("hidden")
            yield sidebar

        yield Footer()

    def _compose_content(self) -> ComposeResult:
        """Override this method in subclasses to provide screen-specific
            content. This is similar to `compose()` but for the main
            content area only.
        """
        if False:
            yield

    def on_mount(self) -> None:
        """Subscribe to state manager when screen is mounted."""
        if hasattr(self.app, 'state'):
            self.app.state.subscribe(self)

    def on_screen_resume(self, event) -> None:
        """Handle screen resume event to update active tab and
            sidebar.
        """
        self._update_active_tab()
        self._update_sidebar_visibility()
        event.stop()

    def on_unmount(self) -> None:
        """Unsubscribe from state manager when screen is unmounted."""
        if hasattr(self.app, 'state'):
            self.app.state.unsubscribe(self)

    def _update_active_tab(self) -> None:
        """Update `top tabs` to highlight the current screen."""
        if self.TAB_ID is None:
            return
        try:
            tabs = self.query_one("#top_tabs")
            tabs.active = self.TAB_ID
        except NoMatches:
            self.log_event(
                "Tabs widget not found in _update_active_tab", "DEBUG"
            )

    def _update_sidebar_visibility(self) -> None:
        """Update sidebar visibility based on app state."""
        if not hasattr(self.app, 'sidebar_visible'):
            return
        try:
            sidebar = self.query_one("#right_sidebar")
            if self.app.sidebar_visible:
                sidebar.remove_class("hidden")
            else:
                sidebar.add_class("hidden")
        except NoMatches:
            pass

    def action_toggle_right_sidebar(self) -> None:
        """Toggle event log sidebar visibility."""
        new_visibility = not self.app.sidebar_visible
        self.app.sidebar_visible = new_visibility
        try:
            sidebar = self.query_one("#right_sidebar")
            if new_visibility:
                sidebar.remove_class("hidden")
            else:
                sidebar.add_class("hidden")
        except NoMatches:
            self.log_event(
                "Sidebar widget not found in action_toggle_right_sidebar", "DEBUG"
            )

    def on_wallet_info_changed(self, wallet_info: dict) -> None:
        """Handle wallet info updates. Override in subclasses that need
            to react to wallet changes.
        """
        pass

    def on_mining_status_changed(self, active: bool, progress: int) -> None:
        """Handle mining status updates. Override in subclasses
            that need to react to mining changes.
        """
        pass

    def on_network_status_changed(self, height: int, peers: int) -> None:
        """Handle network status updates. Override in subclasses that
            need to react to network changes.
        """
        pass

    def on_txn_validated(self, result) -> None:
        """Handle transaction validation result. Override in
            subclasses that need to react to validation results.
        """
        pass

    def on_coins_mined(self, coins: list[Coin | Exception]) -> None:
        """Handle newly mined coins or mining errors. Override in
            subclasses that need to react to new coins.
        """
        pass

    def log_event(self, message: str, level: str = "INFO") -> None:
        """Log an event to the app's event log. `level` is one of
            (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        """
        try:
            if hasattr(self.app, 'query_one'):
                log_widget = self.app.query_one("#event_log", EventLog)
                log_widget.write_log(message, LogLevel[level], persistent=False)
        except Exception as e:
            import logging
            logging.getLogger("easycoin").error(f"Failed to log event: {e}")

    def refresh_data(self) -> None:
        """Refresh screen data. Override in subclasses to implement
            screen-specific refresh logic.
        """
        self.log_event("Refreshing screen data", "INFO")
        pass

    def ensure_wallet_unlocked(self) -> bool:
        """Check if wallet is unlocked; prompt if not. Returns True if
            wallet is unlocked, False otherwise.
        """
        if hasattr(self.app, 'ensure_wallet_unlocked'):
            return self.app.ensure_wallet_unlocked()
        return False
