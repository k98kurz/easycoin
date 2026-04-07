from pathlib import Path
from tapescript import Script
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Static, Input, RadioSet, RadioButton, Checkbox, Footer, OptionList
)
from textual.widgets.option_list import Option
from easycoin.constants import _max_detail_icon_size
from easycoin.models import StampTemplate, Txn, StampType
from easycoin.cui.widgets import ECTextArea
from easycoin.cui.widgets.file_picker_modal import FilePickerModal
from easycoin.cui.helpers import get_image_type, format_script_src
import base64


class CreateStampTemplateModal(ModalScreen[bool|None]):
    """Modal for creating new StampTemplate objects or editing existing ones."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
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
                    yield Static("Covenant Type:", classes="text-bold my-1")
                    yield RadioSet(
                        RadioButton("Single", id="type_single"),
                        RadioButton("Token", id="type_token"),
                        RadioButton("Custom", id="type_unknown"),
                        id="type_radio",
                    )

            with Horizontal(classes="h-5"):
                yield Checkbox(
                    "Allow negative token values",
                    id="allow_negatives",
                    value=False
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
                    yield Checkbox("Enable Mint Lock ('L')", id="enable_mint_lock")
                    yield ECTextArea(
                        id="mint_lock_script", classes="h-12 hidden mt-1"
                    )
                with Vertical(classes="w-50p"):
                    yield Checkbox("Enable Prefix Script ('_')", id="enable_prefix")
                    yield ECTextArea(id="prefix_script", classes="h-12 hidden mt-1")

            yield Static("", id="error_display", classes="text-bold mt-1 hidden")

            yield Static(
                "Stamp Details (optional; stamp 'd' value):",
                classes="text-bold my-1"
            )

            with Horizontal(classes="h-8"):
                with Vertical(classes="w-50p"):
                    yield Static("Details Type:", classes="text-bold mb-1")
                    yield OptionList(
                        Option("N/A", id="na"),
                        Option("Token", id="token"),
                        Option("Image", id="image"),
                        Option("Text", id="text"),
                        id="details_type",
                    )
                with Vertical(classes="w-50p"):
                    yield Static("Name:", classes="text-bold mb-1")
                    yield Input(id="details_name", placeholder="Optional name")

            with Horizontal(classes="h-7 mt-1"):
                with Vertical():
                    yield Static("Description:", classes="text-bold mb-1")
                    yield Input(
                        id="details_description", placeholder="Optional description"
                    )
                with Vertical():
                    yield Static("Icon (b64):", classes="text-bold mb-1")
                    with Horizontal():
                        yield Button(
                            "Import File", id="btn_import_icon", classes="m-0"
                        )
                        yield Input(
                            id="details_icon",
                            placeholder="Base64 encoded image (max "
                            f"{_max_detail_icon_size:,} bytes)",
                        )

            yield Static("Data-script-hash: ...", id="dsh", classes="mt-1 text-bold")
            yield Static("Issue: ...", id="issue", classes="mt-1 text-bold")

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
            stamp_type = StampType.TOKEN
        else:
            stamp_type = StampType.UNKNOWN

        if self.template_id is None:
            self._prepopulate_scripts(stamp_type)

        if self.template_id is None:
            allow_negatives = self.query_one("#allow_negatives")
            if stamp_type == StampType.TOKEN:
                allow_negatives.remove_class("hidden")
            else:
                allow_negatives.add_class("hidden")

    @on(OptionList.OptionHighlighted, "#details_type")
    def _on_details_type_changed(self, event: OptionList.OptionHighlighted) -> None:
        """Handle details type selection."""
        pass

    @on(Checkbox.Changed, "#allow_negatives")
    def _on_allow_negatives_changed(self, event: Checkbox.Changed) -> None:
        """Handle allow_negatives checkbox changes."""
        if self.template_id is None:
            type_radio = self.query_one("#type_radio")
            pressed_index = type_radio.pressed_index
            if pressed_index == 1:
                stamp_type = StampType.TOKEN
                prefix_script = self.query_one("#prefix_script")
                prefix_script.text = format_script_src(Txn.std_stamp_token_series_prefix(
                    event.value
                ).src)

    def _prepopulate_scripts(self, stamp_type: StampType) -> None:
        """Set covenant script text area based on `stamp_type`."""
        covenant_script = self.query_one("#covenant_script")
        enable_prefix = self.query_one("#enable_prefix")
        prefix_script = self.query_one("#prefix_script")
        allow_negatives = self.query_one("#allow_negatives")

        if stamp_type == StampType.SINGLE:
            covenant_script.text = format_script_src(Txn.std_stamp_covenant().src)
            covenant_script.read_only = False
        elif stamp_type == StampType.TOKEN:
            covenant_script.text = format_script_src(Txn.std_stamp_token_series_covenant().src)
            covenant_script.read_only = False
            enable_prefix.value = True
            prefix_script.remove_class("hidden")
            prefix_script.text = format_script_src(Txn.std_stamp_token_series_prefix(
                allow_negatives.value
            ).src)
            prefix_script.read_only = False
            self.update_mintlock_prefix_container()
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

    @on(Button.Pressed, "#btn_import_icon")
    def import_icon(self) -> None:
        """Import icon file from filesystem."""
        filter_func = (
            lambda p: p.suffix.lower() in
            ['.png', '.jpg', '.jpeg', '.gif', '.webp']
        )

        def on_file_selected(filepath: Path | None) -> None:
            """Handle file selection callback."""
            if not filepath:
                return
            try:
                data = filepath.read_bytes()

                if len(data) > _max_detail_icon_size:
                    self.app.notify(
                        f"Icon must be ≤{_max_detail_icon_size:,} bytes",
                        severity="error"
                    )
                    self.app.log_event(
                        "Import validation error: icon exceeds "
                        f"{_max_detail_icon_size:,} bytes ({len(data):,} bytes)",
                        "WARNING"
                    )
                    return

                if get_image_type(data) is None:
                    self.app.notify(
                        "Unsupported icon format (supported: PNG, JPEG, GIF, WebP)",
                        severity="error"
                    )
                    self.app.log_event(
                        "Import validation error: unsupported image format for "
                        f"{filepath.name}",
                        "WARNING"
                    )
                    return

                b64_data = base64.b64encode(data).decode()
                self.query_one("#details_icon").value = b64_data
                self.app.notify(
                    f"Imported: {filepath.name}",
                    severity="success"
                )
            except Exception as e:
                self.app.notify(
                    f"Failed to read file: {e}",
                    severity="error"
                )
                self.app.log_event(f"Import file error: {e}", "ERROR")

        self.app.push_screen(FilePickerModal(
            title="Select Icon Image",
            filter_callback=filter_func
        ), on_file_selected)

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()

    def _save_template(self) -> bool:
        """Validate and save the template. Returns `True` if save succeeded,
            `False` otherwise.
        """
        self.error_message = ""

        name = self.query_one("#name_input").value.strip()
        description = self.query_one("#description_input").value.strip() or None
        version = self.query_one("#version_input").value.strip() or None
        author = self.query_one("#author_input").value.strip() or None
        tags = self.query_one("#tags_input").value.strip() or None
        covenant_script = self.query_one("#covenant_script")
        enable_mint_lock = self.query_one("#enable_mint_lock")
        mint_lock_script = self.query_one("#mint_lock_script")
        enable_prefix = self.query_one("#enable_prefix")
        prefix_script = self.query_one("#prefix_script")

        if not name:
            self.app.log_event("Name is required", "WARNING")
            self.app.notify("Name is required", severity="warning")
            return False

        type_radio = self.query_one("#type_radio")
        type_index = type_radio.pressed_index
        if type_index == 0:
            stamp_type = StampType.SINGLE
        elif type_index == 1:
            stamp_type = StampType.TOKEN
        else:
            stamp_type = StampType.UNKNOWN

        scripts: dict[str, str] = {'$': format_script_src(covenant_script.text)}

        if enable_mint_lock.value and mint_lock_script.text.strip():
            scripts['L'] = format_script_src(mint_lock_script.text.strip())

        if enable_prefix.value and prefix_script.text.strip():
            scripts['_'] = format_script_src(prefix_script.text.strip())

        details: dict[str, bytes|str|None] = {}
        details_type = self.query_one("#details_type")
        selected_option = details_type.highlighted_option
        if selected_option and selected_option.id != "na":
            if selected_option.id == "token":
                details['type'] = 'token'
            elif selected_option.id == "image":
                details['type'] = 'image'
            elif selected_option.id == "text":
                details['type'] = 'text'

        details_name = self.query_one("#details_name").value.strip()
        if details_name:
            details['name'] = details_name

        details_description = self.query_one("#details_description").value.strip()
        if details_description:
            details['desc'] = details_description

        details_icon = self.query_one("#details_icon").value.strip()

        try:
            if details_icon:
                try:
                    icon_bytes = base64.b64decode(details_icon, validate=True)
                except Exception as e:
                    raise ValueError(f"Invalid base64 icon: {e}")
                if len(icon_bytes) > _max_detail_icon_size:
                    raise ValueError(f"Icon must be ≤{_max_detail_icon_size:,} bytes")
                if get_image_type(icon_bytes) is None:
                    raise ValueError(
                        "Unsupported icon format (supported: PNG, JPEG, GIF, WebP)"
                    )
                details['icon'] = icon_bytes
        except ValueError as e:
            self.app.log_event(f"Validation Error: {e}", "WARNING")
            self.app.notify(f"Validation Error: {e}", severity="warning")
            return False

        try:
            self.template.name = name
            self.template.description = description
            self.template.type = stamp_type
            self.template.version = version
            self.template.author = author
            self.template.tags = tags
            self.template.scripts = scripts
            self.template.details = details if details else None
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
        elif stamp_type == StampType.TOKEN:
            self.query_one("#type_token").value = True
        else:
            self.query_one("#type_unknown").value = True

        allow_negatives = self.query_one("#allow_negatives")
        allow_negatives.add_class("hidden")

        scripts = self.template.scripts
        covenant_script = self.query_one("#covenant_script")
        if '$' in scripts:
            covenant_script.text = format_script_src(scripts['$'])

        enable_mint_lock = self.query_one("#enable_mint_lock")
        mint_lock_script = self.query_one("#mint_lock_script")
        if 'L' in scripts:
            enable_mint_lock.value = True
            mint_lock_script.remove_class("hidden")
            mint_lock_script.text = format_script_src(scripts['L'])
        else:
            enable_mint_lock.value = False
            mint_lock_script.add_class("hidden")
            mint_lock_script.text = ""

        enable_prefix = self.query_one("#enable_prefix")
        prefix_script = self.query_one("#prefix_script")
        allow_negatives = self.query_one("#allow_negatives")
        if '_' in scripts:
            enable_prefix.value = True
            prefix_script.remove_class("hidden")
            prefix_script.text = format_script_src(scripts['_'])
        else:
            enable_prefix.value = False
            prefix_script.add_class("hidden")
            prefix_script.text = ""

        details = self.template.details or {}
        details_type = self.query_one("#details_type")
        details_name = self.query_one("#details_name")
        details_description = self.query_one("#details_description")
        details_icon = self.query_one("#details_icon")

        if 'type' in details:
            type_id = details['type']
            for i in range(details_type.option_count):
                opt = details_type.get_option_at_index(i)
                if opt.id == type_id:
                    details_type.highlighted = i
                    break
        else:
            details_type.highlighted = 0

        details_name.value = details.get('name', '')
        details_description.value = details.get('desc', '')
        icon_bytes = details.get('icon')
        if icon_bytes:
            details_icon.value = base64.b64encode(icon_bytes).decode()
        else:
            details_icon.value = ""

        self.query_one("#dsh").update(f"Data-script-hash: {self.template.dsh.hex()}")
        self.query_one("#issue").update(f"Issue: {self.template.issue.hex()}")

    def _initialize_new_template(self) -> None:
        """Initialize form for new template with defaults."""
        self.query_one("#type_single").value = True
        self.query_one("#details_type").highlighted = 0
        self.query_one("#details_name").value = ""
        self.query_one("#details_description").value = ""
        self.query_one("#details_icon").text = ""
        self.query_one("#allow_negatives").add_class("hidden")
        self._prepopulate_scripts(StampType.SINGLE)

    def _show_error(self) -> None:
        """Display error message in error display widget."""
        error_display = self.query_one("#error_display")
        if self.error_message:
            error_display.update(self.error_message)
            error_display.remove_class("hidden")
        else:
            error_display.update("")
            error_display.add_class("hidden")
