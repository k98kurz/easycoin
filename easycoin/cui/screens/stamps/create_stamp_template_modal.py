from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Static, Input, RadioSet, RadioButton, Checkbox, Footer
)
from easycoin.models import StampTemplate, Txn, StampType
from easycoin.cui.widgets import ECTextArea


class CreateStampTemplateModal(ModalScreen[bool|None]):
    """Modal for creating new StampTemplate objects or editing existing ones."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+s", "save", "Save"),
    ]

    CSS = "CreateStampTemplateModal { background: $background 50%; }"

    def __init__(self, template_id: str | None = None):
        """Initialize modal. `template_id=None` for create mode, existing ID
            for edit mode.
        """
        super().__init__()
        self.template_id = template_id
        self.template: StampTemplate | None = None
        self.error_message: str = ""

    def compose(self) -> ComposeResult:
        """Compose modal layout."""
        title = (
            "Edit Stamp Template" if self.template_id else "Create Stamp Template"
        )
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static(title, classes="modal-title")

            with Horizontal(classes="h-8"):
                with Vertical():
                    yield Static("Name:", classes="text-bold my-1")
                    yield Input(id="name_input", placeholder="Template name")
                with Vertical():
                    yield Static("Type:", classes="text-bold my-1")
                    yield RadioSet(
                        RadioButton("Single", id="type_single", value=True),
                        RadioButton("Series", id="type_series"),
                        RadioButton("Custom", id="type_unknown"),
                        id="type_radio",
                    )

            with Horizontal(classes="h-5 mt-1"):
                with Vertical():
                    yield Static("Description:", classes="text-bold mb-1")
                    yield Input(
                        id="description_input",
                        placeholder="Optional description"
                    )
                with Vertical():
                    yield Static("Version:", classes="text-bold mb-1")
                    yield Input(id="version_input", placeholder="e.g. 0.1.0")

            with Horizontal(classes="h-5 mt-1"):
                with Vertical():
                    yield Static("Author:", classes="text-bold mb-1")
                    yield Input(
                        id="author_input",
                        placeholder="Optional author name"
                    )
                with Vertical():
                    yield Static("Tags:", classes="text-bold mb-1")
                    yield Input(
                        id="tags_input",
                        placeholder="comma-separated tags"
                    )

            yield Static("Covenant Script ($):", classes="text-bold my-1")
            yield ECTextArea(id="covenant_script", classes="h-15")

            with Horizontal(id="mintlock_prefix_container", classes="mt-1 h-6"):
                with Vertical(classes="w-50p"):
                    yield Checkbox("Enable Mint Lock (L)", id="enable_mint_lock")
                    yield ECTextArea(id="mint_lock_script", classes="h-12 hidden mt-1")
                with Vertical(classes="w-50p"):
                    yield Checkbox("Enable Prefix (_)", id="enable_prefix")
                    yield ECTextArea(id="prefix_script", classes="h-12 hidden mt-1")

            yield Static("", id="error_display", classes="text-bold mt-1 hidden")

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize modal on mount."""
        if self.template_id:
            self._load_template_data()
        else:
            self.template = StampTemplate()
            self._initialize_new_template()

        self.query_one("#name_input").focus()

    @on(RadioSet.Changed, "#type_radio")
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle type radio set changes."""
        pressed_index = event.radio_set.pressed_index
        if pressed_index == 0:
            stamp_type = StampType.SINGLE
        elif pressed_index == 1:
            stamp_type = StampType.SERIES
        else:
            stamp_type = StampType.UNKNOWN

        self._prepopulate_covenant_script(stamp_type)

    def _prepopulate_covenant_script(self, stamp_type: StampType) -> None:
        """Set covenant script text area based on `stamp_type`."""
        covenant_script = self.query_one("#covenant_script")

        if stamp_type == StampType.SINGLE:
            covenant_script.text = Txn.std_stamp_covenant().src
            covenant_script.read_only = True
        elif stamp_type == StampType.SERIES:
            covenant_script.text = Txn.std_series_covenant().src
            covenant_script.read_only = True
        else:
            covenant_script.text = ""
            covenant_script.read_only = False

    @on(Checkbox.Changed, "#enable_mint_lock")
    def _toggle_mint_lock(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes for mint lock."""
        mint_lock_script = self.query_one("#mint_lock_script")
        if event.value:
            mint_lock_script.remove_class("hidden")
            #mint_lock_script.focus()
        else:
            mint_lock_script.add_class("hidden")
        self.update_mintlock_prefix_container()

    @on(Checkbox.Changed, "#enable_prefix")
    def _toggle_prefix(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes for mint lock and prefix."""
        prefix_script = self.query_one("#prefix_script")
        if event.value:
            prefix_script.remove_class("hidden")
            #prefix_script.focus()
        else:
            prefix_script.add_class("hidden")
        self.update_mintlock_prefix_container()

    def update_mintlock_prefix_container(self):
        container = self.query_one("#mintlock_prefix_container")
        eml = self.query_one("#enable_mint_lock")
        epx = self.query_one("#enable_prefix")
        if eml.value or epx.value:
            container.remove_class("h-6")
            container.add_class("h-16")
        else:
            container.remove_class("h-16")
            container.add_class("h-6")

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        """Save the template."""
        if self._save_template():
            self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and dismiss modal."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()

    def _save_template(self) -> bool:
        """Validate and save the template. Returns `True` if save succeeded,
            `False` otherwise.
        """
        self.error_message = ""

        name_input = self.query_one("#name_input")
        description_input = self.query_one("#description_input")
        version_input = self.query_one("#version_input")
        author_input = self.query_one("#author_input")
        tags_input = self.query_one("#tags_input")
        covenant_script = self.query_one("#covenant_script")
        enable_mint_lock = self.query_one("#enable_mint_lock")
        mint_lock_script = self.query_one("#mint_lock_script")
        enable_prefix = self.query_one("#enable_prefix")
        prefix_script = self.query_one("#prefix_script")

        name = name_input.value.strip()
        if not name:
            self.app.log_event("Name is required", "WARNING")
            self.app.notify("Name is required", severity="warning")
            return False

        type_radio = self.query_one("#type_radio")
        type_index = type_radio.pressed_index
        if type_index == 0:
            stamp_type = StampType.SINGLE
        elif type_index == 1:
            stamp_type = StampType.SERIES
        else:
            stamp_type = StampType.UNKNOWN

        description = description_input.value.strip() or None
        version = version_input.value.strip() or None
        author = author_input.value.strip() or None
        tags = tags_input.value.strip() or None

        scripts: dict[str, str] = {'$': covenant_script.text}

        if enable_mint_lock.value and mint_lock_script.text.strip():
            scripts['L'] = mint_lock_script.text.strip()

        if enable_prefix.value and prefix_script.text.strip():
            scripts['_'] = prefix_script.text.strip()

        try:
            self.template.name = name
            self.template.description = description
            self.template.type = stamp_type
            self.template.version = version
            self.template.author = author
            self.template.tags = tags
            self.template.scripts = scripts
            self.template.save()
            self.error_message = ""
            self._show_error()
            return True
        except ValueError as e:
            self.error_message = str(e)
            self._show_error()
            return False
        except Exception as e:
            self.error_message = f"Error saving template: {e}"
            self._show_error()
            return False

    def _load_template_data(self) -> None:
        """Load existing template data into form."""
        try:
            self.template = StampTemplate.find(self.template_id)
            if not self.template:
                msg = f"Template not found"
                self.app.log_event(msg, 'ERROR')
                self.app.notify(msg, severity='error')
                return self.dismiss(None)
        except Exception as e:
            msg = f"Error loading template: {e}"
            self.app.log_event(msg, 'ERROR')
            self.app.notify(msg, severity='error')
            return self.dismiss(None)

        self.query_one("#name_input").value = self.template.name

        description = self.template.description or ""
        self.query_one("#description_input").value = description

        version = self.template.version or ""
        self.query_one("#version_input").value = version

        author = self.template.author or ""
        self.query_one("#author_input").value = author

        tags = self.template.tags or ""
        self.query_one("#tags_input").value = tags

        stamp_type = self.template.type
        if stamp_type == StampType.SINGLE:
            self.query_one("#type_single").value = True
        elif stamp_type == StampType.SERIES:
            self.query_one("#type_series").value = True
        else:
            self.query_one("#type_unknown").value = True

        self._prepopulate_covenant_script(stamp_type)

        scripts = self.template.scripts
        enable_mint_lock = self.query_one("#enable_mint_lock")
        mint_lock_script = self.query_one("#mint_lock_script")
        if 'L' in scripts:
            enable_mint_lock.value = True
            mint_lock_script.remove_class("hidden")
            mint_lock_script.text = scripts['L']
        else:
            enable_mint_lock.value = False
            mint_lock_script.add_class("hidden")
            mint_lock_script.text = ""

        enable_prefix = self.query_one("#enable_prefix")
        prefix_script = self.query_one("#prefix_script")
        if '_' in scripts:
            enable_prefix.value = True
            prefix_script.remove_class("hidden")
            prefix_script.text = scripts['_']
        else:
            enable_prefix.value = False
            prefix_script.add_class("hidden")
            prefix_script.text = ""

    def _initialize_new_template(self) -> None:
        """Initialize form for new template with defaults."""
        self._prepopulate_covenant_script(StampType.SINGLE)

    def _show_error(self) -> None:
        """Display error message in error display widget."""
        error_display = self.query_one("#error_display")
        if self.error_message:
            error_display.update(self.error_message)
            error_display.remove_class("hidden")
        else:
            error_display.update("")
            error_display.add_class("hidden")
