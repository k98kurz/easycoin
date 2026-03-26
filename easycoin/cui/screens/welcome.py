from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static


class WelcomeScreen(ModalScreen):
    """Welcome screen with a simple message to help new users get started."""

    BINDINGS = [
        ("escape", "dismiss", "Dismiss"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose welcome screen layout."""
        with Vertical(classes="modal-container w-70p"):
            yield Static("Welcome to EasyCoin", classes="modal-title")
            yield Static(
                "This is the Console User Interface (CUI) for EasyCoin.\n\n"
                "EasyCoin is all fun and games. It even has a bona-fide "
                "Proof-of-Concept consensus system that won't be found "
                "in any serious scamchain project.\n\n"
                "The two purposes of this project are 1) to provide a fun "
                "way to make cryptographic puzzle games and 2) to parody "
                "all the projects that came before.\n\n"
                "The mental model is that anyone can mine a coin denominated "
                "in EC⁻¹ (inverse Energy Credits -- proof you burned some "
                "electricity crunching numbers), and then they can stamp it "
                "with some data, kind of like those novelty machines where "
                "you put in a penny and crank the handle to flatten it and "
                "impress an image. Standard Stamp covenants include fungible "
                "series (analogous to tokens) and non-fungible Stamps (kind of "
                "like NFTs but without any guarantee of total uniqueness -- just "
                "that the data itself cannot be split or joined).\n\n"
                "Instead of a blockchain with every transaction ever, EasyCoin "
                "instead tracks input and output coin ids; transactions and the "
                "coins themselves are only of use to the parties involved and the "
                "holders, respectively -- if you want to send a jpeg to someone, "
                "feel free, but not everyone on the network is interested.\n\n"
                "When you join a TrustNet, the trusted nodes create attestations "
                "for transactions and occasional snapshots of the UTXO set. "
                "@todo write more about this here\n\n"
                "Press 'Dismiss' or Esc to begin exploring the app. I recommend "
                "starting with creating a wallet and then configuring a "
                "TrustNet. Have fun!",
                classes="m-1",
            )
            with Horizontal(id="modal_actions"):
                yield Button("Dismiss", id="btn_dismiss", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "btn_dismiss":
            self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()
