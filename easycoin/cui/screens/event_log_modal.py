from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer
from easycoin.cui.widgets.event_log import EventLog


class EventLogModal(ModalScreen):
    """Full-screen modal for viewing and managing event logs."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    DEFAULT_CSS = """
        EventLogModal {
            width: 80;
        }

        #event_log_modal {
            padding: 1;
            border: solid $primary;
            background: $panel-darken-1;
        }
    """

    def compose(self) -> ComposeResult:
        """Compose event log modal layout."""
        with Vertical(id="event_log_modal"):
            yield EventLog(id="event_log")
        yield Footer()

    def on_mount(self) -> None:
        """Subscribe to app state when modal is mounted."""
        if hasattr(self.app, 'state'):
            self.app.state.subscribe(self)

    def on_unmount(self) -> None:
        """Unsubscribe from app state when modal is unmounted."""
        if hasattr(self.app, 'state'):
            self.app.state.unsubscribe(self)

    def action_close(self) -> None:
        """Close the event log modal."""
        self.dismiss()
