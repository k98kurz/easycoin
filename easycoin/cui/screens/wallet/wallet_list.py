from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static
from easycoin.models import Wallet, Coin
from ..base import BaseScreen
from easycoin.cui.widgets.confirmation_modal import ConfirmationModal


class WalletListScreen(BaseScreen):
    """Manage multiple wallets."""

    TAB_ID = "tab_wallet"

    BINDINGS = [
        ("n", "create_wallet", "New Wallet"),
        ("r", "restore_wallet", "Restore Wallet"),
    ]

    def compose(self) -> ComposeResult:
        """Compose wallet list layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose wallet list content."""
        with Vertical(id="wallet_list"):
            yield Static("Wallets", classes="panel-title")
            yield DataTable(id="wallets_table")

            with Horizontal(id="list_actions"):
                yield Button("Create New", id="btn_create", variant="primary")
                yield Button("Restore", id="btn_restore", variant="default")
                yield Button("Switch To", id="btn_switch", variant="success")
                yield Button("Delete", id="btn_delete", variant="error")

    def on_mount(self) -> None:
        """Populate wallets table on mount and auto-navigate if appropriate."""
        super().on_mount()
        self.call_later(self._load_wallet_list_data)

    def _load_wallet_list_data(self) -> None:
        """Load wallet list data with error handling."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            table.add_columns("Wallet ID", "Status", "Balance", "Active")

            try:
                for wallet in Wallet.query().get():
                    try:
                        status = "Locked" if wallet.is_locked else "Unlocked"
                        is_active = wallet.id == self.app.current_wallet_id
                        active_marker = "✓" if is_active else ""
                        balance = self._get_wallet_balance(wallet)

                        table.add_row(
                            self._truncate_id(wallet.id),
                            status,
                            str(balance),
                            active_marker
                        )
                    except Exception as e:
                        self.log_event(f"Error processing wallet: {e}", "ERROR")
            except Exception as e:
                self.app.notify(f"Error loading wallets: {e}", severity="error")
                self.log_event(f"Error querying wallets: {e}", "ERROR")

            if self.app.current_wallet_id and not self.app.wallet_locked:
                try:
                    wallet = Wallet.find(self.app.current_wallet_id)
                    if wallet and not wallet.is_locked:
                        self._navigate_to_wallet_screen(self.app.current_wallet_id)
                except Exception as e:
                    self.log_event(f"Error checking wallet for navigation: {e}", "ERROR")
        except Exception as e:
            self.app.notify(f"Error loading wallet list: {e}", severity="error")
            self.log_event(f"Error in _load_wallet_list_data: {e}", "ERROR")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_create":
            self.action_create_wallet()
        elif event.button.id == "btn_restore":
            self.action_restore_wallet()
        elif event.button.id == "btn_switch":
            self._switch_wallet()
        elif event.button.id == "btn_delete":
            self._delete_wallet()

    def action_create_wallet(self) -> None:
        """Create new wallet."""
        self.app.notify("Setup Wallet screen not yet implemented", severity="warning")

    def action_restore_wallet(self) -> None:
        """Restore wallet from seed."""
        self.app.notify("Restore Wallet screen not yet implemented", severity="warning")

    def _switch_wallet(self) -> None:
        """Switch to selected wallet."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            if table.cursor_row is None:
                self.app.notify("No wallet selected", severity="warning")
                return

            wallet_id = table.get_row(table.cursor_row)[0]

            if self.app.current_wallet_id == wallet_id:
                self.app.notify("This wallet is already active", severity="warning")
                return

            if not self.app.wallet_locked:
                self.app.notify(
                    "Lock the current wallet first before switching",
                    severity="warning"
                )
                return

            self.app.current_wallet_id = wallet_id
            self.app.config.set_current_wallet_id(wallet_id)
            self.app.wallet_locked = True

            self.log_event(f"Switched to wallet: {wallet_id[:16]}...", "INFO")

            wallet = Wallet.find(wallet_id)
            if wallet and not wallet.is_locked:
                self._navigate_to_wallet_screen(wallet_id)
            else:
                self.app.notify(f"Wallet selected: {wallet_id[:16]}...", severity="information")
                self._refresh_table()
        except Exception as e:
            self.app.notify(f"Error switching wallet: {e}", severity="error")
            self.log_event(f"Switch wallet error: {e}", "ERROR")

    def _delete_wallet(self) -> None:
        """Delete selected wallet with confirmation."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            if table.cursor_row is None:
                self.app.notify("No wallet selected", severity="warning")
                return

            wallet_id = table.get_row(table.cursor_row)[0]
            wallet = Wallet.find(wallet_id)

            if not wallet:
                self.app.notify("Wallet not found", severity="error")
                return

            if wallet.id == self.app.current_wallet_id:
                self.app.notify("Cannot delete active wallet", severity="warning")
                return

            confirmation_message = (
                f"Are you sure you want to delete wallet "
                f"{self._truncate_id(wallet_id)}? This action cannot be undone."
            )

            def confirm_delete():
                try:
                    wallet.delete()
                    self.log_event(f"Deleted wallet: {wallet_id[:16]}...", "INFO")
                    self.app.notify("Wallet deleted successfully", severity="information")
                    self._refresh_table()
                except Exception as e:
                    self.app.notify(f"Failed to delete wallet: {e}", severity="error")
                    self.log_event(f"Delete wallet failed: {e}", "ERROR")

            self.app.push_screen(
                ConfirmationModal(
                    title="Confirm Delete Wallet",
                    message=confirmation_message,
                    callback=confirm_delete
                )
            )
        except Exception as e:
            self.app.notify(f"Error preparing delete: {e}", severity="error")
            self.log_event(f"Delete wallet preparation error: {e}", "ERROR")

    def _navigate_to_wallet_screen(self, wallet_id: str) -> None:
        """Navigate to the wallet screen for the given wallet ID."""
        from .wallet_screen import WalletScreen
        self.app.push_screen(WalletScreen(wallet_id))

    def _refresh_table(self) -> None:
        """Refresh wallets table."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            table.clear()

            try:
                for wallet in Wallet.query().get():
                    try:
                        status = "Locked" if wallet.is_locked else "Unlocked"
                        is_active = wallet.id == self.app.current_wallet_id
                        active_marker = "✓" if is_active else ""
                        balance = self._get_wallet_balance(wallet)

                        table.add_row(
                            self._truncate_id(wallet.id),
                            status,
                            str(balance),
                            active_marker
                        )
                    except Exception as e:
                        self.log_event(f"Error refreshing wallet row: {e}", "ERROR")
            except Exception as e:
                self.app.notify(f"Error querying wallets for refresh: {e}", severity="error")
                self.log_event(f"Error in _refresh_table query: {e}", "ERROR")
        except Exception as e:
            self.log_event(f"Error in _refresh_table: {e}", "ERROR")

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
            self.log_event(f"Error calculating wallet balance: {e}", "ERROR")
        return total

    def _truncate_id(self, wallet_id: str) -> str:
        """Truncate wallet ID for display."""
        return f"{wallet_id[:16]}..."
