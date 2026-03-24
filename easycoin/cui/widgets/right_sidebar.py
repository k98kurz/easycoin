"""RightSidebar: toggleable sidebar container for event log."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from .event_log import EventLog


class RightSidebar(Vertical):
    """Toggleable sidebar with event log."""

    DEFAULT_CSS = """
    RightSidebar {
        background: $surface-lighten-1;
        border: solid $primary;
        width: 1fr;
    }

    RightSidebar.hidden {
        width: 0;
        display: none;
    }
    """

    def __init__(self, **kwargs):
        """Initialize RightSidebar."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose sidebar widgets."""
        yield EventLog(id="event_log")
