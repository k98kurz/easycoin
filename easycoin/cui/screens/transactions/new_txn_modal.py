from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Static, Footer, DataTable, Input,
    TextArea, Label, Checkbox
)
from textual.widgets.data_table import RowKey
from easycoin.cui.screens.transactions.edit_output_modal import EditOutputModal
from easycoin.models import Txn, Coin, Output, Address, Wallet
from easycoin.UTXOSet import UTXOSet
from easycoin.cui.helpers import format_balance, truncate_text
from tapescript import Script


class NewTransactionModal(ModalScreen):
    """Modal for creating new transactions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        """Initialize new transaction modal."""
        super().__init__()
        self.current_step = 0
        self.selected_outputs: list[Output] = []
        self.outputs: list[dict] = []
        self.witness_scripts: dict[bytes, bytes] = {}
        self.available_outputs: list[Output] = []
        self.row_keys: list[RowKey] = []
        self.fee = 0

    def compose(self) -> ComposeResult:
        """Compose new transaction modal layout."""
        with VerticalScroll(classes="modal-container w-80p h-70p"):
            yield Static("New Transaction", classes="modal-title")

            with Vertical(id="step_container", classes="mt-1"):
                yield from self._compose_step_1_select_inputs()
                yield from self._compose_step_2_add_outputs()
                yield from self._compose_step_3_witness()
                yield from self._compose_step_4_review()

            with Horizontal(id="modal_actions"):
                yield Button("Back", id="btn_back", variant="default")
                yield Button("Next", id="btn_next", variant="primary")
                yield Button("Submit", id="btn_submit", variant="success")
                yield Button("Delete Output", id="btn_delete_output", variant="error")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def _compose_step_1_select_inputs(self) -> ComposeResult:
        """Compose Step 1: Select inputs."""
        with VerticalScroll(id="step_1_container"):
            yield Static(
                "[bold]Step 1 of 4: Select Inputs[/bold]\n\n"
                "Select coins to spend in this transaction.",
                classes="mb-1"
            )
            yield Static(
                "Selected: 0 coins | Total: 0 EC⁻¹",
                id="input_summary",
                classes="mb-1"
            )
            yield DataTable(id="inputs_table", classes="h-min-20")

    def _compose_step_2_add_outputs(self) -> ComposeResult:
        """Compose Step 2: Add outputs."""
        with VerticalScroll(id="step_2_container"):
            yield Static(
                "[bold]Step 2 of 4: Add Outputs[/bold]\n\n"
                "Specify recipients and amounts for this transaction.",
                classes="mb-1"
            )
            yield Static(
                "Total Input: 0 EC⁻¹ | Total Output: 0 EC⁻¹ | "
                "Estimated Fee: 0 EC⁻¹",
                id="output_summary",
                classes="mb-1"
            )
            yield DataTable(id="outputs_table", classes="h-min-10")
            yield Button("Add Output", id="btn_add_output", variant="default")

    def _compose_step_3_witness(self) -> ComposeResult:
        """Compose Step 3: Witness inputs."""
        with Vertical(id="step_3_container"):
            yield Static(
                "[bold]Step 3 of 4: Witness Inputs[/bold]\n\n"
                "Provide witness scripts to authorize spending selected inputs.",
                classes="mb-1"
            )
            with Vertical(id="witness_container", classes="h-min-20"):
                if not self.selected_outputs:
                    pass
                else:
                    for i, output in enumerate(self.selected_outputs):
                        with Horizontal(id=f"witness_row_{i}", classes="my-1"):
                            with Vertical(classes="w-1fr"):
                                yield Label(
                                    f"Input: {truncate_text(output.id, prefix_len=8, suffix_len=4)} "
                                    f"({format_balance(output.coin.amount, exact=True)})",
                                    classes="form-label"
                                )
                                lock_type = Wallet.get_lock_type(output.coin.lock)
                                is_known = self._is_known_lock(output.id)
                                if is_known:
                                    yield Static(
                                        f"[bold]Known Address ({lock_type})[/bold]\n"
                                        "Witness will be auto-generated from wallet keys.",
                                        classes="text-muted"
                                    )
                                else:
                                    yield Label("Custom Tapescript:", classes="form-label")
                                    yield TextArea(
                                        "",
                                        id=f"witness_script_{i}",
                                        placeholder="Enter tapescript source",
                                        classes="h-5"
                                    )

    def _compose_step_4_review(self) -> ComposeResult:
        """Compose Step 4: Review and submit."""
        with Vertical(id="step_4_container"):
            yield Static(
                "[bold]Step 4 of 4: Review and Submit[/bold]\n\n"
                "Review transaction details before submitting.",
                classes="mb-1"
            )

            with Vertical(id="review_summary", classes="h-min-20"):
                yield Static("Transaction Summary:", classes="text-bold mb-1")

                yield Static("Inputs:", classes="text-bold")
                if not self.selected_outputs:
                    yield Static("No inputs selected.", classes="mb-1 text-muted")
                else:
                    for output in self.selected_outputs:
                        yield Static(
                            f"  • {truncate_text(output.id, prefix_len=8, suffix_len=4)} - "
                            f"{format_balance(output.coin.amount, exact=True)}",
                            classes="mb-1"
                        )
                    yield Static("")

                yield Static("Outputs:", classes="text-bold")
                if not self.outputs:
                    yield Static("No outputs specified.", classes="mb-1 text-muted")
                else:
                    for form in self.outputs:
                        address = form.get('address', 'N/A')
                        amount = form.get('amount', '0')
                        yield Static(
                            f"  • {address} - {amount} EC⁻¹",
                            classes="mb-1"
                        )
                    yield Static("")

                total_input = sum(o.coin.amount for o in self.selected_outputs)
                total_output = 0
                for form in self.outputs:
                    try:
                        total_output += int(form.get('amount', '0'))
                    except ValueError:
                        pass
                fee = max(0, total_input - total_output)

                yield Static("Fee:", classes="text-bold")
                yield Static(f"  Estimated Fee: {format_balance(fee, exact=True)}", classes="mb-1")
                yield Static("")

                yield Static("Status:", classes="text-bold")
                yield Static(
                    "Ready to submit. Please review all details above.",
                    classes="mb-1"
                )

    def on_mount(self) -> None:
        """Initialize modal on mount."""
        self._update_step_visibility()
        self._update_button_visibility()
        self._load_available_outputs()
        self.query_one("#inputs_table").focus()

    def _update_step_visibility(self) -> None:
        """Update visibility of step containers based on current step."""
        try:
            for step_num in range(4):
                container_id = f"#step_{step_num + 1}_container"
                try:
                    container = self.query_one(container_id)
                    container.display = (
                        "block" if step_num == self.current_step else "none"
                    )
                except Exception:
                    pass
        except Exception as e:
            self.app.log_event(f"Error updating step visibility: {e}", "ERROR")

    def _update_button_visibility(self) -> None:
        """Update button visibility based on current step."""
        btn_back = self.query_one("#btn_back")
        btn_next = self.query_one("#btn_next")
        btn_submit = self.query_one("#btn_submit")
        btn_delete = self.query_one("#btn_delete_output")

        btn_back.display = "block" if self.current_step > 0 else "none"

        if self.current_step < 3:
            btn_next.display = "block"
            if self.current_step == 0:
                btn_next.disabled = len(self.selected_outputs) == 0
            else:
                btn_next.disabled = False
            btn_submit.display = "none"
        else:
            btn_next.display = "none"
            btn_submit.display = "block"
            btn_submit.disabled = False

        btn_delete.display = (
            "block" if self.current_step == 1 and self.outputs else "none"
        )

    def _load_available_outputs(self) -> None:
        """Load available unspent outputs for the wallet."""
        if not self.app.wallet:
            self.app.notify(
                "Must select a wallet to use this feature", severity="warning"
            )
            return

        try:
            table = self.query_one("#inputs_table")
            table.clear()
            self.row_keys.clear()
            self.available_outputs.clear()

            if len(table.columns) == 0:
                table.add_columns(
                    ("Coin ID", "coin_id"),
                    ("Amount", "amount"),
                    ("Lock Type", "lock_type"),
                    ("Selected", "selected"),
                )
            table.cursor_type = "row"

            outputs = Output.query().equal(
                'wallet_id', self.app.wallet.id
            ).get()

            for output in outputs:
                try:
                    row_key = table.add_row(
                        truncate_text(output.id, prefix_len=8, suffix_len=4),
                        format_balance(output.coin.amount, exact=True),
                        Wallet.get_lock_type(output.coin.lock),
                        "✓" if output.id in [o.id for o in self.selected_outputs] else " ",
                        key=output.id
                    )
                    self.row_keys.append(row_key)
                    self.available_outputs.append(output)
                except Exception as e:
                    self.app.log_event(
                        f"Error loading output {output.id}: {e}",
                        "DEBUG"
                    )

            self._update_input_summary()

        except Exception as e:
            self.app.log_event(f"Error loading outputs: {e}", "ERROR")

    def _update_input_summary(self) -> None:
        """Update input summary display."""
        try:
            total_amount = sum(o.coin.amount for o in self.selected_outputs)
            summary = self.query_one("#input_summary")
            summary.update(
                f"Selected: {len(self.selected_outputs)} coins | "
                f"Total: {format_balance(total_amount, exact=True)}"
            )
        except Exception:
            pass

    def _is_known_lock(self, coin_id: str) -> bool:
        """Check if lock belongs to a known wallet address."""
        try:
            if not self.app.wallet or self.app.wallet.is_locked:
                return False

            coin = Coin.find(coin_id)
            if not coin:
                return False

            for address in self.app.wallet.addresses:
                if coin.lock == address.lock:
                    return True

            return False
        except Exception:
            return False

    def _generate_witnesses(self) -> dict[bytes, bytes]:
        """Generate witness scripts for all selected inputs."""
        witnesses = {}
        txn = Txn()

        try:
            txn.input_ids = [o.id for o in self.selected_outputs]
            for form in self.outputs:
                address_str = form.get('address', '').strip()
                if not address_str:
                    continue
                try:
                    amount = int(form.get('amount', '0'))
                    if amount <= 0:
                        continue
                    lock_bytes = Address.parse(address_str)
                    coin = Coin.create(lock_bytes, amount)
                    txn.output_ids.append(coin.id)
                except Exception as e:
                    self.app.log_event(
                        f"Error processing output {address_str}: {e}",
                        "WARNING"
                    )
        except Exception as e:
            self.app.log_event(f"Error preparing txn for witnesses: {e}", "ERROR")

        for i, output in enumerate(self.selected_outputs):
            try:
                coin_id = output.id
                coin = output.coin

                if not coin:
                    self.app.log_event(f"No coin found for output {coin_id}", "WARNING")
                    continue

                coin_id_bytes = coin.id_bytes
                is_known = self._is_known_lock(coin_id)

                if is_known:
                    try:
                        lock_type = Wallet.get_lock_type(coin.lock)
                        if lock_type == "P2PKH":
                            witness_script = self.app.wallet.get_p2pkh_witness(
                                0, txn, coin
                            )
                        elif lock_type == "P2PK":
                            witness_script = self.app.wallet.get_p2pk_witness(
                                0, txn, coin
                            )
                        elif lock_type == "P2TR":
                            witness_script = self.app.wallet.get_p2tr_witness_keyspend(
                                0, txn, coin
                            )
                        else:
                            witness_script = Script.from_src('true')

                        witnesses[coin_id_bytes] = witness_script.bytes
                    except Exception as e:
                        self.app.log_event(
                            f"Error generating witness for {coin_id}: {e}",
                            "ERROR"
                        )
                else:
                    try:
                        text_area = self.query_one(f"#witness_script_{i}")
                        if text_area and text_area.text.strip():
                            witness_script = Script.from_src(text_area.text.strip())
                            witnesses[coin_id_bytes] = witness_script.bytes
                    except Exception as e:
                        self.app.log_event(
                            f"Error compiling witness script for {coin_id}: {e}",
                            "ERROR"
                        )
            except Exception as e:
                self.app.log_event(
                    f"Error processing witness for {output.id}: {e}",
                    "ERROR"
                )

        return witnesses

    @on(Button.Pressed, "#btn_next")
    def action_next(self) -> None:
        """Move to next step."""
        if self.current_step < 3:
            self.current_step += 1
            self._refresh_step_content()
            self._update_button_visibility()

        if self.current_step == 0:
            self.query_one("#inputs_table").focus()
        elif self.current_step == 1:
            self.query_one("#outputs_table").focus()

    @on(Button.Pressed, "#btn_back")
    def action_back(self, event = None) -> None:
        """Move to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._refresh_step_content()
            self._update_button_visibility()

        if self.current_step == 0:
            self.query_one("#inputs_table").focus()
        elif self.current_step == 1:
            self.query_one("#outputs_table").focus()

    @on(Button.Pressed, "#btn_submit")
    def action_submit(self) -> None:
        """Submit transaction."""
        try:
            if not self.app.wallet:
                self.app.notify("No wallet loaded", severity="error")
                return

            if self.app.wallet.is_locked:
                self.app.notify("Wallet must be unlocked", severity="error")
                return

            if not self.selected_outputs:
                self.app.notify("No inputs selected", severity="error")
                return

            if not self.outputs:
                self.app.notify("No outputs specified", severity="error")
                return

            self._validate_and_submit_transaction()

        except Exception as e:
            self.app.log_event(f"Error submitting transaction: {e}", "ERROR")
            self.app.notify(f"Error: {e}", severity="error")

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()

    @on(Button.Pressed, "#btn_add_output")
    def action_add_output(self) -> None:
        """Open EditOutputModal to add new output."""
        def on_dismiss(result):
            if not result:
                return
            self.outputs.append({
                'address': result['address'],
                'amount': result['amount']
            })
            self._refresh_outputs_table()
            self._update_output_summary()
            self.query_one("#inputs_table").focus()

        total_out = sum([o['amount'] for o in self.outputs])
        total_in = sum(o.coin.amount for o in self.selected_outputs)
        self.app.push_screen(
            EditOutputModal(
                address=None, amount=0, info=None,
                max_amount=total_in - total_out - self.fee
            ),
            on_dismiss
        )

    @on(DataTable.RowSelected, "#outputs_table")
    def _edit_output(self, event: DataTable.RowSelected) -> None:
        """Open EditOutputModal to edit selected output."""
        output_index = event.row_key.value

        if 0 <= output_index < len(self.outputs):
            def on_dismiss(result):
                if not result:
                    return
                self.outputs[result['info']] = {
                    'address': result['address'],
                    'amount': result['amount']
                }
                self._refresh_outputs_table()
                self._update_output_summary()

            current = self.outputs[output_index]
            total_out = sum([o['amount'] for o in self.outputs])
            total_in = sum(o.coin.amount for o in self.selected_outputs)
            self.app.push_screen(
                EditOutputModal(
                    address=current.get('address', ''),
                    amount=int(current.get('amount', 0)),
                    info=output_index,
                    max_amount=total_in - total_out - self.fee
                ),
                on_dismiss
            )

    @on(Button.Pressed, "#btn_delete_output")
    def action_delete_output(self) -> None:
        """Delete currently selected output."""
        try:
            table = self.query_one("#outputs_table")
            if table.cursor_row is not None and table.cursor_row < len(self.outputs):
                del self.outputs[table.cursor_row]
                self._refresh_outputs_table()
                self._update_output_summary()
                self._update_button_visibility()
        except Exception as e:
            self.app.log_event(f"Error deleting output: {e}", "ERROR")

    @on(DataTable.RowSelected, "#inputs_table")
    def _toggle_selection(self, event: DataTable.RowSelected) -> None:
        """Toggle selection for currently highlighted row."""
        table = event.data_table
        try:
            output = next(
                (o for o in self.available_outputs if o.id == event.row_key),
                None
            )

            if output:
                if output in self.selected_outputs:
                    self.selected_outputs.remove(output)
                    table.update_cell(event.row_key, "selected", " ")
                else:
                    self.selected_outputs.append(output)
                    table.update_cell(event.row_key, "selected", "✓")

                #self._refresh_input_table()
                self._update_input_summary()
                self._update_button_visibility()
        except Exception as e:
            self.app.log_event(f"Error toggling selection: {e}", "ERROR")



    def _validate_and_submit_transaction(self) -> None:
        """Validate and submit the transaction."""
        try:
            txn = Txn()
            txn.input_ids = [o.id for o in self.selected_outputs]

            output_coins = {}
            for form in self.outputs:
                address_str = form.get('address', '').strip()
                amount_str = form.get('amount', '').strip()

                if not address_str or not amount_str:
                    continue

                try:
                    amount = int(amount_str)
                    if amount <= 0:
                        self.app.notify(
                            f"Invalid amount: {amount_str}",
                            severity="error"
                        )
                        return

                    lock_bytes = Address.parse(address_str)
                    coin = Coin.create(lock_bytes, amount)
                    output_coins[coin.id] = coin
                    txn.output_ids.append(coin.id)
                except Exception as e:
                    self.app.notify(
                        f"Invalid address: {address_str}",
                        severity="error"
                    )
                    self.app.log_event(f"Address parse error: {e}", "DEBUG")
                    return

            if not txn.output_ids:
                self.app.notify("No valid outputs", severity="error")
                return

            txn.witness = self._generate_witnesses()
            txn.set_timestamp()

            if not txn.validate():
                self.app.notify(
                    "Transaction validation failed",
                    severity="error"
                )
                self.app.log_event("Transaction validation failed", "DEBUG")
                return

            utxo = UTXOSet()
            if not utxo.can_apply(txn):
                self.app.notify(
                    "Transaction cannot be applied to UTXO",
                    severity="error"
                )
                self.app.log_event("UTXO validation failed", "DEBUG")
                return

            txn.save()
            utxo.apply(txn, output_coins)

            self.app.log_event(f"Submitted txn: {txn.id}", "INFO")

            self.dismiss()

        except Exception as e:
            self.app.log_event(f"Error in validation: {e}", "ERROR")
            self.app.notify(f"Error: {e}", severity="error")

    def _refresh_step_content(self) -> None:
        """Refresh step content based on current step."""
        self._update_step_visibility()

        if self.current_step == 0:
            self._load_available_outputs()
        elif self.current_step == 1:
            self._refresh_outputs_table()
            self._update_output_summary()
        elif self.current_step == 2:
            self._refresh_witness_container()
        elif self.current_step == 3:
            self._refresh_review_container()

    def _update_output_summary(self) -> None:
        """Update output summary display."""
        try:
            total_input = sum(o.coin.amount for o in self.selected_outputs)
            total_output = 0
            for form in self.outputs:
                try:
                    amount = int(form.get('amount', '0'))
                    total_output += amount
                except (ValueError, TypeError):
                    pass

            estimated_fee = max(0, total_input - total_output)
            summary = self.query_one("#output_summary")
            summary.update(
                f"Total Input: {format_balance(total_input, exact=True)} | "
                f"Total Output: {format_balance(total_output, exact=True)} | "
                f"Estimated Fee: {format_balance(estimated_fee, exact=True)}"
            )
        except Exception as e:
            self.app.log_event(f"Error updating output summary: {e}", "DEBUG")

    def _refresh_outputs_table(self) -> None:
        """Refresh the outputs table with current output forms."""
        try:
            table = self.query_one("#outputs_table")
            table.clear()

            if len(table.columns) == 0:
                table.add_columns(
                    ("Address", "address"),
                    ("Amount (EC⁻¹)", "amount"),
                )
            table.cursor_type = "row"

            for i, output in enumerate(self.outputs):
                table.add_row(
                    output.get('address', ''),
                    str(output.get('amount', '')),
                    key=i
                )
        except Exception as e:
            self.app.log_event(f"Error refreshing outputs table: {e}", "ERROR")

    def _refresh_witness_container(self) -> None:
        """Refresh the witness container with current selected outputs."""
        try:
            witness_container = self.query_one("#witness_container")
            witness_container.remove_children()

            if not self.selected_outputs:
                witness_container.mount(
                    Static(
                        "No inputs selected. Go back to Step 1.",
                        id="witness_placeholder"
                    )
                )
            else:
                for i, output in enumerate(self.selected_outputs):
                    row = Horizontal(id=f"witness_row_{i}", classes="my-1")
                    col = Vertical(classes="w-1fr")
                    label = Label(
                        f"Input: {truncate_text(output.id, prefix_len=8, suffix_len=4)} "
                        f"({format_balance(output.coin.amount, exact=True)})",
                        classes="form-label"
                    )

                    lock_type = Wallet.get_lock_type(output.coin.lock)
                    is_known = self._is_known_lock(output.id)

                    witness_container.mount(row)
                    row.mount(col)
                    if is_known:
                        status = Static(
                            f"[bold]Known Address ({lock_type})[/bold]\n"
                            "Witness will be auto-generated from wallet keys.",
                            classes="text-muted"
                        )
                        col.mount(label, status)
                    else:
                        sublabel = Label("Custom Tapescript:", classes="form-label")
                        text_area = TextArea(
                            "",
                            id=f"witness_script_{i}",
                            placeholder="Enter tapescript source",
                            classes="h-5"
                        )
                        col.mount(label, sublabel, text_area)
        except Exception as e:
            self.app.log_event(f"Error refreshing witness container: {e}", "ERROR")

    def _refresh_review_container(self) -> None:
        """Refresh the review container with current transaction details."""
        try:
            review_summary = self.query_one("#review_summary")
            review_summary.remove_children()

            review_summary.mount(Static("Transaction Summary:", classes="text-bold mb-1"))

            review_summary.mount(Static("Inputs:", classes="text-bold"))
            if not self.selected_outputs:
                review_summary.mount(
                    Static("No inputs selected.", classes="mb-1 text-muted")
                )
            else:
                for output in self.selected_outputs:
                    review_summary.mount(
                        Static(
                            f"  • {truncate_text(output.id, prefix_len=8, suffix_len=4)} - "
                            f"{format_balance(output.coin.amount, exact=True)}",
                            classes="mb-1"
                        )
                    )
                review_summary.mount(Static(""))

            review_summary.mount(Static("Outputs:", classes="text-bold"))
            if not self.outputs:
                review_summary.mount(
                    Static("No outputs specified.", classes="mb-1 text-muted")
                )
            else:
                for form in self.outputs:
                    address = form.get('address', 'N/A')
                    amount = form.get('amount', '0')
                    review_summary.mount(
                        Static(
                            f"  • {address} - {amount} EC⁻¹",
                            classes="mb-1"
                        )
                    )
                review_summary.mount(Static(""))

            total_input = sum(o.coin.amount for o in self.selected_outputs)
            total_output = 0
            for form in self.outputs:
                try:
                    total_output += int(form.get('amount', '0'))
                except ValueError:
                    pass
            fee = max(0, total_input - total_output)

            review_summary.mount(Static("Fee:", classes="text-bold"))
            review_summary.mount(Static(f"  Estimated Fee: {format_balance(fee, exact=True)}", classes="mb-1"))
            review_summary.mount(Static(""))

            review_summary.mount(Static("Status:", classes="text-bold"))
            review_summary.mount(
                Static(
                    "Ready to submit. Please review all details above.",
                    classes="mb-1"
                )
            )
        except Exception as e:
            self.app.log_event(f"Error refreshing review container: {e}", "ERROR")

    def _refresh_input_table(self) -> None:
        """Refresh the inputs table to show current selections."""
        try:
            table = self.query_one("#inputs_table")
            table.clear()

            for output in self.available_outputs:
                is_selected = output in self.selected_outputs
                table.add_row(
                    truncate_text(output.id, prefix_len=8, suffix_len=4),
                    format_balance(output.coin.amount, exact=True),
                    Wallet.get_lock_type(output.coin.lock),
                    "✓" if is_selected else " ",
                    key=output.id
                )
        except Exception as e:
            self.app.log_event(f"Error refreshing table: {e}", "ERROR")

