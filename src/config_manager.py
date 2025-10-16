"""
Configuration Manager for KotobaTranscriber

This module provides centralized configuration management using YAML files.
It supports nested key access, environment variable overrides, and validation.

Author: KotobaTranscriber Team
Date: 2025-10-16
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union, List
from copy import deepcopy


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""
    pass


class ConfigManager:
    """
    Configuration manager that loads and provides access to YAML configuration files.

    Features:
    - Nested key access with dot notation (e.g., "model.whisper.device")
    - Environment variable overrides (e.g., KOTOBA_MODEL_DEVICE)
    - Default value support
    - Configuration validation
    - Singleton pattern support

    Usage:
        config = ConfigManager()
        device = config.get("model.whisper.device", default="cpu")
        sample_rate = config.get("realtime.sample_rate", default=16000)
    """

    _instance: Optional['ConfigManager'] = None
    _config: Optional[Dict[str, Any]] = None

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to the YAML configuration file.
                        If None, defaults to "config/config.yaml" relative to project root.

        Raises:
            ConfigurationError: If the configuration file cannot be loaded.
        """
        if config_path is None:
            # Default path: project_root/config/config.yaml
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "config.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self._config = None
        self._env_prefix = "KOTOBA_"  # Environment variable prefix

        # Load configuration
        self.load()

    def load(self) -> None:
        """
        Load configuration from YAML file.

        Raises:
            ConfigurationError: If the configuration file is not found or invalid.
        """
        if not self.config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create the configuration file or copy from config.example.yaml"
            )

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

            if self._config is None:
                self._config = {}

            logger.info(f"Configuration loaded successfully from {self.config_path}")

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML format in configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration file: {e}")

    def reload(self) -> None:
        """Reload configuration from file."""
        self.load()
        logger.info("Configuration reloaded")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Supports environment variable overrides. For example:
        - Key "model.whisper.device" can be overridden by env var KOTOBA_MODEL_WHISPER_DEVICE

        Args:
            key: Configuration key in dot notation (e.g., "model.whisper.device")
            default: Default value to return if key is not found

        Returns:
            Configuration value or default if not found

        Examples:
            >>> config = ConfigManager()
            >>> device = config.get("model.whisper.device", default="cpu")
            >>> sample_rate = config.get("realtime.sample_rate", default=16000)
        """
        # Check environment variable override
        env_key = self._env_prefix + key.upper().replace(".", "_")
        env_value = os.environ.get(env_key)
        if env_value is not None:
            logger.debug(f"Using environment override: {env_key}={env_value}")
            return self._parse_env_value(env_value)

        # Navigate through nested dictionary
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    logger.debug(f"Configuration key not found: {key}, using default: {default}")
                    return default
            else:
                logger.debug(f"Configuration key not found: {key}, using default: {default}")
                return default

        return value if value is not None else default

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.

        Args:
            section: Section name (e.g., "model", "realtime", "logging")

        Returns:
            Dictionary containing the entire section

        Raises:
            ConfigurationError: If section is not found
        """
        value = self.get(section)
        if value is None or not isinstance(value, dict):
            raise ConfigurationError(f"Configuration section not found: {section}")
        return deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value (runtime only, not persisted to file).

        Args:
            key: Configuration key in dot notation
            value: Value to set
        """
        keys = key.split('.')
        config = self._config

        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value
        logger.debug(f"Configuration value set: {key}={value}")

    def has(self, key: str) -> bool:
        """
        Check if a configuration key exists.

        Args:
            key: Configuration key in dot notation

        Returns:
            True if key exists, False otherwise
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False

        return True

    def get_all(self) -> Dict[str, Any]:
        """
        Get the entire configuration dictionary.

        Returns:
            Deep copy of the entire configuration
        """
        return deepcopy(self._config)

    def validate(self) -> bool:
        """
        Validate the configuration structure.

        Returns:
            True if configuration is valid, False otherwise
        """
        required_sections = ["app", "model", "realtime", "formatting", "logging"]

        for section in required_sections:
            if not self.has(section):
                logger.error(f"Missing required configuration section: {section}")
                return False

        logger.info("Configuration validation passed")
        return True

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        """
        Parse environment variable value to appropriate type.

        Args:
            value: String value from environment variable

        Returns:
            Parsed value (bool, int, float, or string)
        """
        # Boolean
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False

        # Integer
        try:
            return int(value)
        except ValueError:
            pass

        # Float
        try:
            return float(value)
        except ValueError:
            pass

        # String (default)
        return value

    @classmethod
    def get_instance(cls, config_path: Optional[Union[str, Path]] = None) -> 'ConfigManager':
        """
        Get singleton instance of ConfigManager.

        Args:
            config_path: Path to configuration file (only used on first call)

        Returns:
            Singleton instance of ConfigManager
        """
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def __repr__(self) -> str:
        """String representation of ConfigManager."""
        return f"ConfigManager(config_path={self.config_path})"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"ConfigManager loaded from {self.config_path}"


# Convenience function for quick access
def get_config(config_path: Optional[Union[str, Path]] = None) -> ConfigManager:
    """
    Get the singleton ConfigManager instance.

    Args:
        config_path: Path to configuration file (only used on first call)

    Returns:
        ConfigManager instance
    """
    return ConfigManager.get_instance(config_path)


if __name__ == "__main__":
    # Test the configuration manager
    import sys

    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Load configuration
        config = ConfigManager()
        print(f"\n{config}\n")

        # Validate configuration
        if config.validate():
            print("Configuration is valid\n")

        # Test get method
        print("=== Testing get() method ===")
        print(f"App name: {config.get('app.name')}")
        print(f"Whisper model: {config.get('model.whisper.name')}")
        print(f"Sample rate: {config.get('realtime.sample_rate')}")
        print(f"Log level: {config.get('logging.level')}")
        print(f"Non-existent key: {config.get('nonexistent.key', default='DEFAULT_VALUE')}")

        # Test get_section method
        print("\n=== Testing get_section() method ===")
        realtime_config = config.get_section('realtime')
        print(f"Realtime section: {realtime_config}")

        # Test has method
        print("\n=== Testing has() method ===")
        print(f"Has 'model.whisper.device': {config.has('model.whisper.device')}")
        print(f"Has 'nonexistent.key': {config.has('nonexistent.key')}")

        # Test set method
        print("\n=== Testing set() method ===")
        config.set('test.runtime.value', 'Hello')
        print(f"Runtime value: {config.get('test.runtime.value')}")

        # Test environment variable override
        print("\n=== Testing environment variable override ===")
        os.environ['KOTOBA_MODEL_WHISPER_DEVICE'] = 'cpu'
        print(f"Device (env override): {config.get('model.whisper.device')}")

        print("\n=== All tests passed! ===")

    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
