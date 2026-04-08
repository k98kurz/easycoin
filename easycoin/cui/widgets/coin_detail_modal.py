from collections.abc import Callable
from tapescript import Script
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Footer
from easycoin.cui.helpers import (
    format_balance, format_timestamp, format_amount, truncate_text, hexify,
    create_temp_file, open_file_with_default_app
)
from easycoin.cui.widgets.textarea import ECTextArea
from .confirmation_modal import ConfirmationModal
from easycoin.models import Address, Coin, Wallet, Input, Output
import json


class CoinDetailModal(ModalScreen):
    """Modal for displaying coin details."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, coin: Coin, on_disassociated: Callable[[], None] | None = None):
        """Initialize coin detail modal."""
        super().__init__()
        self.coin = coin
        self.is_stamp = len(coin.details) > 0
        self.on_disassociated = on_disassociated

    def compose(self) -> ComposeResult:
        """Compose coin detail modal layout."""
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static("Coin Details", classes="modal-title")

            yield Static(f"[b]Coin ID:[/b] {self.coin.id}", classes="mt-1")
            yield Static(
                f"[b]Address:[/b] {Address({'lock': self.coin.lock}).hex}",
                classes="my-1"
            )

            with Horizontal(classes="h-6"):
                with Vertical():
                    yield Static(
                        "[b]Amount:[/b] " +
                        format_balance(self.coin.amount, exact=True),
                        classes="mb-1"
                    )

                    yield Static(
                        "[b]Lock Type:[/b] " +
                        Wallet.get_lock_type(self.coin.lock),
                        classes="mb-1"
                    )

                    yield Static(
                        "[b]Status:[/b] " +
                        ("Spent" if self.coin.spent else "Unspent"),
                        classes="mb-1"
                    )

                with Vertical():
                    yield Static(
                        f"[b]Network:[/b] {self._get_network_name()}",
                        classes="mb-1"
                    )

                    yield Static(
                        f"[b]Timestamp:[/b] " +
                        format_timestamp(self.coin.timestamp),
                        classes="mb-1"
                    )

                    yield Static(f"[b]Nonce:[/b] {self.coin.nonce}", classes="mb-1")

            hideclass = "hidden" if not self.coin.details else ""
            yield Static(
                f"[b]Stamp ID:[/b] {self.coin.stamp_id.hex()}",
                classes=f"my-1 {hideclass}"
            )

            n_value = self.coin.details.get('n', 'N/A')
            yield Static(
                f"[b]Stamp Number/Note:[/b] {n_value}",
                classes=f"mb-1 {hideclass}"
            )

            yield Static(
                f"[b]Data-script-hash:[/b] {self.coin.dsh.hex()}",
                classes=f"mb-1 {hideclass}"
            )

            yield Static(
                f"[b]Issue:[/b] {self.coin.issue.hex()}",
                classes=f"mb-1 {hideclass}"
            )

            if self.coin.details.get('d', None):
                data_size = len(self.coin.data.get('details', None) or b'')
                yield Static(
                    f"[b]Stamp Size:[/b] {format_amount(data_size)}B",
                    classes="my-1"
                )
                yield Static("Stamp Data:", classes="mb-1 text-bold")
                try:
                    stamp_data = self.coin.details['d']
                    if isinstance(stamp_data, dict):
                        if 'file' in stamp_data:
                            filename = stamp_data.get('name', 'unknown')
                            file_type = stamp_data.get('type', 'file')
                            file_content = stamp_data['file']

                            yield Static(f"📎 {filename}", classes="my-1 text-bold")
                            display_size = format_amount(len(file_content)) + "B"
                            yield Static(
                                f"Type: {file_type} | Size: {display_size}",
                                classes="mb-1"
                            )

                            with Horizontal(classes="my-1 h-3"):
                                yield Button(
                                    "Open", id="btn_open_file",
                                    variant="primary", classes="mx-1"
                                )
                                yield Button(
                                    "Save to Disk", id="btn_save_file",
                                    variant="default", classes="mx-1"
                                )
                        else:
                            stamp_data_str = json.dumps(
                                hexify(stamp_data), indent=2, default=str
                            )
                            yield Static(stamp_data_str, classes="text-italic")
                    else:
                        stamp_data_str = str(stamp_data)
                        yield Static(stamp_data_str, classes="text-italic")
                except Exception as e:
                    yield Static(
                        f"Error displaying stamp data: {e}",
                        classes="text-error"
                    )

            if '_' in self.coin.details:
                yield Static(
                    "Prefix Script (_):", classes="text-bold my-1"
                )
                yield ECTextArea(
                    Script.from_bytes(self.coin.details['_']).src,
                    read_only=True,
                    classes="h-12 mb-1"
                )


            has_scripts = 'L' in self.coin.details or '$' in self.coin.details
            if has_scripts:
                with Horizontal(classes="h-14"):
                    if 'L' in self.coin.details:
                        with Container(classes="h-14"):
                            yield Static(
                                "Mint Lock Script (L):", classes="text-bold my-1"
                            )
                            yield ECTextArea(
                                Script.from_bytes(self.coin.details['L']).src,
                                read_only=True,
                                classes="h-12 mb-1"
                            )

                    if '$' in self.coin.details:
                        with Container(classes="h-14"):
                            yield Static(
                                "Covenant Script ($):", classes="text-bold my-1"
                            )
                            yield ECTextArea(
                                Script.from_bytes(self.coin.details['$']).src,
                                read_only=True,
                                classes="h-12 mb-1"
                            )

            with Horizontal(id="modal_actions"):
                yield Button(
                    "Associate with Wallet", id="btn_associate",
                    variant="success", classes="hidden"
                )
                yield Button(
                    "Disassociate from Wallet", id="btn_disassociate",
                    variant="error", classes="hidden"
                )
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize button visibility based on wallet and coin state."""
        btn_associate = self.query_one("#btn_associate", Button)
        btn_disassociate = self.query_one("#btn_disassociate", Button)

        if not self.app.wallet or self.app.wallet.is_locked:
            btn_associate.add_class("hidden")
            btn_disassociate.add_class("hidden")
            return

        is_associated = (
            self.coin.wallet_id is not None
            and self.coin.wallet_id == self.app.wallet.id
        )

        if is_associated:
            btn_associate.add_class("hidden")
            btn_disassociate.remove_class("hidden")
        else:
            btn_associate.remove_class("hidden")
            btn_disassociate.add_class("hidden")

    def _get_network_name(self) -> str:
        """Get network name from ID."""
        if not self.coin.net_id:
            return "None"

        if self.coin.trustnet:
             return self.coin.trustnet.name or "Unknown"

        return truncate_text(self.coin.net_id, suffix_len=0)

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    @on(Button.Pressed, "#btn_open_file")
    def _on_open_file(self) -> None:
        """Open file attachment with system default app."""
        try:
            stamp_data = self.coin.details['d']
            file_content = stamp_data['file']
            filename = stamp_data.get('name', 'file.dat')

            filepath = create_temp_file(file_content, filename)
            open_file_with_default_app(filepath)
        except Exception as e:
            self.app.notify(f"Failed to open file: {e}", severity="error")

    @on(Button.Pressed, "#btn_save_file")
    def _on_save_file(self) -> None:
        """Save file attachment to disk."""
        import os

        try:
            stamp_data = self.coin.details['d']
            file_content = stamp_data['file']
            filename = stamp_data.get('name', 'file.dat')

            filepath = filename
            counter = 1
            while os.path.exists(filepath):
                name, ext = os.path.splitext(filename)
                filepath = f"{name}_{counter}{ext}"
                counter += 1

            with open(filepath, 'wb') as f:
                f.write(file_content)

            abs_path = os.path.abspath(filepath)
            self.app.notify(
                f"File saved to: {abs_path}",
                severity="success"
            )
        except Exception as e:
            self.app.notify(f"Failed to save file: {e}", severity="error")

    @on(Button.Pressed, "#btn_associate")
    def _on_associate(self) -> None:
        """Associate coin with active wallet."""
        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return

            try:
                old_wallet_id = self.coin.wallet_id
                new_wallet_id = self.app.wallet.id
                coin_id = self.coin.id

                if old_wallet_id is not None:
                    old_wallet_short = old_wallet_id[:16]
                    new_wallet_short = new_wallet_id[:16]
                    self.app.notify(
                        f"Coin was already associated with wallet {old_wallet_short}... "
                        f"Re-associating with {new_wallet_short}...",
                        severity="info"
                    )

                self.coin.wallet_id = new_wallet_id
                self.coin.save()

                self.app.log_event(
                    f"Associated coin {coin_id[:16]}... with wallet {new_wallet_id[:16]}...",
                    "INFO"
                )

                Input.query().equal('id', coin_id).update(
                    {'wallet_id': new_wallet_id}
                )
                Output.query().equal('id', coin_id).update(
                    {'wallet_id': new_wallet_id}
                )

                self.app.notify(
                    f"Coin associated with wallet {new_wallet_id[:16]}...",
                    severity="success"
                )

                self.dismiss()
            except Exception as e:
                self.app.notify(
                    f"Failed to associate coin: {e}",
                    severity="error"
                )
                self.app.log_event(f"Associate coin error: {e}", "ERROR")

        if self.coin.wallet_id is not None:
            message = (
                f"This coin is already associated with wallet "
                f"{self.coin.wallet_id[:16]}...\n\n"
                f"Do you want to re-associate it with "
                f"{self.app.wallet.id[:16]}...?"
            )
            modal = ConfirmationModal(
                title="Re-associate with Wallet",
                message=message,
                confirm_btn_text="Re-associate",
                confirm_btn_variant="success"
            )
        else:
            modal = ConfirmationModal(
                title="Associate with Wallet",
                message=f"Associate this coin with {self.app.wallet.id[:16]}...?",
                confirm_btn_text="Associate",
                confirm_btn_variant="success"
            )

        self.app.push_screen(modal, on_confirmed)

    @on(Button.Pressed, "#btn_disassociate")
    def _on_disassociate(self) -> None:
        """Disassociate coin from active wallet."""
        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return

            try:
                wallet_id = self.coin.wallet_id
                coin_id = self.coin.id
                wallet_short = wallet_id[:16]

                self.coin.wallet_id = None
                self.coin.save()

                self.app.log_event(
                    f"Disassociated coin {coin_id[:16]}... from wallet {wallet_short}...",
                    "INFO"
                )

                Input.query().equal('id', coin_id).update({'wallet_id': None})
                Output.query().equal('id', coin_id).update({'wallet_id': None})

                self.app.notify(
                    f"Coin disassociated from wallet {wallet_short}...",
                    severity="success"
                )

                if self.on_disassociated:
                    self.on_disassociated()

                self.dismiss()
            except Exception as e:
                self.app.notify(
                    f"Failed to disassociate coin: {e}",
                    severity="error"
                )
                self.app.log_event(f"Disassociate coin error: {e}", "ERROR")

        modal = ConfirmationModal(
            title="Disassociate from Wallet",
            message=f"Remove this coin's association with {self.app.wallet.id[:16]}...?",
            confirm_btn_text="Disassociate",
            confirm_btn_variant="error"
        )

        self.app.push_screen(modal, on_confirmed)

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()
