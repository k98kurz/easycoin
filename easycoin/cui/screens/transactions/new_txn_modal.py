from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Footer

from easycoin.models import Txn, Coin, Address
from easycoin.UTXOSet import UTXOSet

from easycoin.cui.screens.transactions.new_txn.data import TransactionData
from easycoin.cui.screens.transactions.new_txn.step_1 import SelectInputsContainer
from easycoin.cui.screens.transactions.new_txn.step_2 import AddOutputsContainer
from easycoin.cui.screens.transactions.new_txn.step_3 import WitnessInputsContainer
from easycoin.cui.screens.transactions.new_txn.step_4 import ReviewSubmitContainer


class NewTransactionModal(ModalScreen):
    """Modal for creating new transactions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+b", "back", "Back"),
        Binding("ctrl+n", "next", "Next"),
    ]

    def __init__(self):
        """Initialize new transaction modal."""
        super().__init__()
        self.current_step = 0
        self.txn_data = TransactionData()

    def compose(self) -> ComposeResult:
        """Compose new transaction modal layout."""
        with VerticalScroll(classes="modal-container w-80p h-70p"):
            yield Static("New Transaction", classes="modal-title mb-1")

            self.step_1 = SelectInputsContainer(
                self.txn_data, id="step_1_container"
            )
            self.step_2 = AddOutputsContainer(
                self.txn_data, id="step_2_container"
            )
            self.step_3 = WitnessInputsContainer(
                self.txn_data, id="step_3_container"
            )
            self.step_4 = ReviewSubmitContainer(
                self.txn_data, id="step_4_container"
            )

            yield self.step_1
            yield self.step_2
            yield self.step_3
            yield self.step_4

            with Horizontal(id="modal_actions"):
                yield Button("Back", id="btn_back", variant="default")
                yield Button("Next", id="btn_next", variant="primary")
                yield Button("Submit", id="btn_submit", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize modal on mount."""
        self._update_step_visibility()
        self.update_button_visibility()

    def _update_step_visibility(self) -> None:
        """Update visibility of step containers based on current step."""
        try:
            for step_num in range(4):
                container_id = f"#step_{step_num + 1}_container"
                try:
                    container = self.query_one(container_id)
                    container.display = (
                        "block" if step_num == self.current_step else "none"
                    )
                    if step_num == self.current_step:
                        container.on_show()
                except Exception:
                    pass
        except Exception as e:
            self.app.log_event(f"Error updating step visibility: {e}", "ERROR")

    def update_button_visibility(self) -> None:
        """Update button visibility based on current step."""
        btn_back = self.query_one("#btn_back")
        btn_next = self.query_one("#btn_next")
        btn_submit = self.query_one("#btn_submit")

        btn_back.display = "block" if self.current_step > 0 else "none"

        if self.current_step < 3:
            btn_next.display = "block"
            if self.current_step == 0:
                btn_next.disabled = len(self.txn_data.selected_outputs) == 0
            elif self.current_step == 1:
                btn_next.disabled = len(self.txn_data.outputs) == 0
            else:
                btn_next.disabled = False
            btn_submit.display = "none"
        else:
            btn_next.display = "none"
            btn_submit.display = "block"
            btn_submit.disabled = False

    def _get_current_step(self):
        """Get the current step container."""
        return self.query_one(f"#step_{self.current_step + 1}_container")

    @on(Button.Pressed, "#btn_next")
    def action_next(self) -> None:
        """Move to next step."""
        current_step = self._get_current_step()
        valid, message = current_step.validate_step()
        if not valid:
            self.app.notify(message, severity="warning")
            return

        if self.current_step < 3:
            self.current_step += 1
            self._update_step_visibility()
            self.update_button_visibility()

    @on(Button.Pressed, "#btn_back")
    def action_back(self, event = None) -> None:
        """Move to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step_visibility()
            self.update_button_visibility()

    @on(Button.Pressed, "#btn_submit")
    def action_submit(self) -> None:
        """Submit transaction."""
        try:
            if not self.app.wallet:
                self.app.notify("No wallet loaded", severity="error")
                return

            if self.app.wallet.is_locked:
                self.app.notify("Wallet must be unlocked", severity="error")
                return

            if not self.txn_data.selected_outputs:
                self.app.notify("No inputs selected", severity="error")
                return

            if not self.txn_data.outputs:
                self.app.notify("No outputs specified", severity="error")
                return

            self._validate_and_submit_transaction()

        except Exception as e:
            self.app.log_event(f"Error submitting transaction: {e}", "ERROR")
            self.app.notify(f"Error: {e}", severity="error")

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()

    def _validate_and_submit_transaction(self) -> None:
        """Validate and submit the transaction."""
        try:
            txn = Txn()
            txn.input_ids = [o.id for o in self.txn_data.selected_outputs]

            output_coins = {}
            for form in self.txn_data.outputs:
                address_str = form.get('address', '').strip()
                amount_str = form.get('amount', '').strip()

                if not address_str or not amount_str:
                    continue

                try:
                    amount = int(amount_str)
                    if amount <= 0:
                        self.app.notify(
                            f"Invalid amount: {amount_str}",
                            severity="error"
                        )
                        return

                    lock_bytes = Address.parse(address_str)
                    coin = Coin.create(lock_bytes, amount)
                    output_coins[coin.id] = coin
                    txn.output_ids.append(coin.id)
                except Exception as e:
                    self.app.notify(
                        f"Invalid address: {address_str}",
                        severity="error"
                    )
                    self.app.log_event(f"Address parse error: {e}", "DEBUG")
                    return

            if not txn.output_ids:
                self.app.notify("No valid outputs", severity="error")
                return

            # NOTE: everything below this line will need to be changed manually
            txn.witness = self.step_3.generate_witnesses()
            txn.set_timestamp()

            if not txn.validate():
                self.app.notify(
                    "Transaction validation failed",
                    severity="error"
                )
                self.app.log_event("Transaction validation failed", "DEBUG")
                return

            utxo = UTXOSet()
            if not utxo.can_apply(txn):
                self.app.notify(
                    "Transaction cannot be applied to UTXOSet",
                    severity="error"
                )
                self.app.log_event("UTXO validation failed", "DEBUG")
                return

            txn.save()
            utxo.apply(txn, output_coins)

            self.app.log_event(f"Submitted txn: {txn.id}", "INFO")

            self.dismiss()

        except Exception as e:
            self.app.log_event(f"Error in validation: {e}", "ERROR")
            self.app.notify(f"Error: {e}", severity="error")
