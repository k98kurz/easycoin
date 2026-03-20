from textual.widgets import Static
from ..base import BaseScreen


class NetworkScreen(BaseScreen):
    """Placeholder network screen - not yet implemented."""

    def compose(self):
        """Compose placeholder layout."""
        yield from super().compose()

    def _compose_content(self):
        """Compose placeholder content."""
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
