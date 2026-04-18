from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Footer
from tapescript import Script
from easycoin.cui.widgets.textarea import ECTextArea
from easycoin.models import Coin


class DecompiledLockModal(ModalScreen):
    """Modal for viewing decompiled locking scripts."""

    BINDINGS = [
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, coin: Coin):
        """Initialize decompiled lock modal."""
        super().__init__()
        self.coin = coin

    def compose(self) -> ComposeResult:
        """Compose decompiled lock modal layout."""
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static("Decompiled Lock Script", classes="modal-title")

            yield ECTextArea(
                id="decompiled_script",
                read_only=True,
                classes="h-20"
            )

            with Horizontal(id="modal_actions"):
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Set the decompiled script text."""
        decompiled = Script.from_bytes(self.coin.lock).src
        self.query_one("#decompiled_script").text = decompiled

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()
