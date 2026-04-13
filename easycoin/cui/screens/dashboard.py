from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.css.query import NoMatches
from textual.widgets import Button, Static
from easycoin.helpers import format_balance
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
                yield Static(
                    "This is a WIP. If you have an idea for this, let me know.",
                    classes="my-1"
                )
                yield Static("Network Status", classes="panel-title")
                yield Static(
                    "Coming soon: https://github.com/k98kurz/easycoin/issues/2",
                    classes="my-1"
                )
                yield Static("Mining Status", classes="panel-title")
                yield Static(
                    "Also coming soon, after this: "
                    "https://github.com/k98kurz/easycoin/issues/4",
                    classes="my-1"
                )

    @on(Button.Pressed)
    def _notify_nothing(self):
        self.app.notify("The only buttons in the whole app that do nothing.")

