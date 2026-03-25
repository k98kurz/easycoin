from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.css.query import NoMatches
from textual.widgets import Button, Static
from .base import BaseScreen


class DashboardScreen(BaseScreen):
    """Main dashboard screen with summary widgets and quick actions."""

    TAB_ID = "tab_dashboard"

    BINDINGS = [
        ("f5", "refresh_data", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Compose dashboard layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose dashboard content area."""
        with Horizontal(id="dashboard_layout"):
            with Vertical(id="quick_actions"):
                yield Static("Quick Actions", classes="panel-title")
                yield Button(
                    "Send Transaction",
                    id="btn_send",
                    variant="primary"
                )
                yield Button(
                    "Mine Coins",
                    id="btn_mine",
                    variant="success"
                )
                yield Button("View Wallets", id="btn_wallets", variant="default")
                yield Button("Network Settings", id="btn_network", variant="default")
                yield Button("TrustNet Settings", id="btn_trustnets", variant="default")

            with Vertical(id="dashboard"):
                yield Static("Wallet Info", classes="panel-title")
                yield Static(
                    self._format_wallet_info(),
                    id="wallet_info_display",
                    classes="wallet_info"
                )

                yield Static("Network Status", classes="panel-title")
                yield Static(
                    f"Peers: {self.app.state.peer_count}",
                    id="peer_count"
                )
                yield Static(
                    f"Height: {self.app.state.network_height}",
                    id="network_height"
                )

                yield Static("Mining Status", classes="panel-title")
                yield Static(
                    self._mining_status(),
                    id="mining_status"
                )

    def on_mount(self) -> None:
        """Update top tabs to highlight Dashboard and set button states."""
        super().on_mount()

    def on_wallet_info_changed(self, wallet_info: dict) -> None:
        """Handle wallet info updates. `wallet_info` is a dict with keys
            `balance` (int), `coins` (int), and `stamps` (dict[str, int]).
        """
        self.query_one("#wallet_info_display").update(self._format_wallet_info())

    def on_mining_status_changed(self, active: bool, progress: int) -> None:
        """Handle mining status updates."""
        self.query_one("#mining_status").update(self._mining_status())

    def on_network_status_changed(self, height: int, peers: int) -> None:
        """Handle network status updates."""
        self.query_one("#peer_count").update(f"Peers: {peers}")
        self.query_one("#network_height").update(f"Height: {height}")

    def _format_wallet_info(self) -> str:
        """Format wallet info for display."""
        info = self.app.state.wallet_info
        text = f"{info['balance']:,} EC⁻¹\n"
        text += f"{info['coins']:,} coins\n"
        if len(info['stamps']):
            text += "Stamps:\n"
        for label, count in info['stamps'].items():
            text += f"- <{label}>: {count}\n"
        return text

    def _mining_status(self) -> str:
        """Get mining status text."""
        if self.app.state.mining_active:
            return f"Active ({self.app.state.mining_progress}%)"
        return "Idle"

    def refresh_data(self) -> None:
        """Refresh screen data."""
        self.log_event("Dashboard refreshed", "INFO")
