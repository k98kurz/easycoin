from pathlib import Path
from time import time
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Footer
from easycoin import create_gameset, calculate_gameset_hash
from easycoin.cui.widgets import InputModal
from easycoin.cui.clipboard import universal_copy


class CreateGameSetModal(ModalScreen):
    """Modal for creating a Game Set from current database."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    CSS = "CreateGameSetModal { background: $background 50%; }"

    def __init__(self):
        """Initialize create Game Set modal."""
        super().__init__()
        self.selected_filename = None
        self.gameset_hash = None
        self.gameset_path = None

    def compose(self) -> ComposeResult:
        """Compose modal layout."""
        with VerticalScroll(id="create_gameset_modal", classes="modal-container w-50p"):
            yield Static("Create Game Set", classes="modal-title mb-1")
            yield Static(
                "Create a Game Set from the current database. "
                "This exports all transactions, coins, inputs, and outputs "
                "to a ZIP file."
            )
            yield Static("Output Filename:", classes="text-bold my-1")
            yield Static("", id="filename_display", classes="text-muted")

            with Horizontal(classes="h-5"):
                yield Button(
                    "Set Filename", id="btn_set_filename", variant="default"
                )
                yield Button(
                    "Create Game Set", id="btn_create",
                    variant="primary", disabled=True
                )

            with Vertical(id="result_section", classes="hidden mt-1"):
                yield Static("Result:", classes="text-bold")
                yield Static("File: ...", id="result_file", classes="text-muted")
                yield Static("Hash: ...", id="result_hash", classes="text-bold")

            with Horizontal(id="modal_actions", classes="h-min-5 mt-1"):
                yield Button(
                    "Copy Hash", id="btn_copy",
                    variant="default", disabled=True
                )
                yield Button("Close", id="btn_close", variant="default")

        yield Footer()

    @on(Button.Pressed, "#btn_set_filename")
    def action_set_filename(self) -> None:
        """Open input modal to set output filename."""
        default_filename = f"gameset_{int(time())}.zip"

        def on_filename_selected(filename: str | None) -> None:
            if filename:
                self.selected_filename = filename
                self.query_one("#filename_display", Static).update(filename)
                self.query_one("#btn_create", Button).disabled = False

        self.app.push_screen(
            InputModal(
                title="Set Output Filename",
                description="Enter the filename for the Game Set ZIP file:",
                value=default_filename,
                btn_text="Set"
            ),
            on_filename_selected
        )

    @on(Button.Pressed, "#btn_create")
    def action_create(self) -> None:
        """Create the Game Set."""
        if not self.selected_filename:
            self.app.notify("Please set a filename first", severity="warning")
            return

        try:
            self.gameset_path = create_gameset(self.selected_filename)
            self.gameset_hash = calculate_gameset_hash(self.gameset_path)

            self.query_one("#result_file", Static).update(
                f"File: {self.gameset_path}"
            )
            self.query_one("#result_hash", Static).update(
                f"Hash: {self.gameset_hash}"
            )
            self.query_one("#result_section", Vertical).remove_class("hidden")
            self.query_one("#btn_copy", Button).disabled = False

            self.app.notify(
                f"Game Set created: {self.selected_filename}",
                severity="success"
            )
        except Exception as e:
            self.app.notify(f"Failed to create Game Set: {e}", severity="error")
            self.app.log_event(f"Create Game Set error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_copy")
    def action_copy_hash(self) -> None:
        """Copy the Game Set hash to clipboard."""
        if not self.gameset_hash:
            self.app.notify("No hash to copy", severity="warning")
            return

        try:
            universal_copy(self.gameset_hash)
            self.app.notify("Hash copied to clipboard", severity="success")
        except Exception as e:
            self.app.notify(f"Failed to copy: {e}", severity="error")
            self.app.log_event(f"Copy hash error: {e}", "ERROR")

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        """Quit the application."""
        await self.app.action_quit()
