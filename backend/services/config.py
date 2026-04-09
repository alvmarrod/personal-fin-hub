import json
from pathlib import Path
from typing import Any


class Config:
    _instance = None
    _data: dict = None

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
        value = self._data
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
    def database_path(self) -> str:
        return self.get("database.path", "data/finhub.db")


config = Config()
