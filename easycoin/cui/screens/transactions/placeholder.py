from textual.widgets import Static
from ..base import BaseScreen


class TransactionsScreen(BaseScreen):
    """Placeholder transactions screen - not yet implemented."""

    TAB_ID = "tab_transactions"

    def compose(self):
        """Compose placeholder layout."""
        yield from super().compose()

    def _compose_content(self):
        """Compose placeholder content."""
        yield Static(
            "[bold]Transactions Screen[/bold]\n\n"
            "This screen is not yet implemented.\n\n"
            "It will display:\n"
            "- Transaction history\n"
            "- Send transaction form\n"
            "- Transaction details\n"
            "- Confirmed/unconfirmed tabs",
            classes="card"
        )
