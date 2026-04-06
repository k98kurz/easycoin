from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.css.query import NoMatches
from textual.widgets import Button, Static
from easycoin.cui.helpers import format_balance
from .base import BaseScreen


class DashboardScreen(BaseScreen):
    """Main dashboard screen with summary widgets and quick actions."""

    TAB_ID = "tab_dashboard"

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
                yield Static("Placeholder", classes="panel-title")
                yield Static("Network Status", classes="panel-title")
                yield Static("Mining Status", classes="panel-title")

