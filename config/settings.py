"""读取并暴露环境配置。"""
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self, config_file=None):
        config_file = config_file or BASE_DIR / "config" / "config.yaml"
        with open(config_file, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

    def get(self, key, default=None):
        """用点号取嵌套值，如 get("front.username")。"""
        value = self._data
        for part in key.split("."):
            if not isinstance(value, dict):
                return default
            value = value.get(part)
            if value is None:
                return default
        return value


settings = Settings()
