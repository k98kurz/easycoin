from textual import on
from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal, ItemGrid
from textual.widgets import Button, Static, Input, TextArea, Footer
from textual.binding import Binding
from tapescript import Script
from easycoin.cui.clipboard import universal_copy
from easycoin.models import Address


class ExportAddressModal(Screen):
    """Modal for exporting an address with optional password protection."""

    BINDINGS = [
        Binding("x", "export", "Export"),
        Binding("c", "copy_to_clipboard", "Copy to Clipboard"),
        Binding("s", "save_to_file", "Save to File"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, address: Address):
        """Initialize export address modal."""
        super().__init__()
        self.address = address
        self.exported_hex = None

        try:
            self.decompiled_lock = Script.from_bytes(address.lock).src
        except Exception:
            self.decompiled_lock = "Error decompiling lock"

    def compose(self) -> ComposeResult:
        """Compose export address modal layout."""
        with VerticalScroll(id="export_address_modal", classes="modal-container"):
            yield Static("View/Export Address", classes="modal-title")
            yield Static("")

            yield Static(f"Address: {self.address.hex}", classes="text-bold")
            yield Static("")
            yield Static("Lock (Decompiled):\n", classes="form-label")
            yield TextArea(
                self.decompiled_lock, read_only=True, show_line_numbers=False,
                soft_wrap=True, id="lock_display", classes="h-10"
            )
            yield Static("")

            yield Static("Exported Data:\n", classes="form-label")
            yield Static(
                "Click Export to generate",
                id="export_display",
                classes="text-muted"
            )
            yield Static("")

            with Horizontal(classes="h-min-5"):
                with Vertical():
                    yield Static(
                        "Password (optional):\n",
                        classes="text-bold"
                    )
                    yield Input(
                        placeholder="Leave empty to export secrets unencrypted",
                        password=True,
                        id="password_input"
                    )
                with Vertical():
                    yield Static("Filename:\n", classes="form-label")
                    yield Input(
                        placeholder="address_export.hex",
                        id="file_input"
                    )

            with ItemGrid(id="modal_actions", min_column_width=18):
                yield Button("Export", id="btn_export", variant="primary")
                yield Button(
                    "Copy", id="btn_copy", variant="default", disabled=True
                )
                yield Button(
                    "Save to File",
                    id="btn_save_file",
                    variant="default",
                    disabled=True
                )
                yield Button("Cancel", id="btn_cancel", variant="default")
        yield Footer()

    @on(Button.Pressed, "#btn_export")
    def action_export(self) -> None:
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
        except ValueError as e:
            self.app.notify(f"Export failed: {e}", severity="error")
            self.app.log_event(f"Export address error: {e}", "ERROR")
            return
        except Exception as e:
            self.app.notify(f"Export failed: {e}", severity="error")
            self.app.log_event(f"Export address error: {e}", "ERROR")
            return

        self.exported_hex = exported.hex()
        self.query_one("#export_display", Static).update(
            self.exported_hex
        )
        self.query_one("#btn_copy", Button).disabled = False
        self.query_one("#btn_save_file", Button).disabled = False

    @on(Button.Pressed, "#btn_copy")
    def action_copy_to_clipboard(self) -> None:
        """Copy exported hex to clipboard."""
        if not self.exported_hex:
            self.app.notify("Nothing to copy; must export first", severity="warning")
            return

        try:
            universal_copy(self.exported_hex)
            self.app.notify("Copied to clipboard", severity="success")
        except Exception as e:
            self.app.notify(f"Failed to copy: {e}", severity="error")
            self.app.log_event(f"Copy error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_save_file")
    def action_save_to_file(self) -> None:
        """Save exported hex to a file."""
        if not self.exported_hex:
            self.app.notify("Nothing to save; must export first", severity="warning")
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

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Action handler for Escape key."""
        self.app.pop_screen()

    def _truncate_address(self, address: str) -> str:
        """Truncate address for display."""
        return f"{address[:16]}...{address[-8:]}"
