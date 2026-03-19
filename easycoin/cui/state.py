"""
StateManager: centralized reactive state with subscribe/publish
pattern for cross-screen updates.
"""

from dataclasses import dataclass, field
from typing import Callable

from easycoin.cryptoworker import JobMessage
from easycoin.models import Coin


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


class StateManager:
    """Centralized state management for EasyCoin CUI."""

    def __init__(self, app):
        """Initialize StateManager with app reference."""
        self.app = app
        self.state = AppState()
        self._listeners = []

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
            pass

    def update_balance(self, balance: int) -> None:
        """Update wallet balance in wallet_info dict."""
        self.state.wallet_info["balance"] = balance
        self._notify_listeners("wallet_info_changed", self.state.wallet_info)

    def update_wallet_info(
            self, *,
            balance: int | None = None, coins: int | None = None,
            stamps: dict[str, int] | None = None,
        ) -> None:
        """Update wallet info fields."""
        if balance is not None:
            self.state.wallet_info["balance"] = balance
        if coins is not None:
            self.state.wallet_info["coins"] = coins
        if stamps is not None:
            self.state.wallet_info["stamps"] = stamps
        self._notify_listeners("wallet_info_changed", self.state.wallet_info)

    def update_mining_status(self, active: bool, progress: int = 0) -> None:
        """Update mining status."""
        self.state.mining_active = active
        self.state.mining_progress = progress
        self._notify_listeners("mining_status_changed", active, progress)

    def update_network_status(self, height: int, peers: int) -> None:
        """Update network status."""
        self.state.network_height = height
        self.state.peer_count = peers
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
        self.state.coins_count += coin_count
        self._notify_listeners("coins_mined", coins)

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

