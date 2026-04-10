from pathlib import Path
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Footer
from easycoin import validate_gameset_hash, calculate_gameset_hash, apply_gameset
from easycoin.cui.widgets import FilePickerModal


class ActivateGameSetModal(ModalScreen):
    """Modal for activating or deactivating a Game Set."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    CSS = "ActivateGameSetModal { background: $background 50%; }"

    def __init__(self, active_gameset: str | None = None):
        """Initialize activate Game Set modal."""
        super().__init__()
        self.active_gameset = active_gameset
        self.is_valid = False
        self.selected_file_path: str | None = None
        self.calculated_hash: str | None = None

    def compose(self) -> ComposeResult:
        """Compose modal layout."""
        with Vertical(id="activate_gameset_modal", classes="modal-container w-50p"):
            yield Static("Activate Game Set", classes="modal-title")
            yield Static("\n")
            yield Static(
                "Select a Game Set file and enter its hash (72 hex chars: 64 SHA256 + "
                "8 checksum) to activate."
            )
            yield Static("\n")

            yield Static(
                f"Current active Game Set: {self.active_gameset or 'None'}",
                classes="text-bold mt-1"
            )

            if not self.active_gameset:
                yield Static("Game Set Hash:", classes="text-bold my-1")
                yield Input(
                    id="gameset_hash",
                    placeholder="Enter 72-character hex string",
                    max_length=72
                )
                yield Static("", id="validation_status", classes="text-muted mt-1")

                yield Static("", id="file_path_display", classes="text-muted")
                yield Button(
                    "Select File", id="btn_select_file", variant="default",
                    classes="mt-1"
                )

                with Vertical(id="comparison_section", classes="hidden mt-1"):
                    yield Static(
                        "Comparison of provided vs calculated:", classes="text-bold"
                    )
                    yield Static(
                        "...", id="provided_hash_display", classes="text-muted"
                    )
                    yield Static(
                        "...", id="calculated_hash_display", classes="text-muted"
                    )
                    yield Static(
                        "",
                        id="hash_match_status",
                        classes="text-muted mt-1"
                    )

            with Horizontal(id="modal_actions", classes="h-min-5 mt-1"):
                if self.active_gameset:
                    yield Button(
                        "Deactivate Game Set",
                        id="btn_deactivate",
                        variant="warning"
                    )
                else:
                    yield Button(
                        "Activate Game Set",
                        id="btn_activate",
                        variant="primary",
                        disabled=True
                    )
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize modal on mount."""
        if not self.active_gameset:
            self.query_one("#gameset_hash", Input).focus()

    @on(Button.Pressed, "#btn_select_file")
    def action_select_file(self) -> None:
        """Open file picker to select Game Set file."""
        filter_func = lambda p: p.suffix.lower() == '.zip'

        def on_file_selected(filepath: Path | None) -> None:
            if not filepath:
                return

            try:
                self.selected_file_path = str(filepath)
                self.calculated_hash = calculate_gameset_hash(self.selected_file_path)

                file_path_display = self.query_one("#file_path_display", Static)
                file_path_display.update(str(filepath))

                comparison_section = self.query_one("#comparison_section", Vertical)
                comparison_section.remove_class("hidden")

                calculated_display = self.query_one("#calculated_hash_display", Static)
                calculated_display.update(self.calculated_hash)

                self._update_comparison_display()
                self._update_button_state()

                self.app.notify(f"Selected: {filepath.name}", severity="success")
            except Exception as e:
                self.app.notify(f"Failed to load file: {e}", severity="error")
                self.app.log_event(f"Load Game Set file error: {e}", "ERROR")

        self.app.push_screen(
            FilePickerModal(
                title="Select Game Set File",
                filter_callback=filter_func,
                starting_path="."
            ),
            on_file_selected
        )

    @on(Input.Changed, "#gameset_hash")
    def on_hash_input_changed(self, event: Input.Changed) -> None:
        """Validate hash input as user types."""
        hash_input = event.value.strip()
        validation_status = self.query_one("#validation_status", Static)

        if len(hash_input) == 0:
            validation_status.update("")
            self.is_valid = False
            self._update_input_style()
            self._update_comparison_display()
            self._update_button_state()
            return

        if len(hash_input) != 72:
            validation_status.update(
                f"Length: {len(hash_input)}/72 characters"
            )
            validation_status.remove_class("status-ok")
            validation_status.add_class("status-warning")
            self.is_valid = False
            self._update_input_style()
            self._update_comparison_display()
            self._update_button_state()
            return

        try:
            hash_bytes = bytes.fromhex(hash_input)
        except ValueError:
            validation_status.update("Invalid hex format")
            validation_status.remove_class("status-ok")
            validation_status.add_class("status-error")
            self.is_valid = False
            self._update_input_style()
            self._update_comparison_display()
            self._update_button_state()
            return

        if validate_gameset_hash(hash_input):
            validation_status.update("Valid checksum")
            validation_status.remove_class("status-error")
            validation_status.remove_class("status-warning")
            validation_status.add_class("status-ok")
            self.is_valid = True
            self._update_input_style()
        else:
            validation_status.update("Invalid checksum")
            validation_status.remove_class("status-ok")
            validation_status.add_class("status-error")
            self.is_valid = False
            self._update_input_style()

        self._update_comparison_display()
        self._update_button_state()

    def _update_comparison_display(self) -> None:
        """Update side-by-side comparison display."""
        if not hasattr(self, 'app'):
            return

        provided_display = self.query_one("#provided_hash_display", Static)
        hash_input = self.query_one("#gameset_hash", Input).value.strip()

        if self.calculated_hash:
            provided_display.update(hash_input if hash_input else "...")

            hash_match_status = self.query_one("#hash_match_status", Static)
            if hash_input and self.calculated_hash:
                if hash_input == self.calculated_hash:
                    hash_match_status.update("✓ Hashes match")
                    hash_match_status.remove_class("status-warning")
                    hash_match_status.remove_class("status-error")
                    hash_match_status.add_class("status-ok")
                else:
                    hash_match_status.update("✗ Hashes do not match")
                    hash_match_status.remove_class("status-ok")
                    hash_match_status.remove_class("status-error")
                    hash_match_status.add_class("status-warning")
            else:
                hash_match_status.update("")
        else:
            provided_display.update("...")

    def _update_button_state(self) -> None:
        """Update activate button state based on validation."""
        if not self.active_gameset:
            activate_button = self.query_one("#btn_activate", Button)
            activate_button.disabled = not (
                self.is_valid and self.selected_file_path is not None
            )

    def _update_input_style(self) -> None:
        """Update input field style based on validation."""
        hash_input = self.query_one("#gameset_hash", Input)
        if self.is_valid:
            hash_input.remove_class("input-invalid")
            hash_input.add_class("input-valid")
        else:
            hash_input.remove_class("input-valid")
            hash_input.add_class("input-invalid")

    @on(Button.Pressed, "#btn_activate")
    def action_activate(self) -> None:
        """Activate the Game Set."""
        if not self.selected_file_path:
            self.app.notify("Please select a Game Set file first", severity="error")
            return

        hash_input = self.query_one("#gameset_hash", Input).value.strip()

        if not self.is_valid:
            self.app.notify("Invalid Game Set hash", severity="error")
            return

        if hash_input != self.calculated_hash:
            self.app.notify("Hash does not match selected file", severity="warning")
            self.app.log_event(
                f"Hash mismatch: provided={hash_input}, "
                f"calculated={self.calculated_hash}",
                "WARNING"
            )
            return

        try:
            db_path = self.app.config.get_db_path()
            migrations_path = self.app.config.path('migrations')

            apply_gameset(
                self.selected_file_path,
                db_path,
                migrations_path
            )

            self.app.config.set("active_game_set", hash_input)
            self.app.config.save()
            self.app.notify("Game Set activated and applied", severity="success")
            self.app.log_event(
                f"Game Set activated: {hash_input}",
                "INFO"
            )
            self.dismiss(hash_input)
        except Exception as e:
            self.app.notify(f"Failed to activate Game Set: {e}", severity="error")
            self.app.log_event(
                f"Activate Game Set error: {e} | "
                f"file={self.selected_file_path}, "
                f"hash={hash_input}",
                "ERROR"
            )

    @on(Button.Pressed, "#btn_deactivate")
    def action_deactivate(self) -> None:
        """Deactivate the current Game Set."""
        try:
            old_gameset = self.app.config.get("active_game_set")
            self.app.config.unset("active_game_set")
            self.app.config.save()
            self.app.notify("Game Set deactivated", severity="success")
            self.app.log_event(
                f"Game Set deactivated: {old_gameset}",
                "INFO"
            )
            self.dismiss(None)
        except Exception as e:
            self.app.notify(f"Failed to deactivate Game Set: {e}", severity="error")
            self.app.log_event(f"Deactivate Game Set error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()
