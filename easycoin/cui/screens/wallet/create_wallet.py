from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Input, Button
from easycoin.models import Wallet
from easycoin import wordlist
import random


class CreateWalletModal(Screen):
    """Modal for creating a new wallet with seed phrase and password."""

    def __init__(self, refresh_callback=None):
        """Initialize create wallet modal.

        Args:
            refresh_callback: Optional callback to call after wallet is created
        """
        super().__init__()
        self.refresh_callback = refresh_callback
        self.seed_phrase = Wallet.generate_seed_phrase(wordlist())
        self.default_wallet_name = self._generate_wallet_name()

    def _generate_wallet_name(self) -> str:
        """Generate a random wallet name from two random words and four digits."""
        words = wordlist()
        word1 = random.choice(words)
        word2 = random.choice(words)
        digits = random.randint(1000, 9999)
        return f"{word1}{word2}{digits}"

    def compose(self) -> ComposeResult:
        """Compose create wallet modal layout."""
        with Vertical(id="create_wallet_modal", classes="modal-container"):
            yield Static("Create New Wallet", classes="modal-title")
            yield Static("\n")
            yield Static(
                "Write down this seed phrase and keep it safe. "
                "You'll need it to restore your wallet.",
                classes="text-italic"
            )
            yield Static("\n")
            yield Static(
                " ".join(self.seed_phrase),
                id="seed_phrase_display",
                classes="text-center text-bold"
            )
            yield Static("\n")

            yield Static("Wallet name:\n", classes="form-label")
            yield Input(id="wallet_name")
            yield Static("\n")

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
                yield Button("Create", id="btn_create", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

    def on_mount(self) -> None:
        """Set default wallet name in input field on mount."""
        self.query_one("#wallet_name", Input).value = self.default_wallet_name

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_create":
            self._create_wallet()
        elif event.button.id == "btn_cancel":
            self.app.pop_screen()

    def on_key(self, event) -> None:
        """Handle keyboard events."""
        if event.key == "escape":
            self.app.pop_screen()

    def _create_wallet(self) -> None:
        """Create wallet with provided password and seed phrase."""
        wallet_name = self.query_one("#wallet_name", Input).value
        password = self.query_one("#password_input", Input).value
        confirm_password = self.query_one(
            "#confirm_password_input", Input
        ).value

        if not wallet_name:
            wallet_name = self.default_wallet_name

        if len(wallet_name) < 1 or len(wallet_name) > 30:
            self.app.notify(
                "Wallet name must be between 1 and 30 characters",
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
            wallet = Wallet.create(self.seed_phrase, password, wallet_name)
            wallet.save()

            wallet.unlock(password)
            self.app.wallet = wallet

            self.app.notify(
                "Wallet created and activated",
                severity="success"
            )
            self.app.log_event(
                f"Wallet created and activated: {wallet.id[:16]}...",
                "INFO"
            )

            self.app.pop_screen()

            if self.refresh_callback:
                self.app.call_later(self.refresh_callback)

        except Exception as e:
            self.app.notify(f"Failed to create wallet: {e}", severity="error")
            self.app.log_event(f"Wallet creation error: {e}", "ERROR")
