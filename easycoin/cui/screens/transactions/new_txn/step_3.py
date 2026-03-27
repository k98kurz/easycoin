from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.widgets import Static, DataTable, Button
from textual.widgets.data_table import RowKey

from easycoin.cui.helpers import format_balance, truncate_text
from easycoin.models import Output, Wallet, Coin, Txn, Address
from tapescript import Script

from easycoin.cui.screens.transactions.new_txn.data import TransactionData
from easycoin.cui.screens.transactions.new_txn.edit_witness_modal import (
    EditWitnessModal
)


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
        """Build transaction and load inputs table when step becomes visible."""
        self._reconstruct_txn()
        self._load_addresses()
        self.refresh_table()
        try:
            self.query_one("#inputs_table").focus()
        except Exception:
            pass

    def _reconstruct_txn(self) -> None:
        """Reconstruct the Txn from TransactionData for runtime cache."""
        txn = Txn()
        txn.input_ids = [o.id for o in self.txn_data.selected_outputs]

        try:
            for form in self.txn_data.outputs:
                address_str = form.get('address', '').strip()
                if not address_str:
                    continue
                try:
                    amount = int(form.get('amount', '0'))
                    if amount <= 0:
                        continue
                    lock_bytes = Address.parse(address_str)
                    coin = Coin.create(lock_bytes, amount)
                    txn.output_ids.append(coin.id)
                except Exception as e:
                    self.app.log_event(
                        f"Error processing output {address_str}: {e}",
                        "WARNING"
                    )
            self.txn_data.txn = txn
        except Exception as e:
            self.app.log_event(
                f"Error preparing txn for witnesses: {e}",
                "ERROR"
            )

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

    def _get_address_for_output(self, output: Output) -> str | None:
        """Get address string for an output if it's in the wallet."""
        try:
            lock_hex = output.coin.lock.hex()
            return self.addresses.get(lock_hex)
        except Exception:
            return None

    def _get_witness_len(self, output: Output) -> int:
        """Get witness script length for an output."""
        try:
            coin_id_bytes = output.coin.id_bytes
            if coin_id_bytes in self.txn_data.witness_scripts:
                return len(self.txn_data.witness_scripts[coin_id_bytes])
        except Exception:
            pass
        return 0

    def _is_known_lock(self, coin_id: str) -> bool:
        """Check if lock belongs to a known wallet address."""
        if not self.app.wallet or self.app.wallet.is_locked:
            return False

        try:
            coin = Coin.find(coin_id)
            if not coin:
                return False

            lock_hex = coin.lock.hex()
            return lock_hex in self.addresses
        except Exception:
            return False

    def refresh_table(self) -> None:
        """Refresh the inputs table with current selected outputs."""
        try:
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

            for output in self.txn_data.selected_outputs:
                try:
                    truncated_id = truncate_text(
                        output.id, prefix_len=8, suffix_len=4
                    )
                    lock_type = Wallet.get_lock_type(output.coin.lock)
                    witness_len = self._get_witness_len(output)
                    witness_len_str = str(witness_len) if witness_len > 0 else "-"
                    address = self._get_address_for_output(output)
                    if address:
                        address_display = truncate_text(
                            address, prefix_len=8, suffix_len=4
                        )
                    else:
                        address_display = "Unknown"

                    row_key = table.add_row(
                        truncated_id,
                        lock_type,
                        witness_len_str,
                        address_display,
                        key=output.id
                    )
                    self.row_keys.append(row_key)
                except Exception as e:
                    self.app.log_event(
                        f"Error loading row for {output.id}: {e}",
                        "DEBUG"
                    )

        except Exception as e:
            self.app.log_event(f"Error refreshing table: {e}", "ERROR")

    def validate_step(self) -> tuple[bool, str]:
        """Validate that witness scripts are provided for all inputs."""
        try:
            missing_count = 0
            for output in self.txn_data.selected_outputs:
                try:
                    coin_id_bytes = output.coin.id_bytes
                    if not self._is_known_lock(output.id):
                        if coin_id_bytes not in self.txn_data.witness_scripts:
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

    def generate_witnesses(self) -> dict[bytes, bytes]:
        """Generate witness scripts for all selected inputs."""
        witnesses = {}
        txn = self.txn_data.txn

        if not txn:
            self.app.log_event("Transaction not reconstructed", "ERROR")
            return witnesses

        for output in self.txn_data.selected_outputs:
            try:
                coin = output.coin
                coin_id_bytes = coin.id_bytes

                is_known = self._is_known_lock(output.id)

                if is_known:
                    try:
                        lock_type = Wallet.get_lock_type(coin.lock)
                        if lock_type == "P2PKH":
                            witness_script = self.app.wallet.get_p2pkh_witness(
                                0, txn, coin
                            )
                        elif lock_type == "P2PK":
                            witness_script = self.app.wallet.get_p2pk_witness(
                                0, txn, coin
                            )
                        elif lock_type == "P2TR":
                            witness_script = (
                                self.app.wallet.get_p2tr_witness_keyspend(
                                    0, txn, coin
                                )
                            )
                        else:
                            witness_script = Script.from_src('true')

                        witnesses[coin_id_bytes] = witness_script.bytes
                    except Exception as e:
                        self.app.log_event(
                            f"Error generating witness for {output.id}: {e}",
                            "ERROR"
                        )
                else:
                    if coin_id_bytes in self.txn_data.witness_scripts:
                        witnesses[coin_id_bytes] = (
                            self.txn_data.witness_scripts[coin_id_bytes]
                        )
            except Exception as e:
                self.app.log_event(
                    f"Error processing witness for {output.id}: {e}",
                    "ERROR"
                )

        return witnesses

    def action_edit_witness(self) -> None:
        """Open edit witness modal for selected row."""
        try:
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
                (o for o in self.txn_data.selected_outputs if o.id == row_key),
                None
            )

            if not output:
                self.app.notify("Could not find output", severity="error")
                return

            def _on_modal_result(result: dict | None) -> None:
                if result:
                    self.txn_data.witness_scripts[
                        result['coin_id_bytes']
                    ] = result['witness']
                    self.refresh_table()

            self.app.push_screen(
                EditWitnessModal(output, self.txn_data),
                _on_modal_result
            )
        except Exception as e:
            self.app.log_event(f"Error opening edit modal: {e}", "ERROR")

    @on(DataTable.RowSelected, "#inputs_table")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open edit witness modal when row is selected."""
        self.action_edit_witness()

    @on(Button.Pressed, "#btn_edit_witness")
    def _on_edit_witness_pressed(self) -> None:
        self.action_edit_witness()
