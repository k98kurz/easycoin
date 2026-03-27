from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.widgets import Static, DataTable, Button
from textual.widgets.data_table import RowKey
from easycoin.cui.helpers import format_balance
from easycoin.cui.screens.transactions.edit_output_modal import EditOutputModal


class AddOutputsContainer(Vertical):
    """Step 2: Add outputs for transaction."""

    BINDINGS = [
        Binding("a", "add_output", "Add Output"),
        Binding("e", "edit_output", "Edit Output"),
        Binding("delete", "delete_output", "Delete Output"),
    ]

    def __init__(self, txn_data, **kwargs):
        super().__init__(**kwargs)
        self.txn_data = txn_data
        self.add_class("h-21")

    def compose(self) -> ComposeResult:
        """Compose Step 2: Add outputs."""
        yield Static(
            "[bold]Step 2 of 4: Add Outputs[/bold]\n\n"
            "Specify recipients and amounts for this transaction.",
            classes="mb-1"
        )
        yield Static(
            "Total Input: 0 EC⁻¹ | Total Output: 0 EC⁻¹ | "
            "Estimated Fee: 0 EC⁻¹",
            id="output_summary",
            classes="mb-1"
        )
        yield DataTable(id="outputs_table", classes="h-min-10")
        with Horizontal(classes="h-5"):
            yield Button("Add Output", id="btn_add_output", variant="default")
            yield Button("Edit Output", id="btn_edit_output", variant="default")
            yield Button(
                "Delete Output", id="btn_delete_output", variant="error"
            )

    def on_show(self) -> None:
        """Refresh outputs table and summary when step becomes visible."""
        self.refresh_table()
        self.update_summary()
        self.update_button_visibility()
        try:
            self.query_one("#outputs_table").focus()
        except Exception:
            pass

    def validate_step(self) -> tuple[bool, str]:
        """Validate that at least one output is specified."""
        if not self.txn_data.outputs:
            return False, "Please add at least one output"
        return True, ""

    def refresh_table(self) -> None:
        """Refresh the outputs table with current output forms."""
        try:
            table = self.query_one("#outputs_table")
            table.clear()

            if len(table.columns) == 0:
                table.add_columns(
                    ("Amount (EC⁻¹)", "amount"),
                    ("Address", "address"),
                )
            table.cursor_type = "row"

            for i, output in enumerate(self.txn_data.outputs):
                table.add_row(
                    str(output.get('amount', '')),
                    output.get('address', ''),
                    key=i
                )
        except Exception as e:
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if parent:
                parent.app.log_event(f"Error refreshing outputs table: {e}", "ERROR")

    def update_summary(self) -> None:
        """Update output summary display."""
        try:
            total_input = sum(o.coin.amount for o in self.txn_data.selected_outputs)
            total_output = 0
            for form in self.txn_data.outputs:
                try:
                    amount = int(form.get('amount', '0'))
                    total_output += amount
                except (ValueError, TypeError):
                    pass

            estimated_fee = max(0, total_input - total_output)
            summary = self.query_one("#output_summary")
            summary.update(
                f"Total Input: {format_balance(total_input, exact=True)} | "
                f"Total Output: {format_balance(total_output, exact=True)} | "
                f"Estimated Fee: {format_balance(estimated_fee, exact=True)}"
            )
        except Exception as e:
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if parent:
                parent.app.log_event(f"Error updating output summary: {e}", "DEBUG")

    def update_button_visibility(self) -> None:
        """Update button visibility based on table state."""
        btn_edit = self.query_one("#btn_edit_output")
        btn_delete = self.query_one("#btn_delete_output")

        has_selection = False
        if self.txn_data.outputs:
            table = self.query_one("#outputs_table")
            has_selection = (
                table.cursor_row is not None
                and table.cursor_row < len(self.txn_data.outputs)
            )

        btn_edit.display = "block" if has_selection else "none"
        btn_delete.display = "block" if self.txn_data.outputs else "none"
        self.app.screen.update_button_visibility()

    @on(Button.Pressed, "#btn_add_output")
    def action_add_output(self) -> None:
        """Open EditOutputModal to add new output."""
        parent = self.app.screen if hasattr(self.app, 'screen') else None
        if not parent:
            return

        def on_dismiss(result):
            if not result:
                return
            self.txn_data.outputs.append({
                'address': result['address'],
                'amount': result['amount']
            })
            self.refresh_table()
            self.update_summary()
            self.update_button_visibility()
            try:
                self.query_one("#outputs_table").focus()
            except Exception:
                pass

        total_out = sum([o['amount'] for o in self.txn_data.outputs])
        total_in = sum(o.coin.amount for o in self.txn_data.selected_outputs)
        parent.app.push_screen(
            EditOutputModal(
                address=None, amount=0, info=None,
                max_amount=total_in - total_out - self.txn_data.fee
            ),
            on_dismiss
        )

    @on(DataTable.RowSelected, "#outputs_table")
    def _edit_output(self, event: DataTable.RowSelected) -> None:
        """Open EditOutputModal to edit selected output."""
        output_index = event.row_key.value

        if 0 <= output_index < len(self.txn_data.outputs):
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if not parent:
                return

            def on_dismiss(result):
                if not result:
                    return
                self.txn_data.outputs[result['info']] = {
                    'address': result['address'],
                    'amount': result['amount']
                }
                self.refresh_table()
                self.update_summary()
                self.update_button_visibility()
                try:
                    self.query_one("#outputs_table").focus()
                except Exception:
                    pass

            current = self.txn_data.outputs[output_index]
            total_out = sum([o['amount'] for o in self.txn_data.outputs])
            total_in = sum(o.coin.amount for o in self.txn_data.selected_outputs)
            parent.app.push_screen(
                EditOutputModal(
                    address=current.get('address', ''),
                    amount=int(current.get('amount', 0)),
                    info=output_index,
                    max_amount=total_in - total_out - self.txn_data.fee
                ),
                on_dismiss
            )

    @on(Button.Pressed, "#btn_delete_output")
    def action_delete_output(self) -> None:
        """Delete currently selected output."""
        try:
            table = self.query_one("#outputs_table")
            if (table.cursor_row is not None
                    and table.cursor_row < len(self.txn_data.outputs)):
                del self.txn_data.outputs[table.cursor_row]
                self.refresh_table()
                self.update_summary()
                self.update_button_visibility()
                try:
                    self.query_one("#outputs_table").focus()
                except Exception:
                    pass
        except Exception as e:
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if parent:
                parent.app.log_event(f"Error deleting output: {e}", "ERROR")

    @on(Button.Pressed, "#btn_edit_output")
    def action_edit_output(self) -> None:
        """Edit currently selected output."""
        try:
            table = self.query_one("#outputs_table")
            if (table.cursor_row is not None
                    and table.cursor_row < len(self.txn_data.outputs)):
                output_index = table.cursor_row
                parent = self.app.screen if hasattr(self.app, 'screen') else None
                if not parent:
                    return

                def on_dismiss(result):
                    if not result:
                        return
                    self.txn_data.outputs[result['info']] = {
                        'address': result['address'],
                        'amount': result['amount']
                    }
                    self.refresh_table()
                    self.update_summary()
                    self.update_button_visibility()
                    try:
                        self.query_one("#outputs_table").focus()
                    except Exception:
                        pass

                current = self.txn_data.outputs[output_index]
                total_out = sum([o['amount'] for o in self.txn_data.outputs])
                total_in = sum(o.coin.amount for o in self.txn_data.selected_outputs)
                total_out -= current['amount']
                parent.app.push_screen(
                    EditOutputModal(
                        address=current.get('address', ''),
                        amount=int(current.get('amount', 0)),
                        info=output_index,
                        max_amount=total_in - total_out - self.txn_data.fee
                    ),
                    on_dismiss
                )
        except Exception as e:
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if parent:
                parent.app.log_event(f"Error editing output: {e}", "ERROR")

    @on(DataTable.RowHighlighted, "#outputs_table")
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update button visibility when row is highlighted."""
        self.update_button_visibility()
