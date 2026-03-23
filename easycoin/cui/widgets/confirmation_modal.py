from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button


class ConfirmationModal(ModalScreen):
    """General purpose confirmation modal dialog."""

    def __init__(
            self, title: str, message: str, *,
            confirm_btn_variant="success", confirm_btn_classes="",
            cancel_btn_variant="default", cancel_btn_classes="",
        ):
        """Initialize confirmation modal."""
        super().__init__()
        self.title = title
        self.message = message
        self.confirm_btn_variant = confirm_btn_variant
        self.confirm_btn_classes = confirm_btn_classes
        self.cancel_btn_variant = cancel_btn_variant
        self.cancel_btn_classes = cancel_btn_classes

    def compose(self) -> ComposeResult:
        """Compose confirmation modal layout."""
        with Vertical(id="confirm_modal", classes="modal-container"):
            yield Static(self.title, classes="modal-title")
            yield Static("\n")
            yield Static(self.message)
            with Horizontal(id="modal_actions"):
                yield Button(
                    "Confirm", id="btn_confirm", variant=self.confirm_btn_variant,
                    classes=self.confirm_btn_classes,
                )
                yield Button(
                    "Cancel", id="btn_cancel", variant=self.cancel_btn_variant,
                    classes=self.cancel_btn_classes,
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_confirm":
            self.dismiss(True)
        elif event.button.id == "btn_cancel":
            self.dismiss(False)
