from datetime import datetime
from enum import Enum
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import RichLog, OptionList, Input, Button, Static
from textual.widgets.option_list import Option


class LogLevel(Enum):
    """Severity levels for log entries, ordered from lowest to highest."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventLogDisplay(RichLog):
    """RichLog widget with severity filtering and file persistence."""
    _filter_level: LogLevel
    _search_query: str
    _all_entries: list[tuple[LogLevel, str, datetime]]
    _app_log_count: int

    def __init__(self, max_lines: int = 1000, **kwargs):
        """Initialize EventLogDisplay."""
        super().__init__(max_lines=max_lines, auto_scroll=True, **kwargs)
        self._filter_level = LogLevel.INFO
        self._search_query = ""
        self._all_entries = []
        self._app_log_count = 0

    def on_mount(self) -> None:
        """Subscribe to app state."""
        if hasattr(self.app, 'state'):
            self.app.state.subscribe("append_log", self.on_log_entry_added)
        self._load_all_entries()

    def on_unmount(self) -> None:
        """Unsubscribe from app state."""
        if hasattr(self.app, 'state'):
            self.app.state.unsubscribe("append_log", self.on_log_entry_added)

    def _load_all_entries(self) -> None:
        """Load all log entries from app state on mount."""
        if hasattr(self.app, 'state'):
            for entry in self.app.state.get('log') or []:
                try:
                    level = LogLevel[entry.level]
                    self._display_entry(entry.message, level, entry.timestamp)
                    self._all_entries.append((level, entry.message, entry.timestamp))
                    self._app_log_count += 1
                except KeyError:
                    pass

    def on_log_entry_added(self, entry) -> None:
        """Handle new log entry added to app state."""
        try:
            level = LogLevel[entry.level]
            self._display_entry(entry.message, level, entry.timestamp)
            self._all_entries.append((level, entry.message, entry.timestamp))
            self._app_log_count += 1
        except KeyError:
            pass

    def _display_entry(
            self, message: str, level: LogLevel, timestamp: datetime
        ) -> None:
        """Display a single log entry."""
        if self._should_display(level, message):
            self._write_colored(message, level, timestamp)

    def _should_display(self, level: LogLevel, message: str) -> bool:
        """Check if entry should be displayed based on filter and search."""
        if not self._meets_severity(level):
            return False

        if self._search_query and self._search_query.lower() not in message.lower():
            return False

        return True

    def _meets_severity(self, level: LogLevel) -> bool:
        """Check if level meets minimum severity."""
        severity_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4
        }
        return severity_order[level] >= severity_order[self._filter_level]

    def _write_colored(self, message: str, level: LogLevel, timestamp: datetime):
        """Write message with appropriate color."""
        colors = {
            LogLevel.DEBUG: "dim gray",
            LogLevel.INFO: "cyan",
            LogLevel.WARNING: "yellow",
            LogLevel.ERROR: "red",
            LogLevel.CRITICAL: "bold red on white"
        }

        time_str = timestamp.strftime("%H:%M:%S")
        text = Text(f"[{time_str}] [{level.value}] {message}")
        text.stylize(colors[level])

        self.write(text)

    def set_filter(self, level: LogLevel) -> None:
        """Filter logs by severity level."""
        self._filter_level = level
        self._redisplay()

    def search(self, query: str) -> None:
        """Search logs for matching entries."""
        self._search_query = query
        self._redisplay()

    def _redisplay(self) -> None:
        """Redisplay all entries with current filters."""
        self.clear()
        for level, message, timestamp in self._all_entries:
            if self._should_display(level, message):
                self._write_colored(message, level, timestamp)


class EventLog(Vertical):
    """Complete event log widget with display, filters, and controls."""

    DEFAULT_CSS = """
        EventLog { height: 1fr; }

        #log_search { width: 1fr; }

        #event_log_display { height: 1fr; }

        .log-actions Button { width: 1fr; }
    """

    def compose(self) -> ComposeResult:
        """Compose event log widget layout."""
        yield Static("Event Log", classes="panel-title")

        yield OptionList(
            Option("DEBUG", id="DEBUG"),
            Option("INFO", id="INFO"),
            Option("WARNING", id="WARNING"),
            Option("ERROR", id="ERROR"),
            Option("CRITICAL", id="CRITICAL"),
            id="level_filter",
            classes="h-5",
        )

        yield Input(placeholder="Search logs...", id="log_search")

        yield EventLogDisplay(id="event_log_display")

        with Horizontal(classes="h-auto"):
            yield Button("Clear", id="clear_btn", variant="default")
            yield Button("Export", id="export_btn", variant="success")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "log_search":
            log_widget = self.query_one("#event_log_display", EventLogDisplay)
            log_widget.search(event.value)

    def on_option_list_option_highlighted(
            self, event: OptionList.OptionHighlighted
        ) -> None:
        """Handle severity filter selection."""
        level_mapping = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
            "CRITICAL": LogLevel.CRITICAL
        }

        log_widget = self.query_one("#event_log_display", EventLogDisplay)
        level = level_mapping.get(event.option.id)
        if level is not None:
            log_widget.set_filter(level)

    @on(Button.Pressed, "#clear_btn")
    def action_clear_log(self, event = None) -> None:
        """Clear the log"""
        log_widget = self.query_one("#event_log_display", EventLogDisplay)
        log_widget.clear()
        self.app.log_event("Log cleared", "INFO")

    @on(Button.Pressed, "#export_btn")
    def export_log(self, event = None) -> None:
        """Export log entries to a file."""
        log_widget = self.query_one("#event_log_display", EventLogDisplay)

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
