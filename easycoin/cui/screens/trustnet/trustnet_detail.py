from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static, Footer
from tapescript import Script
from easycoin.models import TrustNet, Snapshot, Address
from easycoin.helpers import (
    format_timestamp, format_timestamp_relative,
    truncate_text, format_script_src
)
from easycoin.cui.widgets import ECTextArea


class TrustNetDetailModal(ModalScreen):
    """Modal for viewing TrustNet details (read-only)."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, trustnet_id: str):
        super().__init__()
        self.trustnet_id = trustnet_id
        self.trustnet = None
        self._row_map_members = {}
        self._row_map_snapshots = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="modal-container w-80p h-70p"):
            yield Static("TrustNet Details", classes="modal-title")

            with Vertical(
                    id="trustnet_info", classes="border-solid-primary px-1 h-8 my-1"
                ):
                yield Static(
                    "ID: ...", id="trustnet_id_display", classes="text-bold"
                )
                yield Static(
                    "Name: ...", id="trustnet_name_display", classes="text-muted"
                )
                yield Static(
                    "Status: ...", id="trustnet_status_display",
                    classes="text-muted"
                )
                yield Static(
                    "Quorum: ...", id="trustnet_quorum_display",
                    classes="text-muted"
                )

            yield Static("Features:", classes="text-bold my-1")
            yield Static("", id="features_display", classes="px-1 mb-1")

            yield Static("Lock Script:", classes="text-bold my-1")
            yield ECTextArea(
                "", id="lock_script_display", read_only=True, classes="h-8"
            )

            yield Static("Members:", classes="text-bold my-1")
            yield DataTable(id="members_table", classes="h-min-8 mb-1")

            yield Static("Snapshots:", classes="text-bold my-1")
            yield DataTable(id="snapshots_table", classes="h-min-8 mb-1")

            with Horizontal(id="modal_actions"):
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        self._setup_tables()
        self._load_trustnet()

    def _setup_tables(self) -> None:
        members_table = self.query_one("#members_table")
        members_table.cursor_type = "row"
        members_table.add_columns(
            ("Address", "address"),
            ("Has Delegate", "has_delegate"),
            ("Delegate Script", "delegate_script"),
        )

        snapshots_table = self.query_one("#snapshots_table")
        snapshots_table.cursor_type = "row"
        snapshots_table.add_columns(
            ("Height", "height"),
            ("Timestamp", "timestamp"),
            ("State", "state"),
            ("Chunk Count", "chunk_count"),
        )

    def _load_trustnet(self) -> None:
        self.trustnet = TrustNet.find(self.trustnet_id)
        if not self.trustnet:
            self.app.notify("TrustNet not found", severity="error")
            self.dismiss()
            return

        self._update_header()
        self._populate_features()
        self._populate_lock_script()
        self._populate_members_table()
        self._populate_snapshots_table()

    def _update_header(self) -> None:
        display_id = truncate_text(
            self.trustnet.id, prefix_len=16, suffix_len=8
        )
        self.query_one("#trustnet_id_display").update(f"ID: {display_id}")
        self.query_one("#trustnet_name_display").update(
            f"Name: {self.trustnet.name or '<unnamed>'}"
        )

        status = "Active" if self.trustnet.active else "Inactive"
        status_static = self.query_one("#trustnet_status_display")
        status_static.update(f"Status: {status}")
        if self.trustnet.active:
            status_static.add_class("status-ok")
        else:
            status_static.add_class("status-warning")

        quorum = (
            str(self.trustnet.quorum)
            if self.trustnet.quorum is not None
            else "None"
        )
        self.query_one("#trustnet_quorum_display").update(f"Quorum: {quorum}")

    def _populate_features(self) -> None:
        features = self.trustnet.features
        if not features:
            self.query_one("#features_display").update("No features enabled")
            return

        feature_names = [
            f.name.replace("_", " ").title() for f in features
        ]
        features_str = ", ".join(feature_names)
        self.query_one("#features_display").update(features_str)

    def _populate_lock_script(self) -> None:
        try:
            decompiled = Script.from_bytes(self.trustnet.lock).src
            formatted = format_script_src(decompiled)
            self.query_one("#lock_script_display").text = formatted
        except Exception as e:
            self.query_one("#lock_script_display").text = (
                f"Error decompiling lock script: {e}"
            )

    def _populate_members_table(self) -> None:
        members_table = self.query_one("#members_table")
        members_table.clear()
        self._row_map_members = {}

        for member_lock in self.trustnet.members:
            address = Address({"lock": member_lock})
            display_address = (
                address.hex[:100] + "..."
                if len(address.hex) > 100
                else address.hex
            )

            has_delegate = str(member_lock) in self.trustnet.delegate_scripts
            has_delegate_display = "Yes" if has_delegate else "No"

            delegate_script = self.trustnet.delegate_scripts.get(
                str(member_lock), None
            )
            if delegate_script:
                try:
                    decompiled = Script.from_bytes(delegate_script).src
                    delegate_display = truncate_text(
                        decompiled, prefix_len=20, suffix_len=10
                    )
                except Exception:
                    delegate_display = "(error)"
            else:
                delegate_display = ""

            row_key = members_table.add_row(
                display_address,
                has_delegate_display,
                delegate_display,
            )
            self._row_map_members[row_key] = member_lock

    def _populate_snapshots_table(self) -> None:
        snapshots_table = self.query_one("#snapshots_table")
        snapshots_table.clear()
        self._row_map_snapshots = {}

        try:
            snapshots = Snapshot.query({
                'net_id': self.trustnet.id
            }).order_by('timestamp', 'desc').get()
        except Exception:
            snapshots = []

        for height, snapshot in enumerate(snapshots, start=1):
            timestamp = format_timestamp(snapshot.timestamp)
            timestamp_relative = format_timestamp_relative(snapshot.timestamp)
            timestamp_display = f"{timestamp} ({timestamp_relative})"

            state_hex = snapshot.state.hex()
            state_display = truncate_text(
                state_hex, prefix_len=16, suffix_len=8
            )

            chunk_count = 0
            if snapshot.chunk_ids:
                chunk_count = len(snapshot.chunk_ids.split(','))

            row_key = snapshots_table.add_row(
                str(height),
                timestamp_display,
                state_display,
                str(chunk_count),
            )
            self._row_map_snapshots[row_key] = snapshot

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()
