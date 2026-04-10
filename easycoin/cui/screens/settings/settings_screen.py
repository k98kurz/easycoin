from os import makedirs, path
from pathlib import Path
from shutil import copy2, move
from time import time
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ItemGrid, Vertical, VerticalScroll
from textual.widgets import (
    Button, Checkbox, Input, RadioSet, RadioButton, Static, TextArea
)
from .activate_gameset_modal import ActivateGameSetModal
from .create_gameset_modal import CreateGameSetModal
from ..base import BaseScreen
from easycoin.cui.widgets import FilePickerModal, ConfirmationModal


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

            with Horizontal(classes="h-17 my-1"):
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
                    yield Static("Game Set:", classes="config-label")
                    yield Static(
                        "Create or activate a Game Set to share game state.",
                        classes="mt-1 text-muted"
                    )
                    yield Static(
                        "Active Game Set:",
                        id="active_gameset_label",
                        classes="text-bold mt-1"
                    )
                    yield Static(
                        "None",
                        id="active_gameset_display",
                        classes="text-muted"
                    )
                    with Horizontal(classes="mt-1"):
                        yield Button(
                            "Create Game Set",
                            id="btn_create_gameset",
                            variant="default"
                        )
                        yield Button(
                            "Activate Game Set",
                            id="btn_activate_gameset",
                            variant="default"
                        )
                        yield Button(
                            "Deactivate",
                            id="btn_deactivate_gameset",
                            variant="warning",
                            classes="hidden"
                        )

            with Horizontal(classes="h-13 my-1"):
                with Vertical(classes="w-50p card"):
                    yield Static("Database Management:", classes="config-label")
                    yield Static(
                        "Restore from a database backup file.",
                        classes="mt-1 text-muted"
                    )
                    yield Button(
                        "Restore Database Backup",
                        id="btn_restore_db_backup",
                        variant="warning",
                        classes="mt-1"
                    )

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
        """Load current App Mode and Game Set on mount."""
        try:
            mode = self.app.config.get("app_mode")
            if mode == "multiplayer":
                self.query_one("#mode_multiplayer").value = True
            else:
                self.query_one("#mode_singleplayer").value = True
        except Exception as e:
            self.app.notify(f"Error loading settings: {e}", severity="error")

        self._load_active_gameset()

        self.app.config.subscribe(
            "set_active_game_set",
            self._on_active_game_set_set
        )
        self.app.config.subscribe(
            "unset_active_game_set",
            self._on_active_game_set_unset
        )

    def on_unmount(self) -> None:
        """Clean up config subscriptions on unmount."""
        self.app.config.unsubscribe(
            "set_active_game_set",
            self._on_active_game_set_set
        )
        self.app.config.unsubscribe(
            "unset_active_game_set",
            self._on_active_game_set_unset
        )

    def _load_active_gameset(self) -> None:
        """Load and display current active Game Set."""
        try:
            active_gameset = self.app.config.get("active_game_set")
            self._update_gameset_display(active_gameset)
        except Exception as e:
            self.app.log_event(f"Error loading Game Set: {e}", "ERROR")

    def _update_gameset_display(self, active_gameset: str | None) -> None:
        """Update Game Set display based on current value."""
        gameset_display = self.query_one("#active_gameset_display", Static)
        btn_activate = self.query_one("#btn_activate_gameset", Button)
        btn_deactivate = self.query_one("#btn_deactivate_gameset", Button)

        if active_gameset:
            gameset_display.update(active_gameset)
            btn_activate.add_class("hidden")
            btn_deactivate.remove_class("hidden")
        else:
            gameset_display.update("None")
            btn_activate.remove_class("hidden")
            btn_deactivate.add_class("hidden")

    def _on_active_game_set_set(self, gameset_hash: str) -> None:
        """Handle active_game_set config change."""
        self._update_gameset_display(gameset_hash)

    def _on_active_game_set_unset(self, value: None) -> None:
        """Handle active_game_set config unset."""
        self._update_gameset_display(None)

    @on(Button.Pressed, "#btn_create_gameset")
    def action_create_gameset(self) -> None:
        """Open Create Game Set modal."""
        self.app.push_screen(CreateGameSetModal())

    @on(Button.Pressed, "#btn_activate_gameset")
    def action_activate_gameset(self) -> None:
        """Open Activate Game Set modal."""
        active_gameset = self.app.config.get("active_game_set")
        self.app.push_screen(ActivateGameSetModal(active_gameset))

    @on(Button.Pressed, "#btn_deactivate_gameset")
    def action_deactivate_gameset(self) -> None:
        """Deactivate the current Game Set."""
        try:
            old_gameset = self.app.config.get("active_game_set")
            self.app.config.unset("active_game_set")
            self.app.config.save()
            self.app.notify("Game Set deactivated", severity="success")
            self.app.log_event(f"Game Set deactivated: {old_gameset}", "INFO")
        except Exception as e:
            self.app.notify(f"Failed to deactivate Game Set: {e}", severity="error")
            self.app.log_event(f"Deactivate Game Set error: {e}", "ERROR")

    def _confirm_restore_backup(self, backup_path: str) -> None:
        """Show confirmation modal before restoring database."""
        filename = path.basename(backup_path)
        message = (
            f"This will replace the current database with:\n\n"
            f"{filename}\n\n"
            f"The current database will be moved to old/replaced."
            f"{{timestamp}}.easycoin.db-backup.\n\n"
            f"This action cannot be undone."
        )

        self.app.push_screen(
            ConfirmationModal(
                title="Confirm Database Restore",
                message=message,
                confirm_btn_text="Restore",
                confirm_btn_variant="warning"
            ),
            lambda confirmed: self._do_restore_backup(backup_path) if confirmed else None
        )

    def _do_restore_backup(self, backup_path: str) -> None:
        """Perform the database restore operation."""
        try:
            db_path = self.app.config.get_db_path()
            db_dir = path.dirname(db_path)
            old_dir = path.join(db_dir, "old")
            timestamp = int(time())
            archive_path = path.join(old_dir, f"replaced.{timestamp}.easycoin.db-backup")

            makedirs(old_dir, exist_ok=True)
            move(db_path, archive_path)
            copy2(backup_path, db_path)

            self.app.notify("Database restored successfully", severity="success")
            self.app.log_event(
                f"Database restored from {backup_path}, "
                f"archived to {archive_path}",
                "INFO"
            )
        except FileNotFoundError as e:
            self.app.notify(f"File not found: {e}", severity="error")
            self.app.log_event(f"Restore failed (FileNotFoundError): {e}", "ERROR")
        except PermissionError as e:
            self.app.notify(f"Permission denied: {e}", severity="error")
            self.app.log_event(f"Restore failed (PermissionError): {e}", "ERROR")
        except Exception as e:
            self.app.notify(f"Failed to restore database: {e}", severity="error")
            self.app.log_event(f"Restore failed: {e}", "ERROR")

    @on(Button.Pressed, "#btn_restore_db_backup")
    def action_restore_database_backup(self) -> None:
        """Open file picker to select database backup."""
        filter_func = lambda p: p.suffix.lower() == '.db-backup'

        def on_file_selected(filepath: Path | None) -> None:
            if not filepath:
                return
            self._confirm_restore_backup(str(filepath))

        db_path = self.app.config.get_db_path()
        db_dir = path.dirname(db_path)

        self.app.push_screen(
            FilePickerModal(
                title="Select Database Backup File",
                filter_callback=filter_func,
                starting_path=db_dir
            ),
            on_file_selected
        )
