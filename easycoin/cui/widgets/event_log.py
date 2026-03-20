from datetime import datetime
from enum import Enum
from rich.text import Text
from textual.widgets import RichLog


class LogLevel(Enum):
    """Severity levels for log entries, ordered from lowest to highest."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventLog(RichLog):
    """Enhanced RichLog with severity filtering and file persistence."""
    _filter_level: LogLevel
    _search_query: str
    _all_entries: list[tuple[LogLevel, str, datetime]]
    _app_log_count: int

    def __init__(self, max_lines: int = 1000, **kwargs):
        """Initialize EventLog."""
        super().__init__(max_lines=max_lines, auto_scroll=True, **kwargs)
        self._filter_level = LogLevel.INFO
        self._search_query = ""
        self._all_entries = []
        self._app_log_count = 0

    def on_mount(self) -> None:
        """Subscribe to app state."""
        if hasattr(self.app, 'state'):
            self.app.state.subscribe(self)
        self._load_all_entries()

    def on_unmount(self) -> None:
        """Unsubscribe from app state."""
        if hasattr(self.app, 'state'):
            self.app.state.unsubscribe(self)

    def _load_all_entries(self) -> None:
        """Load all log entries from app state on mount."""
        if (
            hasattr(self.app, 'state')
            and hasattr(self.app.state._state, 'log_entries')
        ):
            for entry in self.app.state._state.log_entries:
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

    def write_log(
            self, message: str, level: LogLevel = LogLevel.INFO,
            persistent: bool = False
        ):
        """Write a log entry with severity level. Deprecated: use app.log_event."""
        timestamp = datetime.now()
        self._all_entries.append((level, message, timestamp))

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
