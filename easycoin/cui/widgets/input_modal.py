from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Footer


class InputModal(ModalScreen[str|None]):
    """General purpose input modal."""

    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
            self, title: str, description: str, *,
            is_password: bool = False, btn_text: str = "Submit",
            value: str = ""
        ):
        """Initialize."""
        super().__init__()
        self.title = title
        self.description = description
        self.is_password = is_password
        self.btn_text = btn_text
        self.value = value

    def compose(self) -> ComposeResult:
        """Compose unlock modal layout."""
        with Vertical(id="input_modal", classes="modal-container w-50p"):
            yield Static(self.title, classes="modal-title")
            yield Static("\n")
            yield Static(self.description)
            yield Static("\n")
            yield Input(
                placeholder="...",
                password=self.is_password,
                id="input",
                value=self.value,
            )

            with Horizontal(id="modal_actions"):
                yield Button(self.btn_text, id="btn_submit", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="default")
            yield Static("")
        yield Footer()

    @on(Button.Pressed, "#btn_submit")
    def action_submit(self) -> None:
        """Submits the user input to the modal caller."""
        val = self.query_one("#input").value
        self.dismiss(val)

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Dismisses the modal without user input."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        await self.app.action_quit()
