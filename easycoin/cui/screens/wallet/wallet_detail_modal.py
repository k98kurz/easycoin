from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal, ItemGrid
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static
from textual.widgets.data_table import RowKey
from easycoin.cui.clipboard import universal_copy
from easycoin.models import Wallet, Address, Coin
from .export_address_modal import ExportAddressModal
from .import_address_modal import ImportAddressModal
from .make_address_modal import MakeAddressModal
from .unlock_modal import UnlockWalletModal


class WalletDetailModal(Screen):
    """Modal for displaying wallet details."""

    BINDINGS = [
        Binding("ctrl+c", "copy_address", "Copy Address", show=False),
    ]

    def __init__(self):
        """Initialize wallet detail modal."""
        super().__init__()
        self.selected_address = None
        self._row_map = {}

    def compose(self) -> ComposeResult:
        """Compose wallet detail modal layout."""
        with VerticalScroll(id="wallet_detail", classes="modal-container"):
            yield Static("Wallet Details", classes="modal-title")

            with Vertical(classes="border-solid-primary px-1 h-10 my-1"):
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

            yield Static("Addresses", classes="py-1 bold")
            yield DataTable(id="address_book", classes="h-min-10")

            with ItemGrid(id="modal_actions", min_column_width=18):
                yield Button("Unlock", id="btn_unlock", variant="primary")
                yield Button("Lock", id="btn_lock", variant="primary")
                yield Button(
                    "Make Address", id="btn_make_address", variant="default"
                )
                yield Button(
                    "Import Address", id="btn_import_address", variant="default",
                    disabled=True
                )
                yield Button(
                    "Export Address", id="btn_export_address", variant="default",
                    disabled=True
                )
                yield Button(
                    "Copy Address", id="btn_copy_address", variant="default",
                    disabled=True
                )
                yield Button(
                    "Delete Address", id="btn_delete_address", variant="error",
                    disabled=True
                )
                yield Button("Close", id="btn_close", variant="default")

    def on_mount(self) -> None:
        """Populate wallet info and address book table on mount."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
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
                table.add_columns("Address", "Status", "Coins", "Balance")

                self._refresh_address_book()
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
        elif event.button.id == "btn_copy_address":
            self._copy_address()
        elif event.button.id == "btn_make_address":
            self._make_address()
        elif event.button.id == "btn_export_address":
            self._export_address()
        elif event.button.id == "btn_close":
            self.app.pop_screen()

    def action_copy_address(self) -> None:
        """Action handler for Ctrl+C binding."""
        self._copy_address()

    def _copy_address(self) -> None:
        """Copy selected address hex to clipboard."""
        if not self.selected_address:
            self.app.notify("No address selected", severity="warning")
            return

        try:
            universal_copy(self.selected_address.hex)
            self.app.notify("Address copied to clipboard", severity="success")
        except Exception as e:
            self.app.notify(f"Failed to copy: {e}", severity="error")
            self.app.log_event(f"Copy address error: {e}", "ERROR")

    def on_key(self, event) -> None:
        """Handle keyboard events."""
        if event.key == "escape":
            self.app.pop_screen()

    def on_data_table_row_highlighted(
            self, event: DataTable.RowHighlighted
        ) -> None:
        """Handle row highlight in address book table."""
        self._update_selection_for_cursor(event.row_key)

    def _update_selection_for_cursor(self, row_key: RowKey|None = None) -> None:
        """Update selection and button states based on cursor position."""
        try:
            if row_key is None:
                table = self.query_one("#address_book", DataTable)
                cursor = table.cursor_coordinate
                if cursor is None:
                    self.selected_address = None
                    self.query_one(
                        "#btn_export_address", Button
                    ).disabled = True
                    self.query_one(
                        "#btn_copy_address", Button
                    ).disabled = True
                    self.query_one(
                        "#btn_delete_address", Button
                    ).disabled = True
                    return
                row_key = table.coordinate_to_cell_key(cursor).row_key

            is_known = row_key in self._row_map
            is_unlocked = not self.app.wallet.is_locked
            if is_known and is_unlocked:
                self.selected_address = self._row_map[row_key]
                self.query_one(
                    "#btn_export_address", Button
                ).disabled = False
                self.query_one(
                    "#btn_copy_address", Button
                ).disabled = False
                self.query_one(
                    "#btn_delete_address", Button
                ).disabled = False
            else:
                self.selected_address = None
                self.query_one(
                    "#btn_export_address", Button
                ).disabled = True
                self.query_one(
                    "#btn_copy_address", Button
                ).disabled = True
                self.query_one(
                    "#btn_delete_address", Button
                ).disabled = True
        except Exception as e:
            self.app.log_event(f"Error updating selection: {e}", "ERROR")

    def _get_address_book(
            self
        ) -> list[tuple[str, str, int, int, Address|None]]:
        """Build address book from wallet's addresses and coins. Returns
            a list of (status, address_hex, balance, count, address_or_none)
            tuples. Known addresses get ✓ status, unrecognized coin locks
            get ? status with None as the address object.
        """
        entries = []
        known_locks = set()

        try:
            self.app.wallet.addresses().reload()
            for address in self.app.wallet.addresses:
                try:
                    known_locks.add(address.lock)
                    balance = 0
                    count = 0
                    for coin in address.coins().get():
                        balance += coin.amount
                        count += 1
                    entries.append(
                        ('✓', address.hex, balance, count, address)
                    )
                except Exception as e:
                    self.app.log_event(
                        f"Error processing address: {e}", "ERROR"
                    )
        except Exception as e:
            self.app.log_event(f"Error querying addresses: {e}", "ERROR")

        try:
            for coin in Coin.query({'wallet_id': self.app.wallet.id}).get():
                if coin.lock in known_locks:
                    continue
                try:
                    known_locks.add(coin.lock)
                    address_hex = Address({'lock': coin.lock}).hex
                    entries.append(('?', address_hex, coin.amount, 1, None))
                except Exception as e:
                    self.app.log_event(
                        f"Error processing coin: {e}", "ERROR"
                    )
        except Exception as e:
            self.app.log_event(f"Error querying coins: {e}", "ERROR")

        return entries

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
                self._update_selection_for_cursor()
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
            self.selected_address = None
            self.query_one("#btn_export_address", Button).disabled = True
            self.query_one("#btn_copy_address", Button).disabled = True
            self.query_one("#btn_delete_address", Button).disabled = True
            self._set_button_visibility()
            self._refresh_status()
        except Exception as e:
            self.app.notify(f"Error toggling lock: {e}", severity="error")
            self.app.log_event(f"Toggle lock error: {e}", "ERROR")

    def _truncate_address(self, address: str) -> str:
        """Truncate address for display."""
        if len(address) < 100:
            return address
        return f"{address[:92]}...{address[-8:]}"

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
        """Set visibility of lock/unlock buttons and state of address
            buttons based on wallet lock state.
        """
        if not self.app.wallet:
            return

        try:
            if self.app.wallet.is_locked:
                self.query_one("#btn_lock", Button).display = "none"
                self.query_one("#btn_unlock", Button).display = "block"
                self.query_one("#btn_make_address", Button).disabled = True
                self.query_one("#btn_import_address", Button).disabled = True
            else:
                self.query_one("#btn_lock", Button).display = "block"
                self.query_one("#btn_unlock", Button).display = "none"
                self.query_one("#btn_make_address", Button).disabled = False
                self.query_one("#btn_import_address", Button).disabled = False
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

    def _make_address(self) -> None:
        """Open make address modal."""
        self.app.push_screen(
            MakeAddressModal(self._refresh_address_book)
        )

    @on(Button.Pressed, "#btn_import_address")
    def _import_address(self) -> None:
        """Open import address modal."""
        self.app.push_screen(
            ImportAddressModal(self._refresh_address_book)
        )

    def _export_address(self) -> None:
        """Open export address modal."""
        if not self.selected_address:
            self.app.notify("No address selected", severity="warning")
            return
        self.app.push_screen(ExportAddressModal(self.selected_address))

    @on(Button.Pressed, "#btn_delete_address")
    def _delete_address(self) -> None:
        """Delete selected address."""
        if not self.selected_address:
            self.app.notify("No address selected", severity="warning")
            return

        try:
            address_hex = self.selected_address.hex
            self.selected_address.delete()
            self.selected_address = None
            self.app.notify(
                f"Address deleted: {self._truncate_address(address_hex)}",
                severity="success"
            )
            self._refresh_address_book()
        except Exception as e:
            self.app.notify(f"Error deleting address: {e}", severity="error")
            self.app.log_event(f"Delete address error: {e}", "ERROR")

    def _refresh_address_book(self) -> None:
        """Refresh the address book table."""
        try:
            table = self.query_one("#address_book", DataTable)
            table.clear()
            self._row_map = {}
            self.selected_address = None

            # Disable selection-dependent buttons
            self.query_one("#btn_export_address", Button).disabled = True
            self.query_one("#btn_copy_address", Button).disabled = True
            self.query_one("#btn_delete_address", Button).disabled = True

            self._row_map = {}
            address_book = self._get_address_book()
            for status, address_hex, balance, count, addr in address_book:
                row_key = table.add_row(
                    self._truncate_address(address_hex),
                    status,
                    str(count),
                    str(balance)
                )
                if addr:
                    self._row_map[row_key] = addr
        except Exception as e:
            self.app.notify(f"Error refreshing address book: {e}", severity="error")
            self.app.log_event(f"Refresh address book error: {e}", "ERROR")
