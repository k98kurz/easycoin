from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static, TextArea
from easycoin.cui.widgets import ECTextArea


class ReplTextArea(TextArea):
    """Custom TextArea that handles Enter, Ctrl+O, Ctrl+T/Alt+T for REPL input."""

    def on_key(self, event) -> None:
        """Handle key events for submission vs newline."""
        if event.key == "enter":
            event.prevent_default()
            self.screen.action_submit_code()
        elif event.key == "ctrl+o":
            event.prevent_default()
            self.insert("\n")
        elif event.key in ("ctrl+t", 'alt+t'):
            event.prevent_default()
            self.insert(" " * 4)


class ReplModal(Screen):
    """Modal for interactive Python code execution with access to app objects."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    CSS = """
        ReplModal {
            background: $background 50%;
        }

        #repl_output {
            height: 1fr;
            min-height: 20;
            border: solid $primary;
            padding: 1;
        }
    """

    _namespace: dict
    _history: list[str]
    _history_index: int

    def __init__(self):
        """Initialize REPL modal with persistent namespace."""
        super().__init__()
        if not hasattr(ReplModal, '_shared_namespace'):
            ReplModal._shared_namespace = {}
        if not hasattr(ReplModal, '_shared_history'):
            ReplModal._shared_history = []
        self._namespace = ReplModal._shared_namespace
        self._history = ReplModal._shared_history
        self._history_index = len(self._history)

    def compose(self) -> ComposeResult:
        """Compose REPL modal layout."""
        with VerticalScroll(id="repl_modal", classes="modal-container w-70p"):
            yield ECTextArea(
                id="repl_output", read_only=True, soft_wrap=True,
                show_line_numbers=False
            )

            yield Static(
                "Enter: execute. Ctrl+O: insert new line. Cltr+T or Alt+T: indent.",
                classes="mt-1"
            )

            with Vertical(classes="mt-1 h-min-3"):
                yield ReplTextArea(
                    id="repl_input", classes="mt-1",
                    placeholder="Enter Python code"
                )

            with Horizontal(id="modal_actions"):
                yield Button("Clear", id="btn_clear", variant="default")
                yield Button("Close", id="btn_close", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize REPL namespace and display welcome message."""
        self._update_namespace()
        output = self.query_one("#repl_output")
        output.text = (">>> EasyCoin Python REPL\nAccess: app, state, config, "
            "logger, wallet\n")
        output.scroll_end()
        self.query_one("#repl_input").focus()

    def _update_namespace(self) -> None:
        """Update namespace with current app objects."""
        self._namespace['app'] = self.app
        self._namespace['state'] = (
            self.app.state if hasattr(self.app, 'state') else None
        )
        self._namespace['config'] = (
            self.app.config if hasattr(self.app, 'config') else None
        )
        self._namespace['logger'] = (
            self.app.logger if hasattr(self.app, 'logger') else None
        )
        self._namespace['wallet'] = (
            self.app.wallet if hasattr(self.app, 'wallet') else None
        )

    def on_key(self, event) -> None:
        """Handle keyboard events."""
        if event.key == "escape":
            self.action_close()
            return

        input_widget = self.query_one("#repl_input")

        if event.key == "up":
            if self._history_index > 0:
                self._history_index -= 1
                input_widget.text = self._history[self._history_index]
            event.stop()
        elif event.key == "down":
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                input_widget.text = self._history[self._history_index]
            elif self._history_index == len(self._history) - 1:
                self._history_index = len(self._history)
                input_widget.text = ""
            event.stop()

    @on(Button.Pressed, "#btn_clear")
    def action_clear(self) -> None:
        """Clear the output display."""
        self.query_one("#repl_output").text = ""

    @on(Button.Pressed, "#btn_close")
    def action_close(self) -> None:
        """Close the REPL modal."""
        self.app.pop_screen()

    def action_submit_code(self) -> None:
        """Submit the code in the input area for execution."""
        input_widget = self.query_one("#repl_input")
        text = input_widget.text
        if text.strip():
            self._execute_code(text)
            input_widget.text = ""

    def _execute_code(self, code: str) -> None:
        """Execute Python code and display output/errors."""
        output = self.query_one("#repl_output")

        self._history.append(code)
        self._history_index = len(self._history)

        self._update_namespace()

        output.text += f">>> {code}\n"

        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                result = eval(code, self._namespace)

            captured_stdout = stdout_capture.getvalue()
            captured_stderr = stderr_capture.getvalue()

            if captured_stdout:
                output.text += captured_stdout
            if captured_stderr:
                output.text += captured_stderr
            if result is not None:
                output.text += f"{repr(result)}\n"

        except SyntaxError:
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, self._namespace)

                captured_stdout = stdout_capture.getvalue()
                captured_stderr = stderr_capture.getvalue()

                if captured_stdout:
                    output.text += captured_stdout
                if captured_stderr:
                    output.text += captured_stderr

            except Exception as e:
                output.text += f"Error: {type(e).__name__}: {e}\n"
                import traceback
                tb_lines = traceback.format_exc().splitlines()[1:]
                for line in tb_lines:
                    output.text += f"  {line}\n"

        except Exception as e:
            output.text += f"Error: {type(e).__name__}: {e}\n"
            import traceback
            tb_lines = traceback.format_exc().splitlines()[1:]
            for line in tb_lines:
                output.text += f"  {line}\n"

        output.scroll_end()
