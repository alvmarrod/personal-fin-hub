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
    def market_api_rate_sync_hour_utc(self) -> int | None:
        """Hour of day (UTC) for the scheduled FX rate sync; ``None`` disables it."""
        value = self.get("market_api.rate_sync_hour_utc", 1)
        if value is None:
            return None
        return int(value)

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
    def macro_sync_hours_utc(self) -> list[int]:
        """UTC hours the scheduled macro sync fires; empty list disables it."""
        return list(self.get("macro.sync_hours_utc", [3, 15]))

    @property
    def macro_sync_freshness_hours(self) -> float:
        """Skip a series whose last successful fetch is newer than this."""
        return float(self.get("macro.sync_freshness_hours", 12))

    @property
    def macro_sync_pace_seconds(self) -> float:
        """Pause between series requests during a macro sync."""
        return float(self.get("macro.sync_pace_seconds", 1))

    @property
    def macro_timeout(self) -> int:
        """Per-request timeout (seconds) for macro providers."""
        return int(self.get("macro.timeout", 30))

    @property
    def derived_trend_deadband(self) -> float:
        """Deadband for derived trend direction (a real change above float noise)."""
        return float(self.get("derived.trend_deadband", 0.0))

    @property
    def market_cycle_initial_state(self) -> int:
        """State the engine replay starts from (1..6)."""
        return int(self.get("market_cycle.initial_state", 1))

    @property
    def market_cycle_real_rate_high(self) -> float:
        return float(self.get("market_cycle.real_rate_thresholds.high", 1.0))

    @property
    def market_cycle_real_rate_low(self) -> float:
        return float(self.get("market_cycle.real_rate_thresholds.low", 0.25))

    @property
    def market_cycle_persistence(self) -> dict[str, int]:
        """Consecutive months required for emerging / near / triggered."""
        raw = self.get("market_cycle.persistence_months", {"emerging": 1, "near": 2, "triggered": 3})
        return {key: int(value) for key, value in raw.items()}

    @property
    def market_cycle_hikes_resumed_lookback_months(self) -> int:
        return int(self.get("market_cycle.hikes_resumed_lookback_months", 6))

    @property
    def market_cycle_reverse_edges_enabled(self) -> dict[str, bool]:
        raw = self.get(
            "market_cycle.reverse_edges_enabled",
            {"6->2": True, "5->4": True, "4->3": True, "3->2": True},
        )
        return {key: bool(value) for key, value in raw.items()}

    @property
    def market_cycle_priority(self) -> dict[str, int]:
        raw = self.get("market_cycle.priority", {})
        return {key: int(value) for key, value in raw.items()}

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
