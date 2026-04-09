from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option
from easycoin.helpers import truncate_text
from easycoin.models import Address, Wallet


class MineCoinModal(ModalScreen[dict|None]):
    """Modal for mining a single coin."""

    BINDINGS = [
        Binding("escape", "close", "Cancel"),
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("ctrl+q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose mine coin modal layout."""
        with VerticalScroll(classes="modal-container w-50p"):
            yield Static("Mine Coin", classes="modal-title")
            yield Static("Address:", classes="my-1")
            yield OptionList(id="address_selector")
            yield Input(
                placeholder="Enter address hex",
                id="custom_address_input",
                classes="hidden mt-1"
            )
            yield Static("Amount:", classes="my-1")
            yield OptionList(
                Option("1M EC⁻¹", id="amount_1m"),
                Option("500K EC⁻¹", id="amount_500k"),
                Option("100K EC⁻¹", id="amount_100k"),
                id="amount_selector"
            )
            with Horizontal(id="modal_actions", classes="mt-1"):
                yield Button("Mine", id="btn_mine", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize modal on mount."""
        self._populate_addresses()

    def _populate_addresses(self):
        """Populate address selector with wallet addresses."""
        options = []

        if self.app.wallet:
            try:
                self.app.wallet.addresses().reload()
                for address in self.app.wallet.addresses:
                    options.append(Option(
                        f"{truncate_text(address.hex)} "
                        f"({Wallet.get_lock_type(address.lock)})",
                        id=address.hex
                    ))
            except Exception as e:
                self.app.log_event(f"Error loading addresses: {e}", "ERROR")
                self.app.notify(f"Error loading addresses: {e}", severity="error")

        options.append(Option("Custom", id="custom"))

        address_selector = self.query_one("#address_selector")
        for option in options:
            address_selector.add_option(option)

    @on(OptionList.OptionHighlighted, "#address_selector")
    def _on_address_selected(self, event):
        """Show/hide custom address input based on selection."""
        if event.option.id == "custom":
            self.query_one("#custom_address_input").remove_class("hidden")
            self.query_one("#custom_address_input").focus()
        else:
            self.query_one("#custom_address_input").add_class("hidden")

    @on(Button.Pressed, "#btn_cancel")
    def action_close(self):
        """Cancel mining."""
        self.dismiss()

    @on(Button.Pressed, "#btn_mine")
    def action_mine(self):
        """Collect mining parameters and dismiss."""
        highlighted_option = self.query_one("#address_selector").highlighted_option
        if not highlighted_option:
            return self.app.notify("Must select an address", severity="warning")
        selected_addr = highlighted_option.id

        if selected_addr == "custom":
            custom_input = self.query_one("#custom_address_input")
            address_hex = custom_input.value.strip()
            if not address_hex:
                self.app.notify("Please enter a custom address", severity="error")
                return
            if not Address.validate(address_hex):
                self.app.notify("Invalid address", severity="error")
                return
            lock = Address.parse(address_hex)
        else:
            if not Address.validate(selected_addr):
                self.app.notify("Invalid address", severity="error")
                return
            address_hex = selected_addr

        amount_option = self.query_one("#amount_selector").highlighted_option.id
        amount_map = {
            "amount_1m": 1_000_000,
            "amount_500k": 500_000,
            "amount_100k": 100_000
        }
        amount = amount_map.get(amount_option, 500_000)

        self.dismiss({
            "address": address_hex,
            "amount": amount
        })
