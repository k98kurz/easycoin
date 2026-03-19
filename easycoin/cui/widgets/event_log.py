from datetime import datetime
from enum import Enum
from pathlib import Path
from rich.text import Text
from textual.widgets import RichLog
import logging


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

    def __init__(
            self, log_file: str | None = None, max_lines: int = 1000, **kwargs
        ):
        """Initialize EventLog with optional file logging."""
        super().__init__(max_lines=max_lines, auto_scroll=True, **kwargs)
        self._filter_level = LogLevel.INFO
        self._search_query = ""
        self._all_entries = []

        if log_file:
            self.log_file = Path(log_file)
            self._setup_file_logging()

    def _setup_file_logging(self):
        """Setup file-based logging for ERROR and CRITICAL."""
        self.logger = logging.getLogger("easycoin")
        self.logger.setLevel(logging.DEBUG)

        if self.logger.handlers:
            self.logger.handlers.clear()

        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def write_log(
            self, message: str, level: LogLevel = LogLevel.INFO,
            persistent: bool = False
        ):
        """Write a log entry with severity level."""
        timestamp = datetime.now()
        self._all_entries.append((level, message, timestamp))

        if self._should_display(level, message):
            self._write_colored(message, level, timestamp)

        if persistent or level.value in ("ERROR", "CRITICAL"):
            log_levels = {
                LogLevel.DEBUG: logging.DEBUG,
                LogLevel.INFO: logging.INFO,
                LogLevel.WARNING: logging.WARNING,
                LogLevel.ERROR: logging.ERROR,
                LogLevel.CRITICAL: logging.CRITICAL
            }
            self.logger.log(log_levels[level], message)

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
