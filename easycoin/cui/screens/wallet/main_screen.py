from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static
from easycoin.models import Wallet, Coin
from ..base import BaseScreen
from easycoin.cui.widgets import ConfirmationModal, InputModal
from .create_wallet_modal import CreateWalletModal
from .restore_wallet_modal import RestoreWalletModal
from .wallet_detail_modal import WalletDetailModal


class WalletListScreen(BaseScreen):
    """Manage multiple wallets."""

    TAB_ID = "tab_wallet"

    def __init__(self):
        """Initialize wallet list screen."""
        super().__init__()
        self._wallet_id_map = {}

    BINDINGS = [
        ("n", "create_wallet", "New"),
        ("r", "restore_wallet", "Restore"),
        ("s", "select_wallet", "Select"),
        ("d", "delete_wallet", "Delete"),
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
                yield Button(
                    "Create New",
                    id="btn_create",
                    variant="primary",
                )
                yield Button(
                    "Restore",
                    id="btn_restore",
                    variant="default",
                )
                yield Button(
                    "Select",
                    id="btn_select",
                    variant="success",
                )
                yield Button(
                    "Delete",
                    id="btn_delete",
                    variant="error",
                )

    def on_mount(self) -> None:
        """Populate wallets table on mount and auto-navigate if appropriate."""
        super().on_mount()
        table = self.query_one("#wallets_table", DataTable)
        table.add_columns("Name", "Wallet ID", "Status", "Balance", "Active", "Tags")
        table.cursor_type = "row"
        self.call_later(self._load_wallet_list_data)
        self.call_later(self._update_button_state)

    def on_screen_resume(self, event) -> None:
        """Refresh wallet list when returning from modal."""
        super().on_screen_resume(event)
        self._refresh_table()

    def _load_wallet_list_data(self) -> None:
        """Load wallet list data with error handling."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            table.clear()
            self._wallet_id_map.clear()

            try:
                for wallet in Wallet.query().get():
                    try:
                        is_active = self.app.wallet and wallet.id == self.app.wallet.id
                        active_marker = "✓" if is_active else ""
                        if is_active:
                            status = "Locked" if self.app.wallet.is_locked else "Unlocked"
                        else:
                            status = "Locked" if wallet.is_locked else "Unlocked"
                        balance = self._get_wallet_balance(wallet)
                        display_id = self._truncate_id(wallet.id)

                        table.add_row(
                            wallet.name or '',
                            display_id,
                            status,
                            str(balance),
                            active_marker,
                            wallet.tags or ''
                        )
                        self._wallet_id_map[display_id] = wallet.id
                    except Exception as e:
                        self.log_event(f"Error processing wallet: {e}", "ERROR")
            except Exception as e:
                self.app.notify(f"Error loading wallets: {e}", severity="error")
                self.log_event(f"Error querying wallets: {e}", "ERROR")
        except Exception as e:
                self.app.notify(f"Error loading wallet list: {e}", severity="error")
                self.log_event(f"Error in _load_wallet_list_data: {e}", "ERROR")

        self._update_button_state()

    @on(Button.Pressed, "#btn_create")
    def action_create_wallet(self) -> None:
        """Create new wallet."""
        #self._disable_buttons()
        self.app.push_screen(CreateWalletModal(self._refresh_table))

    @on(Button.Pressed, "#btn_restore")
    def action_restore_wallet(self) -> None:
        """Restore wallet from seed."""
        self.app.push_screen(RestoreWalletModal(self._refresh_table))

    @on(Button.Pressed, "#btn_select")
    def action_select_wallet(self) -> None:
        """Select and unlock a wallet."""
        table = self.query_one("#wallets_table", DataTable)
        if table.cursor_row is None:
            self.app.notify("No wallet selected", severity="warning")
            return

        try:
            display_id = table.get_row_at(table.cursor_row)[1]
        except BaseException:
            return self.app.notify("No wallet selected", severity="warning")
        wallet_id = self._wallet_id_map.get(display_id)
        wallet = Wallet.find(wallet_id)

        if not wallet_id:
            self.app.notify("Wallet not found", severity="error")
            self.log_event(f"Wallet ID not in mapping: {display_id}", "ERROR")
            return

        if (self.app.wallet and self.app.wallet.id == wallet_id
                and not self.app.wallet.is_locked):
            self.app.push_screen(WalletDetailModal())
            return

        def on_password_submit(password: str | None):
            if not password:
                self.app.notify("Password is required", severity="warning")
                return

            try:
                wallet.unlock(password)
            except ValueError as e:
                self.app.notify(f"Failed to unlock: {e}", severity="error")
                self.app.log_event(f"Unlock failed: {e}", "ERROR")
                return
            except Exception as e:
                self.app.notify(f"Unexpected error: {e}", severity="error")
                self.app.log_event(f"Unlock error: {e}", "ERROR")
                return

            self.app.wallet = wallet
            self.app.log_event(f"Wallet unlocked: {wallet_id}...", "INFO")

            self.log_event(f"Selected wallet: {wallet_id}...", "INFO")
            self.app.push_screen(WalletDetailModal())
            self._refresh_table()

        modal_description = f"Wallet: '{wallet.name}' ({wallet.id})"
        self.app.push_screen(
            InputModal(
                "Unlock Wallet", modal_description, is_password=True,
                btn_text = "Unlock"
            ),
            on_password_submit
        )

    @on(Button.Pressed, "#btn_delete")
    async def action_delete_wallet(self) -> None:
        """Delete selected wallet with confirmation."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            if table.cursor_row is None:
                self.app.notify("No wallet selected", severity="warning")
                return

            display_id = table.get_row_at(table.cursor_row)[1]
            wallet_id = self._wallet_id_map.get(display_id)

            if not wallet_id:
                self.app.notify("Wallet not found", severity="error")
                self.log_event(f"Wallet ID not in mapping: {display_id}", "ERROR")
                return

            if self.app.wallet and wallet_id == self.app.wallet.id:
                self.app.notify("Cannot delete active wallet", severity="warning")
                return

            wallet_name = table.get_row_at(table.cursor_row)[0]
            confirmation_message = (
                f"Are you sure you want to delete wallet '{wallet_name}' "
                f"({wallet_id})?\n\nThis action cannot be undone."
            )

            def confirm_delete(result: bool):
                if not result:
                    return

                try:
                    wallet = Wallet.find(wallet_id)
                    if wallet:
                        wallet.delete()
                        self.log_event(
                            f"Deleted wallet: {wallet_id[:16]}...", "INFO"
                        )
                        self._refresh_table()
                    else:
                        self.app.notify("Wallet not found", severity="error")
                except Exception as e:
                    self.app.notify(
                        f"Failed to delete wallet: {e}", severity="error"
                    )
                    self.log_event(f"Delete wallet failed: {e}", "ERROR")

            modal = ConfirmationModal(
                title="Confirm Delete Wallet",
                message=confirmation_message,
                confirm_btn_variant="warning",
            )
            self.app.push_screen(modal, confirm_delete)
        except Exception as e:
            self.app.notify(f"Error preparing delete: {e}", severity="error")
            self.log_event(f"Delete wallet preparation error: {e}", "ERROR")

    def _refresh_table(self) -> None:
        """Refresh wallets table."""
        try:
            #self._enable_buttons()
            table = self.query_one("#wallets_table", DataTable)
            table.clear()
            self._wallet_id_map.clear()

            try:
                for wallet in Wallet.query().get():
                    try:
                        is_active = self.app.wallet and wallet.id == self.app.wallet.id
                        active_marker = "✓" if is_active else ""
                        if is_active:
                            status = "Locked" if self.app.wallet.is_locked else "Unlocked"
                        else:
                            status = "Locked" if wallet.is_locked else "Unlocked"
                        balance = self._get_wallet_balance(wallet)
                        display_id = self._truncate_id(wallet.id)

                        table.add_row(
                            wallet.name or '',
                            display_id,
                            status,
                            str(balance),
                            active_marker,
                            wallet.tags or ''
                        )
                        self._wallet_id_map[display_id] = wallet.id
                    except Exception as e:
                        self.log_event(f"Error refreshing wallet row: {e}", "ERROR")
            except Exception as e:
                self.app.notify(f"Error querying wallets for refresh: {e}", severity="error")
                self.log_event(f"Error in _refresh_table query: {e}", "ERROR")
        except Exception as e:
            self.log_event(f"Error in _refresh_table: {e}", "ERROR")

        self._update_button_state()

    def _get_wallet_balance(self, wallet) -> int:
        """Get total balance for a wallet by summing the amounts of all
            coins owned by this wallet (any address).
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

    def _update_button_state(self) -> None:
        """Enable/disable Select and Delete buttons based on wallet count."""
        try:
            table = self.query_one("#wallets_table", DataTable)
            has_wallets = table.row_count > 0

            try:
                self.query_one("#btn_select", Button).disabled = not has_wallets
                self.query_one("#btn_delete", Button).disabled = not has_wallets
            except Exception as e:
                self.log_event(f"Error updating button state: {e}", "ERROR")
        except Exception as e:
            self.log_event(f"Error accessing table for button state: {e}", "ERROR")
