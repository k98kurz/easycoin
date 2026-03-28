from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static, Footer, TextArea
from tapescript import Script
from easycoin.cui.helpers import format_balance, truncate_text
from easycoin.cui.screens.transactions.new_txn.data import TransactionData
from easycoin.cui.widgets import ECTextArea
from easycoin.models import Address, Output, Wallet


class EditWitnessModal(ModalScreen[bool|None]):
    """Modal for editing witness scripts for transaction inputs."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, output: Output, txn_data: TransactionData):
        super().__init__()
        self.output = output
        self.txn_data = txn_data
        self.lock_type = "Unknown"
        self.is_known = False
        self.requires_custom = True
        self.address = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-container w-80p"):
            yield Static("Edit Witness", classes="modal-title")

            with Vertical(classes="h-3 my-1"):
                yield Static("Input Details:", classes="text-bold")
                truncated_id = truncate_text(
                    self.output.id, prefix_len=8, suffix_len=4
                )
                amount_str = format_balance(
                    self.output.coin.amount, exact=True
                )
                lock_type = Wallet.get_lock_type(self.output.coin.lock)
                yield Static(
                    f"ID: {truncated_id} | Amount: {amount_str} | "
                    f"Lock Type: {lock_type}",
                    classes="text-muted"
                )

            with Vertical(classes="h-3 mb-1"):
                yield Static("Address:", classes="text-bold")
                yield Static(
                    "...", id="address_hex", classes="text-muted"
                )
                yield Static(
                    "...",
                    id="address_known_status",
                    classes="text-muted"
                )

            with Vertical():
                yield Static("Decompiled Lock", classes="text-bold my-1")
                yield ECTextArea(
                    id="decompiled_lock", read_only=True, classes="h-8"
                )

            with Horizontal(classes="h-12"):
                with Vertical(id="generate_witness_section", classes="hidden"):
                    with Horizontal(classes="h-4"):
                        yield Button(
                            "Generate",
                            id="btn_generate",
                        )
                        yield Checkbox(
                            "Script spend",
                            id="box_script_spend",
                            classes="hidden mt-1",
                        )
                    yield ECTextArea(
                        "",
                        id="generated_witness_textarea",
                        placeholder="Generated witness will go here",
                        read_only=True,
                        classes="h-6 mt-1"
                    )

                with Vertical(id="custom_script_section", classes="hidden"):
                    yield Static(
                        "Custom Witness Script:", classes="text-bold my-1"
                    )
                    yield ECTextArea(
                        "",
                        id="custom_witness_textarea",
                        placeholder="Enter tapescript source",
                        classes="h-8"
                    )
                    yield Static(
                        "Provide a valid tapescript witness script to "
                        "authorize spending this input.",
                        classes="text-muted mt-1"
                    )

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        self._check_lock()
        self._update_ui()

    def _check_lock(self) -> None:
        if not self.app.wallet or self.app.wallet.is_locked:
            self.app.notify("WALLET IS NOT UNLOCKED??? How did you get here???")
            self.is_known = False
            return

        self.address = Address({"lock": self.output.coin.lock}).hex
        self.lock_type = Wallet.get_lock_type(self.output.coin.lock)
        for addr in self.app.wallet.addresses:
            if addr.lock == self.output.coin.lock:
                self.is_known = True
                if self.lock_type not in ("P2SH", "Unknown"):
                    self.requires_custom = False
                return

    def _update_ui(self) -> None:
        addr_display = self.query_one("#address_hex").update(self.address)
        decompiled = Script.from_bytes(self.output.coin.lock).src
        self.query_one("#decompiled_lock").text = decompiled

        if self.is_known:
            self.query_one("#address_known_status").update("From wallet")
        else:
            self.query_one("#address_known_status").update("Not from wallet")

        if self.lock_type != "Unknown":
            self.query_one("#generate_witness_section").remove_class("hidden")
            if self.output.id in self.txn_data.witness_scripts:
                self.query_one("#generated_witness_textarea").text = (
                    self.txn_data.witness_scripts[self.output.id].src
                )
        else:
            self.query_one("#generate_witness_section").add_class("hidden")

        if self.lock_type in ("P2TR", "P2GR", "P2GT"):
            self.query_one("#box_script_spend").remove_class("hidden")
        else:
            self.query_one("#box_script_spend").add_class("hidden")

        if self.requires_custom:
            self.query_one("#custom_script_section").remove_class("hidden")
            if self.output.id in self.txn_data.witness_scripts:
                self.query_one("#custom_witness_textarea").text = (
                    self.txn_data.witness_scripts[self.output.id].src
                )
            self.query_one("#custom_witness_textarea").focus()
        else:
            self.query_one("#custom_script_section").add_class("hidden")

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        text_area = self.query_one("#custom_witness_textarea")
        witness_src = text_area.text.strip()

        if not witness_src:
            self.app.notify(
                "Witness script is required",
                severity="warning"
            )
            return

        try:
            witness_script = Script.from_src(witness_src)
        except Exception as e:
            self.app.notify(
                f"Invalid tapescript: {e}",
                severity="error"
            )
            return

        self.txn_data.witness_scripts[
            self.output.id
        ] = witness_script
        txn = self.txn_data.txn
        txn.witness = {
            **txn.witness,
            self.output.coin.id_bytes: witness_script.bytes
        }
        self.dismiss(True)

    @on(Checkbox.Changed, "#box_script_spend")
    def _toggle_use_custom_script(self, event: Checkbox.Changed) -> None:
        self.app.log_event(f"{event.checkbox.value=}", "DEBUG")
        self.requires_custom = event.checkbox.value
        self._update_ui()

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)

    async def action_quit(self) -> None:
        await self.app.action_quit()
