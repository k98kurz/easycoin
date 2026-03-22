from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Static, Input
from textual.binding import Binding
from easycoin.cui.clipboard import universal_copy
from easycoin.models import Address


class ExportAddressModal(Screen):
    """Modal for exporting an address with optional password protection."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, address: Address):
        """Initialize export address modal."""
        super().__init__()
        self.address = address
        self.exported_hex = None

    def compose(self) -> ComposeResult:
        """Compose export address modal layout."""
        with Vertical(id="export_address_modal", classes="modal-container"):
            yield Static("Export Address", classes="modal-title")
            yield Static("\n")

            yield Static(f"Address: {self.address.hex}", classes="text-bold")
            yield Static("")

            yield Static(
                "Password (optional, encrypts secrets):\n",
                classes="text-bold"
            )
            yield Input(
                placeholder="Leave empty for no password",
                password=True,
                id="password_input"
            )

            yield Static("")
            yield Static("Exported Data:\n", classes="form-label")
            yield Static(
                "Click Export to generate",
                id="export_display",
                classes="text-muted"
            )
            yield Static("\n")
            yield Static("Filename:\n", classes="form-label")
            yield Input(
                placeholder="address_export.hex",
                id="file_input"
            )

            with Horizontal(id="export_actions"):
                yield Button("Export", id="btn_export", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")
                yield Button(
                    "Copy", id="btn_copy", variant="default", disabled=True
                )
                yield Button(
                    "Save to File",
                    id="btn_save_file",
                    variant="default",
                    disabled=True
                )


    def on_mount(self) -> None:
        """Focus password input on mount."""
        self.query_one("#password_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_export":
            self._do_export()
        elif event.button.id == "btn_cancel":
            self.app.pop_screen()
        elif event.button.id == "btn_copy":
            self._copy_to_clipboard()
        elif event.button.id == "btn_save_file":
            self._save_to_file()

    def action_cancel(self) -> None:
        """Action handler for Escape key."""
        self.app.pop_screen()

    def _do_export(self) -> None:
        """Export the address with optional password."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        if self.app.wallet.is_locked:
            self.app.notify("Wallet must be unlocked", severity="error")
            return

        try:
            password = self.query_one("#password_input", Input).value
            exported = self.app.wallet.export_address(
                self.address, password=password
            )
            self.exported_hex = exported.hex()
            self.query_one("#export_display", Static).update(
                self.exported_hex
            )
            self.query_one("#btn_copy", Button).disabled = False
            self.query_one("#btn_save_file", Button).disabled = False
            self.app.notify("Address exported", severity="success")
        except Exception as e:
            self.app.notify(f"Export failed: {e}", severity="error")
            self.app.log_event(f"Export address error: {e}", "ERROR")

    def _copy_to_clipboard(self) -> None:
        """Copy exported hex to clipboard."""
        if not self.exported_hex:
            self.app.notify("Nothing to copy", severity="warning")
            return

        try:
            universal_copy(self.exported_hex)
            self.app.notify("Copied to clipboard", severity="success")
        except Exception as e:
            self.app.notify(f"Failed to copy: {e}", severity="error")
            self.app.log_event(f"Copy error: {e}", "ERROR")

    def _save_to_file(self) -> None:
        """Save exported hex to a file."""
        if not self.exported_hex:
            self.app.notify("Nothing to save", severity="warning")
            return

        filename = self.query_one("#file_input", Input).value.strip()
        if not filename:
            self.app.notify("Enter a filename", severity="warning")
            return

        try:
            with open(filename, 'w') as f:
                f.write(self.exported_hex)
            self.app.notify(f"Saved to {filename}", severity="success")
        except Exception as e:
            self.app.notify(f"Save failed: {e}", severity="error")
            self.app.log_event(f"Save file error: {e}", "ERROR")

    def _truncate_address(self, address: str) -> str:
        """Truncate address for display."""
        return f"{address[:16]}...{address[-8:]}"
