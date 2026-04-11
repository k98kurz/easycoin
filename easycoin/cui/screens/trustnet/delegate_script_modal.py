from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static, TextArea
from tapescript import Script
from easycoin.cui.widgets import ECTextArea


class DelegateScriptModal(ModalScreen[str | None]):
    """Modal for editing delegate script source text."""

    BINDINGS = [
        Binding("0", "app.open_repl", "REPL"),
        Binding("ctrl+e", "app.open_event_log", "Event Log"),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(
            self, title: str = "Edit Delegate Script",
            description: str = "Enter tapescript source for delegate script",
            script_src: str = ""
        ):
        """Initialize delegate script modal."""
        super().__init__()
        self.title = title
        self.description = description
        self.script_src = script_src
        self.script_error = None

    def compose(self) -> ComposeResult:
        """Compose modal layout."""
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static(self.title, classes="modal-title")
            yield Static("\n")
            yield Static(self.description)
            yield Static("\n")
            yield ECTextArea(
                id="script_textarea",
                classes="h-15",
                text=self.script_src
            )
            yield Static("", id="error_display", classes="text-bold mt-1 hidden")
            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize modal on mount."""
        self.query_one("#error_display").add_class("hidden")
        self.query_one("#script_textarea").focus()

    @on(TextArea.Changed, "#script_textarea")
    def on_script_textarea_changed(self, event: TextArea.Changed) -> None:
        """Validate tapescript source on text change."""
        script_src = event.text_area.text.strip()
        try:
            Script.from_src(script_src)
            self.script_error = None
            self.query_one("#error_display").add_class("hidden")
            self.query_one("#btn_save").disabled = False
        except BaseException as e:
            self.script_error = f"{type(e).__name__}: {e}"
            error_display = self.query_one("#error_display")
            error_display.remove_class("hidden")
            error_display.update(self.script_error)
            self.query_one("#btn_save").disabled = True

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        """Save and return the script source."""
        if self.script_error:
            self.app.notify(
                f"Cannot save: {self.script_error}",
                severity="error"
            )
            return
        textarea = self.query_one("#script_textarea")
        self.dismiss(textarea.text)

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        """Quit application."""
        await self.app.action_quit()
