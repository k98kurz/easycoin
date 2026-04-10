from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll, Vertical, Horizontal
from textual.widgets import Static, DataTable, Button, OptionList
from textual.widgets.data_table import RowKey
from textual.widgets.option_list import Option
from easycoin.helpers import format_balance, format_amount, truncate_text
from easycoin.cui.widgets import CoinDetailModal
from easycoin.models import Address, Output, Wallet
import packify


class SelectInputsContainer(Vertical):
    """Step 1: Select inputs for transaction."""

    BINDINGS = [
        Binding("v", "view_coin", "View Coin"),
    ]

    def __init__(self, txn_data, **kwargs):
        super().__init__(**kwargs)
        self.txn_data = txn_data
        self.row_keys: list[RowKey] = []
        self.input_filter: str = "all"

    def compose(self) -> ComposeResult:
        """Compose Step 1: Select inputs."""
        with VerticalScroll():
            with Horizontal(classes="h-10"):
                with Container(classes=""):
                    yield Static(
                        "[bold]Step 1 of 4: Select Inputs[/bold]\n\n"
                        "Select coins to spend in this transaction.",
                        classes="mb-1"
                    )
                    yield Static(
                        "Selected: 0 coins | Total: 0 EC⁻¹",
                        id="input_summary",
                        classes="mb-1"
                    )
                with Container(classes=""):
                    yield Static("Input Type Filter:", classes="text-bold mb-1")
                yield OptionList(
                    Option("All", id="all"),
                    Option("Non-stamped", id="non_stamped"),
                    Option("All Stamps", id="all_stamps"),
                    Option("Images", id="images"),
                    Option("Tokens", id="tokens"),
                    Option("Files", id="files"),
                    id="input_filter_selector", classes="h-5"
                )
            yield DataTable(id="inputs_table", classes="h-min-10")
            with Horizontal(classes="h-5"):
                yield Button("View Details", id="btn_view_details", variant="default")

    def on_show(self) -> None:
        """Load available outputs when step becomes visible."""
        self.load_outputs()
        try:
            self.query_one("#inputs_table").focus()
        except Exception:
            pass

    def on_option_list_option_highlighted(
            self, event: OptionList.OptionHighlighted
        ) -> None:
        """Handle input type filter selection."""
        self.input_filter = event.option.id
        self.load_outputs()

    def validate_step(self) -> tuple[bool, str]:
        """Validate that at least one output is selected."""
        if not self.txn_data.selected_inputs:
            return False, "Please select at least one input"
        return True, ""

    def load_outputs(self) -> None:
        """Load available unspent outputs for the wallet."""
        if not self.app.wallet:
            return

        table = self.query_one("#inputs_table")
        table.clear()
        self.row_keys.clear()
        self.txn_data.available_inputs.clear()

        if len(table.columns) == 0:
            table.add_columns(
                ("Selected", "selected"),
                ("Coin ID", "coin_id"),
                ("Lock Type", "lock_type"),
                ("Amount", "amount"),
                ("Stamp Size", "stamp_size"),
                ("Stamp Type", "stamp_type"),
                ("Stamp Name", "stamp_name"),
                ("Stamp 'n'", "stamp_n"),
            )
        table.cursor_type = "row"

        outputs = Output.query().equal(
            'wallet_id', self.app.wallet.id
        ).get()

        filtered_outputs = []
        for output in outputs:
            coin_details = output.coin.details or {}

            if self.input_filter == "all":
                filtered_outputs.append(output)
            elif self.input_filter == "non_stamped":
                if not coin_details or len(coin_details) == 0:
                    filtered_outputs.append(output)
            elif self.input_filter == "all_stamps":
                if coin_details and len(coin_details) > 0:
                    filtered_outputs.append(output)
            elif self.input_filter == "images":
                stamp_data = coin_details.get('d', {})
                if stamp_data.get('type') == 'image':
                    filtered_outputs.append(output)
            elif self.input_filter == "tokens":
                stamp_data = coin_details.get('d', {})
                if stamp_data.get('type') == 'token':
                    filtered_outputs.append(output)
            elif self.input_filter == "files":
                stamp_data = coin_details.get('d', {})
                stamp_type = stamp_data.get('type', '')
                if stamp_type and stamp_type not in ('image', 'token'):
                    filtered_outputs.append(output)

        for output in filtered_outputs:
            addr = Address.query().equal('lock', output.coin.lock).first()
            secrets = packify.unpack(
                self.app.wallet.decrypt(addr.secrets)
            ) if addr else None
            try:
                stamp_size = len(output.coin.data.get('details', None) or b'')
                stamp_display = f"{format_amount(stamp_size)}B" if stamp_size > 0 else ""
                stamp_data = output.coin.details.get('d', None) or {}
                stamp_type = stamp_data.get('type', '')
                stamp_name = stamp_data.get('name', '')
                stamp_n = str(output.coin.details.get('n', '')) if output.coin.details else ''
                row_key = table.add_row(
                    ("✓" if output.id in [
                        o.id for o in self.txn_data.selected_inputs
                    ] else " "),
                    truncate_text(output.id, prefix_len=8, suffix_len=4),
                    Wallet.get_lock_type(output.coin.lock, secrets),
                    format_balance(output.coin.amount, exact=True),
                    stamp_display,
                    stamp_type,
                    stamp_name,
                    stamp_n,
                    key=output.id
                )
                self.row_keys.append(row_key)
                self.txn_data.available_inputs.append(output)
            except Exception as e:
                self.app.log_event(
                    f"Error loading output {output.id}: {e}",
                    "DEBUG"
                )

        self.update_summary()

    def update_summary(self) -> None:
        """Update input summary display."""
        try:
            total_amount = sum(o.coin.amount for o in self.txn_data.selected_inputs)
            summary = self.query_one("#input_summary")
            summary.update(
                f"Selected: {len(self.txn_data.selected_inputs)} coins | "
                f"Total: {format_balance(total_amount, exact=True)}"
            )
        except Exception:
            pass

    @on(DataTable.RowSelected, "#inputs_table")
    def _toggle_selection(self, event: DataTable.RowSelected) -> None:
        """Toggle selection for currently highlighted row."""
        table = event.data_table
        try:
            output = next(
                (o for o in self.txn_data.available_inputs
                    if o.id == event.row_key),
                None
            )
            txn = self.txn_data.txn

            if output:
                if output in self.txn_data.selected_inputs:
                    self.txn_data.selected_inputs.remove(output)
                    if output.id in txn.input_ids:
                        txn.inputs = [
                            i for i in txn.inputs if i.id != output.id
                        ]
                        txn.input_ids = [
                            oid for oid in txn.input_ids
                            if oid != output.id
                        ]
                    table.update_cell(event.row_key, "selected", " ")
                else:
                    self.txn_data.selected_inputs.append(output)
                    if output.id not in txn.input_ids:
                        txn.inputs = [
                            output.coin,
                            *txn.inputs
                        ]
                        txn.input_ids = [
                            output.id, *txn.input_ids
                        ]
                    table.update_cell(event.row_key, "selected", "✓")

                self.update_summary()
                try:
                    modal = self.app.screen
                    if modal:
                        modal.update_button_visibility()
                except Exception:
                    pass
        except Exception as e:
            self.app.log_event(f"Error toggling selection: {e}", "ERROR")

    @on(DataTable.RowHighlighted, "#inputs_table")
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update button visibility when row is highlighted."""
        self.update_button_visibility()

    def update_button_visibility(self) -> None:
        """Update button visibility based on table state."""
        btn_view = self.query_one("#btn_view_details")
        has_selection = False
        if self.txn_data.available_inputs:
            table = self.query_one("#inputs_table")
            has_selection = (
                table.cursor_row is not None
                and table.cursor_row < len(self.row_keys)
            )
        btn_view.display = "block" if has_selection else "none"

    def action_view_coin(self) -> None:
        """Open coin detail modal for highlighted row."""
        table = self.query_one("#inputs_table")
        if table.cursor_row is None:
            return

        output_id = self.row_keys[table.cursor_row]
        output = next(
            (o for o in self.txn_data.available_inputs if o.id == output_id),
            None
        )
        if output:
            self.app.push_screen(CoinDetailModal(output.coin))

    @on(Button.Pressed, "#btn_view_details")
    def _on_view_details_pressed(self) -> None:
        """Handle View Details button press."""
        self.action_view_coin()
