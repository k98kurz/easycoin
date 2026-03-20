from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Input, Button


class UnlockWalletModal(Screen):
    """Modal for unlocking a wallet (minimal skeleton)."""

    def __init__(self, wallet_id: str, success_callback=None):
        """Initialize with wallet ID.

        Args:
            wallet_id: ID of the wallet to unlock
            success_callback: Optional callback to call after successful unlock
        """
        super().__init__()
        self.wallet_id = wallet_id
        self.success_callback = success_callback
        self.wallet = None

    def compose(self) -> ComposeResult:
        """Compose unlock modal layout."""
        from easycoin.models import Wallet

        self.wallet = Wallet.find(self.wallet_id)

        with Vertical(id="unlock_modal", classes="modal-container"):
            yield Static("Unlock Wallet", classes="modal-title")
            yield Static(
                f"Wallet: {self._truncate_id(self.wallet_id)}...",
                classes="wallet-id"
            )
            yield Input(
                placeholder="Password",
                password=True,
                id="password_input"
            )

            with Horizontal(id="modal_actions"):
                yield Button("Unlock", id="btn_unlock", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="default")
            yield Static("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_unlock":
            self._unlock_wallet()
        elif event.button.id == "btn_cancel":
            self.app.pop_screen()

    def on_key(self, event) -> None:
        """Handle keyboard events."""
        if event.key == "enter":
            self._unlock_wallet()
        elif event.key == "escape":
            self.app.pop_screen()

    def _unlock_wallet(self) -> None:
        """Attempt to unlock wallet with provided password."""
        password = self.query_one("#password_input", Input).value

        if not password:
            self.app.notify("Password is required", severity="warning")
            return

        if not self.wallet:
            self.app.notify("Wallet not found", severity="error")
            self.app.log_event(f"Unlock error: wallet not found: {self.wallet_id}", "ERROR")
            return

        try:
            self.wallet.unlock(password)
        except ValueError as e:
            self.app.notify(f"Failed to unlock: {e}", severity="error")
            self.app.log_event(f"Unlock failed: {e}", "ERROR")
            return
        except Exception as e:
            self.app.notify(f"Unexpected error: {e}", severity="error")
            self.app.log_event(f"Unlock error: {e}", "ERROR")
            return

        self.app.wallet = self.wallet
        self.app.notify("Wallet unlocked", severity="success")
        self.app.log_event(f"Wallet unlocked: {self.wallet_id[:16]}...", "INFO")

        try:
            self.app.pop_screen()
        except Exception as e:
            self.app.log_event(f"Error dismissing modal: {e}", "ERROR")

        if self.success_callback:
            try:
                self.app.call_later(self.success_callback)
            except Exception as e:
                self.app.log_event(f"Callback error: {e}", "ERROR")

    def _truncate_id(
            self, wallet_id: str, prefix_len: int = 16,
            suffix_len: int = 4
        ) -> str:
        """Truncate wallet ID for display."""
        if len(wallet_id) <= prefix_len + suffix_len:
            return wallet_id
        return f"{wallet_id[:prefix_len]}...{wallet_id[-suffix_len:]}"
