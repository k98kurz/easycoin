from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Footer


class NewTransactionModal(ModalScreen):
    """Modal for creating new transactions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        """Compose send transaction modal layout."""
        with VerticalScroll(id="new_txn_modal", classes="modal-container w-70p"):
            yield Static("New Transaction", classes="modal-title")
            yield Static("\n")
            yield Static(
                "[bold]New Transaction Modal[/bold]\n\n"
                "This modal is not yet implemented.\n\n"
                "It will provide:\n"
                "- Select inputs\n"
                "- Add outputs\n"
                "- Add stamp (optional)\n"
                "- Review and submit",
                classes="text-center"
            )

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self, event: Button.Pressed | None = None) -> None:
        self.dismiss()
