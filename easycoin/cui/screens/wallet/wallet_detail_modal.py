from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, DataTable, Static
from textual.binding import Binding
from easycoin.models import Wallet, Coin
from .unlock_modal import UnlockWalletModal


class WalletDetailModal(Screen):
    """Modal for displaying wallet details."""

    BINDINGS = [
        Binding("ctrl+c", "copy_wallet_id", "Copy Wallet ID", show=False),
    ]

    def __init__(self):
        """Initialize wallet detail modal."""
        super().__init__()

    def compose(self) -> ComposeResult:
        """Compose wallet detail modal layout."""
        with Vertical(id="wallet_detail", classes="modal-container"):
            yield Static("Wallet Details", classes="modal-title")

            with Vertical(classes="card"):
                yield Static("Loading...", id="wallet_name_display", classes="text-bold")
                yield Static("Loading...", id="wallet_id_display", classes="text-muted")

                yield Static("")

                with Horizontal():
                    with Vertical():
                        yield Static("Balance:", classes="text-muted")
                        yield Static("Loading...", id="wallet_balance")
                    with Vertical():
                        yield Static("Status:", classes="text-muted")
                        yield Static("Loading...", id="wallet_status")

            yield Static("\n")

            yield Static("Address Book", classes="panel-title")
            yield DataTable(id="address_book")

            with Horizontal(id="modal_actions"):
                yield Button("Unlock", id="btn_unlock", variant="primary")
                yield Button("Lock", id="btn_lock", variant="primary")
                yield Button("Copy ID", id="btn_copy_id", variant="default")
                yield Button("Backup Seed", id="btn_backup", variant="default")
                yield Button("Export Keys", id="btn_export", variant="default")
                yield Button("Close", id="btn_close", variant="default")

    def on_mount(self) -> None:
        """Populate wallet info and address book table on mount."""
        self._load_wallet_data()

    def _load_wallet_data(self) -> None:
        """Load wallet data with error handling."""
        try:
            if not self.app.wallet: 
                self.app.notify("Wallet not available in memory", severity="error")
                self.app.pop_screen()
                return

            try:
                self.query_one("#wallet_id_display", Static).update(
                    self.app.wallet.id
                )
            except Exception as e:
                self.app.log_event(f"Error updating wallet ID display: {e}", "DEBUG")

            try:
                wallet_name = self.app.wallet.name if self.app.wallet.name else "<unnamed>"
                self.query_one("#wallet_name_display", Static).update(
                    wallet_name
                )
            except Exception as e:
                self.app.log_event(f"Error updating wallet name display: {e}", "DEBUG")

            try:
                balance = self._get_wallet_balance(self.app.wallet)
                self.query_one("#wallet_balance", Static).update(
                    f"{balance:,} EC⁻¹"
                )
            except Exception as e:
                try:
                    self.query_one("#wallet_balance", Static).update("Balance: Error")
                except Exception as e2:
                    self.app.log_event(
                        f"Error updating balance error display: {e2}", "DEBUG"
                    )
                self.app.notify(f"Error calculating balance: {e}", severity="error")

            try:
                status_static = self.query_one("#wallet_status", Static)
                if self.app.wallet.is_locked:
                    status_static.update("Locked")
                    status_static.remove_class("status-ok")
                    status_static.add_class("status-warning")
                else:
                    status_static.update("Unlocked")
                    status_static.remove_class("status-warning")
                    status_static.add_class("status-ok")
            except Exception as e:
                self.app.log_event(f"Error updating wallet status: {e}", "DEBUG")

            self._set_button_visibility()

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
            self.app.log_event(f"Error loading wallet data: {e}", "ERROR")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_unlock":
            self._unlock()
        elif event.button.id == "btn_lock":
            self._lock()
        elif event.button.id == "btn_copy_id":
            self._copy_wallet_id()
        elif event.button.id == "btn_backup":
            self._backup_seed()
        elif event.button.id == "btn_export":
            self._export_keys()
        elif event.button.id == "btn_close":
            self.app.pop_screen()

    def action_copy_wallet_id(self) -> None:
        """Action handler for Ctrl+C binding."""
        self._copy_wallet_id()

    def _copy_wallet_id(self) -> None:
        """Copy wallet ID to clipboard."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        try:
            import pyperclip
            pyperclip.copy(self.app.wallet.id)
            self.app.notify("Wallet ID copied to clipboard", severity="success")
        except ImportError:
            self.app.notify("pyperclip not installed", severity="error")
        except Exception as e:
            self.app.notify(f"Failed to copy: {e}", severity="error")
            self.app.log_event(f"Copy wallet ID error: {e}", "ERROR")

    def on_key(self, event) -> None:
        """Handle keyboard events."""
        if event.key == "escape":
            self.app.pop_screen()

    def _get_address_book(self) -> dict[str, dict[str, int]]:
        """Build address book from wallet's coins. Returns a `dict`
            mapping addresses to balance and coin count.
        """
        address_book = {}

        try:
            for coin in Coin.query({'wallet_id': self.app.wallet.id}).get():
                try:
                    address = Wallet.make_address(coin.lock)

                    if address not in address_book:
                        address_book[address] = {'balance': 0, 'count': 0}
                    address_book[address]['balance'] += coin.amount
                    address_book[address]['count'] += 1
                except Exception as e:
                    self.app.log_event(f"Error processing coin: {e}", "ERROR")
        except Exception as e:
            self.app.log_event(f"Error querying coins: {e}", "ERROR")

        return address_book

    def _unlock(self) -> None:
        """Unlock wallet."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        try:
            def on_unlock_success():
                self._set_status("Unlocked")
                self._set_button_visibility()
                self._refresh_data()
            self.app.push_screen(UnlockWalletModal(self.app.wallet.id, on_unlock_success))
        except Exception as e:
            self.app.notify(f"Error toggling lock: {e}", severity="error")
            self.app.log_event(f"Toggle lock error: {e}", "ERROR")

    def _lock(self) -> None:
        """Lock wallet."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        try:
            self.app.wallet.lock()
            self.app.log_event("Wallet locked", "INFO")
            self._set_button_visibility()
            self._refresh_status()
        except Exception as e:
            self.app.notify(f"Error toggling lock: {e}", severity="error")
            self.app.log_event(f"Toggle lock error: {e}", "ERROR")

    def _truncate_address(self, address: str) -> str:
        """Truncate address for display."""
        return f"{address[:16]}...{address[-8:]}"

    def _truncate_id(self, wallet_id: str) -> str:
        """Truncate wallet ID for display."""
        return f"{wallet_id[:16]}..."

    def _get_wallet_balance(self, wallet) -> int:
        """Get total balance for a wallet by summing the amounts of all
            coins owned by this wallet (any address).
        """
        total = 0
        try:
            for coin in Coin.query({'wallet_id': wallet.id}).get():
                total += coin.amount
        except Exception as e:
            self.app.log_event(f"Error calculating wallet balance: {e}", "ERROR")
        return total

    def _set_status(self, status: str) -> None:
        """Set wallet status display to specific value."""
        try:
            status_static = self.query_one("#wallet_status", Static)
            status_static.update(status)
            if status == "Locked":
                status_static.remove_class("status-ok")
                status_static.add_class("status-warning")
            else:
                status_static.remove_class("status-warning")
                status_static.add_class("status-ok")
        except Exception as e:
            self.app.log_event(f"Error setting status: {e}", "ERROR")

    def _set_button_visibility(self) -> None:
        """Set visibility of lock/unlock buttons based on wallet state."""
        if not self.app.wallet:
            return

        try:
            if self.app.wallet.is_locked:
                self.query_one("#btn_lock", Button).display = "none"
                self.query_one("#btn_unlock", Button).display = "block"
            else:
                self.query_one("#btn_lock", Button).display = "block"
                self.query_one("#btn_unlock", Button).display = "none"
        except Exception as e:
            self.app.log_event(f"Error setting button visibility: {e}", "ERROR")

    def _refresh_data(self) -> None:
        """Refresh wallet data displays after unlock."""
        if not self.app.wallet:
            return

        try:
            balance = self._get_wallet_balance(self.app.wallet)
            self.query_one("#wallet_balance", Static).update(
                f"Balance: {balance:,} EC⁻¹"
            )
            status_static = self.query_one("#wallet_status", Static)
            if self.app.wallet.is_locked:
                status_static.update("Locked")
                status_static.remove_class("status-ok")
                status_static.add_class("status-warning")
            else:
                status_static.update("Unlocked")
                status_static.remove_class("status-warning")
                status_static.add_class("status-ok")
        except Exception as e:
            self.app.log_event(f"Error refreshing data: {e}", "ERROR")

    def _refresh_status(self) -> None:
        """Refresh wallet status display and lock/unlock buttons."""
        if not self.app.wallet:
            return

        try:
            status_static = self.query_one("#wallet_status", Static)
            if self.app.wallet.is_locked:
                status_static.update("Locked")
                status_static.remove_class("status-ok")
                status_static.add_class("status-warning")
            else:
                status_static.update("Unlocked")
                status_static.remove_class("status-warning")
                status_static.add_class("status-ok")
            self._set_button_visibility()
        except Exception as e:
            self.app.log_event(f"Error refreshing status: {e}", "ERROR")

    def _backup_seed(self) -> None:
        """Placeholder for backup seed functionality."""
        self.app.notify("Backup Seed not yet implemented", severity="warning")

    def _export_keys(self) -> None:
        """Placeholder for export keys functionality."""
        self.app.notify("Export Keys not yet implemented", severity="warning")
