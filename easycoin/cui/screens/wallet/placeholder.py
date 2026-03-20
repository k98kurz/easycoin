from textual.widgets import Static
from ..base import BaseScreen


class WalletScreen(BaseScreen):
    """Placeholder wallet screen - not yet implemented."""

    TAB_ID = "tab_wallet"

    def compose(self):
        """Compose placeholder layout."""
        yield Static(
            "[bold]Wallet Screen[/bold]\n\n"
            "This screen is not yet implemented.\n\n"
            "It will display:\n"
            "- Wallet list\n"
            "- Wallet details\n"
            "- Balance information\n"
            "- Address book",
            classes="card"
        )
