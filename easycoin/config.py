from enum import Enum
from crossconfig import get_config
from easycoin.cryptoworker import set_mining_pool_size


class MiningMode(Enum):
    AUTO_TOPUP = "auto_topup"
    CONTINUOUS = "continuous"
    OFF = "off"


class ConfigManager:
    def __init__(self, app_name: str = "easycoin"):
        self.app_name = app_name
        self.config = get_config(app_name)

    def load(self) -> None:
        self.config.load()

    def save(self) -> None:
        self.config.save()

    def path(self, file_or_subdir: str | list[str] | None = None) -> str:
        return self.config.path(file_or_subdir)

    def get_db_path(self) -> str:
        return self.config.path("easycoin.db")

    def get_log_path(self) -> str:
        return self.config.path("easycoin.log")

    def get_mining_mode(self) -> MiningMode:
        mode = self.config.get("mining_mode", MiningMode.AUTO_TOPUP.value)
        return MiningMode(mode)

    def set_mining_mode(self, mode: MiningMode) -> None:
        self.config.set("mining_mode", mode.value)

    def get_mining_processes(self) -> int:
        value = self.config.get("mining_processes", 4)
        if isinstance(value, (int, float)):
            return int(value)
        return 4

    def set_mining_processes(self, count: int) -> None:
        valid_counts = [1, 2, 4, 8]
        if count not in valid_counts:
            raise ValueError(
                f"Invalid mining processes: {count}. Must be one of {valid_counts}"
            )
        self.config.set("mining_processes", count)
        set_mining_pool_size(count)

    def get_coin_size(self) -> int:
        value = self.config.get("coin_size", 500_000)
        if isinstance(value, (int, float)):
            return int(value)
        return 500_000

    def set_coin_size(self, size: int) -> None:
        valid_sizes = [100_000, 500_000, 1_000_000]
        if size not in valid_sizes:
            raise ValueError(
                f"Invalid coin size: {size}. Must be one of {valid_sizes}"
            )
        self.config.set("coin_size", size)

    def get_auto_topup_goal(self) -> int:
        value = self.config.get("auto_topup_goal", 1_000_000)
        if isinstance(value, (int, float)):
            return int(value)
        return 1_000_000

    def set_auto_topup_goal(self, goal: int) -> None:
        valid_goals = [1_000_000, 10_000_000, 100_000_000, 1_000_000_000]
        if goal not in valid_goals:
            raise ValueError(
                f"Invalid auto top-up goal: {goal}. Must be one of {valid_goals}"
            )
        self.config.set("auto_topup_goal", goal)

    def get_bootstrap_nodes(self) -> list[str]:
        nodes = self.config.get("bootstrap_nodes", "")
        if isinstance(nodes, str):
            return [n.strip() for n in nodes.split(",") if n.strip()]
        return []

    def set_bootstrap_nodes(self, nodes: list[str]) -> None:
        self.config.set("bootstrap_nodes", ",".join(nodes))

    def get_network_port(self) -> int:
        value = self.config.get("network_port", 9888)
        if isinstance(value, (int, float)):
            return int(value)
        return 9888

    def set_network_port(self, port: int) -> None:
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ValueError(
                f"Invalid network port: {port}. Must be an integer between 1 "
                "and 65535"
            )
        self.config.set("network_port", port)

    def get_current_wallet_id(self) -> str | None:
        value = self.config.get("current_wallet_id")
        if isinstance(value, str):
            return value
        return None

    def set_current_wallet_id(self, wallet_id: str) -> None:
        self.config.set("current_wallet_id", wallet_id)

    def get_active_trustnet_id(self) -> str | None:
        value = self.config.get("active_trustnet_id")
        if isinstance(value, str):
            return value
        return None

    def set_active_trustnet_id(self, trustnet_id: str) -> None:
        self.config.set("active_trustnet_id", trustnet_id)

    def get_sidebar_visible(self) -> bool:
        """Get sidebar visibility preference. Returns `True` if visible,
            `False` if hidden.
        """
        value = self.config.get("sidebar_visible", False)
        if isinstance(value, bool):
            return value
        return False

    def set_sidebar_visible(self, visible: bool) -> None:
        """Set sidebar visibility preference. Args:
            visible: `True` for visible, `False` for hidden.
        """
        self.config.set("sidebar_visible", visible)
