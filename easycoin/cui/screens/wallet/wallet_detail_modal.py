from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal, ItemGrid
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static, Footer
from textual.widgets.data_table import RowKey
from easycoin.cui.clipboard import universal_copy
from easycoin.cui.widgets import ConfirmationModal, InputModal
from easycoin.models import Wallet, Address, Coin
from .export_address_modal import ExportAddressModal
from .import_address_modal import ImportAddressModal
from .make_address_modal import MakeAddressModal


class WalletDetailModal(Screen):
    """Modal for displaying wallet details."""

    BINDINGS = [
        Binding("l", "toggle_lock", "Lock/Unlock"),
        Binding("a", "make_address", "Make Address"),
        Binding("i", "import_address", "Import Address"),
        Binding("v", "export_address", "View/Export Address"),
        Binding("c", "copy_address", "Copy Address"),
        Binding("d", "delete_address", "Delete Address"),
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = "WalletDetailModal { background: $background 50%; }"

    def __init__(self):
        """Initialize wallet detail modal."""
        super().__init__()
        self.selected_address = None
        self._row_map = {}
        self._row_coin_count = {}

    def compose(self) -> ComposeResult:
        """Compose wallet detail modal layout."""
        with VerticalScroll(id="wallet_detail", classes="modal-container w-70p"):
            yield Static("Wallet Details", classes="modal-title")

            with Vertical(classes="border-solid-primary px-1 h-10 my-1"):
                yield Static(
                    "Loading...", id="wallet_name_display", classes="text-bold"
                )
                yield Static(
                    "Loading...", id="wallet_id_display", classes="text-muted"
                )

                yield Static("")

                with Horizontal():
                    with Vertical():
                        yield Static("Balance:", classes="text-muted")
                        yield Static("Loading...", id="wallet_balance")
                    with Vertical():
                        yield Static("Status:", classes="text-muted")
                        yield Static("Loading...", id="wallet_status")

            yield Static("Addresses (lock + 4 byte checksum)", classes="py-1 bold")
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
                    "View/Export", id="btn_export_address", variant="default",
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
        yield Footer()

    def on_mount(self) -> None:
        """Populate wallet info and address book table on mount."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        self._load_wallet_data()
        table.focus()

    def _load_wallet_data(self) -> None:
        """Load wallet data with error handling."""
        if not self.app.wallet:
            self.app.notify("Wallet not available in memory", severity="error")
            self.app.pop_screen()
            return

        self.query_one("#wallet_id_display", Static).update(
            self.app.wallet.id
        )

        wallet_name = self.app.wallet.name if self.app.wallet.name else "<unnamed>"
        self.query_one("#wallet_name_display", Static).update(
            wallet_name
        )

        balance = self._get_wallet_balance(self.app.wallet)
        self.query_one("#wallet_balance", Static).update(
            f"{balance:,} EC⁻¹"
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

        self._set_button_visibility()

        table = self.query_one("#address_book", DataTable)
        table.add_columns("Coins", "Balance", "Status", "Lock Type", "Address")

        self._refresh_address_book()

    def action_toggle_lock(self) -> None:
        if not self.app.wallet:
            return
        if self.app.wallet.is_locked:
            self.action_unlock()
        else:
            self.action_lock()

    @on(Button.Pressed, "#btn_close")
    def action_cancel(self) -> None:
        """Close wallet detail modal. Action handler for Escape key."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn_copy_address")
    def action_copy_address(self) -> None:
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

    @on(Button.Pressed, "#btn_unlock")
    def action_unlock(self) -> None:
        """Unlock wallet."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        def on_password_submit(password: str | None):
            if not password:
                self.app.notify("Password is required", severity="warning")
                return

            try:
                self.app.wallet.unlock(password)
            except ValueError as e:
                self.app.notify(f"Failed to unlock: {e}", severity="error")
                self.app.log_event(f"Unlock failed: {e}", "ERROR")
                return
            except Exception as e:
                self.app.notify(f"Unexpected error: {e}", severity="error")
                self.app.log_event(f"Unlock error: {e}", "ERROR")
                return

            self.app.log_event(f"Wallet unlocked: {self.app.wallet.id[:16]}...", "INFO")
            self._set_button_visibility()
            self._refresh_data()
            self._update_selection_for_cursor()

        modal_description = f"Wallet: '{self.app.wallet.name}' ({self.app.wallet.id})"
        self.app.push_screen(
            InputModal(
                "Unlock Wallet", modal_description, is_password=True,
                btn_text = "Unlock"
            ),
            on_password_submit
        )

    @on(Button.Pressed, "#btn_lock")
    def action_lock(self) -> None:
        """Lock wallet."""
        if not self.app.wallet:
            self.app.notify("Wallet not loaded", severity="error")
            return

        self.app.wallet.lock()
        self.app.log_event("Wallet locked", "INFO")
        self.selected_address = None
        self.query_one("#btn_export_address", Button).disabled = True
        self.query_one("#btn_copy_address", Button).disabled = True
        self.query_one("#btn_delete_address", Button).disabled = True
        self._set_button_visibility()
        self._refresh_status()

    @on(Button.Pressed, "#btn_make_address")
    def action_make_address(self) -> None:
        """Open make address modal."""
        self.app.push_screen(
            MakeAddressModal(self._refresh_address_book)
        )

    @on(Button.Pressed, "#btn_import_address")
    def action_import_address(self) -> None:
        """Open import address modal."""
        self.app.push_screen(
            ImportAddressModal(self._refresh_address_book)
        )

    @on(Button.Pressed, "#btn_export_address")
    def action_export_address(self) -> None:
        """Open export address modal."""
        if not self.selected_address:
            self.app.notify("No address selected", severity="warning")
            return
        self.app.push_screen(ExportAddressModal(self.selected_address))

    @on(Button.Pressed, "#btn_delete_address")
    def action_delete_address(self) -> None:
        """Delete selected address with confirmation."""
        if not self.selected_address:
            self.app.notify("No address selected", severity="warning")
            return

        table = self.query_one("#address_book", DataTable)
        cursor = table.cursor_coordinate
        if cursor is None:
            return
        row_key = table.coordinate_to_cell_key(cursor).row_key

        if row_key in self._row_coin_count and self._row_coin_count[row_key] > 0:
            self.app.notify(
                "Cannot delete address with coins", severity="warning"
            )
            return

        address_hex = self.selected_address.hex
        truncated = self._truncate_address(address_hex)
        message = (
            f"Are you sure you want to delete address "
            f"'{truncated}'? This action cannot be undone."
        )

        def confirm_delete(result: bool):
            if not result:
                return

            try:
                self.selected_address.delete()
                self.selected_address = None
                self._refresh_address_book()
            except Exception as e:
                self.app.notify(
                    f"Error deleting address: {e}", severity="error"
                )
                self.app.log_event(f"Delete address error: {e}", "ERROR")

        modal = ConfirmationModal(
            title="Confirm Delete Address",
            message=message,
            confirm_btn_variant="warning",
        )
        self.app.push_screen(modal, confirm_delete)

    def on_data_table_row_highlighted(
            self, event: DataTable.RowHighlighted
        ) -> None:
        """Handle row highlight in address book table."""
        self._update_selection_for_cursor(event.row_key)

    def _update_selection_for_cursor(self, row_key: RowKey|None = None) -> None:
        """Update selection and button states based on cursor position."""
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
        has_coins = row_key in self._row_coin_count and self._row_coin_count[row_key] > 0
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
            ).disabled = has_coins
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
        except Exception as e:
            self.app.log_event(f"Error querying addresses: {e}", "ERROR")
            return

        for address in self.app.wallet.addresses:
            known_locks.add(address.lock)
            balance = 0
            count = 0
            for coin in address.coins().get():
                balance += coin.amount
                count += 1
            entries.append(
                ('✓', address.hex, balance, count, address)
            )

        for coin in Coin.query({'wallet_id': self.app.wallet.id}).get():
            if coin.lock in known_locks:
                continue
            known_locks.add(coin.lock)
            address_hex = Address({'lock': coin.lock}).hex
            entries.append(('?', address_hex, coin.amount, 1, None))

        return entries

    def _truncate_address(self, address: str) -> str:
        """Truncate address for display."""
        if len(address) < 100:
            return address
        return f"{address[:92]}...{address[-8:]}"

    def _get_wallet_balance(self, wallet) -> int:
        """Get total balance for a wallet by summing the amounts of all
            coins owned by this wallet (any address).
        """
        wallet.coins().reload()
        return sum([c.amount for c in wallet.coins])

    def _set_status(self) -> None:
        """Set wallet status display."""
        status = "Locked" if self.app.wallet.is_locked else "Unlocked"
        status_static = self.query_one("#wallet_status", Static)
        status_static.update(status)
        if status == "Locked":
            status_static.remove_class("status-ok")
            status_static.add_class("status-warning")
        else:
            status_static.remove_class("status-warning")
            status_static.add_class("status-ok")

    def _set_button_visibility(self) -> None:
        """Set visibility of lock/unlock buttons and state of address
            buttons based on wallet lock state.
        """
        if not self.app.wallet:
            return

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

    def _refresh_data(self) -> None:
        """Refresh wallet data displays after unlock."""
        if not self.app.wallet:
            return

        self._set_status()
        balance = self._get_wallet_balance(self.app.wallet)
        self.query_one("#wallet_balance", Static).update(
            f"Balance: {balance:,} EC⁻¹"
        )

    def _refresh_status(self) -> None:
        """Refresh wallet status display and lock/unlock buttons."""
        if not self.app.wallet:
            return

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

    def _refresh_address_book(self) -> None:
        """Refresh the address book table."""
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
            lock_type = Wallet.get_lock_type(Address.parse(address_hex))
            row_key = table.add_row(
                str(count),
                str(balance),
                status,
                lock_type,
                self._truncate_address(address_hex)
            )
            self._row_coin_count[row_key] = count
            if not addr:
                addr = Address({
                    'id': 'never',
                    'lock': Address.parse(address_hex),
                })
            self._row_map[row_key] = addr
