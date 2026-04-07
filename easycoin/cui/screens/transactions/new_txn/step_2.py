from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.widgets import Static, DataTable, Button
from textual.widgets.data_table import RowKey
from easycoin.cui.helpers import format_balance, format_amount
from .edit_output_modal import EditOutputModal
from easycoin.cui.helpers import estimate_fee_for_witness, truncate_text
from easycoin.models import Address, Coin, Txn, Wallet


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
            "Minimum Fee: 0 EC⁻¹ | Actual Burn: - EC⁻¹",
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
        if not self.txn_data.new_output_coins:
            return False, "Please add at least one output"
        return True, ""

    def refresh_table(self) -> None:
        """Refresh the outputs table with current output coins."""
        table = self.query_one("#outputs_table")
        table.clear()

        if len(table.columns) == 0:
            table.add_columns(
                ("Amount (EC⁻¹)", "amount"),
                ("Stamp Size", "stamp_size"),
                ("Stamp Type", "stamp_type"),
                ("Stamp Name", "stamp_name"),
                ("Stamp 'n'", "stamp_n"),
                ("Address", "address"),
                ("Output ID", "output_id"),
            )
        table.cursor_type = "row"

        for i, coin in enumerate(self.txn_data.new_output_coins):
            stamp_size = len(coin.data.get('details', None) or b'')
            stamp_size_display = f"{format_amount(stamp_size)}B" if stamp_size > 0 else ""
            stamp_data = coin.details.get('d', None) or {}
            stamp_type = stamp_data.get('type', '')
            stamp_name = stamp_data.get('name', '')
            stamp_n = str(coin.details.get('n', '')) if coin.details else ''
            table.add_row(
                format_balance(coin.amount, exact=True),
                stamp_size_display,
                stamp_type,
                stamp_name,
                stamp_n,
                Address({'lock': coin.lock}).hex,
                truncate_text(coin.id),
                key=i
            )

    def update_summary(self) -> None:
        """Update output summary display."""
        total_input = sum(o.coin.amount for o in self.txn_data.selected_inputs)
        total_output = 0
        for coin in self.txn_data.new_output_coins:
            total_output += coin.amount

        self.txn_data.fee = Txn.minimum_fee(self.txn_data.txn)
        if len(self.txn_data.txn.witness) == 0:
            for o in self.txn_data.selected_inputs:
                self.txn_data.fee += estimate_fee_for_witness(
                    Wallet.get_lock_type(o.coin.lock)
                )
        actual_burn = total_input - total_output
        summary = self.query_one("#output_summary")
        summary.update(
            f"Total Input: {format_balance(total_input, exact=True)} | "
            f"Total Output: {format_balance(total_output, exact=True)} | "
            f"Min Fee Estimate: {format_balance(self.txn_data.fee, exact=True)} | "
            f"Actual Burn: {format_balance(actual_burn, exact=True)}"
        )

    def update_button_visibility(self) -> None:
        """Update button visibility based on table state."""
        btn_edit = self.query_one("#btn_edit_output")
        btn_delete = self.query_one("#btn_delete_output")

        has_selection = False
        if self.txn_data.new_output_coins:
            table = self.query_one("#outputs_table")
            has_selection = (
                table.cursor_row is not None
                and table.cursor_row < len(self.txn_data.new_output_coins)
            )

        btn_edit.display = "block" if has_selection else "none"
        btn_delete.display = "block" if has_selection else "none"
        self.app.screen.update_button_visibility()

    @on(Button.Pressed, "#btn_add_output")
    def action_add_output(self) -> None:
        """Open EditOutputModal to add new output."""
        def on_dismiss(result):
            if not result:
                return
            
            if result.get('is_stamp'):
                stamp_details = result['stamp_details']
                n = stamp_details['n']
                optional = {k: v for k, v in stamp_details.items() if k != 'n'}
                coin = Coin.stamp(
                    lock=Address.parse(result['address']),
                    amount=result['amount'],
                    n=n,
                    optional=optional,
                )
            else:
                coin = Coin.create(
                    lock=Address.parse(result['address']),
                    amount=result['amount'],
                )
            
            coin.wallet_id = self.app.wallet.id
            coin.id = coin.generate_id(coin.data)
            self.txn_data.txn.outputs = [
                coin,
                *self.txn_data.txn.outputs,
            ]
            self.txn_data.txn.output_ids = [
                coin.id,
                *self.txn_data.txn.output_ids,
            ]
            self.txn_data.txn.set_timestamp()
            self.txn_data.new_output_coins.append(coin)
            self.refresh_table()
            self.update_summary()
            self.update_button_visibility()
            try:
                self.query_one("#outputs_table").focus()
            except Exception:
                pass

        total_out = sum([c.amount for c in self.txn_data.new_output_coins])
        total_in = sum(o.coin.amount for o in self.txn_data.selected_inputs)
        self.app.push_screen(
            EditOutputModal(
                address=None, amount=0, info=None,
                max_amount=total_in - total_out - self.txn_data.fee,
                txn_data=self.txn_data
            ),
            on_dismiss
        )

    @on(Button.Pressed, "#btn_edit_output")
    @on(DataTable.RowSelected, "#outputs_table")
    def action_edit_output(self) -> None:
        """Open EditOutputModal to edit selected output."""
        table = self.query_one("#outputs_table")
        output_index = table.cursor_row

        if 0 <= output_index < len(self.txn_data.new_output_coins):
            def on_dismiss(result):
                if not result:
                    return
                coin = self.txn_data.new_output_coins[result['info']]
                prev_id = coin.id
                
                if result.get('is_stamp'):
                    stamp_details = result['stamp_details']
                    n = stamp_details['n']
                    optional = {k: v for k, v in stamp_details.items() if k != 'n'}
                    coin.lock = Address.parse(result['address'])
                    coin.amount = result['amount']
                    coin.details = {'n': n, **optional}
                else:
                    coin.lock = Address.parse(result['address'])
                    coin.amount = result['amount']
                    coin.details = None
                
                coin.wallet_id = self.app.wallet.id
                coin.id = coin.generate_id(coin.data)
                self.txn_data.txn.outputs = [
                    coin,
                    *[c for c in self.txn_data.txn.outputs if c.id != prev_id],
                ]
                self.txn_data.txn.output_ids = [
                    coin.id,
                    *[oid for oid in self.txn_data.txn.output_ids if oid != prev_id],
                ]
                self.txn_data.txn.set_timestamp()
                self.refresh_table()
                self.update_summary()
                self.update_button_visibility()
                try:
                    self.query_one("#outputs_table").focus()
                except Exception:
                    pass

            current = self.txn_data.new_output_coins[output_index]
            total_out = sum([o.amount for o in self.txn_data.new_output_coins])
            total_out -= current.amount
            total_in = sum(o.coin.amount for o in self.txn_data.selected_inputs)
            self.app.push_screen(
                EditOutputModal(
                    address=Address({'lock': current.lock}).hex,
                    amount=current.amount,
                    info=output_index,
                    max_amount=total_in - total_out - self.txn_data.fee,
                    txn_data=self.txn_data,
                    coin=current,
                ),
                on_dismiss
            )

    @on(Button.Pressed, "#btn_delete_output")
    def action_delete_output(self) -> None:
        """Delete currently selected output."""
        table = self.query_one("#outputs_table")
        coin = self.txn_data.new_output_coins[table.cursor_row]
        txn = self.txn_data.txn
        txn.outputs = [
            o for o in txn.outputs
            if o.id != coin.id
        ]
        txn.output_ids = [
            oid for oid in txn.output_ids
            if oid != coin.id
        ]
        self.txn_data.txn.set_timestamp()
        del self.txn_data.new_output_coins[table.cursor_row]
        self.refresh_table()
        self.update_summary()
        self.update_button_visibility()
        try:
            self.query_one("#outputs_table").focus()
        except Exception:
            pass

    @on(DataTable.RowHighlighted, "#outputs_table")
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update button visibility when row is highlighted."""
        self.update_button_visibility()
