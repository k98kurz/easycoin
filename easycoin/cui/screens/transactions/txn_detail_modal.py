from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Footer


class TransactionDetailModal(ModalScreen):
    """Modal for viewing transaction details."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, txn_id: str):
        """Initialize transaction detail modal."""
        super().__init__()
        self.txn_id = txn_id

    def compose(self) -> ComposeResult:
        """Compose transaction detail modal layout."""
        with VerticalScroll(id="txn_detail_modal", classes="modal-container w-80p"):
            yield Static("Transaction Details", classes="modal-title")
            yield Static("\n")
            yield Static(f"Transaction ID: {self.txn_id}", classes="text-bold")
            yield Static("")
            yield Static(
                "[bold]Transaction Detail Modal[/bold]\n\n"
                "This modal is not yet implemented.\n\n"
                "It will display:\n"
                "- Input/output coin details\n"
                "- Witness scripts\n"
                "- Raw transaction data (hex view)\n"
                "- Transfer history for stamps\n"
                "- Validation status",
                classes="text-center"
            )

            with Horizontal(id="modal_actions"):
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Set initial focus."""
        pass

    @on(Button.Pressed, "#btn_close")
    def action_close(self, event: Button.Pressed | None = None) -> None:
        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()
