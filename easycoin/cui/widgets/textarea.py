from textual.widgets import TextArea
from easycoin.cui.clipboard import universal_copy


class ECTextArea(TextArea):
    def action_copy(self) -> None:
        """Overrides the default Ctrl+C behavior."""
        # Get the currently selected text (returns empty string if no selection)
        selected_text = self.selected_text
        # Call your existing utility
        universal_copy(selected_text or self.text)
        self.app.notify("Copied to system clipboard")
