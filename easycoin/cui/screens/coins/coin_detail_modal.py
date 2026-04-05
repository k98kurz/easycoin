from tapescript import Script
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Footer
from easycoin.cui.helpers import (
    format_balance, format_timestamp, format_amount, truncate_text
)
from easycoin.cui.widgets import ECTextArea
from easycoin.models import Address, Coin, Wallet
import json


class CoinDetailModal(ModalScreen):
    """Modal for displaying coin details."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, coin: Coin):
        """Initialize coin detail modal."""
        super().__init__()
        self.coin = coin
        self.is_stamp = len(coin.details) > 0

    def compose(self) -> ComposeResult:
        """Compose coin detail modal layout."""
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static("Coin Details", classes="modal-title")

            yield Static(f"Coin ID: {self.coin.id}", classes="mt-1")
            yield Static(
                f"Address: {Address({'lock': self.coin.lock}).hex}",
                classes="my-1"
            )

            with Horizontal(classes="h-6"):
                with Vertical():
                    yield Static(
                        f"Amount: {format_balance(self.coin.amount, exact=True)}",
                        classes="mb-1"
                    )

                    yield Static(
                        f"Lock Type: {Wallet.get_lock_type(self.coin.lock)}",
                        classes="mb-1"
                    )

                    yield Static(
                        "Status: " +
                        ("Spent" if self.coin.spent else "Unspent"),
                        classes="mb-1"
                    )

                with Vertical():
                    yield Static(
                        f"Network: {self._get_network_name()}",
                        classes="mb-1"
                    )

                    yield Static(
                        f"Timestamp: {format_timestamp(self.coin.timestamp)}",
                        classes="mb-1"
                    )

                    yield Static(f"Nonce: {self.coin.nonce}", classes="mb-1")

            with VerticalScroll(
                    classes="border-solid-primary h-30 px-1 my-1 " + (
                        "hidden" if not self.coin.details else ""
                    )
                ):
                yield Static(
                    f"Stamp ID: {self.coin.stamp_id.hex()}",
                    classes="mb-1"
                )

                n_value = self.coin.details.get('n', 'N/A')
                yield Static(
                    f"Stamp Number/Note: {n_value}",
                    classes="mb-1"
                )

                yield Static(
                    f"Data-script-hash: {self.coin.dsh.hex()}",
                    classes="mb-1"
                )

                yield Static(
                    f"Issue: {self.coin.issue.hex()}",
                    classes="mb-1"
                )

                if self.coin.details.get('d', None):
                    yield Static("Stamp Data:", classes="text-muted my-1")
                    try:
                        stamp_data = self.coin.details['d']
                        if isinstance(stamp_data, dict):
                            if stamp_data.get('type', None) == 'file':
                                stamp_data_str = json.dumps(
                                    {
                                        'file': '...',
                                        **{
                                            k:v for k,v in stamp_data.items()
                                            if k != 'file'
                                        }
                                    }, indent=2
                                )
                            else:
                                stamp_data_str = json.dumps(
                                    stamp_data, indent=2, default=str
                                )
                        else:
                            stamp_data_str = str(stamp_data)
                        data_size = len(self.coin.data.get('details', None) or b'')
                        yield Static(
                            f"{stamp_data_str}\n\nData Size: "
                            f"{format_amount(data_size)}B",
                            classes="text-italic"
                        )
                    except Exception as e:
                        yield Static(
                            f"Error displaying stamp data: {e}",
                            classes="text-error"
                        )

                if '_' in self.coin.details:
                    yield Static("Prefix Script (_):", classes="text-bold my-1")
                    yield ECTextArea(
                        Script.from_bytes(self.coin.details['_']).src,
                        read_only=True,
                        classes="h-12 mb-1"
                    )

                if 'L' in self.coin.details:
                    yield Static("Mint Lock Script (L):", classes="text-bold my-1")
                    yield ECTextArea(
                        Script.from_bytes(self.coin.details['L']).src,
                        read_only=True,
                        classes="h-12 mb-1"
                    )

                if '$' in self.coin.details:
                    yield Static("Covenant Script ($):", classes="text-bold my-1")
                    yield ECTextArea(
                        Script.from_bytes(self.coin.details['$']).src,
                        read_only=True,
                        classes="h-12 mb-1"
                    )

            with Horizontal(id="modal_actions"):
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    def _get_network_name(self) -> str:
        """Get network name from ID."""
        if not self.coin.net_id:
            return "None"

        if coin.trustnet:
             return coin.trustnet.name or "Unknown"

        return truncate_text(self.coin.net_id, suffix_len=0)

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()
