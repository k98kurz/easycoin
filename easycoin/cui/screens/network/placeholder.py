from textual.widgets import Static
from ..base import BaseScreen


class NetworkScreen(BaseScreen):
    """Placeholder network screen - not yet implemented."""

    def compose(self):
        """Compose placeholder layout."""
        yield Static(
            "[bold]Network Screen[/bold]\n\n"
            "This screen is not yet implemented.\n\n"
            "It will display:\n"
            "- Connected peers list\n"
            "- Add peer form\n"
            "- Network statistics\n"
            "- Connection settings",
            classes="card"
        )
