from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button, Checkbox, DataTable, Input, RadioSet, RadioButton, Static
)
from easycoin.UTXOSet import UTXOSet
from easycoin.models import Address, Coin, Txn, TrustNet, Wallet
from easycoin.cryptoworker import submit_mine_job, work_mine_job
from easycoin.cui.screens.base import BaseScreen
from easycoin.helpers import format_amount, format_balance, truncate_text
from .mine_config import MiningConfigurationModal
from .mine_coin_modal import MineCoinModal


class CoinsScreen(BaseScreen):
    """View and manage owned coins."""

    TAB_ID = "tab_coins"

    BINDINGS = [
        ("f5", "refresh_coins", "Refresh"),
        ("m", "mine_coin", "Mine a Coin"),
        ("c", "open_mining_config", "Configure Mining"),
    ]

    def __init__(self):
        """Initialize coins screen."""
        super().__init__()
        self._coins = []
        self._coin_row_map = {}
        self.coin_type_filter: str = "all"

    def compose(self) -> ComposeResult:
        """Compose coins screen layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose coins screen content area."""
        with VerticalScroll(id="coins_screen"):
            yield Static("Coins", classes="panel-title")
            with Horizontal(id="coins_header", classes="h-7 mt-1"):
                with Vertical(classes="w-30"):
                    yield Checkbox(
                        "Active Wallet Only", id="box_active_wallet",
                        classes="mb-1"
                    )
                    yield Checkbox(
                        "Unspent Only", id="box_unspent_only", value=True
                    )
                yield RadioSet(
                    RadioButton("All", id="rbtn_all", value=True),
                    RadioButton("Non-stamps", id="rbtn_non_stamps"),
                    RadioButton("All Stamps", id="rbtn_all_stamps"),
                    RadioButton("Images", id="rbtn_images"),
                    RadioButton("Tokens", id="rbtn_tokens"),
                    RadioButton("Files", id="rbtn_files"),
                    id="coin_type_filter",
                    classes="h-7 w-30"
                )
                yield Input(placeholder="Search coins by ID...", id="search_input")

            yield DataTable(id="coins_table", classes="mt-1 h-20")

            with Horizontal(id="coins_actions", classes="h-6"):
                yield Button("Refresh", id="btn_refresh", variant="default")
                yield Button("Mine Coin", id="btn_mine_coin", variant="primary")
                yield Button(
                    "Configure Mining",
                    id="btn_mine_config",
                    variant="default"
                )

    def on_mount(self) -> None:
        """Initialize coins table on mount."""
        table = self.query_one("#coins_table")
        table.cursor_type = "row"
        table.add_columns(
            "Coin ID",
            "Amount",
            "Lock Type",
            "Stamp Size",
            "Stamp Type",
            "Stamp Name",
            "Stamp 'n'",
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

    @on(Checkbox.Changed, "#box_unspent_only")
    def _unspent_only_changed(self, event: Checkbox.Changed) -> None:
        self._load_coins(search_query=self.query_one("#search_input").value)

    @on(RadioSet.Changed, "#coin_type_filter")
    def _update_filter(self):
        radio_set = self.query_one("#coin_type_filter")
        self.coin_type_filter = [
            "all", "non_stamps", "all_stamps", "image", "token", "files"
        ][radio_set.pressed_index]
        self._load_coins(search_query=self.query_one("#search_input").value)

    @on(Input.Changed, "#search_input")
    def _input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.value and not event.value.strip():
            return
        self._load_coins(search_query=event.value)

    @on(Button.Pressed, "#btn_refresh")
    def action_refresh_coins(self) -> None:
        """Refresh coins data."""
        self.log_event("Refreshing coins", "INFO")
        self._load_coins(search_query=self.query_one("#search_input").value)

    @on(Button.Pressed, "#btn_mine_config")
    def action_open_mining_config(self) -> None:
        """Open mining configuration modal."""
        self.app.push_screen(MiningConfigurationModal())

    @on(Button.Pressed, "#btn_mine_coin")
    async def action_mine_coin(self) -> None:
        """Open mine coin modal."""
        async def on_mine_params(result):
            """Handle mining parameters returned from modal."""
            if not result:
                return

            address = result.get("address")
            amount = result.get("amount")

            self.app.notify(
                f"Mining coin of {amount} EC⁻¹ with address "
                f"{truncate_text(address)}",
                severity="info"
            )
            self.log_event(
                f"Mine coin requested: amount={amount}, address={address}",
                "INFO"
            )

            self._mine_coin(address, amount)

        self.app.push_screen(MineCoinModal(), on_mine_params)

    def _load_coins(self, search_query: str = "") -> None:
        """Load coins from database and populate table."""
        search_query = search_query.strip()
        unspent_only = self.query_one("#box_unspent_only").value
        coins = []
        try:
            if self.app.wallet and self.query_one("#box_active_wallet").value:
                sqb = self.app.wallet.coins().query()
            else:
                sqb = Coin.query()

            if self.coin_type_filter == 'non_stamps':
                sqb.is_null('details')
            elif self.coin_type_filter != 'all':
                sqb.not_null('details')

            if unspent_only:
                sqb.equal('spent', False)

            if search_query:
                sqb.contains('id', search_query.lower())

            sqb.order_by('timestamp', 'desc')

            for chunk in sqb.chunk(500):
                coins.extend(chunk)

            if self.coin_type_filter in ('image', 'token', 'files'):
                target_type = self.coin_type_filter
                filtered_coins = []
                for coin in coins:
                    if coin.details:
                        stamp_data = coin.details.get('d', {})
                        stamp_type = stamp_data.get('type', '')
                        if target_type == 'files':
                            if stamp_type and stamp_type not in ('image', 'token'):
                                filtered_coins.append(coin)
                        elif stamp_type == target_type:
                            filtered_coins.append(coin)
                coins = filtered_coins
        except Exception as e:
            self.log_event(f"Error loading coins: {e}", "ERROR")
            self.app.notify(f"Error loading coins: {e}", severity="error")
            return

        table = self.query_one("#coins_table")
        table.clear()
        self._coins.clear()
        self._coin_row_map.clear()

        for coin in coins:
            self._coins.append(coin)

            try:
                # Extract and format stamp data
                stamp_size = len(coin.data.get('details', None) or b'')
                stamp_size_display = f"{format_amount(stamp_size)}B" if stamp_size > 0 else ""
                stamp_data = coin.details.get('d', None) or {}
                stamp_type = stamp_data.get('type', '')
                stamp_name = stamp_data.get('name', '')
                stamp_n = str(coin.details.get('n', '')) if coin.details else ''

                row_key = table.add_row(
                    coin.id,
                    format_balance(coin.amount),
                    Wallet.get_lock_type(coin.lock),
                    stamp_size_display,
                    stamp_type,
                    stamp_name,
                    stamp_n,
                    "Spent" if coin.spent else "Unspent",
                    self._get_network_name(coin.net_id)
                )
                self._coin_row_map[row_key] = coin
            except Exception as e:
                self.log_event(f"Error adding coin row: {e}", "ERROR")

    @work(exclusive=True)
    async def _mine_coin(self, address: str, amount: int) -> None:
        lock = Address.parse(address)
        submit_mine_job(lock, amount, 1)
        result = await work_mine_job()
        if result is None:
            self.app.log_event("work_mine_job() returned None", "WARNING")
            self.app.notify("Mining failed for unknown reason", "warning")
            return

        self.on_coins_mined(result[1])

    def on_coins_mined(self, coins: list[Coin | Exception]) -> None:
        """Handle newly mined coins."""
        new_coins = [c for c in coins if not isinstance(c, Exception)]
        errors = [c for c in coins if isinstance(c, Exception)]
        for e in errors:
            self.app.log_event(
                f"Error mining coin: {e}", "ERROR"
            )

        if errors:
            self.app.notify("Errors encountered mining coins", severity="error")

        if not new_coins:
            return

        self.app.notify(
            f"Mined {len(new_coins)} new coin(s)",
            severity="success"
        )

        utxos = UTXOSet()

        # create a txn for each coin
        for c in new_coins:
            c.id = c.generate_id(c.data)
            if self.app.wallet:
                c.wallet_id = self.app.wallet.id
            txn = Txn({'input_ids': '', 'output_ids': c.id})
            txn.outputs = [c]

            if not txn.validate(reload=False):
                self.app.log_event("mint txn failed validation", "ERROR")
                continue

            if not utxos.can_apply(txn):
                self.app.log_event(
                    "mint txn could not be applied to UTXOSet", "ERROR"
                )
                continue

            c.save()
            txn.save()
            utxos.apply(txn, {c.id: c})
            self.app.log_event(
                f"mint txn {txn.id} saved successfully",
                "INFO"
            )

        self.action_refresh_coins()

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
        from easycoin.cui.widgets.coin_detail_modal import CoinDetailModal
        row_key = event.row_key
        coin = self._coin_row_map.get(row_key)
        if coin:
            def on_disassociated():
                if self.query_one("#box_active_wallet").value:
                    self.action_refresh_coins()

            self.app.push_screen(CoinDetailModal(coin, on_disassociated))

