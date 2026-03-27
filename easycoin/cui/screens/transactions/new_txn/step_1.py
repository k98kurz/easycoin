from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Vertical
from textual.widgets import Static, DataTable
from textual.widgets.data_table import RowKey

from easycoin.cui.helpers import format_balance, truncate_text
from easycoin.models import Output, Wallet


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
        if not self.txn_data.selected_outputs:
            return False, "Please select at least one input"
        return True, ""

    def load_outputs(self) -> None:
        """Load available unspent outputs for the wallet."""
        parent = self.app.screen if hasattr(self.app, 'screen') else None
        if not parent or not parent.app.wallet:
            return

        try:
            table = self.query_one("#inputs_table")
            table.clear()
            self.row_keys.clear()
            self.txn_data.available_outputs.clear()

            if len(table.columns) == 0:
                table.add_columns(
                    ("Coin ID", "coin_id"),
                    ("Amount", "amount"),
                    ("Lock Type", "lock_type"),
                    ("Selected", "selected"),
                )
            table.cursor_type = "row"

            outputs = Output.query().equal(
                'wallet_id', parent.app.wallet.id
            ).get()

            for output in outputs:
                try:
                    row_key = table.add_row(
                        truncate_text(output.id, prefix_len=8, suffix_len=4),
                        format_balance(output.coin.amount, exact=True),
                        Wallet.get_lock_type(output.coin.lock),
                        ("✓" if output.id in [
                            o.id for o in self.txn_data.selected_outputs
                        ] else " "),
                        key=output.id
                    )
                    self.row_keys.append(row_key)
                    self.txn_data.available_outputs.append(output)
                except Exception as e:
                    parent.app.log_event(
                        f"Error loading output {output.id}: {e}",
                        "DEBUG"
                    )

            self.update_summary()

        except Exception as e:
            parent.app.log_event(f"Error loading outputs: {e}", "ERROR")

    def update_summary(self) -> None:
        """Update input summary display."""
        try:
            total_amount = sum(o.coin.amount for o in self.txn_data.selected_outputs)
            summary = self.query_one("#input_summary")
            summary.update(
                f"Selected: {len(self.txn_data.selected_outputs)} coins | "
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
                (o for o in self.txn_data.available_outputs
                    if o.id == event.row_key),
                None
            )

            if output:
                if output in self.txn_data.selected_outputs:
                    self.txn_data.selected_outputs.remove(output)
                    table.update_cell(event.row_key, "selected", " ")
                else:
                    self.txn_data.selected_outputs.append(output)
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

    def refresh_table(self) -> None:
        """Refresh the inputs table to show current selections."""
        try:
            table = self.query_one("#inputs_table")
            table.clear()

            for output in self.txn_data.available_outputs:
                is_selected = output in self.txn_data.selected_outputs
                table.add_row(
                    truncate_text(output.id, prefix_len=8, suffix_len=4),
                    format_balance(output.coin.amount, exact=True),
                    Wallet.get_lock_type(output.coin.lock),
                    "✓" if is_selected else " ",
                    key=output.id
                )
        except Exception as e:
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if parent:
                parent.app.log_event(f"Error refreshing table: {e}", "ERROR")
