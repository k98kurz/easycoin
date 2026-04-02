from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, ItemGrid
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static, Footer
from easycoin.cui.helpers import sigflags_hex_to_ints, sigflags_ints_to_hex


class SigflagsModal(ModalScreen[str|None]):
    """Modal for selecting which sigfields are masked in sigflags."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, sigflags: str, *, msg: str = '', read_only: bool = False):
        super().__init__()
        self.sigflags = sigflags
        self.msg = msg or 'Set sigflags (allowed/actual sigfield masking)'
        self.read_only = read_only

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container w-50p"):
            yield Static("Sigfields", classes="modal-title")
            yield Static(self.msg, classes="p-1")
            yield Static("", id="hex_display", classes="p-1")
            with ItemGrid(min_column_width=12):
                for i in range(1, 9):
                    yield Checkbox(str(i), id=f"sf{i}")
            with Horizontal(id="modal_actions"):
                if self.read_only:
                    yield Button("Close", id="btn_close")
                else:
                    yield Button("Save", id="btn_save", variant="success")
                    yield Button("Cancel", id="btn_cancel")
        yield Footer()

    def on_mount(self) -> None:
        masked = sigflags_hex_to_ints(self.sigflags)
        for i in range(1, 9):
            checkbox = self.query_one(f"#sf{i}", Checkbox)
            if i in masked:
                checkbox.value = True
            if self.read_only:
                checkbox.disable()
        self._update_hex()

    def _update_hex(self) -> None:
        masked: set[int] = set()
        for i in range(1, 9):
            if self.query_one(f"#sf{i}", Checkbox).value:
                masked.add(i)
        hex_val = sigflags_ints_to_hex(masked)
        self.query_one("#hex_display").update(f"Hexadecimal: {hex_val}")

    @on(Checkbox.Changed)
    def _on_checkbox_changed(self) -> None:
        self._update_hex()

    @on(Button.Pressed, "#btn_save")
    def action_save(self) -> None:
        if self.read_only:
            return self.action_cancel()
        masked: set[int] = set()
        for i in range(1, 9):
            if self.query_one(f"#sf{i}", Checkbox).value:
                masked.add(i)
        self.dismiss(sigflags_ints_to_hex(masked))

    @on(Button.Pressed, "#btn_close")
    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    async def action_quit(self) -> None:
        await self.app.action_quit()
