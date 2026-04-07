from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, DataTable
from easycoin.cui.helpers import format_balance, format_amount, truncate_text
from easycoin.models import Address


class ReviewSubmitContainer(VerticalScroll):
    """Step 4: Review and submit transaction."""

    def __init__(self, txn_data, **kwargs):
        super().__init__(**kwargs)
        self.txn_data = txn_data

    def compose(self) -> ComposeResult:
        """Compose Step 4: Review and submit."""
        yield Static(
            "[bold]Step 4 of 4: Review & Submit[/bold]\n\n"
            "Review all details before submitting.",
            classes="mb-1"
        )

        yield Static("Inputs:", classes="text-bold mb-1")
        yield DataTable(
            id="review_inputs_table", classes="h-min-10 mb-1"
        )

        yield Static("Outputs:", classes="text-bold mb-1")
        yield DataTable(
            id="review_outputs_table", classes="h-min-8 mb-1"
        )

        yield Static("Fee:", classes="text-bold mb-1")
        yield Static(
            "Minimum Fee: ... | Actual Fee Burn: ...",
            id="review_fee",
            classes="mb-1"
        )

    def on_show(self) -> None:
        """Build review summary when step becomes visible."""
        self._setup_tables()
        self.refresh_summary()

    def _setup_tables(self) -> None:
        """Set up table columns and cursor type."""
        inputs_table = self.query_one("#review_inputs_table")
        if len(inputs_table.columns) == 0:
            inputs_table.add_columns(
                ("Coin ID", "coin_id"),
                ("Amount", "amount"),
                ("Lock Type", "lock_type"),
                ("Stamp Size", "stamp_size"),
                ("Stamp Type", "stamp_type"),
                ("Stamp Name", "stamp_name"),
                ("Stamp 'n'", "stamp_n"),
                ("Witness Size", "witness_size"),
                ("Address", "address"),
            )
        inputs_table.cursor_type = "none"

        outputs_table = self.query_one("#review_outputs_table")
        if len(outputs_table.columns) == 0:
            outputs_table.add_columns(
                ("Amount", "amount"),
                ("Stamp Size", "stamp_size"),
                ("Stamp Type", "stamp_type"),
                ("Stamp Name", "stamp_name"),
                ("Stamp 'n'", "stamp_n"),
                ("Address", "address"),
            )
        outputs_table.cursor_type = "none"

    def refresh_summary(self) -> None:
        """Refresh the review container with current transaction details."""
        inputs_table = self.query_one("#review_inputs_table")
        outputs_table = self.query_one("#review_outputs_table")
        fee_static = self.query_one("#review_fee")

        # fill inputs table
        total_in = 0
        inputs_table.clear()
        for output in self.txn_data.selected_inputs:
            total_in += output.coin.amount

            # Extract stamp data
            stamp_size = len(output.coin.data.get('details', None) or b'')
            stamp_size_display = f"{format_amount(stamp_size)}B" if stamp_size > 0 else ""
            stamp_data = output.coin.details.get('d', None) or {}
            stamp_type = stamp_data.get('type', '')
            stamp_name = stamp_data.get('name', '')
            stamp_n = str(output.coin.details.get('n', '')) if output.coin.details else ''

            inputs_table.add_row(
                truncate_text(output.coin.id),
                format_balance(output.coin.amount, exact=True),
                self.txn_data.witnesses[output.coin.id].lock_type,
                stamp_size_display,
                stamp_type,
                stamp_name,
                stamp_n,
                len(self.txn_data.witnesses[output.coin.id].full().bytes),
                Address({"lock": output.coin.lock}).hex,
            )

        # fill outputs table
        total_out = 0
        outputs_table.clear()
        for coin in self.txn_data.new_output_coins:
            total_out += coin.amount

            # Extract stamp data
            stamp_size = len(coin.data.get('details', None) or b'')
            stamp_size_display = f"{format_amount(stamp_size)}B" if stamp_size > 0 else ""
            stamp_data = coin.details.get('d', None) or {}
            stamp_type = stamp_data.get('type', '')
            stamp_name = stamp_data.get('name', '')
            stamp_n = str(coin.details.get('n', '')) if coin.details else ''

            outputs_table.add_row(
                format_balance(coin.amount, exact=True),
                stamp_size_display,
                stamp_type,
                stamp_name,
                stamp_n,
                Address({"lock": coin.lock}).hex,
            )

        # set fee text
        txn = self.txn_data.txn
        min_fee = format_balance(txn.minimum_fee(txn), exact=True)
        actual_burn = format_balance(total_in - total_out, exact=True)
        fee_static.update(
            f"Minimum Fee: {min_fee} | Actual Fee Burn: {actual_burn}"
        )

    def _check_txn(self) -> tuple[bool, str]:
        """Check if `txn_data.txn` has gone out-of-sync with the rest of
            `txn_data`. Sanity check with debug messages.
        """
        status = True
        issues = []

        # ensure it has the correct inputs
        for output in self.txn_data.selected_inputs:
            if output.id not in self.txn_data.txn.input_ids:
                status = False
                issues.append(f"Txn missing selected input {output.id}")
                self.app.log_event(
                    f"Txn out of sync: missing selected input {output.id}",
                    "DEBUG",
                )

        # ensure it has the correct witnesses
        for coin_id, witness in self.txn_data.witnesses.items():
            if bytes.fromhex(coin_id) not in self.txn_data.txn.witness:
                status = False
                issues.append(f"Txn missing witness for input {coin_id}")
                self.app.log_event(
                    f"Txn out of sync: missing witness for input {coin_id}",
                    "DEBUG"
                )
            elif self.txn_data.txn.witness[
                    bytes.fromhex(coin_id)
                ] != witness.full().bytes:
                status = False
                issues.append(f"Txn has incorrect witness for input {coin_id}")
                self.app.log_event(
                    f"Txn out of sync: incorrect witness for input {coin_id}",
                    "DEBUG"
                )

        # ensure it has the correct outputs
        for coin in self.txn_data.new_output_coins:
            if coin.id not in self.txn_data.txn.output_ids:
                status = False
                self.app.log_event(
                    f"Txn out of sync: missing new output coin {coin.id}",
                    "DEBUG",
                )

        return status, "\n".join(issues)

    def validate_step(self) -> tuple[bool, str]:
        """Validate step before submission."""
        return self._check_txn()

