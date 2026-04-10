from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.widgets import Static, DataTable, Button
from textual.widgets.data_table import RowKey
from tapescript import Script
from easycoin.helpers import format_balance, format_amount, truncate_text
from .data import TransactionData
from .edit_witness_modal import EditWitnessModal
from easycoin.models import Output, Wallet, Coin, Txn, Address
import packify


class WitnessContainer(VerticalScroll):
    """Step 3: Authorize transaction by providing witness scripts."""

    def __init__(self, txn_data, **kwargs):
        super().__init__(**kwargs)
        self.txn_data = txn_data
        self.input_row_keys: list[RowKey] = []
        self.output_row_keys: list[RowKey] = []

    def compose(self) -> ComposeResult:
        """Compose Step 3: Authorize Transaction."""
        yield Static(
            "[bold]Step 3 of 4: Authorize Transaction[/bold]\n\n"
            "Provide witness scripts to authorize spending selected inputs "
            "(required) and for output coins (optional).",
            classes="mb-1"
        )
        yield Static("Inputs:", classes="text-bold mb-1")
        yield DataTable(id="inputs_table", classes="h-min-10 mb-1")

        yield Button(
            "View/Edit Input Witness", id="btn_edit_witness",
            variant="primary", classes="mb-1"
        )

        yield Static("Outputs:", classes="text-bold mb-1")
        yield DataTable(id="outputs_table", classes="h-min-8 mb-1")

        with Horizontal(classes="h-3"):
            yield Button(
                "View/Edit Output Witness", id="btn_edit_output_witness",
                variant="default", classes="mx-1"
            )
            yield Button(
                "Remove Output Witness", id="btn_remove_output_witness",
                variant="error", classes="mx-1"
            )

    def on_show(self) -> None:
        """Load inputs and outputs tables when step becomes visible."""
        self.refresh_inputs_table()
        self.refresh_outputs_table()
        try:
            self.query_one("#inputs_table").focus()
        except Exception:
            pass

    def _get_witness_len(self, coin_id: str) -> int:
        """Get witness script length for a coin."""
        try:
            if coin_id in self.txn_data.witnesses:
                return len(self.txn_data.witnesses[coin_id].full().bytes)
        except Exception:
            pass
        return 0

    def refresh_inputs_table(self) -> None:
        """Refresh the inputs table with current selected outputs."""
        table = self.query_one("#inputs_table")
        table.clear()
        self.input_row_keys.clear()

        if len(table.columns) == 0:
            table.add_columns(
                ("Input ID", "input_id"),
                ("Lock Type", "lock_type"),
                ("Witness Len", "witness_len"),
                ("Address", "address"),
            )
        table.cursor_type = "row"

        for output in self.txn_data.selected_inputs:
            try:
                truncated_id = truncate_text(
                    output.id, prefix_len=8, suffix_len=4
                )
                addr = Address.query({'lock': output.coin.lock}).first()
                secrets = packify.unpack(
                    self.app.wallet.decrypt(addr.secrets)
                ) if addr else None
                lock_type = Wallet.get_lock_type(output.coin.lock, secrets)
                witness_len = self._get_witness_len(output.coin.id)
                witness_len_str = str(witness_len) if witness_len > 0 else "-"
                address = Address({'lock': output.coin.lock}).hex

                row_key = table.add_row(
                    truncated_id,
                    lock_type,
                    witness_len_str,
                    address,
                    key=output.id
                )
                self.input_row_keys.append(row_key)
            except Exception as e:
                self.app.log_event(
                    f"Error loading row for {output.id}: {e}",
                    "ERROR"
                )

    def refresh_outputs_table(self) -> None:
        """Refresh the outputs table with current output coins."""
        table = self.query_one("#outputs_table")
        table.clear()
        self.output_row_keys.clear()

        if len(table.columns) == 0:
            table.add_columns(
                ("Output ID", "output_id"),
                ("Witness Size", "witness_size"),
                ("Stamp Type", "stamp_type"),
                ("Stamp Name", "stamp_name"),
                ("Stamp 'n'", "stamp_n"),
                ("Stamp Size", "stamp_size"),
                ("Lock Type", "lock_type"),
                ("Address", "address"),
            )
        table.cursor_type = "row"

        for coin in self.txn_data.new_output_coins:
            try:
                truncated_id = truncate_text(
                    coin.id, prefix_len=8, suffix_len=4
                )
                witness_len = self._get_witness_len(coin.id)
                witness_len_str = str(witness_len) if witness_len > 0 else "-"

                stamp_size = len(coin.data.get('details', None) or b'')
                stamp_size_display = f"{format_amount(stamp_size)}B" if stamp_size > 0 else ""
                stamp_data = coin.details.get('d', None) or {}
                stamp_type = stamp_data.get('type', '')
                stamp_name = stamp_data.get('name', '')
                stamp_n = str(coin.details.get('n', '')) if coin.details else ''

                lock_type = Wallet.get_lock_type(coin.lock)
                address = Address({'lock': coin.lock}).hex

                row_key = table.add_row(
                    truncated_id,
                    witness_len_str,
                    stamp_type,
                    stamp_name,
                    stamp_n,
                    stamp_size_display,
                    lock_type,
                    address,
                    key=coin.id
                )
                self.output_row_keys.append(row_key)
            except Exception as e:
                self.app.log_event(
                    f"Error loading row for {coin.id}: {e}",
                    "ERROR"
                )

    def validate_step(self) -> tuple[bool, str]:
        """Validate that witness scripts are provided for all inputs.
            Outputs do not require witness scripts.
        """
        try:
            missing_count = 0
            for output in self.txn_data.selected_inputs:
                try:
                    if output.coin.id not in self.txn_data.witnesses:
                        missing_count += 1
                except Exception:
                    missing_count += 1

            if missing_count > 0:
                return (
                    False,
                    f"Missing witness scripts for {missing_count} inputs"
                )
            return True, ""
        except Exception as e:
            self.app.log_event(f"Witness validation error: {e}", "ERROR")
            return False, "Failed to validate witness scripts"

    @on(DataTable.RowSelected, "#inputs_table")
    @on(Button.Pressed, "#btn_edit_witness")
    def action_edit_input_witness(self) -> None:
        """Open edit witness modal for selected input row."""
        table = self.query_one("#inputs_table")
        if table.cursor_row is None:
            self.app.notify(
                "Select a row to edit witness",
                severity="warning"
            )
            return

        if table.cursor_row >= len(self.input_row_keys):
            self.app.notify("Invalid row selection", severity="error")
            return

        row_key = self.input_row_keys[table.cursor_row]
        output = next(
            (o for o in self.txn_data.selected_inputs if o.id == row_key),
            None
        )

        if not output:
            self.app.notify("Could not find output", severity="error")
            return

        def _on_modal_result(result: dict | None) -> None:
            if result:
                self.refresh_inputs_table()

        self.app.push_screen(
            EditWitnessModal(output, self.txn_data),
            _on_modal_result
        )

    @on(DataTable.RowSelected, "#outputs_table")
    @on(Button.Pressed, "#btn_edit_output_witness")
    def action_edit_output_witness(self) -> None:
        """Open edit witness modal for selected output row."""
        table = self.query_one("#outputs_table")
        if table.cursor_row is None:
            self.app.notify(
                "Select a row to edit witness",
                severity="warning"
            )
            return

        if table.cursor_row >= len(self.output_row_keys):
            self.app.notify("Invalid row selection", severity="error")
            return

        row_key = self.output_row_keys[table.cursor_row]
        coin = next(
            (c for c in self.txn_data.new_output_coins if c.id == row_key),
            None
        )

        if not coin:
            self.app.notify("Could not find coin", severity="error")
            return

        def _on_modal_result(result: dict | None) -> None:
            if result:
                self.refresh_outputs_table()

        self.app.push_screen(
            EditWitnessModal(coin=coin, txn_data=self.txn_data),
            _on_modal_result
        )

    @on(Button.Pressed, "#btn_remove_output_witness")
    def action_remove_output_witness(self) -> None:
        """Remove witness script for selected output row."""
        table = self.query_one("#outputs_table")
        if table.cursor_row is None:
            self.app.notify(
                "Select a row to remove witness",
                severity="warning"
            )
            return

        if table.cursor_row >= len(self.output_row_keys):
            self.app.notify("Invalid row selection", severity="error")
            return

        row_key = self.output_row_keys[table.cursor_row]
        coin = next(
            (c for c in self.txn_data.new_output_coins if c.id == row_key),
            None
        )

        if not coin:
            self.app.notify("Could not find coin", severity="error")
            return

        if coin.id not in self.txn_data.witnesses:
            self.app.notify(
                "No witness script to remove for this output",
                severity="warning"
            )
            return

        del self.txn_data.witnesses[coin.id]
        txn = self.txn_data.txn
        if coin.id_bytes in txn.witness:
            del txn.witness[coin.id_bytes]

        self.refresh_outputs_table()
        self.app.notify("Output witness removed successfully")

