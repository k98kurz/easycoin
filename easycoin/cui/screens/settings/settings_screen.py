from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ItemGrid, Vertical, VerticalScroll
from textual.widgets import (
    Button, Checkbox, Input, RadioSet, RadioButton, Static, TextArea
)
from ..base import BaseScreen


class SettingsScreen(BaseScreen):
    """Settings screen for application configuration."""

    TAB_ID = "tab_settings"

    def compose(self) -> ComposeResult:
        """Compose settings layout."""
        yield from super().compose()

    def _compose_content(self) -> ComposeResult:
        """Compose settings content with grid layout."""
        with VerticalScroll(id="settings_screen"):
            yield Static("Settings", classes="panel-title")

            with Horizontal(classes="h-15 my-1"):
                with Vertical(classes="w-50p card"):
                    yield Static("App Mode:", classes="config-label")
                    yield Static(
                        "Select between multiplayer (network) mode and "
                        "singleplayer (offline) mode.",
                        classes="mt-1 text-muted"
                    )
                    yield RadioSet(
                        RadioButton("Normal/Multiplayer", id="mode_multiplayer"),
                        RadioButton("Offline/Singleplayer", id="mode_singleplayer"),
                        id="app_mode",
                        classes="h-6 mt-1",
                    )
                with Vertical(classes="w-50p card"):
                    yield Static("Placeholder for next setting:", classes="config-label")

            with Horizontal(id="settings_actions", classes="h-min-4 mt-1"):
                yield Button("Save", id="btn_save", variant="success")

    @on(Button.Pressed, "#btn_save")
    def action_save(self, event: Button.Pressed) -> None:
        """Handle save button press - save only the real setting."""
        try:
            mode_radio = self.query_one("#app_mode", RadioSet)
            if mode_radio.pressed_index == 0:
                mode = "multiplayer"
            else:
                mode = "singleplayer"
            self.app.config.set("app_mode", mode)
            self.app.config.save()
            self.app.notify("App Mode saved (dummy settings ignored)", severity="success")
        except Exception as e:
            self.app.notify(f"Error saving: {e}", severity="error")

    def on_mount(self) -> None:
        """Load current App Mode on mount."""
        try:
            mode = self.app.config.get("app_mode")
            if mode == "multiplayer":
                self.query_one("#mode_multiplayer").value = True
            else:
                self.query_one("#mode_singleplayer").value = True
        except Exception as e:
            self.app.notify(f"Error loading settings: {e}", severity="error")
