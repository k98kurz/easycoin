from datetime import datetime
from textual import on
from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Input, Button
from textual.binding import Binding
from easycoin.models import Wallet
from easycoin import wordlist


class RestoreWalletModal(Screen):
    """Modal for restoring a wallet from a 12-word seed phrase."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
        RestoreWalletModal { background: $background 50%; }
    """

    def __init__(self, refresh_callback=None):
        """Initialize restore wallet modal.

        Args:
            refresh_callback: Optional callback to call after wallet is restored
        """
        super().__init__()
        self.refresh_callback = refresh_callback

    def compose(self) -> ComposeResult:
        """Compose restore wallet modal layout."""
        with Vertical(id="restore_wallet_modal", classes="modal-container w-50p"):
            yield Static("Restore Wallet", classes="modal-title")
            yield Static("\n")
            yield Static(
                "Enter your 12-word seed phrase to restore your wallet.",
                classes="text-italic"
            )
            yield Static("")

            yield Static("Seed phrase:\n", classes="form-label")
            yield Input(
                placeholder="word1 word2 word3 ... word12",
                id="seed_phrase_input"
            )
            yield Static("")

            yield Static("Wallet name:\n", classes="form-label")
            yield Input(id="wallet_name_input")
            yield Static("")

            with Horizontal():
                with Vertical():
                    yield Static("Password:\n", classes="form-label")
                    yield Input(
                        placeholder="Enter password",
                        password=True,
                        id="password_input"
                    )
                with Vertical():
                    yield Static("Confirm Password:\n", classes="form-label")
                    yield Input(
                        placeholder="Confirm password",
                        password=True,
                        id="confirm_password_input"
                    )

            with Horizontal(id="modal_actions"):
                yield Button("Restore", id="btn_restore", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

    def on_mount(self) -> None:
        """Set default wallet name and focus seed phrase input on mount."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.query_one("#wallet_name_input", Input).value = (
            f"restored {now}"
        )
        self.query_one("#seed_phrase_input", Input).focus()

    def action_cancel(self) -> None:
        """Action handler for Escape key."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn_restore")
    def _do_restore(self) -> None:
        """Restore wallet from seed phrase."""
        seed_phrase_text = self.query_one(
            "#seed_phrase_input", Input
        ).value.strip()
        wallet_name = self.query_one("#wallet_name_input", Input).value
        password = self.query_one("#password_input", Input).value
        confirm_password = self.query_one(
            "#confirm_password_input", Input
        ).value

        if not wallet_name:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            wallet_name = f"restored {now}"

        if len(wallet_name) < 1 or len(wallet_name) > 30:
            self.app.notify(
                "Wallet name must be between 1 and 30 characters",
                severity="warning"
            )
            return

        seed_phrase = seed_phrase_text.split()
        if len(seed_phrase) != 12:
            self.app.notify(
                "Seed phrase must be exactly 12 words",
                severity="warning"
            )
            return

        word_set = set(wordlist())
        invalid_words = [w for w in seed_phrase if w not in word_set]
        if invalid_words:
            self.app.notify(
                f"Invalid words: {', '.join(invalid_words)}",
                severity="warning"
            )
            return

        if not password:
            self.app.notify("Password is required", severity="warning")
            return

        if password != confirm_password:
            self.app.notify("Passwords do not match", severity="warning")
            return

        try:
            wallet = Wallet.create(seed_phrase, password, wallet_name)
            wallet.save()

            wallet.unlock(password)
            self.app.wallet = wallet

            self.app.log_event(
                f"Wallet restored and activated: {wallet.id[:16]}...",
                "INFO"
            )

            self.app.pop_screen()

            if self.refresh_callback:
                self.app.call_later(self.refresh_callback)

        except Exception as e:
            self.app.notify(f"Failed to restore wallet: {e}", severity="error")
            self.app.log_event(f"Wallet restore error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_cancel")
    def _cancel(self) -> None:
        """Cancel restore and close modal."""
        self.app.pop_screen()
