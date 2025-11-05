"""
Configuration Manager
Loads and manages application configuration from YAML files
"""

import yaml
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager that loads YAML config and provides dot-notation access"""

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration

        Args:
            config_file: Path to config YAML file (defaults to ../config/config.yaml)
        """
        if config_file is None:
            # Default to config/config.yaml in project root
            config_file = Path(__file__).parent.parent / "config" / "config.yaml"

        self.config_file = config_file
        self._config_data = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f) or {}
                logger.info(f"Configuration loaded from: {self.config_file}")
            else:
                logger.warning(f"Config file not found: {self.config_file}, using defaults")
                self._config_data = {}
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            self._config_data = {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation

        Args:
            key: Configuration key in dot notation (e.g., "model.whisper.name")
            default: Default value if key not found

        Returns:
            Configuration value or default

        Examples:
            >>> config.get("model.whisper.name")
            "kotoba-tech/kotoba-whisper-v2.2"
            >>> config.get("audio.ffmpeg.path")
            "C:\\ffmpeg\\ffmpeg-8.0-essentials_build\\bin"
        """
        keys = key.split('.')
        value = self._config_data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """
        Set configuration value using dot notation

        Args:
            key: Configuration key in dot notation
            value: Value to set
        """
        keys = key.split('.')
        config = self._config_data

        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value

    def reload(self):
        """Reload configuration from file"""
        self._load_config()

    def __repr__(self):
        return f"Config(file={self.config_file})"


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(config_file: Optional[Path] = None) -> Config:
    """
    Get the global configuration instance (singleton)

    Args:
        config_file: Optional path to config file (only used on first call)

    Returns:
        Config: Global configuration instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = Config(config_file)

    return _config_instance
