import json
from pathlib import Path
from typing import Any


class Config:
    _instance = None
    _data: dict[str, Any] | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._data is None:
            self._load()

    def _load(self):
        config_path = Path(__file__).parent.parent / "config.json"
        self._data = json.loads(config_path.read_text())

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value: Any = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def market_api_base_url(self) -> str:
        return self.get("market_api.base_url", "http://localhost:5001")

    @property
    def market_api_timeout(self) -> int:
        return self.get("market_api.timeout", 30)

    @property
    def market_api_retry_attempts(self) -> int:
        return int(self.get("market_api.retry_attempts", 3))

    @property
    def market_api_retry_base_delay(self) -> float:
        return float(self.get("market_api.retry_base_delay", 0.5))

    @property
    def market_api_retry_max_delay(self) -> float:
        return float(self.get("market_api.retry_max_delay", 10))

    @property
    def market_api_circuit_failure_threshold(self) -> int:
        return int(self.get("market_api.circuit_failure_threshold", 5))

    @property
    def market_api_circuit_cooldown_seconds(self) -> float:
        return float(self.get("market_api.circuit_cooldown_seconds", 60))

    @property
    def market_api_sync_cron_hours(self) -> list[int]:
        return list(self.get("market_api.sync_cron_hours", [0, 12]))

    @property
    def market_api_sync_cron_pace_seconds(self) -> float:
        return float(self.get("market_api.sync_cron_pace_seconds", 5))

    @property
    def market_api_sync_interactive_pace_seconds(self) -> float:
        return float(self.get("market_api.sync_interactive_pace_seconds", 2))

    @property
    def market_api_sync_freshness_hours(self) -> float:
        return float(self.get("market_api.sync_freshness_hours", 1))

    @property
    def database_path(self) -> str:
        return self.get("database.path", "data/finhub.db")

    @property
    def update_check_enabled(self) -> bool:
        return bool(self.get("update_check.enabled", True))

    @property
    def update_check_repo(self) -> str:
        return self.get("update_check.repo", "alvmarrod/personal-fin-hub")

    @property
    def update_check_cache_seconds(self) -> int:
        return int(self.get("update_check.cache_seconds", 3600))

    @property
    def update_check_timeout(self) -> float:
        return float(self.get("update_check.timeout", 5))


config = Config()
