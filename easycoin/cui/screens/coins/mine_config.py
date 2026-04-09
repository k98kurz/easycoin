from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, RadioButton, RadioSet, Static, Footer
from easycoin.config import ConfigManager


class MiningConfigurationModal(ModalScreen):
    """Modal for configuring mining settings."""

    BINDINGS = [
        Binding("escape", "close", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose mining configuration layout."""
        with Vertical(id="mine_config", classes="modal-container w-50p"):
            yield Static("Mining Configuration", classes="modal-title")

            with Horizontal(classes="h-8 my-1"):
                with Vertical(classes="w-50p"):
                    yield Static("Mining Mode:", classes="config-label")
                    yield RadioSet(
                        RadioButton("Auto Top-up", id="mode_auto_topup"),
                        RadioButton("Continuous", id="mode_continuous"),
                        RadioButton("Off", id="mode_off"),
                        id="mining_mode",
                        classes="h-6 mt-1",
                    )
                with Vertical(id="auto_topup_section", classes="w-50p"):
                    yield Static("Auto Top-up Goal:", classes="config-label")
                    yield RadioSet(
                        RadioButton("1B EC⁻¹", id="goal_1b"),
                        RadioButton("100M EC⁻¹", id="goal_100m"),
                        RadioButton("10M EC⁻¹", id="goal_10m"),
                        RadioButton("1M EC⁻¹", id="goal_1m"),
                        id="auto_topup_goal",
                        classes="h-6 mt-1",
                    )

            with Horizontal(classes="h-8 my-1"):
                with Vertical(classes="w-50p"):
                    yield Static("Coin Size:", classes="config-label")
                    yield RadioSet(
                        RadioButton("1M EC⁻¹", id="size_1m"),
                        RadioButton("500K EC⁻¹", id="size_500k"),
                        RadioButton("100K EC⁻¹", id="size_100k"),
                        id="coin_size",
                        classes="h-6 mt-1",
                    )

                with Vertical(classes="w-50p"):
                    yield Static("Mining Processes:", classes="config-label")
                    yield RadioSet(
                        RadioButton("1", id="proc_1"),
                        RadioButton("2", id="proc_2"),
                        RadioButton("4", id="proc_4"),
                        RadioButton("8", id="proc_8"),
                        id="mining_processes",
                        classes="h-6 mt-1",
                    )

            with Horizontal(id="modal_actions"):
                yield Button("Save", id="btn_save", variant="success")
                yield Button("Cancel", id="btn_cancel", variant="default")

        yield Footer()

    def on_mount(self) -> None:
        """Load current configuration into form fields."""
        config = self.app.config

        mode = config.get("mining_mode")
        if mode == "auto_topup":
            self.query_one("#mode_auto_topup").value = True
        elif mode == "continuous":
            self.query_one("#mode_continuous").value = True
        else:
            self.query_one("#mode_off").value = True

        goal = config.get("auto_topup_goal")
        if goal == 1_000_000_000:
            self.query_one("#goal_1b").value = True
        elif goal == 100_000_000:
            self.query_one("#goal_100m").value = True
        elif goal == 10_000_000:
            self.query_one("#goal_10m").value = True
        else:
            self.query_one("#goal_1m").value = True

        coin_size = config.get("coin_size")
        if coin_size == 1_000_000:
            self.query_one("#size_1m").value = True
        elif coin_size == 500_000:
            self.query_one("#size_500k").value = True
        else:
            self.query_one("#size_100k").value = True

        processes = config.get("mining_processes")
        if processes == 1:
            self.query_one("#proc_1").value = True
        elif processes == 2:
            self.query_one("#proc_2").value = True
        elif processes == 8:
            self.query_one("#proc_8").value = True
        else:
            self.query_one("#proc_4").value = True

        self._update_auto_topup_visibility()

    @on(RadioSet.Changed, "#mining_mode")
    def _update_auto_topup_visibility(self) -> None:
        """Show/hide auto top-up goal section."""
        mode_radio = self.query_one("#mining_mode")
        auto_topup_section = self.query_one("#auto_topup_section")

        is_auto_topup = mode_radio.pressed_index == 0

        if is_auto_topup:
            auto_topup_section.remove_class("hidden")
        else:
            auto_topup_section.add_class("hidden")

    @on(Button.Pressed, "#btn_cancel")
    def action_close(self, event: Button.Pressed = None) -> None:
        """Handle cancel button click."""
        self.dismiss()

    @on(Button.Pressed, "#btn_save")
    def action_save(self, event: Button.Pressed = None) -> None:
        """Save configuration and update mining settings."""
        config = self.app.config

        mode_radio = self.query_one("#mining_mode")
        if mode_radio.pressed_index == 0:
            mode = "auto_topup"
        elif mode_radio.pressed_index == 1:
            mode = "continuous"
        else:
            mode = "off"

        goal_radio = self.query_one("#auto_topup_goal")
        goal_map = {
            0: 1_000_000_000,
            1: 100_000_000,
            2: 10_000_000,
            3: 1_000_000
        }
        goal = goal_map.get(goal_radio.pressed_index, 1_000_000)

        size_radio = self.query_one("#coin_size")
        size_map = {
            0: 1_000_000,
            1: 500_000,
            2: 100_000
        }
        size = size_map.get(size_radio.pressed_index, 500_000)

        proc_radio = self.query_one("#mining_processes")
        proc_map = {
            0: 1,
            1: 2,
            2: 4,
            3: 8
        }
        processes = proc_map.get(proc_radio.pressed_index, 4)

        config.set("mining_mode", mode)
        config.set("auto_topup_goal", goal)
        config.set("coin_size", size)
        config.set("mining_processes", processes)
        config.save()

        self.app.log_event(
            f"Mining config: {mode}, processes={processes}, size={size}",
            "INFO"
        )

        self.dismiss()

    async def action_quit(self) -> None:
        await self.app.action_quit()
