from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, OptionList, Static
from textual.widgets.option_list import Option
from typing import TypeVar

T = TypeVar('T')


class OptionModal(ModalScreen[T|None]):
    """General purpose option selection modal."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
            self, options: dict[str, T], *,
            title: str = "Select an Option",
            text: str = "Select an Option",
        ):
        """Initialize option modal."""
        super().__init__()
        self.options = options
        self.title = title
        self.text = text

    def compose(self) -> ComposeResult:
        """Compose option modal layout."""
        options = [
            Option(option_text, id=str(i))
            for i, option_text in enumerate(self.options.keys())
        ]

        with Vertical(id="option_modal", classes="modal-container w-50p"):
            yield Static(self.title, classes="modal-title")
            yield Static("\n")
            yield Static(self.text)
            yield Static("\n")
            yield OptionList(*options, id="option_list")
            with Horizontal(id="modal_actions"):
                yield Button("Select", id="btn_select", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")
            yield Static("")
        yield Footer()

    @on(OptionList.OptionSelected)
    def action_select(self) -> None:
        """Select the currently highlighted option."""
        option_list = self.query_one("#option_list")
        highlighted = option_list.highlighted_option
        if highlighted:
            self.dismiss(self.options[highlighted.prompt])
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Dismiss without selection."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        await self.app.action_quit()
