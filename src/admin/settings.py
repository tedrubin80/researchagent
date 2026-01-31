"""Settings persistence for the admin panel."""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default settings file location
DEFAULT_SETTINGS_PATH = Path("/var/www/feedresearch/data/settings.json")


@dataclass
class OllamaSettings:
    """Ollama configuration settings."""
    enabled: bool = False
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.1"


@dataclass
class PrioritySettings:
    """Provider priority configuration for a skill."""
    primary: str
    fallbacks: list[str] = field(default_factory=list)


@dataclass
class Settings:
    """All admin settings."""
    priorities: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "synthesis": {"primary": "claude", "fallbacks": ["ollama"]},
        "document-analysis": {"primary": "claude", "fallbacks": ["ollama", "gemini"]},
        "web-search": {"primary": "perplexity", "fallbacks": []},
        "cross-validate": {"primary": "gemini", "fallbacks": ["claude", "ollama"]},
        "general-query": {"primary": "claude", "fallbacks": ["ollama"]},
    })
    ollama: dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.1"
    })
    admin_password_hash: Optional[str] = None
    session_timeout_hours: int = 24

    def get_ollama_settings(self) -> OllamaSettings:
        """Get Ollama settings as typed object."""
        return OllamaSettings(**self.ollama)

    def set_ollama_settings(self, settings: OllamaSettings) -> None:
        """Set Ollama settings from typed object."""
        self.ollama = {
            "enabled": settings.enabled,
            "base_url": settings.base_url,
            "model": settings.model
        }


class SettingsManager:
    """Manages persistence of admin settings.

    Features:
    - JSON file storage
    - Automatic file creation
    - Settings validation
    """

    def __init__(self, settings_path: Optional[Path] = None):
        self._path = settings_path or DEFAULT_SETTINGS_PATH
        self._settings: Optional[Settings] = None

    @property
    def path(self) -> Path:
        """Get settings file path."""
        return self._path

    def load(self) -> Settings:
        """Load settings from file.

        Creates default settings if file doesn't exist.

        Returns:
            Loaded or default Settings object
        """
        if not self._path.exists():
            logger.info(f"Settings file not found, creating default: {self._path}")
            self._settings = Settings()
            self.save()
            return self._settings

        try:
            with open(self._path, 'r') as f:
                data = json.load(f)

            self._settings = Settings(
                priorities=data.get("priorities", Settings().priorities),
                ollama=data.get("ollama", Settings().ollama),
                admin_password_hash=data.get("admin_password_hash"),
                session_timeout_hours=data.get("session_timeout_hours", 24)
            )
            logger.info(f"Settings loaded from {self._path}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
            self._settings = Settings()

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self._settings = Settings()

        return self._settings

    def save(self) -> bool:
        """Save current settings to file.

        Returns:
            True if save was successful
        """
        if self._settings is None:
            self._settings = Settings()

        try:
            # Ensure directory exists
            self._path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "priorities": self._settings.priorities,
                "ollama": self._settings.ollama,
                "admin_password_hash": self._settings.admin_password_hash,
                "session_timeout_hours": self._settings.session_timeout_hours
            }

            with open(self._path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Settings saved to {self._path}")
            return True

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def get_settings(self) -> Settings:
        """Get current settings (loads from file if needed)."""
        if self._settings is None:
            return self.load()
        return self._settings

    def update_settings(self, **kwargs) -> bool:
        """Update specific settings fields.

        Args:
            **kwargs: Fields to update

        Returns:
            True if update and save were successful
        """
        settings = self.get_settings()

        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
            else:
                logger.warning(f"Unknown setting: {key}")

        return self.save()

    # Convenience methods for common operations

    def get_priorities(self) -> dict[str, dict[str, Any]]:
        """Get provider priorities."""
        return self.get_settings().priorities

    def set_priorities(self, priorities: dict[str, dict[str, Any]]) -> bool:
        """Set provider priorities."""
        return self.update_settings(priorities=priorities)

    def update_priority(
        self,
        skill_id: str,
        primary: str,
        fallbacks: Optional[list[str]] = None
    ) -> bool:
        """Update priority for a single skill."""
        priorities = self.get_priorities().copy()
        priorities[skill_id] = {
            "primary": primary,
            "fallbacks": fallbacks or []
        }
        return self.set_priorities(priorities)

    def get_ollama_config(self) -> OllamaSettings:
        """Get Ollama configuration."""
        return self.get_settings().get_ollama_settings()

    def set_ollama_config(self, config: OllamaSettings) -> bool:
        """Set Ollama configuration."""
        settings = self.get_settings()
        settings.set_ollama_settings(config)
        return self.save()

    def is_ollama_enabled(self) -> bool:
        """Check if Ollama is enabled."""
        return self.get_ollama_config().enabled

    def get_password_hash(self) -> Optional[str]:
        """Get admin password hash."""
        return self.get_settings().admin_password_hash

    def set_password_hash(self, password_hash: str) -> bool:
        """Set admin password hash."""
        return self.update_settings(admin_password_hash=password_hash)

    def get_session_timeout(self) -> int:
        """Get session timeout in hours."""
        return self.get_settings().session_timeout_hours

    def set_session_timeout(self, hours: int) -> bool:
        """Set session timeout in hours."""
        if hours < 1:
            raise ValueError("Session timeout must be at least 1 hour")
        return self.update_settings(session_timeout_hours=hours)

    def export_settings(self) -> dict:
        """Export settings as dictionary (for API responses).

        Note: Excludes sensitive data like password hash.
        """
        settings = self.get_settings()
        return {
            "priorities": settings.priorities,
            "ollama": settings.ollama,
            "session_timeout_hours": settings.session_timeout_hours
        }
