from textual import on
from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Static, Input
from textual.binding import Binding


class ImportAddressModal(Screen):
    """Modal for importing an address from hex data."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
        ImportAddressModal { background: $background 50%; }
    """

    def __init__(self, success_callback=None):
        """Initialize import address modal."""
        super().__init__()
        self.success_callback = success_callback

    def compose(self) -> ComposeResult:
        """Compose import address modal layout."""
        with Vertical(classes="modal-container w-70p"):
            yield Static("Import Address", classes="modal-title")
            yield Static("\n")

            yield Static("Address hex:\n", classes="form-label")
            yield Input(
                placeholder="Enter address hex data",
                id="address_input"
            )
            yield Static("")

            yield Static(
                "Password (required if address was exported with one):\n",
                classes="text-bold"
            )
            yield Input(
                placeholder="Leave empty if address secrets were not "
                    "password-protected",
                password=True,
                id="password_input"
            )

            with Horizontal(id="import_actions"):
                yield Button("Import", id="btn_import", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

    def on_mount(self) -> None:
        """Focus address input on mount."""
        self.query_one("#address_input", Input).focus()

    def action_cancel(self) -> None:
        """Action handler for Escape key."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn_import")
    def _do_import(self) -> None:
        """Import the address from hex data."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        if self.app.wallet.is_locked:
            self.app.notify("Wallet must be unlocked", severity="error")
            return

        hex_data = self.query_one("#address_input", Input).value.strip()
        if not hex_data:
            self.app.notify("Enter address hex data", severity="warning")
            return

        try:
            data = bytes.fromhex(hex_data)
            password = self.query_one("#password_input", Input).value
            address = self.app.wallet.import_address(data, password=password)
            address.save()
            self.app.notify("Address imported", severity="success")
            self.app.pop_screen()
            if self.success_callback:
                self.app.call_later(self.success_callback)
        except ValueError as e:
            self.app.notify(f"Import failed: {e}", severity="error")
            self.app.log_event(f"Import address error: {e}", "ERROR")
        except Exception as e:
            self.app.notify(f"Import failed: {e}", severity="error")
            self.app.log_event(f"Import address error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_cancel")
    def _cancel(self) -> None:
        """Cancel import and close modal."""
        self.app.pop_screen()
