from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Static
from easycoin.models import TrustNet
from easycoin.helpers import truncate_text
from easycoin.cui.screens.base import BaseScreen
from easycoin.cui.widgets import ConfirmationModal
from .create_trustnet import CreateTrustNetModal


class TrustNetScreen(BaseScreen):
    """Manage TrustNets: view joined, available, and active TrustNets."""

    TAB_ID = "tab_trustnet"
    BINDINGS = [
        ("n", "create_trustnet", "New TrustNet"),
    ]

    def compose(self) -> ComposeResult:
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        with VerticalScroll(id="trustnet_content"):
            yield Static("TrustNets", classes="panel-title")

            with Vertical(id="joined_trustnets_section", classes="card mb-1"):
                yield Static("Joined TrustNets", classes="text-bold mb-1")
                yield DataTable(id="joined_trustnets_table", classes="h-10")
                with Horizontal(classes="h-min-4"):
                    yield Button(
                        "Leave", id="btn_leave", variant="warning"
                    )

            with Vertical(id="available_trustnets_section", classes="card mb-1"):
                yield Static("Available TrustNets", classes="text-bold mb-1")
                yield DataTable(id="available_trustnets_table", classes="h-10")
                with Horizontal(classes="h-min-4"):
                    yield Button(
                        "Join", id="btn_join", variant="primary"
                    )

            with Vertical(id="active_trustnets_section", classes="card mb-1"):
                yield Static("Active TrustNets", classes="text-bold mb-1")
                yield DataTable(id="active_trustnets_table", classes="h-10")

            with Horizontal(id="trustnet_actions", classes="h-min-4"):
                yield Button("Create TrustNet", id="btn_create", variant="primary")

    def on_mount(self) -> None:
        self._setup_tables()
        self.app.state.subscribe(
            "set_available_trustnets",
            self._load_available_trustnets
        )
        self.app.state.subscribe(
            "append_available_trustnets",
            self._load_available_trustnets
        )
        self.app.state.subscribe(
            "remove_available_trustnets",
            self._load_available_trustnets
        )
        self.app.state.subscribe(
            "set_active_trustnets",
            self._load_active_trustnets
        )
        self.app.state.subscribe(
            "append_active_trustnets",
            self._load_active_trustnets
        )
        self.app.state.subscribe(
            "remove_active_trustnets",
            self._load_active_trustnets
        )

    def on_unmount(self) -> None:
        self.app.state.unsubscribe(
            "set_available_trustnets",
            self._load_available_trustnets
        )
        self.app.state.unsubscribe(
            "append_available_trustnets",
            self._load_available_trustnets
        )
        self.app.state.unsubscribe(
            "remove_available_trustnets",
            self._load_available_trustnets
        )
        self.app.state.unsubscribe(
            "set_active_trustnets",
            self._load_active_trustnets
        )
        self.app.state.unsubscribe(
            "append_active_trustnets",
            self._load_active_trustnets
        )
        self.app.state.unsubscribe(
            "remove_active_trustnets",
            self._load_active_trustnets
        )

    def on_screen_resume(self, event) -> None:
        super().on_screen_resume(event)
        self._load_joined_trustnets()
        self._load_available_trustnets()
        self._load_active_trustnets()

    def _setup_tables(self) -> None:
        joined_table = self.query_one("#joined_trustnets_table")
        joined_table.add_columns(
            ("Name", "name"),
            ("ID", "id"),
            ("Active", "active"),
            ("Lock Length", "lock_length"),
            ("Params Length", "params_length"),
        )
        joined_table.cursor_type = "row"

        available_table = self.query_one("#available_trustnets_table")
        available_table.add_columns(
            ("Name", "name"),
            ("ID", "id"),
            ("Lock Length", "lock_length"),
            ("Params Length", "params_length"),
        )
        available_table.cursor_type = "row"

        active_table = self.query_one("#active_trustnets_table")
        active_table.add_columns(
            ("Name", "name"),
            ("ID", "id"),
        )
        active_table.cursor_type = "row"

    def _load_joined_trustnets(self, *args) -> None:
        joined_table = self.query_one("#joined_trustnets_table")
        joined_table.clear()

        trustnets = TrustNet.query().get()
        self.app.log_event(f"Loaded {len(trustnets)} joined trustnets", "DEBUG")
        for trustnet in trustnets:
            display_id = truncate_text(trustnet.id, prefix_len=16, suffix_len=8)
            joined_table.add_row(
                trustnet.name or "",
                display_id,
                "Yes" if trustnet.active else "No",
                str(len(trustnet.lock)),
                str(len(trustnet.params))
            )

        self._update_button_state()

    def _load_available_trustnets(self, *args) -> None:
        available_table = self.query_one("#available_trustnets_table")
        available_table.clear()

        trustnets = self.app.state.get("available_trustnets") or []
        self.app.log_event(f"Loaded {len(trustnets)} available trustnets", "DEBUG")
        for trustnet in trustnets:
            display_id = truncate_text(trustnet.id, prefix_len=16, suffix_len=8)
            available_table.add_row(
                trustnet.name or "",
                display_id,
                str(len(trustnet.lock)),
                str(len(trustnet.params))
            )

        self._update_button_state()

    def _load_active_trustnets(self, *args) -> None:
        active_table = self.query_one("#active_trustnets_table")
        active_table.clear()

        trustnets = self.app.state.get("active_trustnets") or []
        self.app.log_event(f"Loaded {len(trustnets)} active trustnets", "DEBUG")
        for trustnet in trustnets:
            display_id = truncate_text(trustnet.id, prefix_len=16, suffix_len=8)
            active_table.add_row(
                trustnet.name or "",
                display_id
            )

        self._update_button_state()

    def _update_button_state(self) -> None:
        joined_table = self.query_one("#joined_trustnets_table")
        has_joined_selection = joined_table.cursor_row is not None
        self.query_one("#btn_leave").disabled = not has_joined_selection

        available_table = self.query_one("#available_trustnets_table")
        has_available_selection = available_table.cursor_row is not None
        self.query_one("#btn_join").disabled = not has_available_selection

    @on(Button.Pressed, "#btn_create")
    def action_create_trustnet(self) -> None:
        def on_created(trustnet: TrustNet | None):
            if trustnet:
                self.app.state.append("active_trustnets", trustnet)
                self.app.notify(
                    f"Created TrustNet '{trustnet.name}'",
                    severity="success"
                )
                self.log_event(f"Created TrustNet: {trustnet.id}", "INFO")

        modal = CreateTrustNetModal()
        self.app.push_screen(modal, on_created)

    @on(Button.Pressed, "#btn_join")
    def action_join_trustnet(self) -> None:
        available_table = self.query_one("#available_trustnets_table")
        if available_table.cursor_row is None:
            return

        trustnets = self.app.state.get("available_trustnets") or []
        if not trustnets:
            return

        if available_table.cursor_row >= len(trustnets):
            self.log_event(
                f"cursor_row {available_table.cursor_row} >= len(trustnets) {len(trustnets)}",
                "ERROR"
            )
            return

        trustnet = trustnets[available_table.cursor_row]
        trustnet.save()
        self.app.state.publish("join_trustnet", trustnet)
        self.app.notify(
            f"Joined TrustNet '{trustnet.name}'",
            severity="success"
        )
        self.log_event(f"Joined TrustNet: {trustnet.id}", "INFO")

    @on(Button.Pressed, "#btn_leave")
    def action_leave_trustnet(self) -> None:
        joined_table = self.query_one("#joined_trustnets_table")
        if joined_table.cursor_row is None:
            return

        trustnets = TrustNet.query().get()
        if not trustnets:
            return

        if joined_table.cursor_row >= len(trustnets):
            self.log_event(
                f"cursor_row {joined_table.cursor_row} >= len(trustnets) {len(trustnets)}",
                "ERROR"
            )
            return

        trustnet = trustnets[joined_table.cursor_row]
        trustnet_id = trustnet.id
        trustnet_name = trustnet.name or trustnet_id

        message = (
            f"Are you sure you want to leave TrustNet "
            f"'{trustnet_name}'?"
        )

        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return

            trustnet.delete()
            self.app.state.publish("leave_trustnet", trustnet)
            self.app.notify(
                "Left TrustNet successfully",
                severity="success"
            )
            self.log_event(f"Left TrustNet: {trustnet_id}", "INFO")

        modal = ConfirmationModal(
            title="Confirm Leave TrustNet",
            message=message,
            confirm_btn_text="Leave",
            confirm_btn_variant="warning"
        )
        self.app.push_screen(modal, on_confirmed)
