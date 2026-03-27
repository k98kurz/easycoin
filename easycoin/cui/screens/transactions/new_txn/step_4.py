from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from easycoin.cui.helpers import format_balance, truncate_text


class ReviewSubmitContainer(Vertical):
    """Step 4: Review and submit transaction."""

    def __init__(self, txn_data, **kwargs):
        super().__init__(**kwargs)
        self.txn_data = txn_data

    def compose(self) -> ComposeResult:
        """Compose Step 4: Review and submit."""
        with Vertical(id="review_summary", classes="h-min-20"):
            yield Static("Transaction Summary:", classes="text-bold mb-1")

            yield Static("Inputs:", classes="text-bold")
            yield Static(
                "Loading inputs...", id="review_inputs", classes="mb-1 text-muted"
            )

            yield Static("")

            yield Static("Outputs:", classes="text-bold")
            yield Static(
                "Loading outputs...", id="review_outputs", classes="mb-1 text-muted"
            )

            yield Static("")

            yield Static("Fee:", classes="text-bold")
            yield Static("Loading fee...", id="review_fee", classes="mb-1")
            yield Static("")

            yield Static("Status:", classes="text-bold")
            yield Static(
                "Ready to submit. Please review all details above.",
                classes="mb-1"
            )

    def on_show(self) -> None:
        """Build review summary when step becomes visible."""
        self.refresh_summary()

    def validate_step(self) -> tuple[bool, str]:
        """Validate step before submission."""
        return True, ""

    def refresh_summary(self) -> None:
        """Refresh the review container with current transaction details."""
        try:
            review_inputs = self.query_one("#review_inputs")
            review_outputs = self.query_one("#review_outputs")
            review_fee = self.query_one("#review_fee")

            review_inputs.remove_children()
            review_outputs.remove_children()

            if not self.txn_data.selected_outputs:
                review_inputs.mount(
                    Static("No inputs selected.", classes="mb-1 text-muted")
                )
            else:
                for output in self.txn_data.selected_outputs:
                    truncated_id = truncate_text(
                        output.id, prefix_len=8, suffix_len=4
                    )
                    amount_str = format_balance(output.coin.amount, exact=True)
                    input_str = f"  • {truncated_id} - {amount_str}"
                    review_inputs.mount(Static(input_str, classes="mb-1"))

            if not self.txn_data.outputs:
                review_outputs.mount(
                    Static("No outputs specified.", classes="mb-1 text-muted")
                )
            else:
                for form in self.txn_data.outputs:
                    address = form.get('address', 'N/A')
                    amount = form.get('amount', '0')
                    review_outputs.mount(
                        Static(
                            f"  • {address} - {amount} EC⁻¹",
                            classes="mb-1"
                        )
                    )

            total_input = sum(o.coin.amount for o in self.txn_data.selected_outputs)
            total_output = 0
            for form in self.txn_data.outputs:
                try:
                    total_output += int(form.get('amount', '0'))
                except ValueError:
                    pass
            fee = max(0, total_input - total_output)

            review_fee.remove_children()
            review_fee.mount(Static(
                f"  Estimated Fee: {format_balance(fee, exact=True)}", classes="mb-1"
            ))
        except Exception as e:
            parent = self.app.screen if hasattr(self.app, 'screen') else None
            if parent:
                parent.app.log_event(
                    f"Error refreshing review container: {e}", "ERROR"
                )
