from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Input, Static
from easycoin.models import Coin, TrustNet, Wallet
from easycoin.cui.screens.base import BaseScreen
from easycoin.cui.helpers import format_amount, format_balance, truncate_text
from .mine_config import MiningConfigurationModal


class CoinsScreen(BaseScreen):
    """View and manage owned coins."""

    TAB_ID = "tab_coins"

    BINDINGS = [
        ("f5", "refresh_coins", "Refresh"),
        ("m", "open_mining_config", "Configure Mining"),
    ]

    def __init__(self):
        """Initialize coins screen."""
        super().__init__()
        self._coins = []
        self._coin_row_map = {}

    def compose(self) -> ComposeResult:
        """Compose coins screen layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose coins screen content area."""
        with Vertical(id="coins_screen"):
            yield Static("Coins", classes="panel-title")
            with Horizontal(id="coins_header", classes="h-3 mt-1"):
                yield Checkbox("Active Wallet Only", id="box_active_wallet")
                yield Checkbox("Stamps Only", id="box_stamps_only")
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
            "Data Size",
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

    @on(Checkbox.Changed, "#box_stamps_only")
    def _stamps_only_changed(self, event: Checkbox.Changed) -> None:
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

        stamps_only = self.query_one("#box_stamps_only").value

        table = self.query_one("#coins_table")
        table.clear()
        self._coins.clear()
        self._coin_row_map.clear()

        sorted_coins = sorted(
            coins,
            key=lambda c: c.timestamp if hasattr(c, 'timestamp') else 0,
            reverse=True
        )

        for coin in sorted_coins:
            if search_query and search_query.lower() not in coin.id.lower():
                continue

            is_stamp = len(coin.details) > 0
            if stamps_only and not is_stamp:
                continue

            self._coins.append(coin)

            try:
                data_size = len(coin.data.get('details', None) or b'')
                row_key = table.add_row(
                    coin.id,
                    format_balance(coin.amount),
                    f"{format_amount(data_size)}B",
                    Wallet.get_lock_type(coin.lock),
                    "Spent" if coin.spent else "Unspent",
                    self._get_network_name(coin.net_id)
                )
                self._coin_row_map[row_key] = coin
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

        return truncate_text(net_id, suffix_len=0)

    @on(DataTable.RowSelected, "#coins_table")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection to show coin details."""
        from .coin_detail_modal import CoinDetailModal
        row_key = event.row_key
        coin = self._coin_row_map.get(row_key)
        if coin:
            self.app.push_screen(CoinDetailModal(coin))

