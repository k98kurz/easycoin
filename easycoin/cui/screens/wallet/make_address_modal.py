from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button, Static, OptionList, Input, Checkbox, Footer, TextArea
)
from textual.widgets.option_list import Option
from tapescript import Script, make_scripthash_lock


class MakeAddressModal(Screen):
    """Modal for creating new addresses with different types."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    ADDRESS_TYPES = [
        ("P2PK", "Pay to Public Key"),
        ("P2PKH", "Pay to Public Key Hash"),
        ("P2TR", "Pay to Taproot"),
        ("P2GR", "Pay to Graftroot"),
        ("P2GT", "Pay to Graftap (GR-in-TR)"),
        ("P2SH", "Pay to Script Hash"),
        ("Custom", "Custom"),
    ]

    CSS = "MakeAddressModal { background: $background 50%; }"

    def __init__(self, success_callback=None):
        """Initialize make address modal."""
        super().__init__()
        self.success_callback = success_callback
        self.selected_type = "P2PK"
        self.custom_script_src = None
        self.default_script_src = 'false'
        self.script_error = None
        self.child_nonce_enabled = False
        self.current_child_nonce = None
        self.address = None

    def compose(self) -> ComposeResult:
        """Compose make address modal layout."""
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static("Make Address", classes="modal-title")

            with Horizontal(classes="h-11 mt-1"):
                with Vertical():
                    yield Static("Address Type:", classes="text-bold mb-1")
                    yield OptionList(
                        *[
                            Option(
                                f"{name}: {description}",
                                id=name
                            ) for name, description in self.ADDRESS_TYPES
                        ],
                        id="address_type_selector",
                    )

                with Vertical():
                    yield Static("Use child nonce:", classes="text-bold mb-1")
                    yield Checkbox(id="use_child_nonce")


            with Horizontal(classes="h-5 mt-1"):
                with Vertical():
                    yield Static("Nonce:", classes="text-bold mb-1")
                    yield Static("Loading...", id="nonce_display")

                with Vertical():
                    yield Static("Child nonce:", classes="text-bold mb-1")
                    yield Input(
                        placeholder="Enter child nonce int",
                        id="child_nonce_input",
                        classes="hidden"
                    )

            with Vertical(id="custom_container", classes="hidden h-5 mt-1"):
                yield Static("Custom Script:", classes="text-bold mb-1")
                yield TextArea( "", id="custom_script")

            with Vertical(classes="mt-1 h-auto"):
                yield Static("Locking Script:", classes="text-bold mb-1")
                yield Static(
                    "Generating...", markup=False,
                    id="lock_script_display",
                    classes="text-muted"
                )

            with Vertical(classes="h-3 my-1"):
                yield Static("Address:", classes="text-bold mb-1")
                yield Static(
                    "Generating...",
                    id="address_display",
                    classes="text-bold"
                )

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize preview on mount."""
        self._update_preview()
        self.query_one("#address_type_selector").focus()

    def on_option_list_option_highlighted(
            self, event: OptionList.OptionHighlighted
        ) -> None:
        """Handle address type selection."""
        self.selected_type = event.option.id
        if self.selected_type in ("P2TR", "P2SH", "Custom"):
            self.query_one("#custom_container").remove_class("hidden")
        else:
            self.query_one("#custom_container").add_class("hidden")
        self._update_preview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle child nonce checkbox toggle."""
        if event.checkbox.id == "use_child_nonce":
            self.child_nonce_enabled = event.checkbox.value
            child_nonce_input = self.query_one("#child_nonce_input", Input)
            if self.child_nonce_enabled:
                child_nonce_input.remove_class("hidden")
                child_nonce_input.focus()
            else:
                child_nonce_input.add_class("hidden")
                child_nonce_input.value = ""
                self.current_child_nonce = None
            self._update_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle child nonce input changes."""
        if event.input.id == "child_nonce_input":
            self.current_child_nonce = None
            if event.input.value.strip():
                try:
                    self.current_child_nonce = int(event.input.value.strip())
                except ValueError:
                    pass
            self._update_preview()

    @on(TextArea.Changed, "#custom_script")
    def on_custom_script_changed(self, event: TextArea.Changed) -> None:
        """Handle custom script input changes."""
        self.custom_script_src = event.text_area.text.strip()
        self._update_preview()

    @on(Button.Pressed, "#btn_save")
    def action_save_address(self) -> None:
        """Create and save the address, then increment wallet nonce
            if no child nonce was used.
        """
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        if self.app.wallet.is_locked:
            self.app.notify("Wallet must be unlocked", severity="error")
            return

        if not self.address:
            self.app.notify("No address generated", severity="error")
            return

        try:
            self.address.save()

            custom_type_used = self.selected_type == "Custom"
            child_nonce_used = (
                self.child_nonce_enabled and
                self.current_child_nonce is not None
            )

            if not (child_nonce_used or custom_type_used):
                self.app.wallet.nonce = self.app.wallet.nonce + 1
                self.app.wallet.save()

            self.app.pop_screen()
            if self.success_callback:
                self.app.call_later(self.success_callback)
        except Exception as e:
            self.app.notify(f"Error saving address: {e}", severity="error")
            self.app.log_event(f"Save address error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Action handler for Escape key."""
        self.app.pop_screen()

    def _update_preview(self) -> None:
        """Recalculate Address and update the preview display based on
            selected address type.
        """
        if not self.app.wallet:
            return

        if self.app.wallet.is_locked:
            self.query_one("#nonce_display", Static).update("-")
            self.query_one("#lock_script_display", Static).update(
                "Wallet must be unlocked"
            )
            self.query_one("#address_display", Static).update("-")
            self.query_one("#btn_save", Button).disabled = True
            return

        nonce = self.app.wallet.nonce
        self.query_one("#nonce_display", Static).update(str(nonce))

        lock = None
        committed_script = None
        self.script_error = None
        if self.selected_type == "P2PK":
            lock = self.app.wallet.get_p2pk_lock(
                nonce, child_nonce=self.current_child_nonce
            )
        elif self.selected_type == "P2PKH":
            lock = self.app.wallet.get_p2pkh_lock(
                nonce, child_nonce=self.current_child_nonce
            )
        elif self.selected_type == "P2TR":
            self.default_script_src = f'push d{nonce} false return' 
            lock, committed_script = None, None
            script_src = self.custom_script_src
            if not self.custom_script_src:
                self.query_one("#custom_script").placeholder = self.default_script_src
            else:
                try:
                    committed_script = Script.from_src(
                        self.custom_script_src
                    )
                except BaseException as e:
                    self.script_error = f"{type(e).__name__}: {e}"
                    committed_script = None

            lock = self.app.wallet.get_p2tr_lock(
                nonce, script=committed_script,
                child_nonce=self.current_child_nonce
            )
        elif self.selected_type == "P2GR":
            lock = self.app.wallet.get_p2gr_lock(
                nonce, child_nonce=self.current_child_nonce
            )
        elif self.selected_type == "P2GT":
            lock = self.app.wallet.get_p2gt_lock(
                nonce, child_nonce=self.current_child_nonce
            )
            committed_script = self.app.wallet.get_p2gt_committed_script(
                nonce, child_nonce=self.current_child_nonce
            )
            self.app.log_event(
                f"make P2GT: {lock.src=} {committed_script.src=}",
                "DEBUG"
            )
        else:  # P2SH and Custom
            lock = None
            self.query_one("#custom_script").placeholder = "..."
            if not self.custom_script_src:
                self.script_error = (
                    f"Custom script required for {self.selected_type} address type"
                )
            else:
                try:
                    lock = Script.from_src(self.custom_script_src)
                    if self.selected_type == "P2SH":
                        lock = make_scripthash_lock(lock)

                except BaseException as e:
                    self.script_error = f"{type(e).__name__}: {e}"
                    lock = None

        if self.script_error:
            self.query_one("#lock_script_display").update(
                self.script_error
            )
            self.query_one("#address_display", Static).update("-")
            self.query_one("#btn_save", Button).disabled = True
            return

        self.query_one("#lock_script_display").update(lock.src)

        try:
            secrets = None
            if self.selected_type == "P2GT":
                secrets = {"P2GT": True}
            if self.selected_type in ("P2TR", "P2SH") and not committed_script:
                committed_script = Script.from_src(self.default_script_src)
            address = self.app.wallet.make_address(
                lock, nonce, committed_script=committed_script, secrets=secrets
            )
            address.child_nonce = self.current_child_nonce
        except Exception as e:
            self.query_one("#address_display", Static).update(
                "Error generating address"
            )
            self.app.log_event(f"Error generating address: {e}", "DEBUG")
            return

        self.address = address
        self.query_one("#address_display", Static).update(address.hex)
        self.query_one("#btn_save", Button).disabled = False

