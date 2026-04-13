from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static


class HelpModal(ModalScreen):
    """Context-sensitive help modal with screen-specific content."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("ctrl+q", "app.quit", "Quit"),
    ]

    def __init__(self, screen_id: str | None = None):
        """Initialize HelpModal. Args:
            screen_id: The TAB_ID of the current screen, or 'welcome' for
                the original welcome message, or None for general help.
        """
        super().__init__()
        self.screen_id = screen_id

    def compose(self) -> ComposeResult:
        """Compose help modal layout."""
        title, content = self._get_help_content()
        with VerticalScroll(classes="modal-container w-70p"):
            yield Static(title, classes="modal-title")
            yield Static(content, classes="m-1")
            with Horizontal(id="modal_actions"):
                yield Button("Close", id="btn_close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "btn_close":
            self.dismiss()

    def _get_help_content(self) -> tuple[str, str]:
        """Get title and content based on screen_id. Returns (title, content)."""
        if self.screen_id == "welcome":
            return self._get_welcome_content()
        elif self.screen_id == "tab_wallet":
            return self._get_wallet_content()
        elif self.screen_id == "tab_coins":
            return self._get_coins_content()
        elif self.screen_id == "tab_transactions":
            return self._get_transactions_content()
        elif self.screen_id == "tab_stamps":
            return self._get_stamps_content()
        elif self.screen_id == "tab_network":
            return self._get_network_content()
        elif self.screen_id == "tab_trustnet":
            return self._get_trustnet_content()
        elif self.screen_id == "tab_settings":
            return self._get_settings_content()
        else:
            return ("Help", "No help content available for this screen.")

    def _get_welcome_content(self) -> tuple[str, str]:
        """Get original welcome message content."""
        return (
            "Welcome to EasyCoin",
            "This is the Console User Interface (CUI) for EasyCoin.\n\n"
            "EasyCoin is all fun and games. It even has a bona-fide "
            "Proof-of-Concept consensus system that won't be found "
            "in any serious scamchain project: if it validates, save it "
            "locally and never mind what other nodes think.\n\n"
            "The main purposes of this project are 1) to provide a fun "
            "way to make cryptographic puzzle games, 2) to parody "
            "projects that came before, and 3) to lay bare the innards of a "
            "functional and at least somewhat competent cryptocurrency system "
            "for educational value.\n\n"
            "The mental model is that anyone can mine a coin denominated "
            "in EC⁻¹ (inverse Energy Credits -- proof you burned some "
            "electricity crunching numbers), and then they can stamp it "
            "with some data, kind of like those novelty machines where "
            "you put in a penny and crank the handle to flatten it and "
            "impress an image. Standard Stamp covenants include fungible "
            "tokens and non-fungible Stamps (kind of like NFTs but without any "
            "guarantee of total uniqueness -- just that the data itself cannot "
            "be split or joined).\n\n"
            "Instead of a blockchain with every transaction ever, EasyCoin "
            "instead tracks input and output coin ids; transactions and the "
            "coins themselves are only of use to the parties involved and the "
            "holders, respectively -- if you want to send a jpeg to someone, "
            "feel free, but not everyone on the network is interested: after "
            "the network protocol and TrustNet features are implemented, local "
            "db pruning will be implemented to enable the full vision of this "
            "system design (see the forum conversation between Red and Satoshi "
            "Nakamoto from August 10-13, 2010 for the incitement/inspiration).\n\n"
            "Note that at the current time, only single-player/offline mode is "
            "functional. Future updates include network protocol and TrustNet "
            "functionality, which will include txn/utxo mutation attestations "
            "and snapshots for synchronizing new nodes.\n\n"
            "Press 'Close' or Esc to begin exploring the app. Each screen has "
            "help text accessible via hitting the `?` key. Start by creating a "
            "wallet and then activating a single-player GameSet in the Settings "
            "screen, which will import coins and txns for inspection and/or "
            "hijacking (think of the locking scripts as puzzles to solve). "
            "Have fun, and happy hunting.\n\n"
            "P.S. If you are at the HackNWA or Sparkcon 2026 conference, I'll "
            "be around to answer questions and take feedback."
        )

    def _get_wallet_content(self) -> tuple[str, str]:
        """Get Wallet help content."""
        return (
            "Wallet Help",
            "Manage your cryptographic wallets and identities.\n\n"
            "Actions:\n"
            "- Create (N): Generate a new wallet\n"
            "- Restore (R): Recover a wallet from seed phrase\n"
            "- Select (S): Unlock and use a wallet\n"
            "- Delete (D): Remove a wallet permanently\n\n"
            "Press 'Close' or Esc to continue."
        )

    def _get_coins_content(self) -> tuple[str, str]:
        """Get Coins help content."""
        return (
            "Coins Help",
            "View and manage your coins and stamps.\n\n"
            "Actions:\n"
            "- Mine Coin (M): Create new coins\n"
            "- Configure Mining (C): Adjust mining settings\n"
            "  - Auto Top-up and Continuous modes are currently nonfunctional\n"
            "  - Manual mining via the Mine Coins(s) button respects process "
            "pool configuration\n"
            "- Refresh (F5): Update the coins list\n\n"
            "Filter coins by type, search by ID, and paginate through results.\n\n"
            "Press 'Close' or Esc to continue."
        )

    def _get_transactions_content(self) -> tuple[str, str]:
        """Get Transactions help content."""
        return (
            "Transactions Help",
            "View transaction history and create new transactions.\n\n"
            "Actions:\n"
            "- New Transaction (N): Send coins to an address\n"
            "- View Transaction (V): See transaction details\n"
            "- Refresh (F5): Update the transactions list\n\n"
            "Notes:\n"
            "- Be warned that it is possible to burn/erase non-token std stamps.\n"
            "- Selecting an output in the txn detail modal will either open the "
            "spending txn or the coin details. Selecting an input will open the "
            "witness details with the option to view coin details.\n"
            "- Once the TrustNet features are fully implemented, pruning of txns "
            "not associated with a local wallet/address will be a configurable "
            "policy (on by default).\n"
            "- Filter by date range and amount.\n\n"
            "Press 'Close' or Esc to continue."
        )

    def _get_stamps_content(self) -> tuple[str, str]:
        """Get Stamp Templates help content."""
        return (
            "Stamp Templates Help",
            "Manage stamp templates for creating tokens and NFTs.\n\n"
            "Actions:\n"
            "- Create Template (N): Design a new stamp\n"
            "- Edit Template (E): Modify an existing template\n"
            "- Delete Template (D): Remove a template\n"
            "- Refresh (R): Update the templates list\n\n"
            "See the project readme for documentation on the stamping system and "
            "the tapescript runtime used in validating coins/stamps.\n\n"
            "Press 'Close' or Esc to continue."
        )

    def _get_network_content(self) -> tuple[str, str]:
        """Get Network help content."""
        return (
            "Network Help",
            "NOTE: this screen is a placeholder for when full network functionality "
            "has been implemented, after which the following will apply.\n\n"
            "Configure peer connections and view network statistics.\n\n"
            "Manage connected peers and bootstrap nodes to join the network.\n\n"
            "View statistics on messages and data transferred.\n\n"
            "Press 'Close' or Esc to continue."
        )

    def _get_trustnet_content(self) -> tuple[str, str]:
        """Get TrustNet help content."""
        return (
            "TrustNet Help",
            "NOTE: the TrustNet features have not yet been fully implemented. "
            "This screen is a rough draft for part of the UI/UX once those features "
            "have been implemented.\n\n"
            "Manage TrustNet participation and consensus.\n\n"
            "TrustNets provide transaction attestations and UTXO snapshots.\n\n"
            "Press 'Close' or Esc to continue."
        )

    def _get_settings_content(self) -> tuple[str, str]:
        """Get Settings help content."""
        return (
            "Settings Help",
            "Configure application preferences and settings.\n\n"
            "- Select App Mode (currently only offline mode is actually available).\n"
            "- Create or activate a GameSet.\nRestore an automatic db backup.\n"
            "- Eventually, more settings like segmented cache size will be "
            "configurable here.\n\n"
            "Press 'Close' or Esc to continue."
        )
