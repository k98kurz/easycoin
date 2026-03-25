from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Input, Static
from easycoin.models import Coin, TrustNet, Wallet
from ..base import BaseScreen
from .mine_config import MiningConfigurationModal


class CoinsScreen(BaseScreen):
    """View and manage owned coins."""

    TAB_ID = "tab_coins"

    BINDINGS = [
        ("f5", "refresh_coins", "Refresh"),
        ("m", "open_mining_config", "Configure Mining"),
    ]

    def compose(self) -> ComposeResult:
        """Compose coins screen layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose coins screen content area."""
        with Vertical(id="coins_screen"):
            yield Static("Coins", classes="panel-title")
            with Horizontal(id="coins_header", classes="h-3 mt-1"):
                yield Checkbox("Active Wallet Only", id="box_active_wallet")
                yield Input(placeholder="Search coins...", id="search_input")

            yield DataTable(id="coins_table", classes="mt-1")

            with Horizontal(id="coins_actions"):
                yield Button("Refresh", id="btn_refresh", variant="default")
                yield Button(
                    "Configure Mining",
                    id="btn_mine_config",
                    variant="primary"
                )

    def on_mount(self) -> None:
        """Initialize coins table on mount."""
        super().on_mount()
        table = self.query_one("#coins_table")
        table.cursor_type = "row"
        table.add_columns(
            "Coin ID",
            "Amount",
            "Lock Type",
            "Status",
            "Network"
        )
        self.watch(self.app, "wallet", self.check_wallet_status, init=True)
        self._load_coins()

    def check_wallet_status(self, wallet) -> None:
        if wallet is None:
            self.query_one("#box_active_wallet").disabled = True
        else:
            self.query_one("#box_active_wallet").disabled = False

    @on(Checkbox.Changed, "#box_active_wallet")
    def _checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._load_coins(search_query=self.query_one("#search_input").value)

    @on(Input.Changed, "#search_input")
    def _input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        self._load_coins(search_query=event.value)

    @on(Button.Pressed, "#btn_refresh")
    def action_refresh_coins(self) -> None:
        """Refresh coins data."""
        self.log_event("Refreshing coins", "INFO")
        search_input = self.query_one("#search_input")
        self._load_coins(search_query=search_input.value)

    @on(Button.Pressed, "#btn_mine_config")
    def action_open_mining_config(self) -> None:
        """Open mining configuration modal."""
        self.app.push_screen(MiningConfigurationModal())

    def _load_coins(self, search_query: str = "") -> None:
        """Load coins from database and populate table."""
        coins = []
        try:
            if self.app.wallet and self.query_one("#box_active_wallet").value:
                self.app.wallet.coins().reload()
                coins = self.app.wallet.coins
            else:
                for chunk in Coin.query().chunk(500):
                    coins.extend(chunk)
        except Exception as e:
            self.log_event(f"Error loading coins: {e}", "ERROR")
            self.app.notify(f"Error loading coins: {e}", severity="error")
            return

        table = self.query_one("#coins_table")
        table.clear()

        sorted_coins = sorted(
            coins,
            key=lambda c: c.timestamp if hasattr(c, 'timestamp') else 0,
            reverse=True
        )

        for coin in sorted_coins:
            if search_query and search_query.lower() not in coin.id.lower():
                continue

            try:
                table.add_row(
                    coin.id,
                    f"{coin.amount:,} EC⁻¹",
                    Wallet.get_lock_type(coin.lock),
                    "Available",
                    self._get_network_name(coin.net_id)
                )
            except Exception as e:
                self.log_event(f"Error adding coin row: {e}", "ERROR")

    def on_coins_mined(self, coins: list[Coin | Exception]) -> None:
        """Handle newly mined coins."""
        self.action_refresh_coins()

        new_coins = [c for c in coins if not isinstance(c, Exception)]
        if new_coins:
            self.app.notify(
                f"Mined {len(new_coins)} new coin(s)",
                severity="success"
            )

    def _get_network_name(self, net_id: str) -> str:
        """Get network name from ID."""
        if not net_id:
            return "None"

        try:
            trustnet = TrustNet.find(net_id)
            if trustnet:
                return trustnet.name or "Unknown"
        except Exception as e:
            self.log_event(f"Error finding trustnet: {e}", "DEBUG")

        return net_id[:16] + "..."

