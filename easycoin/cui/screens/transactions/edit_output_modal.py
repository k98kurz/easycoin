from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Input, Footer
from easycoin.models import Address
from easycoin.cui.helpers import format_balance


class EditOutputModal(ModalScreen[dict|None]):
    """Modal for editing transaction outputs."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
            self, address: str | None = None, amount: int = 0, info=None,
            max_amount: int | None = None
        ):
        """Initialize edit output modal. The `info` parameter is passed
            through to the callback, e.g. an index/key for tracking the output.
        """
        super().__init__()
        self.address = address or ""
        self.amount = amount
        self.info = info
        self.max_amount = max_amount
        self.remaining_amount = max_amount or 0

    def on_mount(self) -> None:
        """Focus address input on mount."""
        self.query_one("#address_input").focus()

    def compose(self) -> ComposeResult:
        """Compose edit output modal layout."""
        with VerticalScroll(classes="modal-container w-60p"):
            title = "Edit Output" if self.address else "Add Output"
            yield Static(title, classes="modal-title")

            with Vertical():
                yield Static("Recipient Address:", classes="text-bold m-1")
                yield Input(
                    placeholder="Enter recipient address",
                    id="address_input",
                    value=self.address,
                    classes="form-input"
                )

            with Vertical():
                yield Static("Amount (EC⁻¹):", classes="text-bold my-1")
                yield Input(
                    placeholder="Enter amount", id="amount_input",
                    value=str(self.amount), classes="form-input"
                )
                if self.max_amount:
                    yield Static(
                        f"Max: {format_balance(self.max_amount, exact=True)}",
                        classes="my-1"
                    )
                    bal = format_balance(self.remaining_amount, exact=True)
                    yield Static(
                        f"Remaining: {bal}", id="remaining_amount", classes="my-1",
                    )

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    @on(Input.Changed, "#amount_input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "amount_input":
            return
        try:
            amount = int(event.value)
            if self.max_amount:
                self.remaining_amount = self.max_amount - amount
                self.query_one("#remaining_amount").update(
                    f"Remaining: {format_balance(self.remaining_amount, exact=True)}"
                )
        except ValueError:
            self.app.notify("Amount must be an integer", severity="warning")

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        """Save output and dismiss with result."""
        try:
            address_input = self.query_one("#address_input", Input)
            amount_input = self.query_one("#amount_input", Input)

            address = address_input.value.strip()
            amount_str = amount_input.value.strip()

            if not address:
                self.app.notify("Address is required", severity="error")
                return

            if not Address.validate(address):
                self.app.notify(
                    "Invalid address: address failed validation",
                    severity="warning"
                )
                return

            try:
                amount = int(amount_str)
                if amount <= 0:
                    self.app.notify("Amount must be positive", severity="error")
                    return
            except ValueError:
                self.app.notify("Invalid amount", severity="error")
                return

            if self.max_amount and amount > self.max_amount:
                self.app.notify(
                    f"Amount must be <= {self.max_amount}",
                    severity="warning"
                )
                return

            self.dismiss({
                'address': address,
                'amount': amount,
                'info': self.info
            })
        except Exception as e:
            self.app.notify(f"Error saving output: {e}", severity="error")
            self.app.log_event(f"Save output error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        await self.app.action_quit()
