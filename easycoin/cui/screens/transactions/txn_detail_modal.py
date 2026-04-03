from contextlib import redirect_stdout
from io import StringIO
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Footer, DataTable
from textual.widgets.data_table import RowKey
from easycoin.cui.helpers import (
    format_balance, format_timestamp, format_timestamp_relative,
    truncate_text
)
from easycoin.cui.widgets import ECTextArea
from easycoin.cui.clipboard import universal_copy
from easycoin.models import Txn, Address, Coin, Wallet
from .readonly_witness_modal import ReadOnlyWitnessModal
import json
import packify


class TransactionDetailModal(ModalScreen):
    """Modal for viewing transaction details."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, txn_id: str):
        super().__init__()
        self.txn_id = txn_id
        self.txn = None
        self.is_valid = False
        self.validation_msg = ''
        self._coin_map_inputs = {}
        self._coin_map_outputs = {}
        self.displaying_hex = False
        self.displaying_data = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(
                id="txn_detail_modal", classes="modal-container w-80p h-70p"
            ):
            yield Static("Transaction Details", classes="modal-title")
            yield Static("\n")

            with Vertical(
                    id="txn_info", classes="border-solid-primary px-1 h-6 my-1"
                ):
                yield Static(
                    "Transaction ID: ...",
                    id="txn_id_display", classes="text-bold"
                )
                yield Static(
                    "Timestamp: ...",
                    id="timestamp_display", classes="text-muted"
                )
                yield Static(
                    "Summary: ...",
                    id="summary_display", classes="text-muted"
                )
                yield Static(
                    "Validation: ...",
                    id="validation_display", classes="text-muted"
                )

            yield ECTextArea(
                "", id="validation_errors", classes="h-10 hidden", read_only=True,
            )

            yield Static("Inputs:", classes="text-bold mb-1")
            yield DataTable(
                id="inputs_table", classes="h-min-10 mb-1"
            )

            yield Static("Outputs:", classes="text-bold mb-1")
            yield DataTable(
                id="outputs_table", classes="h-min-10 mb-1"
            )

            with Horizontal(classes="h-5"):
                yield Button("View Data", id="btn_view_data")
                yield Button("View Hex", id="btn_view_hex")

            with Vertical(id="data_display", classes="hidden h-12"):
                yield Static("Data:", classes="text-bold mb-1")
                yield ECTextArea(
                    id="data_textarea", read_only=True, classes="h-10"
                )

            with Vertical(id="hex_display", classes="hidden h-12 mt-1"):
                yield Static("Raw Hex:", classes="text-bold mb-1")
                yield ECTextArea(
                    id="hex_textarea", read_only=True, classes="h-10"
                )

            with Horizontal(id="modal_actions"):
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        self._setup_tables()
        self._load_transaction()

    def _setup_tables(self) -> None:
        inputs_table = self.query_one("#inputs_table")
        inputs_table.cursor_type = "row"
        inputs_table.add_columns(
            ("Coin ID", "coin_id"),
            ("Amount", "amount"),
            ("Lock Type", "lock_type"),
            ("Data Size", "data_size"),
            ("Witness Size", "witness_size"),
            ("Address", "address"),
        )

        outputs_table = self.query_one("#outputs_table")
        outputs_table.cursor_type = "row"
        outputs_table.add_columns(
            ("Coin ID", "coin_id"),
            ("Amount", "amount"),
            ("Lock Type", "lock_type"),
            ("Data Size", "data_size"),
            ("Spent", "spent"),
            ("Address", "address"),
        )

    def _load_transaction(self) -> None:
        self.txn = Txn.find(self.txn_id)
        if not self.txn:
            self.app.notify("Transaction not found", severity="error")
            self.dismiss()
            return

        try:
            self.is_valid = self.txn.validate()
            if not self.is_valid:
                buf = StringIO()
                with redirect_stdout(buf):
                    self.txn.validate(debug="Txn Detail Modal")
                self.validation_msg = buf.getvalue().strip()
        except Exception as e:
            self.is_valid = False
            self.validation_msg = f'Could not validate: {e}'
        self._update_header()
        self._populate_inputs_table()
        self._populate_outputs_table()
        self.query_one("#hex_textarea").text = self.txn.pack().hex()
        def hexify(thing, name=None):
            if type(thing) is dict:
                return {
                    hexify(k): hexify(v, k)
                    for k,v in thing.items()
                }
            if type(thing) is bytes:
                if name != 'witness':
                    return thing.hex()
                return hexify(packify.unpack(thing))
            return thing
        self.query_one("#data_textarea").text = json.dumps(
            hexify(self.txn.data), indent=2,
        )

    def _update_header(self) -> None:
        self.query_one("#txn_id_display").update(
            f"Transaction ID: {self.txn.id}"
        )

        timestamp = self.txn.timestamp
        self.query_one("#timestamp_display").update(
            f"Timestamp: {format_timestamp(timestamp)} "
            f"({format_timestamp_relative(timestamp)})"
        )

        validation_static = self.query_one("#validation_display")
        error_area = self.query_one("#validation_errors")
        if self.is_valid:
            validation_static.update("Validation: ✓ Validated")
            validation_static.remove_class("status-error")
            validation_static.add_class("status-ok")
        else:
            validation_static.update("Validation: ✗ Could not validate")
            validation_static.remove_class("status-ok")
            validation_static.add_class("status-error")
            error_area.text = self.validation_msg
            error_area.remove_class("hidden")
            error_area.add_class("mb-1")

        total_in = sum(coin.amount for coin in self.txn.inputs)
        total_out = sum(coin.amount for coin in self.txn.outputs)
        fee_burn = total_in - total_out

        summary_str = (
            f"Total In: {format_balance(total_in, exact=True)} | "
            f"Total Out: {format_balance(total_out, exact=True)} | "
            f"Fee Burn: {format_balance(fee_burn, exact=True)}"
        )
        self.query_one("#summary_display").update(summary_str)

    def _populate_inputs_table(self) -> None:
        inputs_table = self.query_one("#inputs_table")
        inputs_table.clear()
        self._coin_map_inputs = {}

        for coin in self.txn.inputs:
            truncated_id = truncate_text(coin.id, prefix_len=8, suffix_len=4)
            address = Address({"lock": coin.lock})
            lock_type = Wallet.get_lock_type(coin.lock)
            witness_size = 0
            data_size = len(coin.data.get('details', None) or b'')

            witness_bytes = self.txn.witness.get(coin.id_bytes, b'')
            witness_size = len(witness_bytes)

            row_key = inputs_table.add_row(
                truncated_id,
                format_balance(coin.amount, exact=True),
                lock_type,
                str(data_size),
                str(witness_size),
                address.hex,
            )
            self._coin_map_inputs[row_key] = (coin, witness_bytes)

    def _populate_outputs_table(self) -> None:
        outputs_table = self.query_one("#outputs_table")
        outputs_table.clear()
        self._coin_map_outputs = {}

        for coin in self.txn.outputs:
            truncated_id = truncate_text(coin.id, prefix_len=8, suffix_len=4)
            address = Address({"lock": coin.lock})
            lock_type = Wallet.get_lock_type(coin.lock)
            data_size = len(coin.data.get('details', None) or b'')
            spent_status = "Yes" if coin.spent else "No"

            row_key = outputs_table.add_row(
                truncated_id,
                format_balance(coin.amount, exact=True),
                lock_type,
                str(data_size),
                spent_status,
                address.hex,
            )
            self._coin_map_outputs[row_key] = coin

    @on(DataTable.RowSelected, "#inputs_table")
    def _open_input_detail(self) -> None:
        inputs_table = self.query_one("#inputs_table")
        cursor = inputs_table.cursor_coordinate
        if cursor is None:
            return
        row_key = inputs_table.coordinate_to_cell_key(cursor).row_key

        if row_key not in self._coin_map_inputs:
            return

        coin, witness_bytes = self._coin_map_inputs[row_key]
        modal = ReadOnlyWitnessModal(coin, witness_bytes)
        self.app.push_screen(modal)

    @on(DataTable.RowSelected, "#outputs_table")
    def _open_output_detail(self) -> None:
        outputs_table = self.query_one("#outputs_table")
        cursor = outputs_table.cursor_coordinate
        if cursor is None:
            return
        row_key = outputs_table.coordinate_to_cell_key(cursor).row_key

        if row_key not in self._coin_map_outputs:
            return

        coin = self._coin_map_outputs[row_key]
        if coin.spends:
            spending_txn = coin.spends[0]
            modal = TransactionDetailModal(spending_txn.id)
            self.app.push_screen(modal)
        else:
            self.app.notify("No spending transaction found", severity="info")

    @on(Button.Pressed, "#btn_view_hex")
    def _toggle_hex(self) -> None:
        display = self.query_one("#hex_display")
        if self.displaying_hex:
            self.displaying_hex = False
            display.add_class("hidden")
        else:
            self.displaying_hex = True
            display.remove_class("hidden")

    @on(Button.Pressed, "#btn_view_data")
    def _toggle_data(self) -> None:
        display = self.query_one("#data_display")
        if self.displaying_data:
            self.displaying_data = False
            display.add_class("hidden")
        else:
            self.displaying_data = True
            display.remove_class("hidden")

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()
