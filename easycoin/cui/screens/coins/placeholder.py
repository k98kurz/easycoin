from textual.widgets import Static
from ..base import BaseScreen


class CoinsScreen(BaseScreen):
    """Placeholder coins screen - not yet implemented."""

    TAB_ID = "tab_coins"

    def compose(self):
        """Compose placeholder layout."""
        yield Static(
            "[bold]Coins Screen[/bold]\n\n"
            "This screen is not yet implemented.\n\n"
            "It will display:\n"
            "- Coin list with filtering\n"
            "- Mining configuration\n"
            "- Coin details\n"
            "- Mining progress",
            classes="card"
        )
