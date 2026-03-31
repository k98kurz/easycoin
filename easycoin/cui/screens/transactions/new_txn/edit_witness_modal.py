from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static, Footer, TextArea
from tapescript import Script
from easycoin.cui.helpers import format_balance, truncate_text
from easycoin.cui.screens.transactions.new_txn.data import TransactionData, Witness
from easycoin.cui.widgets import ECTextArea
from easycoin.models import Address, Output, Wallet
import packify


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
        self.is_known = False
        self.requires_custom = True
        self.address = None
        if output.id in txn_data.witnesses:
            witness = txn_data.witnesses[output.id]
            self.witness = Witness(
                witness.lock_type,
                witness.generated,
                witness.custom,
                witness.scriptspend,
            )
        else:
            self.witness = Witness()
        self.default_script_src = 'false'

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-container w-80p"):
            yield Static("Edit Witness", classes="modal-title")

            with Vertical(classes="h-3 my-1"):
                yield Static("Input Details:", classes="text-bold")
                yield Static("...", id="input_info", classes="text-muted")

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

            with Horizontal(classes="h-10 my-1"):
                with Vertical():
                    yield Static("Decompiled Lock", classes="text-bold")
                    yield ECTextArea(
                        id="decompiled_lock", read_only=True, classes="h-8"
                    )
                with Vertical(id="committed_script_section"):
                    yield Static("Committed Script", classes="text-bold")
                    yield ECTextArea(
                        id="decompiled_committed_script",
                        read_only=True, classes="h-8"
                    )

            with Horizontal(classes="h-14"):
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
                        classes="h-8 mt-1"
                    )

                with Vertical(id="custom_script_section", classes="hidden"):
                    yield Static(
                        "Custom Witness Script:", classes="text-bold my-1"
                    )
                    yield ECTextArea(
                        "",
                        id="custom_witness_textarea",
                        placeholder="Enter tapescript source",
                        classes="h-10"
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

        self.witness.lock_type = Wallet.get_lock_type(self.output.coin.lock)
        self.address = Address({"lock": self.output.coin.lock})
        for addr in self.app.wallet.addresses:
            if addr.lock == self.output.coin.lock:
                self.is_known = True
                self.address = addr
                secrets = packify.unpack(
                    self.app.wallet.decrypt(addr.secrets)
                ) if addr else None
                self.witness.lock_type = Wallet.get_lock_type(
                    addr.lock, secrets
                )
                if self.witness.lock_type not in ("P2SH", "Unknown"):
                    self.requires_custom = False
                if self.witness.lock_type == "P2TR":
                    nonce = addr.nonce or 0
                    self.default_script_src = f'push d{nonce} false return'
                return

    def _update_ui(self) -> None:
        self.query_one("#address_hex").update(self.address.hex)
        decompiled = Script.from_bytes(self.output.coin.lock).src
        self.query_one("#decompiled_lock").text = decompiled
        scriptspend, generated, custom = False, '', ''

        truncated_id = truncate_text(
            self.output.id, prefix_len=8, suffix_len=4
        )
        amount_str = format_balance(
            self.output.coin.amount, exact=True
        )
        self.query_one("#input_info").update(
            f"ID: {truncated_id} | Amount: {amount_str} | "
            f"Lock Type: {self.witness.lock_type}",
        )

        if self.is_known:
            self.query_one("#address_known_status").update("From wallet")
        else:
            self.query_one("#address_known_status").update("Not from wallet")

        scriptspend = self.witness.scriptspend
        generated = "\n".join([
            l for l in self.witness.generated.src.split("\n") if l
        ])
        custom = "\n".join([
            l for l in self.witness.custom.src.split("\n") if l
        ])

        if self.witness.lock_type not in ("P2SH", "Unknown"):
            self.query_one("#generate_witness_section").remove_class("hidden")
            self.query_one("#generated_witness_textarea").text = generated
            if scriptspend:
                self.query_one("#box_script_spend").value = True
                self.query_one("#custom_witness_textarea").text = custom
        else:
            self.query_one("#generate_witness_section").add_class("hidden")

        if self.witness.lock_type in ("P2TR", "P2GR", "P2GT"):
            self.query_one("#box_script_spend").remove_class("hidden")
        else:
            self.query_one("#box_script_spend").add_class("hidden")

        if self.requires_custom or self.witness.scriptspend:
            self.query_one("#custom_script_section").remove_class("hidden")
            if custom:
                self.query_one("#custom_witness_textarea").text = custom
            self.query_one("#custom_witness_textarea").focus()
        else:
            self.query_one("#custom_script_section").add_class("hidden")

        if self.witness.lock_type in ("P2TR", "P2SH"):
            self.query_one("#committed_script_section").remove_class("hidden")
            script = Script.from_bytes(self.address.committed_script or b'')
            self.query_one("#decompiled_committed_script").text = script.src
        else:
            self.query_one("#committed_script_section").add_class("hidden")

    @on(Button.Pressed, "#btn_generate")
    def action_generate_witness(self) -> None:
        self.witness.generated = Script('', b'')
        self.witness.custom = Script('', b'')
        custom_witness = self.query_one("#custom_witness_textarea").text.strip()

        if self.requires_custom or self.witness.scriptspend:
            try:
                self.witness.custom = Script.from_src(custom_witness)
            except Exception as e:
                self.app.notify(
                    f"Tapescript compilation error: {e}",
                    severity="warning"
                )
                if self.requires_custom:
                    return

        if self.requires_custom or self.witness.scriptspend:
            if not self.witness.custom.bytes:
                return self.app.notify(
                    "Custom script required",
                    severity="warning"
                )

        if self.witness.lock_type == "P2PK":
            self.witness.generated = self.app.wallet.get_p2pk_witness(
                self.address.nonce, self.txn_data.txn, self.output.coin,
                child_nonce=self.address.child_nonce,
            )
        elif self.witness.lock_type == "P2PKH":
            self.witness.generated = self.app.wallet.get_p2pkh_witness(
                self.address.nonce, self.txn_data.txn, self.output.coin,
                child_nonce=self.address.child_nonce,
            )
        elif self.witness.lock_type == "P2TR":
            if self.address.committed_script:
                committed_script = Script.from_bytes(self.address.committed_script)
            else:
                committed_script = Script.from_src(self.default_script_src)

            if self.witness.scriptspend:
                self.witness.generated = self.app.wallet.get_p2tr_witness_scriptspend(
                    self.address.nonce,
                    child_nonce=self.address.child_nonce,
                    script=committed_script,
                )
            else:
                self.witness.generated = self.app.wallet.get_p2tr_witness_keyspend(
                    self.address.nonce, self.txn_data.txn, self.output.coin,
                    child_nonce=self.address.child_nonce,
                    script=committed_script,
                )
        elif self.witness.lock_type == "P2GR":
            if self.witness.scriptspend:
                self.witness.generated = self.app.wallet.get_p2gr_witness_surrogate(
                    self.address.nonce, self.witness.custom,
                    child_nonce=self.address.child_nonce,
                )
            else:
                self.witness.generated = self.app.wallet.get_p2gr_witness_keyspend(
                    self.address.nonce, self.txn_data.txn, self.output.coin,
                    child_nonce=self.address.child_nonce,
                )
        elif self.witness.lock_type == "P2GT":
            if self.witness.scriptspend:
                self.witness.generated = self.app.wallet.get_p2gt_witness_scriptspend(
                    self.address.nonce, self.witness.custom,
                    child_nonce=self.address.child_nonce,
                )
            else:
                self.witness.generated = self.app.wallet.get_p2gt_witness_keyspend(
                    self.address.nonce, self.txn_data.txn, self.output.coin,
                    child_nonce=self.address.child_nonce,
                )

        if self.witness.generated:
            textarea = self.query_one("#generated_witness_textarea")
            # remove empty lines
            cleaned = self.witness.generated.src.split("\n")
            cleaned = '\n'.join([l for l in cleaned if l.strip()])
            textarea.text = cleaned

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        text_area = self.query_one("#custom_witness_textarea")
        custom_witness_src = text_area.text.strip()

        if self.requires_custom and not custom_witness_src:
            self.app.notify(
                "Witness script is required",
                severity="warning"
            )
            return

        if custom_witness_src:
            try:
                self.witness.custom = Script.from_src(custom_witness_src)
            except Exception as e:
                self.app.notify(
                    f"Invalid tapescript: {e}",
                    severity="error"
                )
                if self.requires_custom:
                    return

        if self.witness.lock_type == "P2SH" and self.address.committed_script:
            self.witness.generated = Script.from_bytes(
                self.address.committed_script
            )

        if not self.witness.full().bytes:
            self.app.notify(
                "No witness script to save",
                severity="warning"
            )
            return

        self.txn_data.witnesses[
            self.output.id
        ] = self.witness
        txn = self.txn_data.txn
        txn.witness = {
            **txn.witness,
            self.output.coin.id_bytes: self.witness.full().bytes
        }
        self.dismiss(True)

    @on(Checkbox.Changed, "#box_script_spend")
    def _toggle_use_custom_script(self, event: Checkbox.Changed) -> None:
        self.witness.scriptspend = event.checkbox.value
        self._update_ui()

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)

    async def action_quit(self) -> None:
        await self.app.action_quit()
