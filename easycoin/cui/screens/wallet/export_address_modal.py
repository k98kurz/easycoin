from textual import on
from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal, ItemGrid
from textual.widgets import Button, Static, Input, Footer, Checkbox
from textual.binding import Binding
from easycoin.cui.widgets import ECTextArea
from tapescript import Script
from easycoin.cui.clipboard import universal_copy
from easycoin.models import Address
import packify


class ExportAddressModal(Screen):
    """Modal for exporting an address with optional password protection."""

    BINDINGS = [
        Binding("x", "export", "Export"),
        Binding("c", "copy_to_clipboard", "Copy to Clipboard"),
        Binding("s", "save_to_file", "Save to File"),
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
        ExportAddressModal { background: $background 50%; }
    """

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
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static("View/Export Address", classes="modal-title")

            yield Static(f"Address: {self.address.hex}", classes="text-bold mt-1")

            with Horizontal(id="secrets_container", classes="mt-1 h-8"):
                with Vertical(classes="h-7 w-20p"):
                    yield Static(
                        "Nonce: ...", id="nonce_display", classes="mb-1"
                    )
                    yield Static(
                        "Child nonce: ", id="child_nonce_display",
                        classes="mb-1"
                    )
                    yield Checkbox(
                        "Show Secrets", id="show_secrets_checkbox", value=False
                    )
                yield ECTextArea(
                    "", read_only=True, show_line_numbers=False, soft_wrap=True,
                    id="secrets_display", classes="hidden",
                )

            with Horizontal(classes="mt-1 h-10"):
                with Vertical():
                    yield Static("Lock (Decompiled):\n", classes="text-bold")
                    yield ECTextArea(
                        self.decompiled_lock, read_only=True,
                        show_line_numbers=False, soft_wrap=True,
                        id="lock_display", classes="h-8"
                    )
                with Vertical(id="committed_script_container", classes="hidden"):
                    yield Static(
                        "Committed Script (Decompiled):\n", classes="text-bold"
                    )
                    yield ECTextArea(
                        "", read_only=True, show_line_numbers=False,
                        soft_wrap=True, id="committed_script_display",
                        classes="h-8"
                    )

            yield Static("Exported Data:\n", classes="text-bold mt-1")
            yield Static(
                "Click Export to generate",
                id="export_display",
                classes="text-muted"
            )

            with Horizontal(classes="h-min-5 mt-1"):
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
                    yield Static("Filename:\n", classes="text-bold")
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

    def on_mount(self):
        self.query_one("#nonce_display").update(f"Nonce: {self.address.nonce}")
        self.query_one("#child_nonce_display").update(
            f"Child nonce: {self.address.child_nonce}"
        )
        if self.address.committed_script:
            self.query_one("#committed_script_container").remove_class("hidden")
            self.query_one("#committed_script_display").text = (
                Script.from_bytes(self.address.committed_script).src
            )

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

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle Show Secrets checkbox toggle."""
        if event.checkbox.id == "show_secrets_checkbox":
            secrets_container = self.query_one("#secrets_container")
            secrets_display = self.query_one("#secrets_display")

            if event.value:
                secrets_container.remove_class("h-8")
                secrets_container.add_class("h-10")
                secrets_display.remove_class("hidden")
                self._populate_secrets()
            else:
                secrets_container.remove_class("h-10")
                secrets_container.add_class("h-8")
                secrets_display.add_class("hidden")

    def _populate_secrets(self) -> None:
        """Decrypt and display address secrets."""
        secrets_display = self.query_one("#secrets_display")

        if not self.app.wallet:
            secrets_display.text = "Wallet not available"
            return

        if self.app.wallet.is_locked:
            secrets_display.text = ("Wallet must be unlocked to view secrets")
            return

        if not self.address.secrets:
            secrets_display.text = ("No secrets available for this address")
            return

        try:
            decrypted = self.app.wallet.decrypt(self.address.secrets)
        except Exception as e:
            secrets_display.text = (f"Failed to decrypt secrets: {e}")
            return

        try:
            unpacked = packify.unpack(decrypted)
            secrets_display.text = (str(unpacked))
        except Exception:
            try:
                secrets_display.text = (decrypted.decode('utf-8'))
            except Exception:
                secrets_display.text = (decrypted.hex())
