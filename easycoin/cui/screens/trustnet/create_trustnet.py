from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import (
    Horizontal, ItemGrid, Vertical, VerticalScroll
)
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Static
from tapescript import Script
from easycoin.models import TrustNet, TrustNetFeature, Address
from easycoin.helpers import truncate_text
from easycoin.cui.widgets import ECTextArea, ConfirmationModal, InputModal


class CreateTrustNetModal(ModalScreen[TrustNet | None]):
    """Modal for creating new TrustNet objects."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self):
        """Initialize create TrustNet modal."""
        super().__init__()
        self.members_data: dict[str, str] = {}
        self.feature_flags: set[TrustNetFeature] = set()

    def compose(self) -> ComposeResult:
        """Compose modal layout."""
        with VerticalScroll(classes="modal-container w-80p"):
            yield Static("Create TrustNet", classes="modal-title")

            yield Static("Name:", classes="text-bold my-1")
            yield Input(id="name_input", placeholder="TrustNet name")

            yield Static("Lock Script:", classes="text-bold my-1")
            yield ECTextArea(id="lock_script", classes="h-10")

            yield Static("Members:", classes="text-bold my-1")
            yield DataTable(id="members_table", classes="h-8")
            with Horizontal(classes="h-min-4"):
                yield Button("Add", id="btn_add_member", variant="primary")
                yield Button("Remove", id="btn_remove_member", variant="warning")
                yield Button(
                    "Edit Delegation", id="btn_edit_delegation", variant="default"
                )

            yield Static("Feature Flags:", classes="text-bold my-1")
            with ItemGrid(id="feature_flags_grid", min_column_width=25):
                for feature in TrustNetFeature:
                    yield Checkbox(
                        feature.name.replace("_", " ").title(),
                        id=f"feature_{feature.name}",
                    )

            yield Static("Quorum:", classes="text-bold my-1")
            yield Input(id="quorum_input", placeholder="Number of members required")

            yield Static("", id="error_display", classes="text-bold mt-1 hidden")

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize modal on mount."""
        self._setup_members_table()
        self.query_one("#name_input").focus()

    def _setup_members_table(self) -> None:
        """Setup the members DataTable."""
        table = self.query_one("#members_table")
        table.add_columns(("Address", "address"), ("Delegate Script", "delegate"))
        table.cursor_type = "row"

    def _refresh_members_table(self) -> None:
        """Refresh the members DataTable with current data."""
        table = self.query_one("#members_table")
        table.clear()

        for address, delegate_src in self.members_data.items():
            display_address = truncate_text(address, prefix_len=16, suffix_len=8)
            display_delegate = (
                truncate_text(delegate_src, prefix_len=12, suffix_len=6)
                if delegate_src
                else "(none)"
            )
            table.add_row(display_address, display_delegate)

        self._update_member_buttons()

    def _update_member_buttons(self) -> None:
        """Update button states based on table selection."""
        table = self.query_one("#members_table")
        has_selection = table.cursor_row is not None

        self.query_one("#btn_remove_member").disabled = not has_selection
        self.query_one("#btn_edit_delegation").disabled = not has_selection

    @on(Button.Pressed, "#btn_add_member")
    def _action_add_member(self) -> None:
        """Open modal to add a new member."""
        self.app.push_screen(
            InputModal(
                title="Add Member",
                description="Enter member address hex:"
            ),
            self._on_add_member_result
        )

    def _on_add_member_result(self, address_hex: str | None) -> None:
        """Handle result from add member modal."""
        if address_hex is None:
            return

        address_hex = address_hex.strip()
        if not address_hex:
            self.app.notify("Address cannot be empty", severity="error")
            return

        if not Address.validate(address_hex):
            self.app.notify("Invalid address", severity="error")
            self.app.log_event(f"Invalid address validation: {address_hex}", "ERROR")
            return

        if address_hex in self.members_data:
            self.app.notify("Member already added", severity="warning")
            return

        self.members_data[address_hex] = ""
        self._refresh_members_table()

    @on(Button.Pressed, "#btn_remove_member")
    def _action_remove_member(self) -> None:
        """Open confirmation modal to remove selected member."""
        table = self.query_one("#members_table")
        if table.cursor_row is None:
            return

        addresses = list(self.members_data.keys())
        if table.cursor_row >= len(addresses):
            return

        address = addresses[table.cursor_row]

        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return

            del self.members_data[address]
            self._refresh_members_table()

        modal = ConfirmationModal(
            title="Confirm Remove Member",
            message=f"Remove member {address}?",
            confirm_btn_text="Remove",
            confirm_btn_variant="warning"
        )
        self.app.push_screen(modal, on_confirmed)

    @on(Button.Pressed, "#btn_edit_delegation")
    def _action_edit_delegation(self) -> None:
        """Open modal to edit delegation script for selected member."""
        table = self.query_one("#members_table")
        if table.cursor_row is None:
            return

        addresses = list(self.members_data.keys())
        if table.cursor_row >= len(addresses):
            return

        address = addresses[table.cursor_row]
        delegate_src = self.members_data[address]

        from .delegate_script_modal import DelegateScriptModal

        modal = DelegateScriptModal(
            title=f"Edit Delegation for {address}",
            script_src=delegate_src
        )

        def on_script_saved(script_src: str | None) -> None:
            if script_src is None:
                return

            self.members_data[address] = script_src
            self._refresh_members_table()

        self.app.push_screen(modal, on_script_saved)

    @on(Checkbox.Changed)
    def _on_feature_flag_changed(self, event: Checkbox.Changed) -> None:
        """Handle feature flag checkbox changes."""
        checkbox = event.checkbox
        feature_name = checkbox.id.replace("feature_", "")

        try:
            feature = TrustNetFeature[feature_name]
            if checkbox.value:
                self.feature_flags.add(feature)
            else:
                self.feature_flags.discard(feature)
        except KeyError:
            self.app.log_event(f"Unknown feature flag: {feature_name}", "ERROR")

    def _validate_inputs(self) -> tuple[bool, str]:
        """Validate all inputs. Returns (is_valid, error_message)."""
        name = self.query_one("#name_input").value.strip()
        if not name:
            return False, "TrustNet name is required"

        lock_src = self.query_one("#lock_script").text.strip()
        if not lock_src:
            return False, "Lock script is required"

        try:
            Script.from_src(lock_src)
        except Exception as e:
            return False, f"Invalid lock script: {e}"

        quorum_input = self.query_one("#quorum_input").value.strip()
        quorum = 0
        if quorum_input:
            try:
                quorum = int(quorum_input)
                if quorum < 0:
                    return False, "Quorum must be a non-negative integer"
            except ValueError:
                return False, "Quorum must be a valid integer"

        if quorum > len(self.members_data):
            return (
                False,
                f"Quorum ({quorum}) cannot exceed number of members "
                f"({len(self.members_data)})"
            )

        for address, delegate_src in self.members_data.items():
            if delegate_src:
                try:
                    Script.from_src(delegate_src)
                except Exception as e:
                    return False, f"Invalid delegate script for {address}: {e}"

        return True, ""

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        """Save and create the TrustNet."""
        is_valid, error_message = self._validate_inputs()
        if not is_valid:
            error_display = self.query_one("#error_display")
            error_display.remove_class("hidden")
            error_display.update(f"Error: {error_message}", markup=False)
            self.app.notify(error_message, severity="error")
            self.app.log_event(
                f"CreateTrustNet validation error: {error_message}",
                "ERROR"
            )
            return

        error_display = self.query_one("#error_display")
        error_display.add_class("hidden")

        name = self.query_one("#name_input").value.strip()
        lock_src = self.query_one("#lock_script").text.strip()
        quorum_input = self.query_one("#quorum_input").value.strip()
        quorum = int(quorum_input) if quorum_input else None

        trustnet = TrustNet({
            'name': name,
            'lock': Script.from_src(lock_src).bytes,
            'members': [Address.parse(addr) for addr in self.members_data.keys()],
            'delegate_scripts': {
                addr: Script.from_src(src).bytes
                for addr, src in self.members_data.items()
                if src
            },
            'quorum': quorum,
            'active': True,
        })
        trustnet.features = self.feature_flags
        trustnet.save()

        self.dismiss(trustnet)

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and dismiss modal."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        """Quit application."""
        await self.app.action_quit()
