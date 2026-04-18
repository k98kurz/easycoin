from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button, DataTable, Input, RadioSet, RadioButton, Static
)
from textual.widgets.data_table import RowKey
from datetime import datetime, timedelta
from typing import Callable
from easycoin.models import Txn, Confirmation, Attestation
from ..base import BaseScreen
from easycoin.helpers import format_balance, format_timestamp, truncate_text
from .new_txn.modal import NewTransactionModal
from .txn_detail_modal import TransactionDetailModal


class TransactionsScreen(BaseScreen):
    """View and send transactions."""

    TAB_ID = "tab_transactions"

    BINDINGS = [
        ("n", "new_transaction", "New Transaction"),
        ("v", "view_transaction", "View Transaction"),
        ("f5", "refresh_transactions", "Refresh"),
    ]

    def __init__(self):
        """Initialize transactions screen."""
        super().__init__()
        self.selected_txn_id = None
        self.txn_id_map = {}
        self._is_initializing = True
        self._page: int = 1
        self._page_size: int = 50
        self._total_count: int = 0

    def compose(self) -> ComposeResult:
        """Compose transactions screen layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose transactions screen content area."""
        with VerticalScroll(id="transactions_screen"):
            yield Static("Transactions", classes="panel-title")

            with Horizontal(id="date_filters", classes="h-12"):
                with Vertical(id="quick_date_filters"):
                    yield Static("Date:", classes="config-label m-1")
                    yield RadioSet(
                        RadioButton("All time", id="date_all", value=True),
                        RadioButton("Today", id="date_today"),
                        RadioButton("Last 7 days", id="date_7days"),
                        RadioButton("Last 30 days", id="date_30days"),
                        RadioButton("Custom", id="date_custom"),
                        id="date_filter",
                        classes="h-7",
                    )
                with Vertical(id="custom_date_section", classes="hidden"):
                    yield Static(
                        "Start Date (YYYY-MM-DD):",
                        classes="config-label m-1",
                    )
                    yield Input(
                        placeholder="YYYY-MM-DD",
                        id="start_date",
                        classes="form-input"
                    )
                    yield Static(
                        "End Date (YYYY-MM-DD):",
                        classes="config-label m-1",
                    )
                    yield Input(
                        placeholder="YYYY-MM-DD",
                        id="end_date",
                        classes="form-input"
                    )
                with Vertical(id="amount_filter"):
                    yield Static("Min Input Amount:", classes="config-label m-1")
                    yield Input(
                        placeholder="Minimum input amount to display",
                        id="min_amount",
                        classes="form-input"
                    )

            yield DataTable(id="transactions_table", classes="mt-1 h-16")

            with Horizontal(id="txn_actions", classes="h-6"):
                yield Button("← Previous", id="btn_prev_page", variant="default")
                yield Static(
                    "Page 1 of 1", id="page_info", classes="text-center w-12 mt-2"
                )
                yield Button("Next →", id="btn_next_page", variant="default")
                yield Button("New Transaction", id="btn_new", variant="primary")
                yield Button("Refresh", id="btn_refresh", variant="default")
                yield Button(
                    "View Details", id="btn_view_txn", variant="default",
                    disabled=True
                )

    def on_mount(self) -> None:
        """Initialize table and load data on mount."""
        table = self.query_one("#transactions_table")
        table.cursor_type = "row"
        table.add_columns(
            "Txn ID",
            "Timestamp",
            "Inputs",
            "Outputs",
            "In Amount",
            "Burned",
            "Out Amount",
            "Attestations",
            "Confirmed"
        )
        self.app.state.subscribe("append_new_txn", self._on_new_transaction)
        self.call_later(self._finish_initialization)

    def _finish_initialization(self) -> None:
        """Complete initialization and load data."""
        self._is_initializing = False

    def on_unmount(self) -> None:
        """Clean up subscriptions on unmount."""
        self.app.state.unsubscribe("append_new_txn", self._on_new_transaction)

    def on_screen_resume(self, event) -> None:
        """Refresh data when returning from modal."""
        super().on_screen_resume(event)
        self._load_transactions()

    def _on_new_transaction(self, txn_id: str) -> None:
        """Refresh transactions table when new transaction is synced."""
        if self.screen.visible:
            self._load_transactions()

    def on_txn_validated(self, result) -> None:
        """Handle transaction validation result."""
        self._load_transactions()

    @on(RadioSet.Changed, "#date_filter")
    def on_date_filter_changed(self, event: RadioSet.Changed) -> None:
        """Handle date filter radio set changes."""
        radio_set = self.query_one("#date_filter")
        custom_section = self.query_one("#custom_date_section")

        is_custom = radio_set.pressed_index == 4

        if is_custom:
            custom_section.remove_class("hidden")
        else:
            custom_section.add_class("hidden")

        self._page = 1
        self._load_transactions()

    @on(Input.Changed, "#start_date")
    def on_start_date_changed(self, event: Input.Changed) -> None:
        """Handle start date input changes."""
        self._page = 1
        self._load_transactions()

    @on(Input.Changed, "#end_date")
    def on_end_date_changed(self, event: Input.Changed) -> None:
        """Handle end date input changes."""
        self._page = 1
        self._load_transactions()

    @on(Input.Changed, "#min_amount")
    def on_min_amount_changed(self, event: Input.Changed) -> None:
        """Handle minimum amount input changes."""
        self._page = 1
        self._load_transactions()

    @on(Button.Pressed, "#btn_new")
    def action_new_transaction(self) -> None:
        """Open new transaction modal."""
        self.app.push_screen(NewTransactionModal())

    @on(Button.Pressed, "#btn_refresh")
    def action_refresh_transactions(self) -> None:
        """Refresh transactions data."""
        self.log_event("Refreshing transactions", "INFO")
        self._page = 1
        self._load_transactions()

    @on(Button.Pressed, "#btn_prev_page")
    def _on_prev_page(self) -> None:
        """Handle previous page button press."""
        if self._page > 1:
            self._page -= 1
            self._load_transactions()

    @on(Button.Pressed, "#btn_next_page")
    def _on_next_page(self) -> None:
        """Handle next page button press."""
        if self._page * self._page_size < self._total_count:
            self._page += 1
            self._load_transactions()

    @on(DataTable.RowSelected, "#transactions_table")
    @on(Button.Pressed, "#btn_view_txn")
    def action_view_transaction(self) -> None:
        """View details of selected transaction."""
        if not self.selected_txn_id:
            return

        self.app.push_screen(TransactionDetailModal(self.selected_txn_id))

    @on(DataTable.RowHighlighted, "#transactions_table")
    def on_table_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle table row higlight to enable View Details."""
        row_key = event.row_key
        self.selected_txn_id = self.txn_id_map.get(row_key)
        btn_view_txn = self.query_one("#btn_view_txn")
        btn_view_txn.disabled = self.selected_txn_id is None

    def _load_transactions(self) -> None:
        """Load transactions from database and populate table."""
        if self._is_initializing:
            return
        try:
            table = self.query_one("#transactions_table")
            table.clear()
            self.txn_id_map.clear()

            radio_set = self.query_one("#date_filter")
            start_date_input = self.query_one("#start_date")
            end_date_input = self.query_one("#end_date")
            min_amount_input = self.query_one("#min_amount")

            filter_type = radio_set.pressed_index

            date_conditions = self._get_date_conditions(
                filter_type,
                start_date_input.value,
                end_date_input.value
            )

            query = Txn.query()

            if date_conditions:
                query = date_conditions(query)

            query = query.order_by('timestamp', 'desc')

            self._total_count = query.count()
            transactions = query.skip(
                (self._page - 1) * self._page_size
            ).take(self._page_size)

            for txn in transactions:
                self._add_txn_to_table(txn, min_amount_input.value)

            self._update_pagination_controls()
            self.log_event(
                f"Loaded {len(transactions)} transactions",
                "INFO"
            )
        except Exception as e:
            self.log_event(f"Error loading transactions: {e}", "ERROR")
            self.app.notify(f"Error loading transactions: {e}", severity="error")

    def _get_date_conditions(
            self, filter_type: int, start_date_str: str,
            end_date_str: str
        ) -> Callable | None:
        """Get date filter conditions based on filter type."""
        if filter_type == 1:
            start_ts = int(datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).timestamp())
            return lambda q: q.greater_or_equal('timestamp', start_ts)
        elif filter_type == 2:
            cutoff_ts = int((datetime.now() - timedelta(days=7)).timestamp())
            return lambda q: q.greater_or_equal('timestamp', cutoff_ts)
        elif filter_type == 3:
            cutoff_ts = int((datetime.now() - timedelta(days=30)).timestamp())
            return lambda q: q.greater_or_equal('timestamp', cutoff_ts)
        elif filter_type == 4:
            start_ts = self._parse_date(start_date_str)
            end_ts = self._parse_date(end_date_str)
            if start_ts is not None and end_ts is not None:
                return lambda q: q.greater_or_equal(
                    'timestamp', start_ts
                ).less_or_equal('timestamp', end_ts)
        return None

    def _parse_date(self, date_str: str) -> int | None:
        """Parse YYYY-MM-DD to unix timestamp."""
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return int(dt.timestamp())
        except ValueError:
            return None

    def _add_txn_to_table(self, txn: Txn, min_amount_str: str) -> None:
        """Add transaction to table after filtering."""
        try:
            in_amount, out_amount, burned = self._calculate_amounts(txn)

            if min_amount_str:
                try:
                    min_amount = float(min_amount_str)
                    if in_amount < min_amount:
                        return
                except ValueError:
                    pass

            attestation_count = txn.attestations().query().count()
            is_confirmed = 1 if txn.confirmation else 0

            table = self.query_one("#transactions_table")
            row_key = table.add_row(
                truncate_text(txn.id, prefix_len=8, suffix_len=4),
                format_timestamp(txn.timestamp),
                len(txn.input_ids),
                len(txn.output_ids),
                format_balance(in_amount),
                format_balance(burned),
                format_balance(out_amount),
                attestation_count,
                is_confirmed
            )
            self.txn_id_map[row_key] = txn.id

        except Exception as e:
            self.log_event(f"Error adding txn {txn.id}: {e}", "DEBUG")

    def _calculate_amounts(self, txn: Txn) -> tuple[int, int, int]:
        """Calculate in/out amounts and burned fee."""
        try:
            in_amount = sum(c.amount for c in txn.inputs)
            out_amount = sum(c.amount for c in txn.outputs)
            burned = max(0, in_amount - out_amount)
            return in_amount, out_amount, burned
        except Exception as e:
            self.log_event(f"Error calculating amounts for {txn.id}: {e}", "DEBUG")
            return 0, 0, 0

    def _update_pagination_controls(self) -> None:
        """Update pagination info and button states."""
        total_pages = (
            (self._total_count + self._page_size - 1) // self._page_size
            if self._total_count > 0 else 1
        )
        self.query_one("#page_info").update(
            f"Page {self._page} of {total_pages}"
        )
        self.query_one("#btn_prev_page").disabled = self._page <= 1
        self.query_one("#btn_next_page").disabled = (
            self._page * self._page_size >= self._total_count
        )
