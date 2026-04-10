from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Static
from easycoin.cui.widgets import ConfirmationModal
from ..base import BaseScreen
from .add_peer import AddPeerModal


class NetworkScreen(BaseScreen):
    """Configure network settings, view connected peers, manage bootstrap nodes."""

    TAB_ID = "tab_network"

    def compose(self) -> ComposeResult:
        """Compose network layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose network content."""
        with VerticalScroll(id="network_content"):
            yield Static("Network", classes="panel-title")

            with Vertical(id="network_stats", classes="card h-8"):
                yield Static("Network Statistics", classes="text-bold mb-1")
                with Horizontal(classes="h-3"):
                    with Vertical(classes="w-25p"):
                        yield Static("Messages Sent:", classes="text-muted")
                        yield Static("0", id="messages_sent", classes="text-bold")
                    with Vertical(classes="w-25p"):
                        yield Static("Data Sent:", classes="text-muted")
                        yield Static("0", id="data_sent", classes="text-bold")
                    with Vertical(classes="w-25p"):
                        yield Static("Messages Received:", classes="text-muted")
                        yield Static("0", id="messages_received", classes="text-bold")
                    with Vertical(classes="w-25p"):
                        yield Static("Data Received:", classes="text-muted")
                        yield Static("0", id="data_received", classes="text-bold")

            with Horizontal(classes="h-22 mb-1"):
                with Vertical(classes="w-50p card"):
                    yield Static("Connected Peers", classes="text-bold mb-1")
                    yield DataTable(id="connected_peers_table", classes="h-10")
                    with Horizontal(classes="h-min-4"):
                        yield Button(
                            "Add", id="btn_add_peer", variant="primary"
                        )
                        yield Button(
                            "Remove", id="btn_remove_peer", variant="warning"
                        )

                with Vertical(classes="w-50p card"):
                    yield Static("Bootstrap Nodes", classes="text-bold mb-1")
                    yield DataTable(id="bootstrap_nodes_table", classes="h-10")
                    with Horizontal(classes="h-min-4"):
                        yield Button(
                            "Add", id="btn_add_bootstrap", variant="primary"
                        )
                        yield Button(
                            "Remove", id="btn_remove_bootstrap", variant="warning"
                        )

    def on_mount(self) -> None:
        """Initialize network tables and load data on mount."""
        self._setup_tables()
        self.app.config.subscribe(
            "set_bootstrap_nodes",
            self._load_bootstrap_nodes
        )
        self.app.state.subscribe(
            "set_connected_peers",
            self._load_peers
        )

    def on_unmount(self) -> None:
        """Clean up subscriptions on unmount."""
        self.app.config.unsubscribe(
            "set_bootstrap_nodes",
            self._load_bootstrap_nodes
        )
        self.app.state.unsubscribe(
            "set_connected_peers",
            self._load_peers
        )

    def on_screen_resume(self, event) -> None:
        """Refresh data when returning from modal."""
        super().on_screen_resume(event)
        self._load_bootstrap_nodes()
        self._load_peers()

    def _setup_tables(self) -> None:
        """Setup connected peers and bootstrap nodes tables."""
        try:
            peers_table = self.query_one("#connected_peers_table")
            peers_table.add_columns("Peer Address", "Port", "RxMessages", "TxMessages")
            peers_table.cursor_type = "row"
        except Exception as e:
            self.log_event(f"Error setting up peers table: {e}", "ERROR")

        try:
            bootstrap_table = self.query_one("#bootstrap_nodes_table")
            bootstrap_table.add_columns("Address", "Port")
            bootstrap_table.cursor_type = "row"
        except Exception as e:
            self.log_event(f"Error setting up bootstrap table: {e}", "ERROR")

    def _load_peers(self, *args) -> None:
        """Load connected peers from app state into table."""
        try:
            peers_table = self.query_one("#connected_peers_table")
            peers_table.clear()

            peers = self.app.state.get("connected_peers") or []
            self.app.log_event(f"{peers=}", "DEBUG")
            for peer in peers:
                peers_table.add_row(
                    peer["address"],
                    peer["port"],
                    peer["rx_messages"],
                    peer["tx_messages"]
                )

            self._update_button_state()
        except Exception as e:
            self.app.notify(f"Error loading peers: {e}", severity="error")
            self.log_event(f"Load peers error: {e}", "ERROR")

    def _load_bootstrap_nodes(self, *args) -> None:
        """Load bootstrap nodes from config into table."""
        try:
            bootstrap_table = self.query_one("#bootstrap_nodes_table")
            bootstrap_table.clear()

            bootstrap_nodes = self.app.config.get("bootstrap_nodes")
            self.app.log_event(f"{bootstrap_nodes=}", "DEBUG")
            for node in bootstrap_nodes:
                if ":" in node:
                    addr_part, port_part = node.split(":")
                    bootstrap_table.add_row(addr_part.strip(), port_part.strip())

            self._update_button_state()
        except Exception as e:
            self.app.notify(f"Error loading bootstrap nodes: {e}", severity="error")
            self.log_event(f"Load bootstrap nodes error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_add_bootstrap")
    def action_add_bootstrap(self) -> None:
        """Open add peer modal."""
        self.app.push_screen(AddPeerModal("bootstrap"))

    @on(Button.Pressed, "#btn_add_peer")
    def action_add_peer(self) -> None:
        """Open add peer modal for connected peers."""
        self.app.push_screen(AddPeerModal("connected"))

    @on(Button.Pressed, "#btn_remove_bootstrap")
    def action_remove_bootstrap(self) -> None:
        """Delete selected bootstrap peer with confirmation."""
        try:
            bootstrap_table = self.query_one("#bootstrap_nodes_table")
            if bootstrap_table.cursor_row is None:
                self.app.notify("No peer selected", severity="warning")
                return

            row = bootstrap_table.get_row_at(bootstrap_table.cursor_row)
            addr_part = row[0]
            port_part = row[1]
            address = f"{addr_part}:{port_part}"

            message = (
                f"Are you sure you want to delete bootstrap node "
                f"'{address}'?"
            )

            def on_confirmed(confirmed: bool) -> None:
                if not confirmed: return

                try:
                    bootstrap_nodes = self.app.config.get("bootstrap_nodes")
                    if address in bootstrap_nodes:
                        bootstrap_nodes.remove(address)
                        self.app.config.set("bootstrap_nodes", bootstrap_nodes)
                        self.app.config.save()
                        self._load_bootstrap_nodes()
                        self.app.notify(
                            "Bootstrap node deleted successfully",
                            severity="success"
                        )
                    else:
                        self.app.notify(
                            "Bootstrap node not found in list",
                            severity="warning"
                        )
                except Exception as e:
                    self.app.notify(
                        f"Failed to delete bootstrap node: {e}",
                        severity="error"
                    )
                    self.log_event(f"Delete boostrap node error: {e}", "ERROR")

            modal = ConfirmationModal(
                title="Confirm Remove Bootstrap Node",
                message=message,
                confirm_btn_text="Remove",
                confirm_btn_variant="warning"
            )
            self.app.push_screen(modal, on_confirmed)
        except Exception as e:
            self.app.notify(f"Error removing bootstrap node: {e}", severity="error")
            self.log_event(f"Remove bootstrap node error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_remove_peer")
    def action_remove_peer(self) -> None:
        """Delete selected connected peer with confirmation."""
        try:
            peers_table = self.query_one("#connected_peers_table")
            if peers_table.cursor_row is None:
                self.app.notify("No peer selected", severity="warning")
                return

            row = peers_table.get_row_at(peers_table.cursor_row)
            addr_part = row[0]
            port_part = row[1]
            address = f"{addr_part}:{port_part}"

            message = (
                f"Are you sure you want to disconnect from peer "
                f"'{address}'?"
            )

            def on_confirmed(confirmed: bool) -> None:
                if not confirmed: return

                try:
                    peers = self.app.state.get("connected_peers") or []
                    for i, peer in enumerate(peers):
                        if peer["address"] == addr_part and peer["port"] == port_part:
                            peers.pop(i)
                            break

                    self.app.state.set("connected_peers", peers)
                    self.app.notify(
                        "Peer disconnected successfully",
                        severity="success"
                    )
                except Exception as e:
                    self.app.notify(
                        f"Failed to disconnect peer: {e}",
                        severity="error"
                    )
                    self.log_event(f"Disconnect peer error: {e}", "ERROR")

            modal = ConfirmationModal(
                title="Confirm Disconnect Peer",
                message=message,
                confirm_btn_text="Disconnect",
                confirm_btn_variant="warning"
            )
            self.app.push_screen(modal, on_confirmed)
        except Exception as e:
            self.app.notify(f"Error disconnecting peer: {e}", severity="error")
            self.log_event(f"Disconnect peer error: {e}", "ERROR")

    def _update_button_state(self) -> None:
        """Enable/disable delete buttons based on table selections."""
        try:
            bootstrap_table = self.query_one("#bootstrap_nodes_table")
            has_bootstrap_selection = bootstrap_table.cursor_row is not None
            self.query_one("#btn_remove_bootstrap").disabled = not has_bootstrap_selection
        except Exception as e:
            self.log_event(f"Error updating bootstrap button state: {e}", "ERROR")

        try:
            peers_table = self.query_one("#connected_peers_table")
            has_peer_selection = peers_table.cursor_row is not None
            self.query_one("#btn_remove_peer").disabled = not has_peer_selection
        except Exception as e:
            self.log_event(f"Error updating peer button state: {e}", "ERROR")
