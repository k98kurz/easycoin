from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button, DataTable, Input, RadioSet, RadioButton, Static
)
from textual.widgets.data_table import RowKey
from easycoin.models import StampTemplate
from ..base import BaseScreen
from easycoin.helpers import truncate_text
from easycoin.cui.widgets import ConfirmationModal
from .create_stamp_template_modal import CreateStampTemplateModal


class StampTemplatesScreen(BaseScreen):
    """View and manage stamp templates."""

    TAB_ID = "tab_stamps"

    BINDINGS = [
        ("n", "create_template", "New Template"),
        ("r", "refresh_templates", "Refresh"),
        ("e", "edit_template", "Edit Template"),
        ("d", "delete_template", "Delete Template"),
    ]

    def __init__(self):
        """Initialize stamp templates screen."""
        super().__init__()
        self.selected_template_id = None
        self.template_id_map = {}

    def compose(self) -> ComposeResult:
        """Compose stamp templates screen layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose stamp templates screen content area."""
        with Vertical(id="stamp_templates_screen"):
            yield Static("Stamp Templates", classes="panel-title")

            with Horizontal(id="template_filters", classes="h-9"):
                with Vertical(id="type_filter_section", classes="w-30p"):
                    yield Static("Type:", classes="config-label m-1")
                    yield RadioSet(
                        RadioButton("All", id="type_all", value=True),
                        RadioButton("Single", id="type_single"),
                        RadioButton("Token", id="type_token"),
                        RadioButton("Unknown", id="type_unknown"),
                        id="type_filter",
                        classes="h-7",
                    )
                with Vertical(id="search_section", classes="w-70p"):
                    yield Static("Search:", classes="config-label m-1")
                    yield Input(
                        placeholder="Name, description, author, tags...",
                        id="search_input",
                        classes="form-input"
                    )

            yield DataTable(id="templates_table", classes="mt-1")

            with Horizontal(id="template_actions", classes="h-min-4"):
                yield Button(
                    "Create Template",
                    id="btn_create",
                    variant="primary"
                )
                yield Button(
                    "Edit Template",
                    id="btn_edit",
                    variant="default",
                    disabled=True
                )
                yield Button(
                    "Delete Template",
                    id="btn_delete",
                    variant="error",
                    disabled=True
                )
                yield Button("Refresh", id="btn_refresh", variant="default")

    def on_mount(self) -> None:
        """Initialize table and load data on mount."""
        table = self.query_one("#templates_table")
        table.cursor_type = "row"
        table.add_columns(
            "Name",
            "Covenant Type",
            "Version",
            "Author",
            "Tags",
            "dsh",
            "issue",
        )
        self._load_templates()

    @on(RadioSet.Changed, "#type_filter")
    def _on_type_filter_changed(self, event: RadioSet.Changed) -> None:
        """Handle type filter changes."""
        self._load_templates()

    @on(Input.Changed, "#search_input")
    def _on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        self._load_templates()

    @on(Button.Pressed, "#btn_create")
    def action_create_template(self) -> None:
        """Open create template modal."""
        self.log_event("Opening create template modal", "INFO")

        def on_save_result(result: bool | None) -> None:
            if result:
                self._load_templates()

        self.app.push_screen(
            CreateStampTemplateModal(),
            on_save_result
        )

    @on(Button.Pressed, "#btn_refresh")
    def action_refresh_templates(self) -> None:
        """Refresh templates data."""
        self.log_event("Refreshing stamp templates", "INFO")
        self._load_templates()

    @on(Button.Pressed, "#btn_edit")
    def action_edit_template(self) -> None:
        """Edit selected template."""
        if not self.selected_template_id:
            return

        self.log_event(
            f"Opening edit modal for template {self.selected_template_id}",
            "INFO"
        )

        def on_save_result(result: bool | None) -> None:
            if result:
                self._load_templates()

        self.app.push_screen(
            CreateStampTemplateModal(template_id=self.selected_template_id),
            on_save_result
        )

    @on(Button.Pressed, "#btn_delete")
    def action_delete_template(self) -> None:
        """Delete selected template with confirmation."""
        if not self.selected_template_id:
            return

        self._confirm_delete(self.selected_template_id)

    @on(DataTable.RowSelected, "#templates_table")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        row_key = event.row_key
        self.selected_template_id = self.template_id_map.get(row_key)
        self.action_edit_template()

    @on(DataTable.RowHighlighted, "#templates_table")
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight for button enable/disable."""
        row_key = event.row_key
        self.selected_template_id = self.template_id_map.get(row_key)

        btn_edit = self.query_one("#btn_edit")
        btn_delete = self.query_one("#btn_delete")

        is_selected = self.selected_template_id is not None
        btn_edit.disabled = not is_selected
        btn_delete.disabled = not is_selected

    def _load_templates(self) -> None:
        """Load templates from database and populate table."""
        try:
            templates = []
            for template in StampTemplate.query().get():
                templates.append(template)

            table = self.query_one("#templates_table")
            table.clear()
            self.template_id_map.clear()

            type_filter = self.query_one("#type_filter")
            search_query = self.query_one("#search_input").value.lower()

            for template in templates:
                if not self._matches_filter(template, type_filter, search_query):
                    continue

                try:
                    row_key = table.add_row(
                        truncate_text(template.name, 20, 0),
                        template.type.value.capitalize(),
                        template.version or "N/A",
                        truncate_text(template.author or "", 20, 0),
                        truncate_text(template.tags or "None", 20, 0),
                        template.dsh.hex(),
                        template.issue.hex(),
                    )
                    self.template_id_map[row_key] = template.id
                except Exception as e:
                    self.log_event(
                        f"Error adding template row {template.id}: {e}",
                        "DEBUG"
                    )

            self.log_event(
                f"Loaded {len(self.template_id_map)} stamp templates",
                "INFO"
            )
        except Exception as e:
            self.log_event(f"Error loading templates: {e}", "ERROR")
            self.app.notify(f"Error loading templates: {e}", severity="error")

    def _matches_filter(
            self, template: StampTemplate,
            type_filter: RadioSet, search_query: str
        ) -> bool:
        """Check if template matches current filters."""
        type_idx = type_filter.pressed_index

        if type_idx == 1 and template.type.value != "single":
            return False
        elif type_idx == 2 and template.type.value != "token":
            return False
        elif type_idx == 3 and template.type.value != "unknown":
            return False

        if search_query:
            searchable_text = self._get_searchable_text(template).lower()
            if search_query.lower() not in searchable_text:
                return False

        return True

    def _get_searchable_text(self, template: StampTemplate) -> str:
        """Get searchable text from template."""
        parts = [
            template.name or "",
            template.description or "",
            template.author or "",
            template.tags or ""
        ]
        return " ".join(parts)

    def _confirm_delete(self, template_id: str) -> None:
        """Show confirmation modal for template deletion."""
        try:
            template = StampTemplate.find(template_id)
            if not template:
                self.app.notify(
                    f"Template not found: {template_id}",
                    severity="error"
                )
                return

            modal = ConfirmationModal(
                title="Delete Stamp Template",
                message=f"Are you sure you want to delete '{template.name}'?\n\n"
                        f"This action cannot be undone.",
                confirm_btn_variant="error",
                confirm_btn_classes="error"
            )

            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._delete_template(template_id)

            self.app.push_screen(modal, on_confirm)
        except Exception as e:
            self.log_event(f"Error preparing delete: {e}", "ERROR")
            self.app.notify(f"Error: {e}", severity="error")

    def _delete_template(self, template_id: str) -> None:
        """Delete template from database."""
        try:
            template = StampTemplate.find(template_id)
            if not template:
                self.app.notify(
                    f"Template not found: {template_id}",
                    severity="error"
                )
                return

            name = template.name
            template.delete()

            self.log_event(
                f"Deleted stamp template: {template_id} ({name})",
                "INFO"
            )
            self.app.notify(
                f"Deleted template: {name}",
                severity="success"
            )

            self._load_templates()
            self.selected_template_id = None
            self.query_one("#btn_edit").disabled = True
            self.query_one("#btn_delete").disabled = True
        except Exception as e:
            self.log_event(f"Error deleting template: {e}", "ERROR")
            self.app.notify(f"Error deleting template: {e}", severity="error")
