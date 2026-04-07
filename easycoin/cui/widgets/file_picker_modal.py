from pathlib import Path
from typing import Callable
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Footer, Static


class ECDirectoryTree(DirectoryTree):
    def __init__(self, filter_callback, *args, **kwargs):
        self.filter_callback = filter_callback
        super().__init__(*args, **kwargs)

    def filter_paths(self, paths: list[Path]) -> list[Path]:
        """Filter displayed paths if a filter callback is provided."""
        if self.filter_callback is None:
            return paths
        return [p for p in paths if p.is_dir() or self.filter_callback(p)]


class FilePickerModal(ModalScreen[Path|None]):
    """Modal for selecting files from the filesystem."""

    BINDINGS = [
        ("enter", "select", "Select"),
        ("escape", "cancel", "Cancel"),
        ("ctrl+q", "quit", "Quit"),
    ]

    CSS = "FilePickerModal { background: $background 50%; }"

    def __init__(
            self, *, title: str = "Select File",
            filter_callback: Callable[[Path], bool] | None = None,
            starting_path: str = ".",
        ):
        """Initialize file picker modal with optional filtering."""
        super().__init__()
        self.title = title
        self.filter_callback = filter_callback
        self.starting_path = Path(starting_path).expanduser().resolve()

    def compose(self) -> ComposeResult:
        """Compose file picker layout."""
        with Vertical(classes="modal-container w-70p h-40"):
            yield Static(self.title, classes="modal-title")
            yield ECDirectoryTree(
                self.filter_callback, self.starting_path, id="file_tree",
            )

            with Horizontal(id="modal_actions"):
                yield Button("Select", id="btn_select", variant="primary")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    @on(Button.Pressed, "#btn_select")
    def action_select(self) -> None:
        """Select the currently highlighted file."""
        tree = self.query_one("#file_tree", DirectoryTree)
        if tree.cursor_node and tree.cursor_node.data.path.is_file():
            self.dismiss(tree.cursor_node.data.path)
        else:
            self.app.notify("Please select a file", severity="warning")

    @on(Button.Pressed, "#btn_cancel")
    def action_cancel(self) -> None:
        """Dismiss without selection."""
        self.dismiss(None)

    async def action_quit(self) -> None:
        await self.app.action_quit()
