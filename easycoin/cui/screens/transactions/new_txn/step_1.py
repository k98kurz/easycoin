from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Vertical
from textual.widgets import Static, DataTable
from textual.widgets.data_table import RowKey
from easycoin.cui.helpers import format_balance, truncate_text
from easycoin.models import Address, Output, Wallet
import packify


class SelectInputsContainer(Vertical):
    """Step 1: Select inputs for transaction."""

    def __init__(self, txn_data, **kwargs):
        super().__init__(**kwargs)
        self.txn_data = txn_data
        self.row_keys: list[RowKey] = []

    def compose(self) -> ComposeResult:
        """Compose Step 1: Select inputs."""
        with VerticalScroll():
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
            yield DataTable(id="inputs_table", classes="h-min-20")

    def on_show(self) -> None:
        """Load available outputs when step becomes visible."""
        self.load_outputs()
        try:
            self.query_one("#inputs_table").focus()
        except Exception:
            pass

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
                ("Coin ID", "coin_id"),
                ("Amount", "amount"),
                ("Lock Type", "lock_type"),
                ("Selected", "selected"),
            )
        table.cursor_type = "row"

        outputs = Output.query().equal(
            'wallet_id', self.app.wallet.id
        ).get()

        for output in outputs:
            addr = Address.query().equal('lock', output.coin.lock).first()
            secrets = packify.unpack(
                self.app.wallet.decrypt(addr.secrets)
            ) if addr else None
            try:
                row_key = table.add_row(
                    truncate_text(output.id, prefix_len=8, suffix_len=4),
                    format_balance(output.coin.amount, exact=True),
                    Wallet.get_lock_type(output.coin.lock, secrets),
                    ("✓" if output.id in [
                        o.id for o in self.txn_data.selected_inputs
                    ] else " "),
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
                        txn.input_ids = [
                            oid for oid in txn.input_ids
                            if oid != output.id
                        ]
                        txn.inputs = [
                            i for i in txn.inputs if i.id != output.id
                        ]
                    table.update_cell(event.row_key, "selected", " ")
                else:
                    self.txn_data.selected_inputs.append(output)
                    if output.id not in txn.input_ids:
                        txn.input_ids = [
                            output.id, *txn.input_ids
                        ]
                        txn.inputs = [
                            output.coin,
                            *txn.inputs
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
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if parent:
                parent.app.log_event(f"Error toggling selection: {e}", "ERROR")
