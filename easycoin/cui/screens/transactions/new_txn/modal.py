from contextlib import redirect_stdout
from io import StringIO
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Footer
from easycoin.models import Txn, Coin, Address
from easycoin.UTXOSet import UTXOSet
from .data import TransactionData
from .step_1 import SelectInputsContainer
from .step_2 import AddOutputsContainer
from .step_3 import WitnessContainer
from .step_4 import ReviewSubmitContainer


class NewTransactionModal(ModalScreen):
    """Modal for creating new transactions."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
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
            self.step_3 = WitnessContainer(
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
                btn_next.disabled = len(self.txn_data.selected_inputs) == 0
            elif self.current_step == 1:
                btn_next.disabled = len(self.txn_data.new_output_coins) == 0
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
        if not self.app.wallet:
            self.app.notify("No wallet loaded", severity="error")
            return

        if self.app.wallet.is_locked:
            self.app.notify("Wallet must be unlocked", severity="error")
            return

        if not self.txn_data.selected_inputs:
            self.app.notify("No inputs selected", severity="error")
            return

        if not self.txn_data.new_output_coins:
            self.app.notify("No outputs specified", severity="error")
            return

        self._validate_and_submit_transaction()

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()

    def _validate_and_submit_transaction(self) -> None:
        """Validate and submit the transaction."""
        self.txn_data.txn.set_timestamp()
        step_4 = self.query_one(f"#step_4_container")
        status, msg = step_4.validate_step()

        if not status:
            self.app.log_event(f"New Txn Step 4 failed: {msg}", "WARNING")
            return self.app.notify(msg, severity="warning")

        utxoset = UTXOSet()
        txn = self.txn_data.txn
        if not utxoset.can_apply(txn):
            self.app.log_event(
                "Txn is invalid: it cannot be applied to the UTXO set "
                "(double spend?)",
                "ERROR"
            )
            return self.app.notify(
                "Txn is invalid: it cannot be applied to the UTXO set "
                "(double spend?)",
                severity="error"
            )

        if not txn.validate(reload=False):
            buf = StringIO()
            with redirect_stdout(buf):
                txn.validate(debug="New Txn Modal", reload=False)
            debug_output = buf.getvalue().strip()
            self.app.log_event(
                f"Txn failed validation:\n{debug_output}",
                "ERROR"
            )
            self.app.log_event(f"{txn.data=}", "DEBUG")
            txn_witness = {
                k.hex(): v.hex()
                for k,v in txn.witness.items()
            }
            self.app.log_event(f"{txn_witness=}", "DEBUG")
            self.app.log_event(f"{self.txn_data=}", "DEBUG")
            if len(debug_output.split("\n")) > 7:
                return self.app.notify(
                    f"Txn failed validation: see event log for full details",
                    severity="error"
                )
            return self.app.notify(
                f"Txn failed validation:\n{debug_output}",
                severity="error"
            )

        # mark coins as spent
        Coin.query().is_in('id', [c.id for c in txn.inputs]).update({'spent': True})

        # persist new coins to database
        for coin in self.txn_data.new_output_coins:
            cid = coin.id
            coin_data1 = f"{coin.data}"
            coin.save()
            if cid != coin.id:
                coin_data2 = f"{coin.data}"
                self.app.notify("coin ID changed on save", severity="error")
                self.app.log_event("coin ID changed on save", "ERROR")
                self.app.log_event(f"{coin_data1=}", "ERROR")
                self.app.log_event(f"{coin_data2=}", "ERROR")
                # roll back
                coin.delete()
                Coin.query().is_in(
                    'id', [c.id for c in txn.inputs]
                ).update({'spent': False})
                return

        # persist txn and changes to UTXOSet
        txn.save()
        coins = {c.id: c for c in self.txn_data.new_output_coins}
        for c in self.txn_data.txn.inputs:
            coins[c.id] = c
        utxoset.apply(self.txn_data.txn, coins)

        self.app.notify(
            "Txn has been validated and changes saved to database. "
            "@todo network stuff"
        )
        self.app.log_event(
            f"Txn persisted to database: {txn.id}",
            "INFO"
        )

        self.dismiss()

