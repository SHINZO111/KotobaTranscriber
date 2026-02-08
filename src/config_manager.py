"""
設定マネージャー - KotobaTranscriber Configuration Manager

アプリケーション設定の読み込み、アクセス、管理を行うモジュール。
YAMLファイルからの設定読み込みとドット記法でのアクセスをサポート。
"""

import os
import copy
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ['get_config', 'ConfigManager', 'Config']


class Config:
    """
    設定値へのドット記法アクセスを提供するクラス

    Example:
        config = Config({"model": {"whisper": {"name": "kotoba"}}})
        name = config.get("model.whisper.name", default="default")
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """
        初期化

        Args:
            data: 設定データの辞書
        """
        self._data = data or {}
        self._data_lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得

        Args:
            key: ドット区切りのキー（例: "model.whisper.name"）
            default: キーが存在しない場合のデフォルト値

        Returns:
            設定値、またはデフォルト値
        """
        with self._data_lock:
            keys = key.split('.')
            value = self._data

            for k in keys:
                if isinstance(value, dict):
                    if k not in value:
                        return default
                    value = value[k]
                else:
                    return default
            return value

    def set(self, key: str, value: Any) -> None:
        """
        ドット記法で設定値を設定

        Args:
            key: ドット区切りのキー
            value: 設定する値
        """
        with self._data_lock:
            keys = key.split('.')
            data = self._data

            for k in keys[:-1]:
                if k not in data or not isinstance(data[k], dict):
                    data[k] = {}
                data = data[k]

            data[keys[-1]] = value

    def __getitem__(self, key: str) -> Any:
        """辞書形式でのアクセス"""
        return self.get(key)

    _MISSING = object()

    def __contains__(self, key: str) -> bool:
        """キーの存在チェック"""
        return self.get(key, default=self._MISSING) is not self._MISSING

    @property
    def data(self) -> Dict[str, Any]:
        """内部データのコピーを返す（外部からの書き換え防止）"""
        with self._data_lock:
            return copy.deepcopy(self._data)


class ConfigManager:
    """
    設定ファイルの読み込みと管理を行うシングルトンクラス
    """

    _instance: Optional['ConfigManager'] = None
    _config: Optional[Config] = None
    _init_lock = threading.Lock()

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            with self._init_lock:
                if self._config is None:
                    self._load_config()

    def _find_config_file(self) -> Optional[Path]:
        """設定ファイルを探す"""
        # 可能な設定ファイルの場所
        possible_paths = [
            Path(__file__).parent.parent / "config" / "config.yaml",
            Path(__file__).parent.parent / "config" / "config.yml",
            Path(__file__).parent / "config" / "config.yaml",
            Path.cwd() / "config" / "config.yaml",
            Path.cwd() / "config.yaml",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    def _load_config(self) -> None:
        """設定ファイルを読み込む"""
        config_path = self._find_config_file()

        if config_path is None:
            logger.warning("Config file not found, using defaults")
            self._config = Config(self._get_default_config())
            return

        # セキュリティ: ファイルサイズ制限 (10MB)
        MAX_CONFIG_SIZE = 10 * 1024 * 1024
        file_size = config_path.stat().st_size
        if file_size > MAX_CONFIG_SIZE:
            logger.error(f"Config file too large: {file_size} bytes (max: {MAX_CONFIG_SIZE})")
            self._config = Config(self._get_default_config())
            return

        try:
            # YAMLのインポート（オプショナル）
            try:
                import yaml
            except ImportError:
                logger.warning("PyYAML not installed, using defaults")
                self._config = Config(self._get_default_config())
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if data is None:
                data = {}

            # デフォルト値とマージ
            merged = self._merge_configs(self._get_default_config(), data)
            self._config = Config(merged)

            logger.info(f"Config loaded from: {config_path}")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = Config(self._get_default_config())

    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を返す"""
        return {
            "app": {
                "name": "KotobaTranscriber",
                "version": "2.2.0",
                "language": "ja"
            },
            "model": {
                "whisper": {
                    "name": "kotoba-tech/kotoba-whisper-v2.2",
                    "device": "auto",
                    "chunk_length_s": 15,
                    "language": "ja",
                    "task": "transcribe",
                    "return_timestamps": True
                },
                "faster_whisper": {
                    "model_size": "base",
                    "compute_type": "auto",
                    "beam_size": 5
                }
            },
            "audio": {
                "preprocessing": {
                    "enabled": False,
                    "noise_reduction": False,
                    "normalize": False,
                    "remove_silence": False
                },
                "ffmpeg": {
                    "path": r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin",
                    "auto_configure": True
                }
            },
            "vocabulary": {
                "enabled": False,
                "file": "custom_vocabulary.json"
            },
            "realtime": {
                "sample_rate": 16000,
                "buffer_duration": 3.0,
                "vad": {
                    "enabled": True,
                    "threshold": 0.01
                }
            },
            "formatting": {
                "remove_fillers": True,
                "add_punctuation": True,
                "format_paragraphs": True,
                "sentences_per_paragraph": 3
            },
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 1.0,
                "max_consecutive_errors": 5
            },
            "logging": {
                "level": "INFO",
                "format": "text",
                "file": "logs/app.log"
            },
            "performance": {
                "thread_pool_size": 4,
                "memory_limit_mb": 4096
            },
            "output": {
                "default_format": "txt",
                "save_directory": "results"
            },
            "export": {
                "default_formats": ["txt", "srt"],
                "merge_short_segments": True,
                "min_segment_duration": 1.0,
                "max_chars_per_segment": 40,
                "split_long_segments": True
            },
            "api": {
                "anthropic": {
                    "enabled": False,
                    "api_key": "",
                    "model": "claude-sonnet-4-5-20250929",
                    "temperature": 0.3,
                    "max_tokens": 4096
                },
                "openai": {
                    "enabled": False,
                    "api_key": "",
                    "model": "gpt-4",
                    "temperature": 0.3,
                    "max_tokens": 4096
                }
            },
            "batch": {
                "enhanced_mode": True,
                "enable_checkpoint": True,
                "checkpoint_interval": 10,
                "auto_adjust_workers": True,
                "max_workers": 4,
                "memory_limit_mb": 4096
            },
            "ui": {
                "dark_mode": False,
                "compact_mode": True,
                "show_realtime_tab": True,
                "show_export_options": True
            }
        }

    def _merge_configs(self, default: Dict, override: Dict) -> Dict:
        """2つの設定辞書を再帰的にマージ"""
        result = default.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    @property
    def config(self) -> Config:
        """設定オブジェクトを返す"""
        if self._config is None:
            self._load_config()
        return self._config

    def reload(self) -> None:
        """設定を再読み込み"""
        with self._init_lock:
            self._config = None
            self._load_config()


# グローバルな設定マネージャーインスタンス
_manager: Optional[ConfigManager] = None
_manager_lock = threading.Lock()


def get_config() -> Config:
    """
    設定オブジェクトを取得

    シングルトンパターンで、アプリケーション全体で同じ設定を共有。
    スレッドセーフな実装。

    Returns:
        Config: 設定オブジェクト

    Example:
        config = get_config()
        model_name = config.get("model.whisper.name", default="default")
    """
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ConfigManager()
    return _manager.config


# テスト用
if __name__ == "__main__":
    print("Testing ConfigManager...")

    config = get_config()

    # テスト: ドット記法でのアクセス
    print(f"App name: {config.get('app.name')}")
    print(f"Model name: {config.get('model.whisper.name')}")
    print(f"FFmpeg path: {config.get('audio.ffmpeg.path')}")
    print(f"Default value: {config.get('nonexistent.key', default='default_value')}")

    print("\nConfigManager test completed!")
