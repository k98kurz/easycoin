from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.widgets import Static, DataTable, Button
from textual.widgets.data_table import RowKey
from tapescript import Script
from easycoin.cui.helpers import format_balance, truncate_text
from easycoin.cui.screens.transactions.new_txn.data import TransactionData
from easycoin.cui.screens.transactions.new_txn.edit_witness_modal import (
    EditWitnessModal
)
from easycoin.models import Output, Wallet, Coin, Txn, Address
import packify


class WitnessInputsContainer(Vertical):
    """Step 3: Authorize transaction by providing witness scripts."""

    BINDINGS = [
        Binding("w", "edit_witness", "View/Edit Witness"),
    ]

    def __init__(self, txn_data, **kwargs):
        super().__init__(**kwargs)
        self.txn_data = txn_data
        self.row_keys: list[RowKey] = []
        self.addresses: dict[str, str] = {}
        self.add_class("h-19")

    def compose(self) -> ComposeResult:
        """Compose Step 3: Authorize Transaction."""
        yield Static(
            "[bold]Step 3 of 4: Authorize Transaction[/bold]\n\n"
            "Provide witness scripts to authorize spending selected inputs.",
            classes="mb-1"
        )
        yield DataTable(id="inputs_table", classes="h-min-10")

        with Horizontal(classes="mt-1 h-5"):
            yield Button(
                "View/Edit Witness", id="btn_edit_witness", variant="primary"
            )

    def on_show(self) -> None:
        """Load inputs table when step becomes visible."""
        self._load_addresses()
        self.refresh_table()
        try:
            self.query_one("#inputs_table").focus()
        except Exception:
            pass

    def _load_addresses(self) -> None:
        """Load wallet addresses for display in table."""
        if not self.app.wallet or self.app.wallet.is_locked:
            self.addresses.clear()
            return

        try:
            self.addresses = {}
            for address in self.app.wallet.addresses:
                self.addresses[address.lock.hex()] = address.hex
        except Exception as e:
            self.app.log_event(f"Error loading addresses: {e}", "ERROR")

    def _get_witness_len(self, output: Output) -> int:
        """Get witness script length for an output."""
        try:
            if output.id in self.txn_data.witnesses:
                return len(self.txn_data.witnesses[output.id].full().bytes)
        except Exception:
            pass
        return 0

    def refresh_table(self) -> None:
        """Refresh the inputs table with current selected outputs."""
        table = self.query_one("#inputs_table")
        table.clear()
        self.row_keys.clear()

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
                witness_len = self._get_witness_len(output)
                witness_len_str = str(witness_len) if witness_len > 0 else "-"
                address = Address({'lock': output.coin.lock}).hex

                row_key = table.add_row(
                    truncated_id,
                    lock_type,
                    witness_len_str,
                    address,
                    key=output.id
                )
                self.row_keys.append(row_key)
            except Exception as e:
                self.app.log_event(
                    f"Error loading row for {output.id}: {e}",
                    "ERROR"
                )

    def validate_step(self) -> tuple[bool, str]:
        """Validate that witness scripts are provided for all inputs."""
        try:
            missing_count = 0
            for output in self.txn_data.selected_inputs:
                try:
                    if output.id not in self.txn_data.witnesses:
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
    def action_edit_witness(self) -> None:
        """Open edit witness modal for selected row."""
        table = self.query_one("#inputs_table")
        if table.cursor_row is None:
            self.app.notify(
                "Select a row to edit witness",
                severity="warning"
            )
            return

        if table.cursor_row >= len(self.row_keys):
            self.app.notify("Invalid row selection", severity="error")
            return

        row_key = self.row_keys[table.cursor_row]
        output = next(
            (o for o in self.txn_data.selected_inputs if o.id == row_key),
            None
        )

        if not output:
            self.app.notify("Could not find output", severity="error")
            return

        def _on_modal_result(result: dict | None) -> None:
            if result:
                self.refresh_table()

        self.app.push_screen(
            EditWitnessModal(output, self.txn_data),
            _on_modal_result
        )

