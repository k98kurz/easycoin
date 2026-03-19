"""RightSidebar: toggleable sidebar container for event log and controls."""

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, OptionList, Static
from textual.app import ComposeResult
from datetime import datetime

from .event_log import EventLog, LogLevel


class RightSidebar(Vertical):
    """Toggleable sidebar with event log and controls."""

    DEFAULT_CSS = """
    RightSidebar {
        width: 400px;
        background: $surface-lighten-1;
        border: solid $primary;
    }

    RightSidebar.hidden {
        width: 0;
        display: none;
    }

    .log-header {
        height: 3;
        text-align: center;
        text-style: bold;
        background: $primary;
    }

    .log-controls {
        height: 3;
        dock: top;
    }

    #log_search {
        width: 1fr;
    }

    #level_filter {
        height: 10;
    }

    .log-actions {
        height: 3;
    }
    """

    def __init__(self, log_file: str | None = None, **kwargs):
        """Initialize RightSidebar with optional log file."""
        super().__init__(**kwargs)
        self.log_file = log_file

    def compose(self) -> ComposeResult:
        """Compose sidebar widgets."""
        with Vertical(classes="log-header"):
            yield Static("Event Log")

        with Horizontal(classes="log-controls"):
            yield Input(placeholder="Search logs...", id="log_search")
            yield Button("🔍", id="search_btn", variant="primary")

        yield OptionList(
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
            id="level_filter"
        )

        yield EventLog(id="event_log", log_file=self.log_file)

        with Horizontal(classes="log-actions"):
            yield Button("Clear", id="clear_btn", variant="default")
            yield Button("Export", id="export_btn", variant="success")

    def on_mount(self) -> None:
        """Initialize log widget with config."""
        log_widget = self.query_one("#event_log", EventLog)
        log_widget.write_log("EasyCoin CUI started", LogLevel.INFO, persistent=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "log_search":
            log_widget = self.query_one("#event_log", EventLog)
            log_widget.search(event.value)

    def on_option_list_option_selected(
            self, event: OptionList.OptionSelected
        ) -> None:
        """Handle severity filter selection."""
        level_mapping = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
            "CRITICAL": LogLevel.CRITICAL
        }

        log_widget = self.query_one("#event_log", EventLog)
        level = level_mapping.get(str(event.option))
        if level is not None:
            log_widget.set_filter(level)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        log_widget = self.query_one("#event_log", EventLog)

        if event.button.id == "clear_btn":
            log_widget.clear()
            log_widget.write_log("Log cleared", LogLevel.INFO)
        elif event.button.id == "export_btn":
            self.export_log()
        elif event.button.id == "search_btn":
            search_input = self.query_one("#log_search", Input)
            log_widget.search(search_input.value)

    def export_log(self) -> None:
        """Export log entries to a file."""
        log_widget = self.query_one("#event_log", EventLog)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = f"easycoin_log_{timestamp}.txt"

        try:
            with open(export_path, "w") as f:
                for level, message, ts in log_widget._all_entries:
                    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{ts_str}] [{level.value}] {message}\n")

            self.app.notify(f"Log exported to {export_path}", severity="information")
        except Exception as e:
            self.app.notify(f"Export failed: {e}", severity="error")
