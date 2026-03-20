from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static
from easycoin.models import Wallet, Coin
from ..base import BaseScreen
from .unlock_modal import UnlockWalletModal


class WalletScreen(BaseScreen):
    """Manage a single wallet."""

    def __init__(self, wallet_id: str):
        """Initialize with wallet ID.

        Args:
            wallet_id: ID of the wallet to display
        """
        super().__init__()
        self.wallet_id = wallet_id
        self.wallet = None

    def compose(self) -> ComposeResult:
        """Compose wallet screen layout."""
        with Vertical(id="wallet_screen"):
            yield Static("Wallet Info", classes="panel-title")
            yield Static("ID: Loading...", id="wallet_id_display")
            yield Static("Balance: Loading...", id="wallet_balance", classes="balance")
            yield Static("Status: Loading...", id="wallet_status")

            yield Static("Address Book", classes="panel-title")
            yield DataTable(id="address_book")

            with Horizontal(id="wallet_actions"):
                yield Button("Lock/Unlock", id="btn_lock", variant="primary")
                yield Button("Backup Seed", id="btn_backup", variant="default")
                yield Button("Export Keys", id="btn_export", variant="default")

    def on_mount(self) -> None:
        """Populate wallet info and address book table on mount."""
        super().on_mount()
        self.call_later(self._load_wallet_data)

    def _load_wallet_data(self) -> None:
        """Load wallet data with error handling."""
        try:
            self.wallet = Wallet.find(self.wallet_id)

            if not self.wallet:
                try:
                    self.query_one("#wallet_id_display", Static).update(
                        "Wallet not found"
                    )
                    self.query_one("#wallet_status", Static).update("Error")
                except Exception as e:
                    self.log_event(f"Error updating wallet not found UI: {e}", "DEBUG")
                self.app.notify(
                    f"Wallet {self._truncate_id(self.wallet_id)} not found",
                    severity="error"
                )
                return

            try:
                self.query_one("#wallet_id_display", Static).update(
                    f"ID: {self._truncate_id(self.wallet.id)}"
                )
            except Exception as e:
                self.log_event(f"Error updating wallet ID display: {e}", "DEBUG")

            try:
                balance = self._get_wallet_balance(self.wallet)
                self.query_one("#wallet_balance", Static).update(
                    f"Balance: {balance:,} EC⁻¹"
                )
            except Exception as e:
                try:
                    self.query_one("#wallet_balance", Static).update("Balance: Error")
                except Exception as e2:
                    self.log_event(f"Error updating balance error display: {e2}", "DEBUG")
                self.app.notify(f"Error calculating balance: {e}", severity="error")

            try:
                self.query_one("#wallet_status", Static).update(
                    f"Status: {'Locked' if self.wallet.is_locked else 'Unlocked'}"
                )
            except Exception as e:
                self.log_event(f"Error updating wallet status: {e}", "DEBUG")

            try:
                table = self.query_one("#address_book", DataTable)
                table.add_columns("Address", "Balance", "Coins")

                address_book = self._get_address_book()
                for address, data in address_book.items():
                    table.add_row(
                        self._truncate_address(address),
                        str(data['balance']),
                        str(data['count'])
                    )
            except Exception as e:
                self.app.notify(f"Error loading address book: {e}", severity="error")
        except Exception as e:
            self.app.notify(f"Error loading wallet: {e}", severity="error")
            self.log_event(f"Error loading wallet data: {e}", "ERROR")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_lock":
            self._toggle_lock()
        elif event.button.id == "btn_backup":
            self._backup_seed()
        elif event.button.id == "btn_export":
            self._export_keys()

    def _get_address_book(self) -> dict[str, dict[str, int]]:
        """Build address book from wallet's coins.

        Returns:
            Dict mapping addresses to balance and coin count.
        """
        address_book = {}

        try:
            for coin in Coin.query({'wallet_id': self.wallet_id}).get():
                try:
                    address = Wallet.make_address(coin.lock)

                    if address not in address_book:
                        address_book[address] = {'balance': 0, 'count': 0}
                    address_book[address]['balance'] += coin.amount
                    address_book[address]['count'] += 1
                except Exception as e:
                    self.log_event(f"Error processing coin: {e}", "ERROR")
        except Exception as e:
            self.log_event(f"Error querying coins: {e}", "ERROR")

        return address_book

    def _toggle_lock(self) -> None:
        """Toggle wallet lock status."""
        if not self.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        try:
            if self.wallet.is_locked:
                self.app.push_screen(UnlockWalletModal(self.wallet_id))
            else:
                self.wallet.lock()
                self.app.wallet_locked = True
                self.log_event("Wallet locked", "INFO")
                self._refresh_status()
        except Exception as e:
            self.app.notify(f"Error toggling lock: {e}", severity="error")
            self.log_event(f"Toggle lock error: {e}", "ERROR")

    def _truncate_address(self, address: str) -> str:
        """Truncate address for display."""
        return f"{address[:16]}...{address[-8:]}"

    def _truncate_id(self, wallet_id: str) -> str:
        """Truncate wallet ID for display."""
        return f"{wallet_id[:16]}..."

    def _format_balance(self) -> str:
        """Format wallet balance."""
        return f"{self._get_wallet_balance(self.wallet):,} EC⁻¹"

    def _get_wallet_balance(self, wallet) -> int:
        """Get total balance for a wallet.

        Sums the amounts of all coins owned by this wallet (any address).

        Args:
            wallet: Wallet instance

        Returns:
            Total balance
        """
        total = 0
        try:
            for coin in Coin.query({'wallet_id': wallet.id}).get():
                total += coin.amount
        except Exception as e:
            self.log_event(f"Error calculating balance: {e}", "ERROR")
        return total

    def _refresh_status(self) -> None:
        """Refresh wallet status display."""
        if not self.wallet:
            return

        try:
            self.query_one("#wallet_status", Static).update(
                f"Status: {'Locked' if self.wallet.is_locked else 'Unlocked'}"
            )
        except Exception as e:
            self.log_event(f"Error refreshing status: {e}", "ERROR")

    def _backup_seed(self) -> None:
        """Placeholder for backup seed functionality."""
        self.app.notify("Backup Seed not yet implemented", severity="warning")

    def _export_keys(self) -> None:
        """Placeholder for export keys functionality."""
        self.app.notify("Export Keys not yet implemented", severity="warning")
