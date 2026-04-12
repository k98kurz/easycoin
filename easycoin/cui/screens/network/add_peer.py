from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Footer
from easycoin.constants import DEFAULT_PORT


class AddPeerModal(ModalScreen[bool]):
    """Modal for adding new bootstrap peer with address:port configuration."""

    BINDINGS = [
        Binding("enter", "submit", "Submit", priority=True),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    CSS = "AddPeerModal { background: $background 50%; }"

    def __init__(self, target: str = "bootstrap", **kwargs):
        """Initialize modal with target (bootstrap or connected)."""
        super().__init__(**kwargs)
        self.target = target

    def compose(self) -> ComposeResult:
        """Compose modal layout."""
        if self.target == "bootstrap":
            title = "Add Bootstrap Peer"
        else:
            title = "Add Peer"
        with Vertical(id="add_peer_modal", classes="modal-container w-50p"):
            yield Static(title, classes="modal-title mb-1")
            yield Static(
                "Enter the peer address, optionally with port "
                "(defaults to 9876). Only UDP connections are supported.",
                classes="text-muted mb-1"
            )
            yield Static("Peer Address:", classes="text-bold")
            yield Input(
                placeholder="address[:port]",
                id="peer_address",
                classes="mt-1"
            )

            with Horizontal(id="modal_actions", classes="h-min-5 mt-1"):
                yield Button("Add", id="btn_add", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    @on(Button.Pressed, "#btn_add")
    def action_submit(self) -> None:
        """Validate and add peer to bootstrap nodes or connected peers."""
        address_input = self.query_one("#peer_address", Input)
        peer_address = address_input.value.strip()

        if not peer_address:
            self.app.notify("Address cannot be empty", severity="warning")
            return

        validation_error = self._validate_peer_address(peer_address)
        if validation_error:
            self.app.notify(validation_error, severity="error")
            return

        if self.target == "bootstrap":
            self._add_bootstrap_node(peer_address)
        else:
            self._add_connected_peer(peer_address)

    def _add_bootstrap_node(self, peer_address: str) -> None:
        """Add peer to bootstrap nodes list."""
        try:
            normalized_address = self._normalize_peer_address(peer_address)
            bootstrap_nodes = self.app.config.get("bootstrap_nodes")
            if normalized_address in bootstrap_nodes:
                self.app.notify("Peer already in bootstrap list", severity="warning")
                return

            bootstrap_nodes.append(normalized_address)
            self.app.config.set("bootstrap_nodes", bootstrap_nodes)
            self.app.config.save()
            self.app.notify("Peer added successfully", severity="success")
            self.dismiss(True)
        except Exception as e:
            self.app.notify(f"Failed to add peer: {e}", severity="error")
            self.log_event(f"Add peer error: {e}", "ERROR")

    def _add_connected_peer(self, peer_address: str) -> None:
        """Add peer to connected peers list."""
        try:
            normalized_address = self._normalize_peer_address(peer_address)
            addr_part, port_part = normalized_address.split(":")

            peers = self.app.state.get("connected_peers") or []

            for peer in peers:
                if peer["address"] == addr_part and peer["port"] == port_part:
                    self.app.notify("Peer already connected", severity="warning")
                    return

            new_peer = {
                "address": addr_part,
                "port": port_part,
                "rx_messages": "0",
                "tx_messages": "0"
            }
            peers.append(new_peer)
            self.app.state.set("connected_peers", peers)
            self.app.notify("Peer connected successfully", severity="success")
            self.dismiss(True)
        except Exception as e:
            self.app.notify(f"Failed to connect peer: {e}", severity="error")
            self.log_event(f"Connect peer error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Dismiss the modal without adding peer."""
        self.dismiss(False)

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()

    def _validate_peer_address(self, address: str) -> str | None:
        """Validate peer address format and return error message if invalid."""
        try:
            if ":" not in address:
                addr_part = address.strip()
                if not addr_part:
                    return "Address cannot be empty"
                return None

            parts = address.split(":")
            if len(parts) != 2:
                return "Address must be in format 'address:port'"

            addr_part, port_part = parts
            addr_part = addr_part.strip()
            port_part = port_part.strip()

            if not addr_part:
                return "Address part cannot be empty"

            if not port_part:
                return "Port part cannot be empty"

            try:
                port = int(port_part)
            except ValueError:
                return "Port must be a number"

            if port < 1 or port > 65535:
                return "Port must be between 1 and 65535"

            return None
        except Exception:
            return "Invalid address format"

    def _normalize_peer_address(self, address: str) -> str:
        """Normalize address by appending default port if not present."""
        if ":" not in address:
            addr_part = address.strip()
            return f"{addr_part}:{DEFAULT_PORT}"

        parts = address.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid address format")

        addr_part, port_part = parts
        addr_part = addr_part.strip()
        port_part = port_part.strip()
        return f"{addr_part}:{port_part}"
