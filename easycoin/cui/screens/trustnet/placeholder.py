from textual.widgets import Static
from ..base import BaseScreen


class TrustNetScreen(BaseScreen):
    """Placeholder TrustNet screen - not yet implemented."""

    def compose(self):
        """Compose placeholder layout."""
        yield from super().compose()

    def _compose_content(self):
        """Compose placeholder content."""
        yield Static(
            "[bold]TrustNet Screen[/bold]\n\n"
            "This screen is not yet implemented.\n\n"
            "It will display:\n"
            "- TrustNet list\n"
            "- Join TrustNet form\n"
            "- TrustNet details\n"
            "- Create TrustNet",
            classes="card"
        )
