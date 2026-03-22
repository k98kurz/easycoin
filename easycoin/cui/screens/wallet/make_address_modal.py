from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Static, OptionList
from textual.widgets.option_list import Option
from textual.binding import Binding
from tapescript import Script


class MakeAddressModal(Screen):
    """Modal for creating new addresses with different types."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    ADDRESS_TYPES = [
        ("P2PK", "Pay to Public Key"),
        ("P2PKH", "Pay to Public Key Hash"),
        ("P2TR", "Pay to Taproot"),
    ]

    def __init__(self):
        """Initialize make address modal."""
        super().__init__()
        self.selected_type = "P2PK"
        self.current_lock = None
        self.current_committed_script = None

    def compose(self) -> ComposeResult:
        """Compose make address modal layout."""
        with Vertical(id="make_address_modal", classes="modal-container"):
            yield Static("Make Address", classes="modal-title")
            yield Static("\n")

            yield Static("Address Type:", classes="form-label")
            yield OptionList(
                *[Option(f"{name}: {description}", id=name) for name, description in self.ADDRESS_TYPES],
                id="address_type_selector"
            )

            yield Static("\n")
            yield Static("Nonce:", classes="form-label")
            yield Static("Loading...", id="nonce_display")
            yield Static("\n")

            yield Static("Locking Script:", classes="form-label")
            yield Static("Generating...", id="lock_script_display", classes="text-muted")
            yield Static("\n")

            yield Static("Address:", classes="form-label")
            yield Static("Generating...", id="address_display", classes="text-bold")
            yield Static("\n")

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

    def on_mount(self) -> None:
        """Initialize preview on mount."""
        self._update_preview()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle address type selection."""
        self.selected_type = event.option.id
        self._update_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_save":
            self._save_address()
        elif event.button.id == "btn_cancel":
            self.app.pop_screen()

    def action_cancel(self) -> None:
        """Action handler for Escape key."""
        self.app.pop_screen()

    def _update_preview(self) -> None:
        """Update the preview display based on selected address type."""
        if not self.app.wallet:
            return

        if self.app.wallet.is_locked:
            self.query_one("#nonce_display", Static).update("-")
            self.query_one("#lock_script_display", Static).update(
                "Wallet must be unlocked"
            )
            self.query_one("#address_display", Static).update("-")
            return

        try:
            nonce = self.app.wallet.nonce
            self.query_one("#nonce_display", Static).update(str(nonce))

            committed_script = None
            if self.selected_type == "P2PK":
                lock = self.app.wallet.get_p2pk_lock(nonce)
            elif self.selected_type == "P2PKH":
                lock = self.app.wallet.get_p2pkh_lock(nonce)
            elif self.selected_type == "P2TR":
                committed_script = Script.from_src("OP_TRUE")
                lock = self.app.wallet.get_p2tr_lock(
                    nonce, script=committed_script
                )
            else:
                return

            self.current_lock = lock
            self.current_committed_script = committed_script

            try:
                self.query_one("#lock_script_display", Static).update(lock.src)
            except Exception as e:
                self.app.log_event(f"Error updating lock script: {e}", "DEBUG")

            try:
                address = self.app.wallet.make_address(
                    lock, nonce, committed_script=committed_script
                )
                self.query_one("#address_display", Static).update(address.hex)
            except Exception as e:
                self.query_one("#address_display", Static).update(
                    "Error generating address"
                )
                self.app.log_event(f"Error generating address: {e}", "DEBUG")

        except Exception as e:
            self.app.notify(f"Error updating preview: {e}", severity="error")
            self.app.log_event(f"Make address preview error: {e}", "ERROR")

    def _save_address(self) -> None:
        """Create and save the address, then increment wallet nonce."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        if self.app.wallet.is_locked:
            self.app.notify("Wallet must be unlocked", severity="error")
            return

        if not self.current_lock:
            self.app.notify("No lock generated", severity="error")
            return

        try:
            nonce = self.app.wallet.nonce
            address = self.app.wallet.make_address(
                self.current_lock, nonce,
                committed_script=getattr(self, 'current_committed_script', None)
            )
            address.save()

            self.app.wallet.nonce = nonce + 1
            self.app.wallet.save()

            truncated = f"{address.hex[:16]}..."
            self.app.notify(f"Address saved: {truncated}", severity="success")
            self.app.pop_screen()
        except Exception as e:
            self.app.notify(f"Error saving address: {e}", severity="error")
            self.app.log_event(f"Save address error: {e}", "ERROR")
