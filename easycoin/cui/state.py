"""
StateManager: centralized reactive state with subscribe/publish
pattern for cross-screen updates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from easycoin.cryptoworker import JobMessage
from easycoin.models import Coin


@dataclass
class LogEntry:
    """Single log entry in event log."""
    message: str
    level: str
    timestamp: datetime


@dataclass
class AppState:
    """Application state data."""

    wallet_info: dict = field(
        default_factory=lambda: {"balance": 0, "coins": 0, "stamps": {}}
    )
    coins_count: int = 0
    transactions_count: int = 0
    mining_active: bool = False
    mining_progress: int = 0
    network_height: int = 0
    peer_count: int = 0
    log_entries: list[LogEntry] = field(default_factory=list)
    log_entry_count: int = 0


class StateManager:
    """Centralized state management for EasyCoin CUI."""

    def __init__(self, app):
        """Initialize StateManager with app reference."""
        self.app = app
        self._state = AppState()
        self._listeners = []

    @property
    def wallet_info(self) -> dict:
        """Current wallet info dict with balance, coins, and stamps."""
        return self._state.wallet_info

    @property
    def coins_count(self) -> int:
        """Total number of coins owned."""
        return self._state.coins_count

    @property
    def transactions_count(self) -> int:
        """Total number of transactions."""
        return self._state.transactions_count

    @property
    def mining_active(self) -> bool:
        """Whether mining is currently active."""
        return self._state.mining_active

    @property
    def mining_progress(self) -> int:
        """Current mining progress percentage (0-100)."""
        return self._state.mining_progress

    @property
    def network_height(self) -> int:
        """Current network blockchain height."""
        return self._state.network_height

    @property
    def peer_count(self) -> int:
        """Number of connected peers."""
        return self._state.peer_count

    def subscribe(self, listener: Callable):
        """Subscribe to state changes."""
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable):
        """Unsubscribe from state changes. Silently ignores if not
            subscribed.
        """
        try:
            self._listeners.remove(listener)
        except ValueError:
            self.app.logger.debug("Listener not found in _listeners")

    def update_balance(self, balance: int) -> None:
        """Update wallet balance in wallet_info dict."""
        self._state.wallet_info["balance"] = balance
        self._notify_listeners("wallet_info_changed", self._state.wallet_info)

    def update_wallet_info(
            self, *,
            balance: int | None = None, coins: int | None = None,
            stamps: dict[str, int] | None = None,
        ) -> None:
        """Update wallet info fields."""
        if balance is not None:
            self._state.wallet_info["balance"] = balance
        if coins is not None:
            self._state.wallet_info["coins"] = coins
        if stamps is not None:
            self._state.wallet_info["stamps"] = stamps
        self._notify_listeners("wallet_info_changed", self._state.wallet_info)

    def update_mining_status(self, active: bool, progress: int = 0) -> None:
        """Update mining status."""
        self._state.mining_active = active
        self._state.mining_progress = progress
        self._notify_listeners("mining_status_changed", active, progress)

    def update_network_status(self, height: int, peers: int) -> None:
        """Update network status."""
        self._state.network_height = height
        self._state.peer_count = peers
        self._notify_listeners("network_status_changed", height, peers)

    def on_txn_validated(self, result: JobMessage) -> None:
        """Handle transaction validation result. `result.result` can be
            bool (valid) or Exception (error).
        """
        self._notify_listeners("txn_validated", result)

    def on_coins_mined(self, coins: list[Coin | Exception]) -> None:
        """Handle newly mined coins or mining errors. The list can
            contain `Coin` objects or `Exception` objects. Screens
            should handle both cases.
        """
        coin_count = sum(1 for c in coins if not isinstance(c, Exception))
        self._state.coins_count += coin_count
        self._notify_listeners("coins_mined", coins)

    def add_log_entry(self, message: str, level: str) -> None:
        """Add a log entry to state and notify listeners."""
        from datetime import datetime
        entry = LogEntry(
            message=message,
            level=level,
            timestamp=datetime.now()
        )
        self._state.log_entries.append(entry)
        self._state.log_entry_count += 1
        self._notify_listeners("log_entry_added", entry)

    def _notify_listeners(self, event: str, *args) -> None:
        """Notify all listeners of state change. Looks for `on_{event}`
            method on each listener and calls it with `args`.
        """
        for listener in self._listeners:
            callback = getattr(listener, f"on_{event}", None)
            if callback:
                try:
                    callback(*args)
                except Exception as e:
                    self.app.logger.warning(
                        f"Listener {listener} failed on {event}: {e}"
                    )

