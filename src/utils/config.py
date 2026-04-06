"""
Configuration management.

Handles loading, saving, and accessing application settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..scraper.models import SettingsModel


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: Path | None = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to config file. Defaults to config.json in project root.
        """
        self.config_path = config_path or Path("config.json")
        self._settings: SettingsModel | None = None

    def load(self) -> SettingsModel:
        """Load settings from config file."""
        if self._settings is not None:
            return self._settings

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._settings = SettingsModel(**data)
            except Exception:
                self._settings = SettingsModel()
        else:
            self._settings = SettingsModel()

        return self._settings

    def save(self, settings: SettingsModel | None = None) -> None:
        """Save settings to config file."""
        if settings:
            self._settings = settings

        if self._settings:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings.model_dump(), f, indent=2)

    @property
    def settings(self) -> SettingsModel:
        """Get current settings, loading if necessary."""
        if self._settings is None:
            self._settings = self.load()
        return self._settings

    def update(self, **kwargs: Any) -> SettingsModel:
        """Update specific settings."""
        current = self.settings.model_dump()
        current.update(kwargs)
        self._settings = SettingsModel(**current)
        self.save()
        return self._settings

    def get_download_folder(self) -> Path:
        """Get the download folder path, creating if necessary."""
        folder = Path(self.settings.download_folder)
        folder.mkdir(parents=True, exist_ok=True)
        return folder


# Global config instance
config = ConfigManager()