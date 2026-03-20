from textual.widgets import Tabs, Tab


class TopTabs(Tabs):
    """Top navigation tabs for switching between screens."""

    def __init__(self, **kwargs):
        """Initialize TopTabs with main navigation tabs."""
        super().__init__(
            Tab("Dashboard", id="tab_dashboard"),
            Tab("Wallet", id="tab_wallet"),
            Tab("Coins", id="tab_coins"),
            Tab("Transactions", id="tab_transactions"),
            **kwargs
        )

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Handle tab activation to switch screens."""
        tab_id = event.tab.id
        screen_map = {
            "tab_dashboard": "dashboard",
            "tab_wallet": "wallet",
            "tab_coins": "coins",
            "tab_transactions": "transactions",
        }
        screen_name = screen_map.get(tab_id)
        if screen_name:
            self.app.push_screen(screen_name)
