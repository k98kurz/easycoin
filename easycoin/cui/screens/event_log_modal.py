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
        Binding("ctrl+q", "quit", "Quit"),
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

    def action_close(self) -> None:
        """Close event log modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()
