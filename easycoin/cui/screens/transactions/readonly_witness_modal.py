from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Footer
from tapescript import Script
from easycoin.helpers import format_balance, format_amount, truncate_text
from easycoin.cui.widgets import ECTextArea, CoinDetailModal
from easycoin.models import Address, Coin
import packify


class ReadOnlyWitnessModal(ModalScreen):
    """Modal for viewing witness scripts (read-only)."""

    BINDINGS = [
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("v", "view_coin", "View Coin"),
    ]

    def __init__(self, coin: Coin, witness_bytes: bytes):
        super().__init__()
        self.coin = coin
        self.witness_bytes = witness_bytes
        self.witness_script = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-container w-80p"):
            yield Static("Witness Details", classes="modal-title")

            with Vertical(classes="h-4 my-1"):
                yield Static("Input Details:", classes="text-bold")
                yield Static("...", id="input_info", classes="text-muted")
                yield Static("...", id="stamp_info1", classes="text-muted")
                yield Static("...", id="stamp_info2", classes="text-muted hidden")

            with Vertical(classes="h-3 mb-1"):
                yield Static("Address:", classes="text-bold")
                yield Static(
                    "...", id="address_hex", classes="text-muted"
                )

            with Horizontal(classes="h-11 my-1"):
                with Vertical():
                    yield Static("Decompiled Lock", classes="text-bold mb-1")
                    yield ECTextArea(
                        id="decompiled_lock", read_only=True, classes="h-8"
                    )
                with Vertical(id="committed_script_section", classes="hidden"):
                    yield Static("Committed Script", classes="text-bold mb-1")
                    yield ECTextArea(
                        id="decompiled_committed_script",
                        read_only=True, classes="h-8"
                    )

            with Vertical(id="witness_script_section", classes="hidden my-1 h-10"):
                yield Static("Witness Script", classes="text-bold mb-1")
                yield ECTextArea(
                    id="witness_script_textarea",
                    read_only=True,
                    classes="h-8"
                )

            with Horizontal(id="modal_actions"):
                yield Button("Close", id="btn_close", variant="default")
                yield Button("View Coin", id="btn_view_coin")

        yield Footer()

    def on_mount(self) -> None:
        self._update_ui()

    def _update_ui(self) -> None:
        amount_str = format_balance(
            self.coin.amount, exact=True
        )
        self.query_one("#input_info").update(
            f"Amount: {amount_str} | ID: {self.coin.id}"
        )

        stamp_size = len(self.coin.data.get('details', None) or b'')
        stamp_type = self.coin.details.get('d', {}).get('type', 'N/A')
        stamp_name = None
        if stamp_type in ('token', 'file'):
            stamp_name = self.coin.details.get('d', {}).get('name', 'N/A')
        if stamp_type == 'file':
            stamp_name += ' (is a file)'
        self.query_one("#stamp_info1").update(
            f"Stamp Size: {format_amount(stamp_size)}B | Stamp Type: {stamp_type}"
        )
        if stamp_name:
            si2 = self.query_one("#stamp_info2")
            si2.remove_class("hidden")
            si2.update(f"Stamp Name: {stamp_name}")

        address = Address({"lock": self.coin.lock})
        self.query_one("#address_hex").update(address.hex)

        decompiled = Script.from_bytes(self.coin.lock).src
        self.query_one("#decompiled_lock").text = decompiled

        if address.committed_script:
            self.query_one("#committed_script_section").remove_class("hidden")
            committed_script = Script.from_bytes(address.committed_script)
            self.query_one("#decompiled_committed_script").text = \
                committed_script.src
        else:
            self.query_one("#committed_script_section").add_class("hidden")

        if self.witness_bytes:
            self.query_one("#witness_script_section").remove_class("hidden")
            self.witness_script = Script.from_bytes(self.witness_bytes)
            self.query_one("#witness_script_textarea").text = \
                self.witness_script.src
        else:
            self.query_one("#witness_script_section").add_class("hidden")

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#btn_view_coin")
    def action_view_coin(self) -> None:
        modal = CoinDetailModal(self.coin)
        self.app.push_screen(modal)

    async def action_quit(self) -> None:
        await self.app.action_quit()
