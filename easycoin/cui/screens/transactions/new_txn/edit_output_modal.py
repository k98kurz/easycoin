from tapescript import Script
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Static, Input, Footer, Checkbox, OptionList, DataTable
)
from textual.widgets.option_list import Option
from textual.widgets.data_table import RowKey
from secrets import token_hex
from easycoin.models import Address, Coin, StampTemplate
from easycoin.cui.helpers import format_balance, format_amount, truncate_text
from easycoin.cui.widgets import InputModal, ConfirmationModal


class EditOutputModal(ModalScreen[dict|None]):
    """Modal for editing transaction outputs."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
            self, address: str | None = None, amount: int = 0, info=None,
            max_amount: int | None = None, txn_data=None, coin: Coin | None = None
        ):
        """Initialize edit output modal. The `info` parameter is passed
            through to the callback, e.g. an index/key for tracking the
            output.
        """
        super().__init__()
        self.address = address or ""
        self.amount = amount
        self.info = info
        self.max_amount = max_amount
        self.remaining_amount = max_amount or 0
        self.txn_data = txn_data
        self.coin = coin

        self.stamp_enabled = False
        self.stamp_source = ""
        self.selected_input_id = None
        self.selected_template_id = None
        self.copied_details = {}
        self.custom_details = {}
        self._stamp_input_options = []
        self._stamp_template_options = []
        self._custom_details_rows = []

    def on_mount(self) -> None:
        """Focus address input on mount."""
        self.query_one("#address_input").focus()
        self._load_stamp_templates()
        self._load_stamp_inputs()
        self._setup_custom_details_table()
        self._populate_stamp_from_coin()

    def compose(self) -> ComposeResult:
        """Compose edit output modal layout."""
        with VerticalScroll(classes="modal-container w-60p"):
            title = "Edit Output" if self.address else "Add Output"
            yield Static(title, classes="modal-title")

            yield Static("Recipient Address:", classes="text-bold m-1")
            yield Input(
                placeholder="Enter recipient address",
                id="address_input",
                value=self.address,
                classes="form-input"
            )

            yield Static("Amount (EC⁻¹):", classes="text-bold my-1")
            yield Input(
                placeholder="Enter amount", id="amount_input",
                value=str(self.amount), classes="form-input"
            )
            if self.max_amount:
                yield Static(
                    f"Max: {format_balance(self.max_amount, exact=True)}",
                    classes="my-1"
                )
                bal = format_balance(self.remaining_amount, exact=True)
                yield Static(
                    f"Remaining: {bal}", id="remaining_amount", classes="my-1",
                )

            yield Checkbox("Stamp", id="is_stamp_checkbox", classes="my-1")

            with Horizontal(classes="h-8"):
                with Container(
                        id="stamp_source_container", classes="hidden my-1 h-7"
                    ):
                    yield Static("Stamp Source:", classes="text-bold mb-1")
                    yield OptionList(
                        Option("From Input", id="source_from_input"),
                        Option("New Stamp", id="source_new_stamp"),
                        id="stamp_source", classes="h-5"
                    )
    
                with Container(
                        id="stamp_input_container", classes="hidden my-1 h-7"
                    ):
                    yield Static("Select Stamped Input:", classes="text-bold mb-1")
                    yield OptionList(id="stamp_input_list", classes="h-5")
    
                with Container(
                        id="stamp_template_container", classes="hidden my-1 h-7"
                    ):
                    yield Static("Select Stamp Template:", classes="text-bold mb-1")
                    yield OptionList(id="stamp_template_list", classes="h-5")

            with Container(id="stamp_n_container", classes="hidden my-1 h-6"):
                yield Static("Stamp Number (n):", classes="text-bold mb-1")
                yield Input(
                    placeholder="Enter stamp number/note",
                    id="stamp_n_input",
                    classes="form-input"
                )

            with Container(id="custom_details_container", classes="hidden my-1 h-11"):
                yield Static("Custom Details:", classes="text-bold mb-1")
                yield DataTable(id="custom_details_table", classes="h-5")
                yield Button(
                    "Add Custom Field",
                    id="btn_add_custom_field",
                    classes="my-1"
                )

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def _load_stamp_templates(self) -> None:
        """Load stamp templates from database."""
        template_list = self.query_one("#stamp_template_list")
        template_list.clear_options()

        self._stamp_template_options = []
        self._stamp_template_options.append(("blank", None, "Blank/No Template"))
        template_list.add_option(Option("Blank/No Template", id="template_blank"))

        try:
            templates = StampTemplate.query().get()
            for template in templates:
                self._stamp_template_options.append((
                    template.id,
                    template,
                    f"{template.name} ({template.type.value}) ({template.version})"
                ))
                template_list.add_option(
                    Option(
                        f"{template.name} ({template.type.value}) "
                        f"({template.version})",
                        id=f"template_{template.id}"
                    )
                )
        except Exception as e:
            self.log_event(f"Error loading stamp templates: {e}", "ERROR")

    def _load_stamp_inputs(self) -> None:
        """Load stamped inputs from selected inputs."""
        input_list = self.query_one("#stamp_input_list")
        input_list.clear_options()

        self._stamp_input_options = []

        if not self.txn_data or not self.txn_data.selected_inputs:
            return

        for output in self.txn_data.selected_inputs:
            coin = output.coin
            if len(coin.details) > 0:
                data_size = len(coin.data.get('details', None) or b'')
                self._stamp_input_options.append(output)
                input_list.add_option(
                    Option(
                        f"{truncate_text(coin.id, 8, 4)} "
                        f"({format_amount(data_size)}B)",
                        id=f"input_{output.id}"
                    )
                )

    def _setup_custom_details_table(self) -> None:
        """Setup custom details DataTable."""
        table = self.query_one("#custom_details_table")
        table.add_columns("Field Name", "Field Value", "Parse Value as Hex")
        table.cursor_type = "row"

    def _populate_stamp_from_coin(self) -> None:
        """Populate stamp UI fields from existing coin details."""
        if not self.coin or not self.coin.details:
            return

        self.stamp_enabled = True
        self.copied_details = {**self.coin.details}

        stamp_checkbox = self.query_one("#is_stamp_checkbox")
        stamp_checkbox.value = True

        n_value = self.copied_details.get('n', '')
        n_input = self.query_one("#stamp_n_input")
        n_input.value = str(n_value) if n_value is not None else ''

        self._populate_custom_details_from_coin()
        self._select_matching_stamp_source()
        self._update_stamp_ui_visibility()

    def _populate_custom_details_from_coin(self) -> None:
        """Populate custom details table from coin's 'd' field."""
        d_data = self.copied_details.get('d', {})
        if not isinstance(d_data, dict):
            return

        for field_name, field_value in d_data.items():
            is_hex = isinstance(field_value, bytes)
            self._add_custom_field_row(field_name, field_value, is_hex)
            self.custom_details[field_name] = (field_value, is_hex)

    def _select_matching_stamp_source(self) -> None:
        """Try to select matching template or input based on coin details."""
        if not self.copied_details:
            return

        for tid, template, _ in self._stamp_template_options:
            if template is None:
                continue
            template_details = {
                k: Script.from_src(v).bytes for k,v in template.scripts.items()
            }
            template_details['d'] = template.details
            if self._details_match_template(template_details):
                self.stamp_source = "new_stamp"
                self.selected_template_id = tid
                template_list = self.query_one("#stamp_template_list")
                for i, option in enumerate(template_list.options):
                    if option.id == f"template_{tid}":
                        template_list.highlighted = i
                        break
                return

        for output in self._stamp_input_options:
            if output.coin.details == self.copied_details:
                self.stamp_source = "from_input"
                self.selected_input_id = output.id
                input_list = self.query_one("#stamp_input_list")
                for i, option in enumerate(input_list.options):
                    if option.id == f"input_{output.id}":
                        input_list.highlighted = i
                        break
                return

        self.stamp_source = "new_stamp"
        if len(self._stamp_template_options) > 1:
            tid, _, _ = self._stamp_template_options[1]
            self.selected_template_id = tid
            template_list = self.query_one("#stamp_template_list")
            if len(template_list.options) > 1:
                template_list.highlighted = 1

    def _details_match_template(self, template_details: dict) -> bool:
        """Check if coin details match template details (excluding 'n')."""
        for k, v in self.copied_details.items():
            if k == 'n':
                continue
            if k not in template_details or template_details[k] != v:
                return False
        return True

    def _update_stamp_ui_visibility(self) -> None:
        """Update visibility of stamp UI elements based on current state."""
        stamp_checkbox = self.query_one("#is_stamp_checkbox")
        source_container = self.query_one("#stamp_source_container")
        input_container = self.query_one("#stamp_input_container")
        template_container = self.query_one("#stamp_template_container")
        n_container = self.query_one("#stamp_n_container")
        custom_container = self.query_one("#custom_details_container")

        if stamp_checkbox.value:
            source_container.remove_class("hidden")
            
            if self.stamp_source == "from_input":
                input_container.remove_class("hidden")
                template_container.add_class("hidden")
            elif self.stamp_source == "new_stamp":
                input_container.add_class("hidden")
                template_container.remove_class("hidden")
            else:
                input_container.add_class("hidden")
                template_container.add_class("hidden")
        else:
            source_container.add_class("hidden")
            input_container.add_class("hidden")
            template_container.add_class("hidden")

        if stamp_checkbox.value and self.stamp_source:
            n_container.remove_class("hidden")
        else:
            n_container.add_class("hidden")

        if stamp_checkbox.value and self.stamp_source == "new_stamp":
            custom_container.remove_class("hidden")
        else:
            custom_container.add_class("hidden")

    @on(Checkbox.Changed, "#is_stamp_checkbox")
    def _on_stamp_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle stamp checkbox changes."""
        self.stamp_enabled = event.value
        if not event.value:
            self.stamp_source = ""
            self.selected_input_id = None
            self.selected_template_id = None
            self.copied_details = {}
        self._update_stamp_ui_visibility()

    @on(OptionList.OptionHighlighted, "#stamp_source")
    def _on_stamp_source_highlighted(
            self, event: OptionList.OptionHighlighted
        ) -> None:
        """Handle stamp source selection."""
        option = event.option
        if option.id == "source_from_input":
            self.stamp_source = "from_input"
            self.selected_template_id = None
            self.copied_details = {}
        elif option.id == "source_new_stamp":
            self.stamp_source = "new_stamp"
            self.selected_input_id = None
            self.copied_details = {}
        self._update_stamp_ui_visibility()

    @on(OptionList.OptionHighlighted, "#stamp_input_list")
    def _on_stamp_input_highlighted(
            self, event: OptionList.OptionHighlighted
        ) -> None:
        """Handle stamp input selection."""
        option = event.option
        option_id = option.id
        if option_id.startswith("input_"):
            output_id = option_id.replace("input_", "")
            for output in self._stamp_input_options:
                if output.id == output_id:
                    self.selected_input_id = output_id
                    self.copied_details = {**output.coin.details}
                    
                    n_input = self.query_one("#stamp_n_input")
                    n_value = self.copied_details.get('n', '')
                    n_input.value = str(n_value) if n_value is not None else ''
                    break

    @on(OptionList.OptionHighlighted, "#stamp_template_list")
    def _on_stamp_template_highlighted(
            self, event: OptionList.OptionHighlighted
        ) -> None:
        """Handle stamp template selection."""
        option = event.option
        if option.id == "template_blank":
            self.selected_template_id = None
            self.copied_details = {}
        else:
            template_id = option.id.replace("template_", "")
            for tid, template, _ in self._stamp_template_options:
                if tid == template_id:
                    self.selected_template_id = template_id
                    self.copied_details = {
                        k: Script.from_src(v).bytes
                        for k,v in template.scripts.items()
                    }
                    self.copied_details['d'] = template.details
                    break

    @on(Button.Pressed, "#btn_add_custom_field")
    def _on_add_custom_field(self) -> None:
        """Handle adding a custom field."""
        self._edit_custom_field(None)

    @on(DataTable.RowSelected, "#custom_details_table")
    def _on_custom_field_selected(self, event: DataTable.RowSelected) -> None:
        """Handle custom field row selection for editing."""
        row_key = event.row_key
        field_index = None
        for i, (rk, _) in enumerate(self._custom_details_rows):
            if rk == row_key:
                field_index = i
                break
        if field_index is not None:
            self._edit_custom_field(field_index)

    def _edit_custom_field(self, field_index: int | None) -> None:
        """Edit a custom field through 3-step modal flow."""
        def on_name_dismissed(name: str | None) -> None:
            if not name or not name.strip():
                return
            
            def on_value_dismissed(value: str | None) -> None:
                if value is None:
                    return
                
                def on_hex_confirmed(parse_as_hex: bool) -> None:
                    if parse_as_hex is None:
                        return
                    
                    parsed_value = value
                    if parse_as_hex:
                        try:
                            parsed_value = bytes.fromhex(value)
                        except ValueError:
                            self.app.notify("Invalid hex value", severity="warning")
                            return
                    
                    if field_index is None:
                        row_key = self._add_custom_field_row(
                            name.strip(), parsed_value, parse_as_hex
                        )
                    else:
                        row_key, _, _ = self._custom_details_rows[field_index]
                        self._update_custom_field_row(
                            row_key, name.strip(), parsed_value, parse_as_hex
                        )
                
                modal = ConfirmationModal(
                    title="Parse Value as Hex",
                    message="Should this value be parsed as hex?",
                    confirm_btn_variant="success",
                    confirm_btn_text="Parse as Hex",
                    cancel_btn_text="Nope",
                )
                self.app.push_screen(modal, on_hex_confirmed)
            
            modal = InputModal(
                title="Field Value",
                description="Enter the value for this field:",
                btn_text="Next"
            )
            self.app.push_screen(modal, on_value_dismissed)
        
        if field_index is not None:
            _, current_name, _ = self._custom_details_rows[field_index]
            title = "Edit Field Name"
            placeholder = current_name
        else:
            title = "New Field Name"
            placeholder = token_hex(4)
        
        modal = InputModal(
            title=title,
            description=f"Enter the field name:",
            btn_text="Next"
        )
        self.app.push_screen(modal, on_name_dismissed)

    def _add_custom_field_row(self, name: str, value: str | bytes, is_hex: bool) -> RowKey:
        """Add a row to the custom details table."""
        table = self.query_one("#custom_details_table")
        value_display = value.hex() if isinstance(value, bytes) else str(value)
        row_key = table.add_row(name, value_display, "Yes" if is_hex else "No")
        self._custom_details_rows.append((row_key, name, (value, is_hex)))
        self.custom_details[name] = (value, is_hex)
        return row_key

    def _update_custom_field_row(
            self, row_key: RowKey, name: str, value: str | bytes, is_hex: bool
        ) -> None:
        """Update a row in the custom details table."""
        table = self.query_one("#custom_details_table")
        value_display = value.hex() if isinstance(value, bytes) else str(value)
        table.update_cell(row_key, "Field Name", name)
        table.update_cell(row_key, "Field Value", value_display)
        table.update_cell(row_key, "Parse Value as Hex", "Yes" if is_hex else "No")
        
        for i, (rk, _, _) in enumerate(self._custom_details_rows):
            if rk == row_key:
                self._custom_details_rows[i] = (row_key, name, (value, is_hex))
                break
        
        self.custom_details[name] = (value, is_hex)

    @on(Input.Changed, "#amount_input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "amount_input":
            return
        try:
            amount = int(event.value)
            if self.max_amount:
                self.remaining_amount = self.max_amount - amount
                self.query_one("#remaining_amount").update(
                    f"Remaining: {format_balance(self.remaining_amount, exact=True)}"
                )
        except ValueError:
            self.app.notify("Amount must be an integer", severity="warning")

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        """Save output and dismiss with result."""
        try:
            address = self.query_one("#address_input").value.strip()
            amount_str = self.query_one("#amount_input").value.strip()

            if not address:
                self.app.notify("Address is required", severity="error")
                return

            if not Address.validate(address):
                self.app.notify(
                    "Invalid address: address failed validation",
                    severity="warning"
                )
                return

            try:
                amount = int(amount_str)
                if amount <= 0:
                    self.app.notify("Amount must be positive", severity="warning")
                    return
            except ValueError:
                self.app.notify("Invalid amount", severity="warning")
                return

            if self.max_amount and amount > self.max_amount:
                self.app.notify(
                    f"Amount must be <= {self.max_amount}",
                    severity="warning"
                )
                return

            stamp_checkbox = self.query_one("#is_stamp_checkbox")
            result = {
                'address': address,
                'amount': amount,
                'info': self.info,
                'is_stamp': stamp_checkbox.value,
            }

            if stamp_checkbox.value:
                n = self.query_one("#stamp_n_input").value.strip()
                
                if not n:
                    self.app.log_event("Stamp number/note is required", "WARNING")
                    self.app.notify(
                        "Stamp number/note is required",
                        severity="warning"
                    )
                    return

                stamp_details = {'n': n, **self.copied_details}
                
                d_data = self.copied_details.get('d', {})
                
                if d_data and d_data.get('type') == 'token':
                    try:
                        stamp_details['n'] = int(n)
                    except ValueError:
                        self.app.notify(
                            "Stamp number must be an integer for token type",
                            severity="warning"
                        )
                        return
                
                if self.custom_details:
                    d_copy = {**d_data} if isinstance(d_data, dict) else {}
                    for field_name, (field_value, _) in self.custom_details.items():
                        d_copy[field_name] = field_value
                    stamp_details['d'] = d_copy

                result['stamp_details'] = stamp_details
                result['stamp_source'] = self.stamp_source
                result['selected_input_id'] = self.selected_input_id
                result['selected_template_id'] = self.selected_template_id

            self.dismiss(result)
        except Exception as e:
            self.app.notify(f"Error saving output: {e}", severity="error")
            self.app.log_event(f"Save output error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        await self.app.action_quit()
