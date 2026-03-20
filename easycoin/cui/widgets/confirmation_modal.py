from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button


class ConfirmationModal(Screen):
    """General purpose confirmation modal dialog."""

    def __init__(self, title: str, message: str, callback=None):
        """Initialize confirmation modal.

        Args:
            title: Modal title text
            message: Confirmation message/question
            callback: Optional callback to call on confirm
        """
        super().__init__()
        self.title = title
        self.message = message
        self.callback = callback

    def compose(self) -> ComposeResult:
        """Compose confirmation modal layout."""
        with Vertical(id="confirm_modal", classes="modal-container"):
            yield Static(self.title, classes="modal-title")
            yield Static(self.message)
            with Horizontal(id="modal_actions"):
                yield Button("Confirm", id="btn_confirm", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_confirm":
            if self.callback:
                self.callback()
            self.app.pop_screen()
        elif event.button.id == "btn_cancel":
            self.app.pop_screen()
