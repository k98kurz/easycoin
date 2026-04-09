from crossconfig import get_config
from easycoin.cryptoworker import set_mining_pool_size


_mining_modes = ["auto_topup", "continuous", "off"]
_auto_topup_goals = [1_000_000, 10_000_000, 100_000_000, 1_000_000_000]
_coin_sizes = [100_000, 500_000, 1_000_000]
_app_modes = ["multiplayer", "singleplayer"]


_schema = {
    "mining_mode": {
        "validator": (
            lambda v: None
            if v in _mining_modes
            else ValueError(
                f"Invalid mining mode: {v}. Must be one of {_mining_modes}"
            )
        ),
        "default": "auto_topup",
    },
    "mining_processes": {
        "validator": (
            lambda v: set_mining_pool_size(v)
            if (v in [1, 2, 4, 8])
            else ValueError(
                f"Invalid mining processes: {v}. Must be one of [1, 2, 4, 8]"
            )
        ),
        "default": 4,
    },
    "coin_size": {
        "validator": (
            lambda v: None
            if v in _coin_sizes
            else ValueError(
                f"Invalid coin size: {v}. Must be one of {_coin_sizes}"
            )
        ),
        "default": 500_000,
    },
    "auto_topup_goal": {
        "validator": (
            lambda v: None
            if v in _auto_topup_goals
            else ValueError(
                f"Invalid auto top-up goal: {v}. Must be one of "
                f"{_auto_topup_goals}"
            )
        ),
        "default": 1_000_000,
    },
    "bootstrap_nodes": {
        "get": lambda v: [n.strip() for n in v.split(',') if n.strip()],
        "set": lambda v: ','.join([n.strip() for n in v if n.strip()]),
        "default": "",
    },
    "network_port": {
        "validator": (
            lambda v: None
            if 1 <= v <= 65535
            else ValueError(
                f"Invalid network port: {v}. Must be between 1 and 65535"
            )
        ),
        "default": 9888,
    },
    "app_mode": {
        "validator": (
            lambda v: None
            if v in _app_modes
            else ValueError(
                f"Invalid app mode: {v}. Must be one of {_app_modes}"
            )
        ),
        "default": "multiplayer",
    },
    "current_wallet_id": {
        "default": None,
    },
    "active_trustnet_id": {
        "default": None,
    },
    "sidebar_visible": {
        "default": False,
    },
    "welcome_shown": {
        "default": False,
    },
}

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

    def get(self, key: str, default = None) -> list|bool|str|int|float|None:
        if default is None and key in _schema and 'default' in _schema[key]:
            default = _schema[key]['default']
        if key in _schema and 'get' in _schema[key]:
            return _schema[key]['get'](
                self.config.get(key, default)
            )
        return self.config.get(key, default)

    def set(self, key: str, value: list|bool|str|int|float) -> ValueError|None:
        if key in _schema and 'validator' in _schema[key]:
            validation_error = _schema[key]['validator'](value)
            if validation_error is not None:
                return validation_error
        if key in _schema and 'set' in _schema[key]:
            value = _schema[key]['set'](value)
        self.config.set(key, value)

    def unset(self, key: str) -> None:
        self.config.unset(key)

    def get_db_path(self) -> str:
        return self.config.path("easycoin.db")

    def get_log_path(self) -> str:
        return self.config.path("easycoin.log")
