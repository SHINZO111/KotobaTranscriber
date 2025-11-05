"""
Configuration manager for KotobaTranscriber.
Loads and manages YAML configuration files.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """Configuration manager for loading and accessing YAML configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to config file. If None, uses default config/config.yaml
        """
        if config_path is None:
            # Default to config/config.yaml in project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "config.yaml"

        self.config_path = Path(config_path)
        self._config = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            # Create default config if it doesn't exist
            self._create_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            self._config = {}

    def _create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            'app': {
                'name': 'KotobaTranscriber',
                'version': '2.1.0',
                'skip_permissions': False
            },
            'paths': {
                'ffmpeg': '',
                'model_cache': 'models'
            },
            'whisper': {
                'model': 'medium',
                'device': 'auto',
                'compute_type': 'int8'
            },
            'output': {
                'format': 'txt',
                'encoding': 'utf-8'
            }
        }

        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
            self._config = default_config
        except Exception as e:
            print(f"Warning: Failed to create default config: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-separated key path.

        Args:
            key_path: Dot-separated path (e.g., 'app.name', 'whisper.model')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Examples:
            >>> config = ConfigManager()
            >>> config.get('app.name')
            'KotobaTranscriber'
            >>> config.get('whisper.model')
            'medium'
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any):
        """
        Set a configuration value by dot-separated key path.

        Args:
            key_path: Dot-separated path (e.g., 'app.skip_permissions')
            value: Value to set
        """
        keys = key_path.split('.')
        config = self._config

        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the final value
        config[keys[-1]] = value

    def save(self):
        """Save current configuration to file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")


# Global configuration instance
_global_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """
    Get the global configuration instance.

    Returns:
        Global ConfigManager instance
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
    return _global_config


def initialize_config(config_path: Optional[str] = None):
    """
    Initialize the global configuration with a specific path.

    Args:
        config_path: Path to config file
    """
    global _global_config
    _global_config = ConfigManager(config_path)
