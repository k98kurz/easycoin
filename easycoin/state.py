"""
StateManager: subscribe/publish + state bag for cross-screen updates.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class LogEntry:
    """Single log entry in event log."""
    message: str
    level: str
    timestamp: datetime


class StateManager:
    """Pub/sub layer with some state sharing features."""

    def __init__(self, logger: logging.Logger):
        """Initialize StateManager with logger."""
        self.logger = logger
        self.data = {}
        self._subscriptions = {}

    def subscribe(self, event_name: str, listener: Callable):
        """Subscribe to a specific event."""
        if event_name not in self._subscriptions:
            self._subscriptions[event_name] = []
        self._subscriptions[event_name].append(listener)

    def unsubscribe(self, event_name: str, listener: Callable):
        """Unsubscribe from a specific event. Silently ignores if not
            subscribed.
        """
        if event_name not in self._subscriptions:
            return
        try:
            self._subscriptions[event_name].remove(listener)
        except ValueError:
            self.logger.debug(
                f"Listener not found in _subscriptions[{event_name}]"
            )

    def publish(self, event_name: str, data: Any = None):
        """Publish an event to all subscriptions to that event."""
        if event_name not in self._subscriptions:
            return
        for callback in self._subscriptions[event_name]:
            try:
                callback(data)
            except Exception as e:
                self.logger.warning(
                    f"subscription callback for event {event_name} failed: {e}"
                )

    def get(self, key: str) -> Any | None:
        """Get some state."""
        return self.data.get(key, None)

    def set(self, key: str, data: Any):
        """Set some state. Notify subscriptions for the `set_{key}`
            event.
        """
        self.data[key] = data
        self.publish(f"set_{key}", data)

    def unset(self, key: str):
        """Unset some state. Notify subscriptions for the `unset_{key}`
            event.
        """
        self.publish(f"unset_{key}", self.data.pop(key, None))

    def append(self, key: str, data: Any):
        """Append to a list. If the list does not yet exist, create it.
            Notify subscriptions for the `append_{key}` event. Raises
            `TypeError` if the state with that key is set to a non-list.
        """
        if key not in self.data:
            self.data[key] = []
        if not isinstance(self.data[key], list):
            raise TypeError(f"state item '{key}' is not a list; cannot append")
        self.data[key].append(data)
        self.publish(f"append_{key}", data)

    def add_log_entry(self, message: str, level: str) -> None:
        """Add a log entry to state and push to subscriptions."""
        entry = LogEntry(
            message=message,
            level=level,
            timestamp=datetime.now()
        )
        self.append('log', entry)

