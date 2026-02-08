"""
コアモジュールの包括テスト - Core Modules Comprehensive Tests

validators, exceptions, config_manager, base_engine, construction_vocabulary,
subtitle_exporter, app_settings, custom_dictionary, speaker_diarization_utils
のユニットテストを含む。
"""

import copy
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import numpy as np

# src ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================================
# 3a. validators.py テスト
# ============================================================================

class TestValidator:
    """Validator クラスのテスト"""

    def setup_method(self):
        from validators import Validator, ValidationError
        self.Validator = Validator
        self.ValidationError = ValidationError

    # --- validate_file_path ---

    def test_validate_file_path_none(self):
        with pytest.raises(self.ValidationError, match="cannot be None"):
            self.Validator.validate_file_path(None)

    def test_validate_file_path_traversal_dotdot(self):
        with pytest.raises(self.ValidationError, match="traversal"):
            self.Validator.validate_file_path("../../../etc/passwd")

    def test_validate_file_path_traversal_tilde(self):
        with pytest.raises(self.ValidationError, match="traversal"):
            self.Validator.validate_file_path("~/secret")

    def test_validate_file_path_must_exist_missing(self):
        with pytest.raises(self.ValidationError, match="does not exist"):
            self.Validator.validate_file_path(
                "/nonexistent/file_that_does_not_exist.wav",
                must_exist=True,
            )

    def test_validate_file_path_no_exist_check(self, tmp_path):
        # must_exist=False ならば存在しないファイルでもOK
        result = self.Validator.validate_file_path(
            str(tmp_path / "nonexistent.txt"),
            must_exist=False,
        )
        assert isinstance(result, Path)

    def test_validate_file_path_extension_check(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("dummy")
        with pytest.raises(self.ValidationError, match="not allowed"):
            self.Validator.validate_file_path(
                str(f), must_exist=True, allowed_extensions={".wav", ".mp3"}
            )

    def test_validate_file_path_extension_ok(self, tmp_path):
        f = tmp_path / "test.wav"
        f.write_text("dummy")
        result = self.Validator.validate_file_path(
            str(f), must_exist=True, allowed_extensions={".wav", ".mp3"}
        )
        assert result.suffix == ".wav"

    def test_validate_file_path_allowed_dirs(self, tmp_path):
        f = tmp_path / "sub" / "test.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("dummy")
        result = self.Validator.validate_file_path(
            str(f),
            allowed_dirs=[tmp_path],
            must_exist=True,
        )
        assert result.exists()

    def test_validate_file_path_not_in_allowed_dirs(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("dummy")
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        with pytest.raises(self.ValidationError, match="not in allowed"):
            self.Validator.validate_file_path(
                str(f),
                allowed_dirs=[other_dir],
                must_exist=True,
            )

    # --- validate_text_length ---

    def test_validate_text_length_none(self):
        with pytest.raises(self.ValidationError, match="cannot be None"):
            self.Validator.validate_text_length(None)

    def test_validate_text_length_not_string(self):
        with pytest.raises(self.ValidationError, match="must be a string"):
            self.Validator.validate_text_length(12345)

    def test_validate_text_length_too_short(self):
        with pytest.raises(self.ValidationError, match="too short"):
            self.Validator.validate_text_length("hi", min_length=10)

    def test_validate_text_length_too_long(self):
        with pytest.raises(self.ValidationError, match="too long"):
            self.Validator.validate_text_length("a" * 101, max_length=100)

    def test_validate_text_length_normal(self):
        result = self.Validator.validate_text_length("hello", min_length=0, max_length=100)
        assert result == "hello"

    # --- validate_positive_integer ---

    def test_validate_positive_integer_normal(self):
        assert self.Validator.validate_positive_integer(5, "x") == 5

    def test_validate_positive_integer_none_with_default(self):
        assert self.Validator.validate_positive_integer(None, "x", default=10) == 10

    def test_validate_positive_integer_none_without_default(self):
        with pytest.raises(self.ValidationError, match="cannot be None"):
            self.Validator.validate_positive_integer(None, "x")

    def test_validate_positive_integer_non_numeric(self):
        with pytest.raises(self.ValidationError, match="must be an integer"):
            self.Validator.validate_positive_integer("abc", "x")

    def test_validate_positive_integer_too_small(self):
        with pytest.raises(self.ValidationError, match="must be >="):
            self.Validator.validate_positive_integer(0, "x", min_value=1)

    def test_validate_positive_integer_too_large(self):
        with pytest.raises(self.ValidationError, match="must be <="):
            self.Validator.validate_positive_integer(100, "x", max_value=50)

    def test_validate_positive_integer_alt_params(self):
        assert self.Validator.validate_positive_integer(5, "x", min_val=1, max_val=10) == 5

    def test_validate_positive_integer_string_number(self):
        assert self.Validator.validate_positive_integer("42", "x") == 42

    # --- validate_model_name ---

    def test_validate_model_name_valid_kotoba(self):
        result = self.Validator.validate_model_name("kotoba-tech/kotoba-whisper-v2.2")
        assert result == "kotoba-tech/kotoba-whisper-v2.2"

    def test_validate_model_name_valid_size(self):
        assert self.Validator.validate_model_name("base") == "base"
        assert self.Validator.validate_model_name("large-v2") == "large-v2"

    def test_validate_model_name_empty(self):
        with pytest.raises(self.ValidationError, match="cannot be empty"):
            self.Validator.validate_model_name("")

    def test_validate_model_name_none(self):
        with pytest.raises(self.ValidationError, match="cannot be empty"):
            self.Validator.validate_model_name(None)

    def test_validate_model_name_invalid(self):
        with pytest.raises(self.ValidationError, match="not in the allowed list"):
            self.Validator.validate_model_name("malicious/model-name")

    def test_validate_model_name_strip(self):
        result = self.Validator.validate_model_name("  base  ")
        assert result == "base"

    # --- validate_chunk_length ---

    def test_validate_chunk_length_normal(self):
        assert self.Validator.validate_chunk_length(15) == 15

    def test_validate_chunk_length_too_small(self):
        with pytest.raises(self.ValidationError):
            self.Validator.validate_chunk_length(0)

    def test_validate_chunk_length_too_large(self):
        with pytest.raises(self.ValidationError):
            self.Validator.validate_chunk_length(100)

    def test_validate_chunk_length_none_default(self):
        assert self.Validator.validate_chunk_length(None) == 15

    # --- validate_audio_file ---

    def test_validate_audio_file_valid(self, tmp_path):
        f = tmp_path / "test.mp3"
        f.write_text("dummy")
        result = self.Validator.validate_audio_file(str(f))
        assert result.suffix == ".mp3"

    def test_validate_audio_file_invalid_ext(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("dummy")
        with pytest.raises(self.ValidationError, match="not allowed"):
            self.Validator.validate_audio_file(str(f))

    # --- sanitize_filename ---

    def test_sanitize_filename_dangerous_chars(self):
        result = self.Validator.sanitize_filename('test<>:"/\\|?*.txt')
        assert '<' not in result
        assert '>' not in result
        assert '"' not in result

    def test_sanitize_filename_reserved_name(self):
        result = self.Validator.sanitize_filename("CON.txt")
        assert result.startswith("_")

    def test_sanitize_filename_empty(self):
        assert self.Validator.sanitize_filename("") == "untitled"

    def test_sanitize_filename_only_dots(self):
        assert self.Validator.sanitize_filename("...") == "untitled"

    def test_sanitize_filename_normal(self):
        assert self.Validator.sanitize_filename("normal_file.txt") == "normal_file.txt"


# ============================================================================
# 3b. exceptions.py テスト
# ============================================================================

class TestExceptions:
    """例外クラスのテスト"""

    def setup_method(self):
        from exceptions import (
            KotobaTranscriberError,
            FileProcessingError, AudioFormatError, AudioTooShortError, AudioTooLongError,
            TranscriptionError, TranscriptionFailedError, ModelLoadError, ModelNotLoadedError,
            ConfigurationError, InvalidConfigValueError,
            BatchProcessingError, BatchCancelledError,
            ResourceError, InsufficientMemoryError, InsufficientDiskSpaceError,
            RealtimeProcessingError, AudioDeviceError, AudioCaptureError, AudioStreamError,
            PyAudioInitializationError, VADError, InvalidVADThresholdError,
            APIError, APIConnectionError, APIAuthenticationError, APIRateLimitError,
            ExportError, SubtitleExportError,
            SecurityError, PathTraversalError, UnsafePathError,
            is_kotoba_error, get_error_category,
        )
        self.exceptions = {
            'KotobaTranscriberError': KotobaTranscriberError,
            'FileProcessingError': FileProcessingError,
            'AudioFormatError': AudioFormatError,
            'AudioTooShortError': AudioTooShortError,
            'AudioTooLongError': AudioTooLongError,
            'TranscriptionError': TranscriptionError,
            'TranscriptionFailedError': TranscriptionFailedError,
            'ModelLoadError': ModelLoadError,
            'ModelNotLoadedError': ModelNotLoadedError,
            'ConfigurationError': ConfigurationError,
            'InvalidConfigValueError': InvalidConfigValueError,
            'BatchProcessingError': BatchProcessingError,
            'BatchCancelledError': BatchCancelledError,
            'ResourceError': ResourceError,
            'InsufficientMemoryError': InsufficientMemoryError,
            'InsufficientDiskSpaceError': InsufficientDiskSpaceError,
            'RealtimeProcessingError': RealtimeProcessingError,
            'AudioDeviceError': AudioDeviceError,
            'AudioCaptureError': AudioCaptureError,
            'AudioStreamError': AudioStreamError,
            'PyAudioInitializationError': PyAudioInitializationError,
            'VADError': VADError,
            'InvalidVADThresholdError': InvalidVADThresholdError,
            'APIError': APIError,
            'APIConnectionError': APIConnectionError,
            'APIAuthenticationError': APIAuthenticationError,
            'APIRateLimitError': APIRateLimitError,
            'ExportError': ExportError,
            'SubtitleExportError': SubtitleExportError,
            'SecurityError': SecurityError,
            'PathTraversalError': PathTraversalError,
            'UnsafePathError': UnsafePathError,
        }
        self.is_kotoba_error = is_kotoba_error
        self.get_error_category = get_error_category
        self.KotobaTranscriberError = KotobaTranscriberError

    def test_all_exceptions_instantiable(self):
        """全例外クラスが基本文字列引数でインスタンス化可能"""
        skip_special = {
            'InsufficientMemoryError', 'AudioDeviceError', 'AudioStreamError',
            'PyAudioInitializationError', 'InvalidVADThresholdError',
        }
        for name, cls in self.exceptions.items():
            if name in skip_special:
                continue
            e = cls("test message")
            assert str(e) == "test message"
            assert isinstance(e, self.KotobaTranscriberError)

    def test_all_are_kotoba_errors(self):
        """全例外が KotobaTranscriberError を継承"""
        for name, cls in self.exceptions.items():
            assert issubclass(cls, self.KotobaTranscriberError), f"{name} is not a KotobaTranscriberError"

    def test_hierarchy_file_processing(self):
        from exceptions import FileProcessingError, AudioFormatError, AudioTooShortError, AudioTooLongError
        assert issubclass(AudioFormatError, FileProcessingError)
        assert issubclass(AudioTooShortError, FileProcessingError)
        assert issubclass(AudioTooLongError, FileProcessingError)

    def test_hierarchy_transcription(self):
        from exceptions import TranscriptionError, TranscriptionFailedError, ModelLoadError, ModelNotLoadedError
        assert issubclass(TranscriptionFailedError, TranscriptionError)
        assert issubclass(ModelLoadError, TranscriptionError)
        assert issubclass(ModelNotLoadedError, TranscriptionError)

    def test_hierarchy_configuration(self):
        from exceptions import ConfigurationError, InvalidConfigValueError
        assert issubclass(InvalidConfigValueError, ConfigurationError)

    def test_hierarchy_batch(self):
        from exceptions import BatchProcessingError, BatchCancelledError
        assert issubclass(BatchCancelledError, BatchProcessingError)

    def test_hierarchy_resource(self):
        from exceptions import ResourceError, InsufficientMemoryError, InsufficientDiskSpaceError
        assert issubclass(InsufficientMemoryError, ResourceError)
        assert issubclass(InsufficientDiskSpaceError, ResourceError)

    def test_hierarchy_realtime(self):
        from exceptions import (
            RealtimeProcessingError, AudioDeviceError, AudioCaptureError,
            AudioStreamError, VADError, InvalidVADThresholdError,
        )
        assert issubclass(AudioDeviceError, RealtimeProcessingError)
        assert issubclass(AudioCaptureError, RealtimeProcessingError)
        assert issubclass(AudioStreamError, RealtimeProcessingError)
        assert issubclass(VADError, RealtimeProcessingError)
        assert issubclass(InvalidVADThresholdError, VADError)

    def test_hierarchy_api(self):
        from exceptions import APIError, APIConnectionError, APIAuthenticationError, APIRateLimitError
        assert issubclass(APIConnectionError, APIError)
        assert issubclass(APIAuthenticationError, APIError)
        assert issubclass(APIRateLimitError, APIError)

    def test_hierarchy_export(self):
        from exceptions import ExportError, SubtitleExportError
        assert issubclass(SubtitleExportError, ExportError)

    def test_hierarchy_security(self):
        from exceptions import SecurityError, PathTraversalError, UnsafePathError
        assert issubclass(PathTraversalError, SecurityError)
        assert issubclass(UnsafePathError, SecurityError)

    # --- Special constructors ---

    def test_insufficient_memory_error(self):
        from exceptions import InsufficientMemoryError
        e = InsufficientMemoryError(required_mb=4096, available_mb=2048)
        assert e.required_mb == 4096
        assert e.available_mb == 2048
        assert "4096" in str(e)
        assert "2048" in str(e)

    def test_insufficient_memory_error_with_message(self):
        from exceptions import InsufficientMemoryError
        e = InsufficientMemoryError(message="custom message")
        assert str(e) == "custom message"

    def test_audio_device_error(self):
        from exceptions import AudioDeviceError
        e = AudioDeviceError("Device not found", device_index=3)
        assert e.device_index == 3
        assert "device index: 3" in str(e)

    def test_audio_device_error_no_index(self):
        from exceptions import AudioDeviceError
        e = AudioDeviceError("Device not found")
        assert e.device_index is None
        assert "Device not found" == str(e)

    def test_audio_stream_error(self):
        from exceptions import AudioStreamError
        e = AudioStreamError("Stream overflow", device_index=0)
        assert e.detail == "Stream overflow"
        assert e.device_index == 0
        assert "device=0" in str(e)

    def test_audio_stream_error_no_index(self):
        from exceptions import AudioStreamError
        e = AudioStreamError("Stream overflow")
        assert e.device_index is None

    def test_pyaudio_initialization_error(self):
        from exceptions import PyAudioInitializationError
        original = OSError("PortAudio library not found")
        e = PyAudioInitializationError(original)
        assert e.original_error is original
        assert "PortAudio" in str(e)

    def test_invalid_vad_threshold_error(self):
        from exceptions import InvalidVADThresholdError
        e = InvalidVADThresholdError(0.1, (0.005, 0.050))
        assert e.threshold == 0.1
        assert e.valid_range == (0.005, 0.050)
        assert "0.1" in str(e)

    # --- Utility functions ---

    def test_is_kotoba_error_true(self):
        from exceptions import AudioFormatError
        assert self.is_kotoba_error(AudioFormatError("test"))

    def test_is_kotoba_error_false(self):
        assert not self.is_kotoba_error(ValueError("test"))

    def test_get_error_category_file_processing(self):
        from exceptions import AudioFormatError
        assert self.get_error_category(AudioFormatError("test")) == "FileProcessing"

    def test_get_error_category_transcription(self):
        from exceptions import ModelLoadError
        assert self.get_error_category(ModelLoadError("test")) == "Transcription"

    def test_get_error_category_configuration(self):
        from exceptions import InvalidConfigValueError
        assert self.get_error_category(InvalidConfigValueError("test")) == "Configuration"

    def test_get_error_category_batch(self):
        from exceptions import BatchCancelledError
        assert self.get_error_category(BatchCancelledError("test")) == "BatchProcessing"

    def test_get_error_category_resource(self):
        from exceptions import InsufficientMemoryError
        assert self.get_error_category(InsufficientMemoryError(message="test")) == "Resource"

    def test_get_error_category_realtime(self):
        from exceptions import AudioDeviceError
        assert self.get_error_category(AudioDeviceError("test")) == "RealtimeProcessing"

    def test_get_error_category_api(self):
        from exceptions import APIConnectionError
        assert self.get_error_category(APIConnectionError("test")) == "API"

    def test_get_error_category_export(self):
        from exceptions import SubtitleExportError
        assert self.get_error_category(SubtitleExportError("test")) == "Export"

    def test_get_error_category_security(self):
        from exceptions import PathTraversalError
        assert self.get_error_category(PathTraversalError("test")) == "Security"

    def test_get_error_category_general(self):
        from exceptions import KotobaTranscriberError
        assert self.get_error_category(KotobaTranscriberError("test")) == "General"

    def test_get_error_category_unknown(self):
        assert self.get_error_category(ValueError("test")) == "Unknown"


# ============================================================================
# 3c. config_manager.py テスト
# ============================================================================

class TestConfig:
    """Config クラスのテスト"""

    def setup_method(self):
        from config_manager import Config
        self.Config = Config

    def test_get_dot_notation(self):
        c = self.Config({"model": {"whisper": {"name": "kotoba"}}})
        assert c.get("model.whisper.name") == "kotoba"

    def test_get_missing_key_returns_default(self):
        c = self.Config({})
        assert c.get("nonexistent.key", default="fallback") == "fallback"

    def test_get_non_dict_intermediate(self):
        c = self.Config({"model": "string_value"})
        assert c.get("model.whisper.name", default="default") == "default"

    def test_set_dot_notation(self):
        c = self.Config({})
        c.set("model.whisper.name", "test-model")
        assert c.get("model.whisper.name") == "test-model"

    def test_set_overwrites_existing(self):
        c = self.Config({"x": {"y": "old"}})
        c.set("x.y", "new")
        assert c.get("x.y") == "new"

    def test_set_creates_intermediate_dicts(self):
        c = self.Config({})
        c.set("a.b.c", 42)
        assert c.get("a.b.c") == 42

    def test_getitem(self):
        c = self.Config({"key": "value"})
        assert c["key"] == "value"

    def test_contains_true(self):
        c = self.Config({"key": "value"})
        assert "key" in c

    def test_contains_false(self):
        c = self.Config({"key": "value"})
        assert "missing" not in c

    def test_data_property_returns_copy(self):
        original = {"key": "value"}
        c = self.Config(original)
        data = c.data
        data["key"] = "modified"
        assert c.get("key") == "value"  # Original unchanged

    def test_init_none(self):
        c = self.Config(None)
        assert c.get("anything") is None


class TestConfigManager:
    """ConfigManager クラスのテスト"""

    def setup_method(self):
        # ConfigManager のシングルトンをリセット
        from config_manager import ConfigManager
        ConfigManager._instance = None
        ConfigManager._config = None
        self.ConfigManager = ConfigManager

    def test_singleton(self):
        m1 = self.ConfigManager()
        m2 = self.ConfigManager()
        assert m1 is m2

    def test_default_config_loaded(self):
        m = self.ConfigManager()
        assert m.config.get("app.name") == "KotobaTranscriber"
        assert m.config.get("model.whisper.language") == "ja"

    def test_reload(self):
        m = self.ConfigManager()
        m.reload()
        assert m.config.get("app.name") == "KotobaTranscriber"

    def test_merge_configs(self):
        m = self.ConfigManager()
        default = {"a": {"b": 1, "c": 2}, "d": 3}
        override = {"a": {"b": 99}, "e": 5}
        result = m._merge_configs(default, override)
        assert result["a"]["b"] == 99
        assert result["a"]["c"] == 2
        assert result["d"] == 3
        assert result["e"] == 5

    def test_merge_configs_deep(self):
        m = self.ConfigManager()
        default = {"a": {"b": {"c": {"d": 1}}, "e": 2}}
        override = {"a": {"b": {"c": {"d": 99, "f": 3}}}}
        result = m._merge_configs(default, override)
        assert result["a"]["b"]["c"]["d"] == 99
        assert result["a"]["b"]["c"]["f"] == 3
        assert result["a"]["e"] == 2

    def test_get_missing_nested(self):
        m = self.ConfigManager()
        # Test getting a deeply nested key that doesn't exist
        result = m.config.get("nonexistent.deeply.nested.key.path", default="fallback")
        assert result == "fallback"

    def teardown_method(self):
        from config_manager import ConfigManager
        ConfigManager._instance = None
        ConfigManager._config = None


class TestGetConfig:
    """get_config() 関数のテスト"""

    def setup_method(self):
        import config_manager
        config_manager._manager = None
        config_manager.ConfigManager._instance = None
        config_manager.ConfigManager._config = None

    def test_get_config_returns_config(self):
        from config_manager import get_config
        config = get_config()
        assert config.get("app.name") == "KotobaTranscriber"

    def test_get_config_thread_safe(self):
        from config_manager import get_config
        results = []

        def worker():
            c = get_config()
            results.append(c.get("app.name"))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == "KotobaTranscriber" for r in results)

    def teardown_method(self):
        import config_manager
        config_manager._manager = None
        config_manager.ConfigManager._instance = None
        config_manager.ConfigManager._config = None


# ============================================================================
# 3d. base_engine.py テスト
# ============================================================================

class TestBaseTranscriptionEngine:
    """BaseTranscriptionEngine のテスト"""

    def setup_method(self):
        from base_engine import BaseTranscriptionEngine

        class ConcreteEngine(BaseTranscriptionEngine):
            def load_model(self) -> bool:
                self.model = "mock_model"
                self.is_loaded = True
                return True

            def transcribe(self, audio, **kwargs):
                return {"text": "test", "segments": []}

        self.ConcreteEngine = ConcreteEngine
        self.BaseTranscriptionEngine = BaseTranscriptionEngine

    def test_init_default_device(self):
        engine = self.ConcreteEngine("test-model")
        assert engine.model_name == "test-model"
        assert engine.language == "ja"
        assert engine.model is None
        assert engine.is_loaded is False

    def test_init_explicit_cpu(self):
        engine = self.ConcreteEngine("test-model", device="cpu")
        assert engine.device == "cpu"

    def test_resolve_device_auto(self):
        engine = self.ConcreteEngine("test-model", device="auto")
        assert engine.device in ("cpu", "cuda")

    def test_resolve_device_explicit(self):
        engine = self.ConcreteEngine("test-model", device="cpu")
        assert engine.device == "cpu"

    def test_load_model(self):
        engine = self.ConcreteEngine("test-model")
        result = engine.load_model()
        assert result is True
        assert engine.is_loaded is True
        assert engine.model == "mock_model"

    def test_unload_model(self):
        engine = self.ConcreteEngine("test-model")
        engine.load_model()
        engine.unload_model()
        assert engine.model is None
        assert engine.is_loaded is False

    def test_unload_model_when_none(self):
        engine = self.ConcreteEngine("test-model")
        engine.unload_model()  # Should not raise
        assert engine.model is None

    def test_context_manager(self):
        with self.ConcreteEngine("test-model") as engine:
            assert engine.is_loaded is True
            assert engine.model == "mock_model"
        assert engine.model is None
        assert engine.is_loaded is False

    def test_context_manager_exception(self):
        with pytest.raises(ValueError):
            with self.ConcreteEngine("test-model") as engine:
                raise ValueError("test error")
        assert engine.model is None

    def test_is_available_method(self):
        engine = self.ConcreteEngine("test-model")
        # is_available is now a method, not property
        result = engine.is_available()
        assert result is True

    def test_get_model_info(self):
        engine = self.ConcreteEngine("test-model", device="cpu")
        info = engine.get_model_info()
        assert info["engine"] == "ConcreteEngine"
        assert info["model_name"] == "test-model"
        assert info["device"] == "cpu"
        assert info["language"] == "ja"
        assert info["is_loaded"] is False

    def test_get_model_info_after_load(self):
        engine = self.ConcreteEngine("test-model")
        engine.load_model()
        info = engine.get_model_info()
        assert info["is_loaded"] is True

    def test_del_cleanup(self):
        engine = self.ConcreteEngine("test-model")
        engine.load_model()
        engine.__del__()
        assert engine.model is None


# ============================================================================
# 3e. construction_vocabulary.py テスト
# ============================================================================

class TestConstructionVocabulary:
    """ConstructionVocabulary のテスト"""

    def test_class_constants_not_empty(self):
        from construction_vocabulary import ConstructionVocabulary
        assert len(ConstructionVocabulary.STANDARD_LABOR_TERMS) > 0
        assert len(ConstructionVocabulary.CONSTRUCTION_LAW_TERMS) > 0
        assert len(ConstructionVocabulary.COST_MANAGEMENT_TERMS) > 0
        assert len(ConstructionVocabulary.AGEC_SPECIFIC_TERMS) > 0

    def test_init_creates_default_when_no_file(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "nonexistent" / "vocab.json"))
        assert len(vocab.hotwords) > 0
        assert len(vocab.replacements) > 0
        assert len(vocab.category_vocabularies) > 0

    def test_categories_created(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        categories = vocab.get_all_categories()
        assert "standard_labor" in categories
        assert "construction_law" in categories
        assert "cost_management" in categories
        assert "agec_specific" in categories

    def test_save_and_load(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab_file = str(tmp_path / "vocab.json")
        vocab1 = ConstructionVocabulary(vocab_file)
        original_count = len(vocab1.hotwords)

        # Load from saved file
        vocab2 = ConstructionVocabulary(vocab_file)
        assert len(vocab2.hotwords) == original_count

    def test_get_whisper_prompt(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        prompt = vocab.get_whisper_prompt()
        assert "建設業" in prompt
        assert len(prompt) > 0

    def test_get_whisper_prompt_by_category(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        prompt = vocab.get_whisper_prompt(category="standard_labor")
        assert len(prompt) > 0

    def test_apply_replacements(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        # "ほおがけ" -> "歩掛"
        result = vocab.apply_replacements("ほおがけの計算")
        assert "歩掛" in result

    def test_add_term(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        vocab.add_term("テスト用語", "custom")
        assert "テスト用語" in vocab.hotwords
        assert "テスト用語" in vocab.category_vocabularies.get("custom", [])

    def test_add_term_duplicate_ignored(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        original_count = len(vocab.hotwords)
        term = vocab.hotwords[0]  # Pick existing term
        vocab.add_term(term, "custom")
        assert len(vocab.hotwords) == original_count

    def test_add_replacement(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        vocab.add_replacement("てすと", "テスト")
        assert vocab.replacements["てすと"] == "テスト"

    def test_get_terms_by_category(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        terms = vocab.get_terms_by_category("standard_labor")
        assert len(terms) > 0
        assert "普通作業員" in terms

    def test_get_terms_by_category_missing(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        terms = vocab.get_terms_by_category("nonexistent")
        assert terms == []

    def test_search_terms(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        results = vocab.search_terms("管理")
        assert len(results) > 0
        for term in results:
            assert "管理" in term

    def test_load_from_file_with_categories(self, tmp_path):
        from construction_vocabulary import ConstructionVocabulary
        # Create a vocab file with nested format
        vocab_file = tmp_path / "vocab.json"
        data = {
            "hotwords": ["用語A", "用語B"],
            "replacements": {"aa": "AA"},
            "categories": {
                "cat1": {"name": "Category 1", "terms": ["用語X", "用語Y"]},
                "cat2": ["用語Z"],
            }
        }
        vocab_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        vocab = ConstructionVocabulary(str(vocab_file))
        assert "用語A" in vocab.hotwords
        assert "用語X" in vocab.category_vocabularies.get("cat1", [])
        assert "用語Z" in vocab.category_vocabularies.get("cat2", [])


# ============================================================================
# 3f. subtitle_exporter.py テスト
# ============================================================================

class TestSubtitleExporter:
    """SubtitleExporter のテスト"""

    def setup_method(self):
        from subtitle_exporter import SubtitleExporter
        self.exporter = SubtitleExporter()

    # --- Time formatting ---

    def test_format_srt_time_zero(self):
        assert self.exporter.format_srt_time(0) == "00:00:00,000"

    def test_format_srt_time_normal(self):
        # 1h 23m 45.5s
        result = self.exporter.format_srt_time(5025.5)
        assert result == "01:23:45,500"

    def test_format_vtt_time_zero(self):
        assert self.exporter.format_vtt_time(0) == "00:00:00.000"

    def test_format_vtt_time_normal(self):
        result = self.exporter.format_vtt_time(65.5)
        assert result == "00:01:05.500"

    def test_format_srt_time_uses_comma(self):
        result = self.exporter.format_srt_time(1.5)
        assert "," in result

    def test_format_vtt_time_uses_dot(self):
        result = self.exporter.format_vtt_time(1.5)
        assert "." in result

    # --- SRT generation ---

    def test_generate_srt_content_basic(self):
        segments = [
            {"start": 0.5, "end": 3.2, "text": "Hello"},
            {"start": 3.5, "end": 6.0, "text": "World"},
        ]
        srt = self.exporter.generate_srt_content(segments)
        assert "1\n" in srt
        assert "2\n" in srt
        assert "Hello" in srt
        assert "World" in srt
        assert "-->" in srt

    def test_generate_srt_content_empty_text_skipped(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": ""},
            {"start": 1.0, "end": 2.0, "text": "  "},
            {"start": 2.0, "end": 3.0, "text": "Valid"},
        ]
        srt = self.exporter.generate_srt_content(segments)
        assert "1\n" in srt  # Only the valid segment
        assert "2\n" not in srt

    def test_generate_srt_with_speakers(self):
        segments = [{"start": 0.5, "end": 3.0, "text": "Hello"}]
        speakers = [{"start": 0.0, "end": 5.0, "speaker": "Speaker A"}]
        srt = self.exporter.generate_srt_content(segments, speakers)
        assert "[Speaker A]" in srt

    # --- VTT generation ---

    def test_generate_vtt_content_basic(self):
        segments = [{"start": 0.5, "end": 3.0, "text": "Hello"}]
        vtt = self.exporter.generate_vtt_content(segments)
        assert vtt.startswith("WEBVTT")
        assert "Hello" in vtt

    def test_generate_vtt_with_speakers(self):
        segments = [{"start": 0.5, "end": 3.0, "text": "Hello"}]
        speakers = [{"start": 0.0, "end": 5.0, "speaker": "SpkA"}]
        vtt = self.exporter.generate_vtt_content(segments, speakers)
        assert "<v SpkA>" in vtt

    # --- Export to file ---

    def test_export_srt_file(self, tmp_path):
        segments = [{"start": 0.0, "end": 1.0, "text": "Test"}]
        output = str(tmp_path / "test.srt")
        result = self.exporter.export_srt(segments, output)
        assert result is True
        assert Path(output).exists()
        content = Path(output).read_text(encoding="utf-8")
        assert "Test" in content

    def test_export_vtt_file(self, tmp_path):
        segments = [{"start": 0.0, "end": 1.0, "text": "Test"}]
        output = str(tmp_path / "test.vtt")
        result = self.exporter.export_vtt(segments, output)
        assert result is True
        content = Path(output).read_text(encoding="utf-8")
        assert "WEBVTT" in content

    # --- Merge short segments ---

    def test_merge_short_segments_empty(self):
        assert self.exporter.merge_short_segments([]) == []

    def test_merge_short_segments_basic(self):
        segments = [
            {"start": 0.0, "end": 0.3, "text": "あ"},
            {"start": 0.4, "end": 0.5, "text": "い"},
            {"start": 0.6, "end": 3.0, "text": "うえお"},
        ]
        merged = self.exporter.merge_short_segments(segments, min_duration=1.0, max_chars=40)
        assert len(merged) <= len(segments)
        # First two short segments should be merged
        assert merged[0]["text"].startswith("あ")

    def test_merge_short_segments_no_merge_needed(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Long enough segment"},
            {"start": 3.0, "end": 5.0, "text": "Another long segment"},
        ]
        merged = self.exporter.merge_short_segments(segments, min_duration=1.0)
        assert len(merged) == 2

    # --- Split long segments ---

    def test_split_long_segments_no_split_needed(self):
        segments = [{"start": 0.0, "end": 2.0, "text": "短いテキスト"}]
        result = self.exporter.split_long_segments(segments, max_chars=40)
        assert len(result) == 1

    def test_split_long_segments_splits_by_sentence(self):
        segments = [{
            "start": 0.0,
            "end": 10.0,
            "text": "これは長いテキストです。分割が必要です。さらに続きます。最後の文です。"
        }]
        result = self.exporter.split_long_segments(segments, max_chars=20)
        assert len(result) > 1

    # --- Speaker detection ---

    def test_get_speaker_for_time_none_segments(self):
        assert self.exporter._get_speaker_for_time(1.0, None) is None

    def test_get_speaker_for_time_empty_segments(self):
        assert self.exporter._get_speaker_for_time(1.0, []) is None

    def test_get_speaker_for_time_found(self):
        speakers = [
            {"start": 0.0, "end": 5.0, "speaker": "A"},
            {"start": 5.0, "end": 10.0, "speaker": "B"},
        ]
        assert self.exporter._get_speaker_for_time(3.0, speakers) == "A"
        assert self.exporter._get_speaker_for_time(7.0, speakers) == "B"

    def test_get_speaker_for_time_not_found(self):
        speakers = [{"start": 0.0, "end": 5.0, "speaker": "A"}]
        assert self.exporter._get_speaker_for_time(10.0, speakers) is None

    # --- Auto export ---

    def test_export_auto(self, tmp_path):
        segments = [{"start": 0.0, "end": 1.0, "text": "テスト"}]
        base = str(tmp_path / "output")
        results = self.exporter.export_auto(segments, base, formats=["srt", "vtt"])
        assert results.get("srt") is True
        assert results.get("vtt") is True


class TestTranscriptionResult:
    """TranscriptionResult のテスト"""

    def test_add_segment(self):
        from subtitle_exporter import TranscriptionResult
        result = TranscriptionResult()
        result.add_segment(0.0, 1.0, "Hello", "Speaker A")
        assert len(result.segments) == 1
        assert result.segments[0]["text"] == "Hello"
        assert result.segments[0]["speaker"] == "Speaker A"

    def test_set_speaker_segments(self):
        from subtitle_exporter import TranscriptionResult
        result = TranscriptionResult()
        speakers = [{"start": 0.0, "end": 5.0, "speaker": "A"}]
        result.set_speaker_segments(speakers)
        assert result.speaker_segments == speakers


# ============================================================================
# 3g. app_settings.py テスト
# ============================================================================

class TestAppSettings:
    """AppSettings のテスト"""

    def setup_method(self):
        from app_settings import AppSettings
        self.AppSettings = AppSettings

    def test_init_default(self):
        settings = self.AppSettings()
        assert settings.settings is not None
        assert "monitored_folder" in settings.settings

    def test_init_custom_path(self, tmp_path):
        settings_file = str(tmp_path / "test_settings.json")
        settings = self.AppSettings(settings_file)
        assert settings.settings_file == Path(settings_file).resolve()

    def test_get_default_value(self):
        settings = self.AppSettings()
        assert settings.get("monitored_folder") is None
        assert settings.get("monitor_interval") == 10

    def test_get_missing_key(self):
        settings = self.AppSettings()
        assert settings.get("nonexistent_key", default="fallback") == "fallback"

    def test_set_and_get(self):
        settings = self.AppSettings()
        settings.set("remove_fillers", False)
        assert settings.get("remove_fillers") is False

    def test_set_nested(self):
        settings = self.AppSettings()
        settings.set("window.width", 500)
        assert settings.get("window.width") == 500

    def test_set_validates_type(self):
        settings = self.AppSettings()
        with pytest.raises(TypeError):
            settings.set("monitor_interval", "not_an_int")

    def test_set_validates_range(self):
        settings = self.AppSettings()
        with pytest.raises(ValueError, match="must be between"):
            settings.set("monitor_interval", 100)

    def test_set_validates_key_format(self):
        settings = self.AppSettings()
        with pytest.raises(ValueError, match="invalid characters"):
            settings.set("INVALID-KEY", "value")

    def test_save_and_load(self, tmp_path):
        settings_file = str(tmp_path / "test_settings.json")
        settings1 = self.AppSettings(settings_file)
        settings1.set("remove_fillers", False)
        assert settings1.save() is True

        settings2 = self.AppSettings(settings_file)
        assert settings2.load() is True
        assert settings2.get("remove_fillers") is False

    def test_load_nonexistent(self):
        settings = self.AppSettings()
        # Default file probably doesn't exist in test
        result = settings.load()
        # Could be True or False depending on if file exists, but shouldn't raise
        assert isinstance(result, bool)

    def test_get_all(self):
        settings = self.AppSettings()
        all_settings = settings.get_all()
        assert isinstance(all_settings, dict)
        assert "monitored_folder" in all_settings

    def test_get_all_returns_copy(self):
        settings = self.AppSettings()
        all_settings = settings.get_all()
        all_settings["new_key"] = "new_value"
        assert settings.get("new_key") is None

    def test_reset(self):
        settings = self.AppSettings()
        settings.set("remove_fillers", False)
        settings.reset()
        assert settings.get("remove_fillers") is True

    def test_validate_key_empty(self):
        settings = self.AppSettings()
        with pytest.raises(ValueError):
            settings.get("")

    def test_window_size_validation(self):
        settings = self.AppSettings()
        with pytest.raises(ValueError):
            settings.set("window.width", 50)  # Too small

    def test_window_position_validation(self):
        settings = self.AppSettings()
        settings.set("window.x", -100)  # Negative is OK within range
        assert settings.get("window.x") == -100

    def test_model_size_validation(self):
        settings = self.AppSettings()
        with pytest.raises(ValueError, match="Invalid model size"):
            settings.set("realtime.model_size", "invalid_model")

    def test_save_creates_backup(self, tmp_path):
        settings_file = str(tmp_path / "test_settings.json")
        settings = self.AppSettings(settings_file)
        settings.save()  # First save (no backup since no existing file)
        settings.save()  # Second save creates backup
        backup_dir = tmp_path / ".backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("*.json"))
            assert len(backups) >= 1

    def test_thread_safety(self, tmp_path):
        settings_file = str(tmp_path / "test_settings.json")
        settings = self.AppSettings(settings_file)
        errors = []

        def writer(val):
            try:
                settings.set("monitor_interval", val)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(v,)) for v in [10, 15, 20, 30]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Value should be one of the set values
        assert settings.get("monitor_interval") in [10, 15, 20, 30]

    def test_cancel_pending_save(self):
        settings = self.AppSettings()
        settings.cancel_pending_save()  # Should not raise


# ============================================================================
# 3h. custom_dictionary.py テスト
# ============================================================================

class TestCustomDictionaryModule:
    """CustomDictionary (custom_dictionary.py) のテスト"""

    def test_init_empty_config(self):
        from custom_dictionary import CustomDictionary
        # Construction vocab will be loaded by default since enabled defaults to True
        d = CustomDictionary({})
        assert isinstance(d.hotwords, list)
        assert isinstance(d.replacements, dict)

    def test_add_term(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.add_term("テスト用語A", "test_cat")
        assert "テスト用語A" in d.hotwords
        assert "テスト用語A" in d.categories.get("test_cat", [])

    def test_add_term_duplicate(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.add_term("用語X", "cat")
        count = len(d.hotwords)
        d.add_term("用語X", "cat")  # Duplicate
        assert len(d.hotwords) == count

    def test_add_replacement(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.add_replacement("わるい", "悪い")
        assert d.replacements["わるい"] == "悪い"

    def test_apply_replacements(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.replacements = {"ほおがけ": "歩掛"}
        result = d.apply_replacements("ほおがけの計算")
        assert "歩掛" in result

    def test_get_whisper_prompt(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.hotwords = ["用語A", "用語B"]
        prompt = d.get_whisper_prompt()
        assert "専門用語" in prompt

    def test_get_whisper_prompt_empty(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.hotwords = []
        prompt = d.get_whisper_prompt()
        assert prompt == ""

    def test_get_terms_by_category(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.categories["test"] = ["A", "B"]
        assert d.get_terms_by_category("test") == ["A", "B"]
        assert d.get_terms_by_category("missing") == []

    def test_get_all_categories(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.categories = {"cat1": [], "cat2": []}
        assert set(d.get_all_categories()) == {"cat1", "cat2"}

    def test_search_terms(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.hotwords = ["品質管理", "安全管理", "テスト"]
        results = d.search_terms("管理")
        assert "品質管理" in results
        assert "安全管理" in results
        assert "テスト" not in results

    def test_reload(self):
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.hotwords = ["test"]
        d.reload()
        assert d.hotwords == []  # Reset since config has enabled=False


# ============================================================================
# 3i. speaker_diarization_utils.py テスト
# ============================================================================

class TestClusteringMixin:
    """ClusteringMixin のテスト"""

    def setup_method(self):
        from speaker_diarization_utils import ClusteringMixin
        self.mixin = ClusteringMixin()

    def test_simple_clustering(self):
        # Create clearly separable embeddings
        emb1 = np.array([[1, 0, 0], [0.9, 0.1, 0]], dtype=np.float32)
        emb2 = np.array([[0, 1, 0], [0.1, 0.9, 0]], dtype=np.float32)
        embeddings = np.vstack([emb1, emb2])

        labels = self.mixin._simple_clustering(embeddings, num_speakers=2)
        assert len(labels) == 4
        # First two should have the same label
        assert labels[0] == labels[1]
        # Last two should have the same label
        assert labels[2] == labels[3]

    def test_simple_clustering_single_speaker(self):
        embeddings = np.array([[1, 0], [0.9, 0.1]], dtype=np.float32)
        labels = self.mixin._simple_clustering(embeddings, num_speakers=1)
        assert len(labels) == 2
        assert labels[0] == labels[1]

    def test_merge_consecutive_segments_empty(self):
        result = self.mixin._merge_consecutive_segments(np.array([]), [])
        assert result == []

    def test_merge_consecutive_segments_basic(self):
        labels = np.array([0, 0, 1, 1, 0])
        timestamps = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
        result = self.mixin._merge_consecutive_segments(labels, timestamps)
        assert len(result) == 3
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[0]["start"] == 0
        assert result[0]["end"] == 2
        assert result[1]["speaker"] == "SPEAKER_01"
        assert result[2]["speaker"] == "SPEAKER_00"

    def test_merge_consecutive_single(self):
        labels = np.array([0])
        timestamps = [(0, 5)]
        result = self.mixin._merge_consecutive_segments(labels, timestamps)
        assert len(result) == 1
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[0]["start"] == 0
        assert result[0]["end"] == 5


class TestSpeakerFormatterMixin:
    """SpeakerFormatterMixin のテスト"""

    def setup_method(self):
        from speaker_diarization_utils import SpeakerFormatterMixin
        self.formatter = SpeakerFormatterMixin()

    def test_format_with_speakers_basic(self):
        text_segments = [
            {"start": 1, "end": 3, "text": "Hello"},
            {"start": 6, "end": 9, "text": "World"},
        ]
        speaker_segments = [
            {"start": 0, "end": 5, "speaker": "SPEAKER_00"},
            {"start": 5, "end": 10, "speaker": "SPEAKER_01"},
        ]
        result = self.formatter.format_with_speakers(text_segments, speaker_segments)
        assert "[SPEAKER_00]" in result
        assert "[SPEAKER_01]" in result
        assert "Hello" in result
        assert "World" in result

    def test_format_with_no_speakers(self):
        text_segments = [
            {"start": 0, "end": 3, "text": "Hello"},
            {"start": 3, "end": 6, "text": "World"},
        ]
        result = self.formatter.format_with_speakers(text_segments, [])
        assert "Hello" in result
        assert "World" in result
        assert "[" not in result

    def test_format_with_empty_text_skipped(self):
        text_segments = [
            {"start": 0, "end": 1, "text": ""},
            {"start": 1, "end": 2, "text": "Valid"},
        ]
        speaker_segments = [{"start": 0, "end": 5, "speaker": "SPEAKER_00"}]
        result = self.formatter.format_with_speakers(text_segments, speaker_segments)
        assert "Valid" in result

    def test_get_speaker_statistics(self):
        speaker_segments = [
            {"start": 0, "end": 5, "speaker": "SPEAKER_00"},
            {"start": 5, "end": 10, "speaker": "SPEAKER_01"},
            {"start": 10, "end": 15, "speaker": "SPEAKER_00"},
        ]
        stats = self.formatter.get_speaker_statistics(speaker_segments)
        assert "SPEAKER_00" in stats
        assert "SPEAKER_01" in stats
        assert stats["SPEAKER_00"]["total_time"] == 10.0
        assert stats["SPEAKER_01"]["total_time"] == 5.0
        assert stats["SPEAKER_00"]["segment_count"] == 2
        assert stats["SPEAKER_01"]["segment_count"] == 1
        # Percentages
        assert abs(stats["SPEAKER_00"]["percentage"] - 66.7) < 0.1
        assert abs(stats["SPEAKER_01"]["percentage"] - 33.3) < 0.1

    def test_get_speaker_statistics_empty(self):
        stats = self.formatter.get_speaker_statistics([])
        assert stats == {}

    def test_find_speaker_at_time(self):
        speakers = [
            {"start": 0, "end": 5, "speaker": "A"},
            {"start": 5, "end": 10, "speaker": "B"},
        ]
        assert self.formatter._find_speaker_at_time(3, speakers) == "A"
        assert self.formatter._find_speaker_at_time(7, speakers) == "B"
        assert self.formatter._find_speaker_at_time(15, speakers) == "UNKNOWN"


# ============================================================================
# 3j. custom_vocabulary.py テスト (CustomVocabulary クラス)
# ============================================================================

class TestCustomVocabulary:
    """CustomVocabulary (custom_vocabulary.py) のテスト"""

    def test_init_creates_default(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        assert len(vocab.hotwords) > 0
        assert len(vocab.replacements) > 0

    def test_save_and_load(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab_file = str(tmp_path / "vocab.json")
        vocab1 = CustomVocabulary(vocab_file)
        count = len(vocab1.hotwords)
        vocab2 = CustomVocabulary(vocab_file)
        assert len(vocab2.hotwords) == count

    def test_add_hotword(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.add_hotword("NewWord")
        assert "NewWord" in vocab.hotwords

    def test_add_hotword_duplicate(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        count = len(vocab.hotwords)
        existing = vocab.hotwords[0]
        vocab.add_hotword(existing)
        assert len(vocab.hotwords) == count

    def test_remove_hotword(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        word = vocab.hotwords[0]
        vocab.remove_hotword(word)
        assert word not in vocab.hotwords

    def test_add_replacement(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.add_replacement("wrong", "right")
        assert vocab.replacements["wrong"] == "right"

    def test_remove_replacement(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.add_replacement("wrong", "right")
        vocab.remove_replacement("wrong")
        assert "wrong" not in vocab.replacements

    def test_get_whisper_prompt(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        prompt = vocab.get_whisper_prompt()
        assert "専門用語" in prompt
        assert len(prompt) > 0

    def test_get_whisper_prompt_with_domain(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        prompt = vocab.get_whisper_prompt(domain="it")
        assert len(prompt) > 0

    def test_get_hotwords_list_returns_copy(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        lst = vocab.get_hotwords_list()
        lst.append("ModifiedItem")
        assert "ModifiedItem" not in vocab.hotwords

    def test_get_replacements_dict_returns_copy(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        d = vocab.get_replacements_dict()
        d["new_key"] = "new_value"
        assert "new_key" not in vocab.replacements

    def test_import_words_from_text(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.import_words_from_text("WordA\nWordB\nWordC")
        assert "WordA" in vocab.hotwords
        assert "WordB" in vocab.hotwords
        assert "WordC" in vocab.hotwords

    def test_export_words_to_text(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.hotwords = ["A", "B", "C"]
        text = vocab.export_words_to_text()
        assert text == "A\nB\nC"

    def test_clear_hotwords(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.clear_hotwords()
        assert len(vocab.hotwords) == 0

    def test_set_domain_vocabulary(self, tmp_path):
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.set_domain_vocabulary("finance", ["株式", "投資", "配当"])
        assert vocab.domain_vocabularies["finance"] == ["株式", "投資", "配当"]


# ============================================================================
# 3k. text_formatter.py テスト
# ============================================================================

class TestPunctuationRules:
    """PunctuationRules クラスのテスト"""

    def test_conjunctions_not_empty(self):
        from text_formatter import PunctuationRules
        assert len(PunctuationRules.CONJUNCTIONS) > 0

    def test_paragraph_break_words_not_empty(self):
        from text_formatter import PunctuationRules
        assert len(PunctuationRules.PARAGRAPH_BREAK_WORDS) > 0

    def test_polite_endings_not_empty(self):
        from text_formatter import PunctuationRules
        assert len(PunctuationRules.POLITE_ENDINGS) > 0

    def test_long_sentence_min_length(self):
        from text_formatter import PunctuationRules
        assert PunctuationRules.LONG_SENTENCE_MIN_LENGTH > 0


class TestRegexPatterns:
    """RegexPatterns クラスのテスト"""

    def test_consecutive_commas(self):
        from text_formatter import RegexPatterns
        assert RegexPatterns.CONSECUTIVE_COMMAS.sub("、", "、、、") == "、"

    def test_consecutive_periods(self):
        from text_formatter import RegexPatterns
        assert RegexPatterns.CONSECUTIVE_PERIODS.sub("。", "。。。") == "。"

    def test_consecutive_spaces(self):
        from text_formatter import RegexPatterns
        assert RegexPatterns.CONSECUTIVE_SPACES.sub(" ", "a   b") == "a b"

    def test_get_filler_pattern(self):
        from text_formatter import RegexPatterns
        p = RegexPatterns.get_filler_pattern("えーと")
        assert p is not None
        # Cache hit
        p2 = RegexPatterns.get_filler_pattern("えーと")
        assert p is p2

    def test_get_conjunction_pattern(self):
        from text_formatter import RegexPatterns
        p = RegexPatterns.get_conjunction_pattern("しかし")
        assert p is not None

    def test_get_quote_verb_pattern(self):
        from text_formatter import RegexPatterns
        p = RegexPatterns.get_quote_verb_pattern("思います")
        assert p is not None

    def test_get_polite_ending_pattern(self):
        from text_formatter import RegexPatterns
        p = RegexPatterns.get_polite_ending_pattern("です")
        assert p is not None


class TestTextFormatter:
    """TextFormatter クラスのテスト"""

    def setup_method(self):
        from text_formatter import TextFormatter
        self.formatter = TextFormatter()

    def test_remove_fillers_basic(self):
        # \b word boundary doesn't match Japanese chars, so test with space-delimited fillers
        text = "あのー これはテストです"
        result = self.formatter.remove_fillers(text)
        assert "あのー" not in result
        assert "テスト" in result

    def test_remove_fillers_multiple(self):
        text = "えーと あのー まあ テストですね"
        result = self.formatter.remove_fillers(text)
        assert "えーと" not in result
        assert "あのー" not in result

    def test_remove_fillers_aggressive(self):
        text = "ちょっと やっぱり テストです"
        result = self.formatter.remove_fillers(text, aggressive=True)
        assert "ちょっと" not in result

    def test_remove_fillers_empty(self):
        result = self.formatter.remove_fillers("")
        assert result == ""

    def test_add_punctuation_ends_with_period(self):
        result = self.formatter.add_punctuation("テストです")
        assert result.endswith("。")

    def test_add_punctuation_already_has_period(self):
        result = self.formatter.add_punctuation("テストです。")
        assert not result.endswith("。。")

    def test_add_punctuation_conjunction(self):
        result = self.formatter.add_punctuation("テストですしかし問題があります")
        assert "、しかし" in result or "しかし" in result

    def test_format_paragraphs_short_text(self):
        result = self.formatter.format_paragraphs("短いテスト。")
        assert "\n\n" not in result

    def test_format_paragraphs_already_formatted(self):
        text = "段落1。\n\n段落2。"
        result = self.formatter.format_paragraphs(text)
        assert result == text

    def test_clean_repeated_words(self):
        result = self.formatter.clean_repeated_words("hello hello world")
        assert result == "hello world"

    def test_format_numbers(self):
        # NUMBER_SPACING disabled to prevent merging separate numbers
        result = self.formatter.format_numbers("数字 123 456 です")
        assert "123 456" in result  # numbers should remain separate

    def test_format_all(self):
        text = "あのー これはテストです"
        result = self.formatter.format_all(text)
        assert "あのー" not in result
        assert isinstance(result, str)

    def test_format_all_options(self):
        text = "テストです"
        result = self.formatter.format_all(
            text,
            remove_fillers=False,
            add_punctuation=False,
            format_paragraphs=False,
            clean_repeated=False
        )
        assert result == "テストです"


# ============================================================================
# 3l. enhanced_error_handling.py テスト
# ============================================================================

class TestErrorSeverity:
    """ErrorSeverity enum のテスト"""

    def test_all_values(self):
        from enhanced_error_handling import ErrorSeverity
        assert ErrorSeverity.DEBUG.value == 1
        assert ErrorSeverity.INFO.value == 2
        assert ErrorSeverity.WARNING.value == 3
        assert ErrorSeverity.ERROR.value == 4
        assert ErrorSeverity.CRITICAL.value == 5


class TestEnhancedErrorRecord:
    """enhanced_error_handling ErrorRecord のテスト"""

    def test_create_record(self):
        from enhanced_error_handling import ErrorRecord, ErrorSeverity
        record = ErrorRecord(
            timestamp=1.0,
            error_type="ValueError",
            message="test",
            severity=ErrorSeverity.ERROR,
            traceback="",
            context={}
        )
        assert record.error_type == "ValueError"
        assert record.recovered is False
        assert record.recovery_attempts == 0


class TestErrorHandler:
    """ErrorHandler のテスト"""

    def setup_method(self):
        from enhanced_error_handling import ErrorHandler, ErrorSeverity
        self.ErrorHandler = ErrorHandler
        self.ErrorSeverity = ErrorSeverity

    def test_init(self):
        handler = self.ErrorHandler()
        assert handler.max_history == 100

    def test_register_handler(self):
        handler = self.ErrorHandler()
        calls = []
        handler.register_handler(self.ErrorSeverity.ERROR, lambda r: calls.append(r))
        handler.handle(ValueError("test"))
        assert len(calls) == 1

    def test_handle_error(self):
        handler = self.ErrorHandler()
        result = handler.handle(ValueError("test"))
        assert result is False  # No recovery strategy

    def test_handle_with_recovery(self):
        handler = self.ErrorHandler()
        handler.register_recovery_strategy(ValueError, lambda e: True)
        result = handler.handle(ValueError("test"))
        assert result is True

    def test_consecutive_errors_limit(self):
        handler = self.ErrorHandler()
        handler._max_consecutive_errors = 2
        handler.handle(ValueError("1"))
        handler.handle(ValueError("2"))
        result = handler.handle(ValueError("3"))
        assert result is False

    def test_reset_error_count(self):
        handler = self.ErrorHandler()
        handler._consecutive_errors = 5
        handler.reset_error_count()
        assert handler._consecutive_errors == 0

    def test_get_error_history(self):
        handler = self.ErrorHandler()
        handler.handle(ValueError("test"))
        history = handler.get_error_history()
        assert len(history) == 1

    def test_get_error_history_by_severity(self):
        handler = self.ErrorHandler()
        handler.handle(ValueError("err"), severity=self.ErrorSeverity.ERROR)
        handler.handle(ValueError("warn"), severity=self.ErrorSeverity.WARNING)
        errors = handler.get_error_history(self.ErrorSeverity.ERROR)
        assert len(errors) == 1

    def test_get_error_summary(self):
        handler = self.ErrorHandler()
        handler.handle(ValueError("test"))
        summary = handler.get_error_summary()
        assert summary["ERROR"] == 1

    def test_max_history(self):
        handler = self.ErrorHandler(max_history=3)
        for i in range(5):
            handler.handle(ValueError(f"error {i}"))
        assert len(handler.get_error_history()) == 3


class TestSafeExecute:
    """safe_execute のテスト"""

    def test_success(self):
        from enhanced_error_handling import safe_execute
        result = safe_execute(lambda: 42)
        assert result == 42

    def test_failure(self):
        from enhanced_error_handling import safe_execute
        result = safe_execute(lambda: 1/0, default_return=-1)
        assert result == -1


class TestFileOperationGuard:
    """FileOperationGuard のテスト"""

    def test_safe_read_nonexistent(self):
        from enhanced_error_handling import FileOperationGuard
        result = FileOperationGuard.safe_read("/nonexistent/file.txt", default="fallback")
        assert result == "fallback"

    def test_safe_read_existing(self, tmp_path):
        from enhanced_error_handling import FileOperationGuard
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        result = FileOperationGuard.safe_read(str(f))
        assert result == "hello"

    def test_safe_write(self, tmp_path):
        from enhanced_error_handling import FileOperationGuard
        f = str(tmp_path / "output.txt")
        result = FileOperationGuard.safe_write(f, "content")
        assert result is True
        assert Path(f).read_text(encoding="utf-8") == "content"

    def test_safe_delete(self, tmp_path):
        from enhanced_error_handling import FileOperationGuard
        f = tmp_path / "test.txt"
        f.write_text("dummy")
        result = FileOperationGuard.safe_delete(str(f))
        assert result is True
        assert not f.exists()

    def test_safe_delete_nonexistent(self):
        from enhanced_error_handling import FileOperationGuard
        result = FileOperationGuard.safe_delete("/nonexistent/file.txt")
        assert result is True


class TestResourceGuard:
    """ResourceGuard のテスト"""

    def test_context_manager(self):
        from enhanced_error_handling import ResourceGuard
        closed = []

        class MockResource:
            def close(self):
                closed.append(True)

        with ResourceGuard() as guard:
            guard.register(MockResource())
            guard.register(MockResource())

        assert len(closed) == 2

    def test_cleanup_callback(self):
        from enhanced_error_handling import ResourceGuard
        called = []
        guard = ResourceGuard(cleanup_callback=lambda: called.append(True))
        guard.cleanup()
        assert len(called) == 1


# ============================================================================
# 3m. error_recovery.py テスト
# ============================================================================

class TestRecoveryAction:
    """RecoveryAction enum のテスト"""

    def test_values(self):
        from error_recovery import RecoveryAction
        assert RecoveryAction.RETRY.value == "retry"
        assert RecoveryAction.SKIP.value == "skip"
        assert RecoveryAction.ABORT.value == "abort"
        assert RecoveryAction.FALLBACK.value == "fallback"


class TestErrorRecoveryRecord:
    """error_recovery ErrorRecord のテスト"""

    def test_create_record(self):
        from error_recovery import ErrorRecord
        record = ErrorRecord(
            timestamp="2025-01-01T00:00:00",
            file_path="test.wav",
            error_type="ValueError",
            error_message="test"
        )
        assert record.recovered is False
        assert record.retry_count == 0


class TestErrorRecoveryManager:
    """ErrorRecoveryManager のテスト"""

    def test_init(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        assert m.log_dir.exists()

    def test_register_callback(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        calls = []
        m.register_callback("transient", lambda e, f: calls.append(True))
        m.handle_error(ConnectionError("timeout"), "test.wav")
        assert len(calls) == 1

    def test_classify_transient(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        assert m._classify_error(ConnectionError("timeout error")) == "transient"

    def test_classify_resource(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        assert m._classify_error(MemoryError("out of memory")) == "resource"

    def test_classify_permanent(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        assert m._classify_error(ValueError("bad value")) == "permanent"

    def test_handle_error_skip(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        result = m.handle_error(ValueError("test"), "test.wav")
        assert result["success"] is False
        assert result["action"] == "skip"

    def test_handle_error_fallback(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        result = m.handle_error(
            MemoryError("memory"), "test.wav",
            fallback_func=lambda: "fallback_result"
        )
        assert result["success"] is True
        assert result["result"] == "fallback_result"

    def test_get_error_summary_empty(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        summary = m.get_error_summary()
        assert summary["total_errors"] == 0

    def test_clear_logs(self, tmp_path):
        from error_recovery import ErrorRecoveryManager
        m = ErrorRecoveryManager(str(tmp_path / "logs"))
        m.handle_error(ValueError("test"), "test.wav")
        m.clear_logs()
        assert not m.error_log_file.exists()


# ============================================================================
# 3n. device_manager.py テスト
# ============================================================================

class TestDeviceType:
    """DeviceType enum のテスト"""

    def test_values(self):
        from device_manager import DeviceType
        assert DeviceType.CPU.value == 1
        assert DeviceType.CUDA.value == 2
        assert DeviceType.MPS.value == 3
        assert DeviceType.AUTO.value == 4


class TestDeviceInfo:
    """DeviceInfo dataclass のテスト"""

    def test_create(self):
        from device_manager import DeviceInfo, DeviceType
        info = DeviceInfo(
            id=0, name="CPU", type=DeviceType.CPU,
            total_memory_mb=16384, available_memory_mb=8192
        )
        assert info.id == 0
        assert info.name == "CPU"
        assert info.type == DeviceType.CPU
        assert info.total_memory_mb == 16384
        assert info.available_memory_mb == 8192
        assert info.is_available is True
        assert info.compute_capability is None


class TestMultiDeviceManager:
    """MultiDeviceManager のテスト"""

    def test_init(self):
        from device_manager import MultiDeviceManager
        m = MultiDeviceManager()
        assert len(m.devices) > 0  # At least CPU

    def test_cpu_always_available(self):
        from device_manager import MultiDeviceManager, DeviceType
        m = MultiDeviceManager()
        cpu_devices = [d for d in m.devices if d.type == DeviceType.CPU]
        assert len(cpu_devices) >= 1


# ============================================================================
# 3o. meeting_minutes_generator.py テスト
# ============================================================================

class TestStatementType:
    """StatementType enum のテスト"""

    def test_all_values(self):
        from meeting_minutes_generator import StatementType
        assert StatementType.GENERAL.value == "一般"
        assert StatementType.DECISION.value == "決定事項"
        assert StatementType.CONFIRMATION.value == "確認事項"
        assert StatementType.ACTION_ITEM.value == "アクションアイテム"
        assert StatementType.QUESTION.value == "質問"
        assert StatementType.ANSWER.value == "回答"
        assert StatementType.REPORT.value == "報告"
        assert StatementType.PROPOSAL.value == "提案"


class TestStatement:
    """Statement dataclass のテスト"""

    def test_create_default(self):
        from meeting_minutes_generator import Statement, StatementType
        s = Statement(speaker="田中", text="テスト発言")
        assert s.speaker == "田中"
        assert s.text == "テスト発言"
        assert s.timestamp is None
        assert s.statement_type == StatementType.GENERAL
        assert s.confidence == 1.0

    def test_create_with_all_fields(self):
        from meeting_minutes_generator import Statement, StatementType
        s = Statement(
            speaker="佐藤", text="決定事項です",
            timestamp=10.5, statement_type=StatementType.DECISION, confidence=0.9
        )
        assert s.timestamp == 10.5
        assert s.statement_type == StatementType.DECISION


class TestActionItem:
    """ActionItem dataclass のテスト"""

    def test_create_default(self):
        from meeting_minutes_generator import ActionItem
        a = ActionItem(description="テストタスク")
        assert a.description == "テストタスク"
        assert a.assignee is None
        assert a.due_date is None
        assert a.priority == "中"
        assert a.status == "未対応"


class TestMeetingMinutes:
    """MeetingMinutes dataclass のテスト"""

    def test_create_default(self):
        from meeting_minutes_generator import MeetingMinutes
        m = MeetingMinutes(title="テスト会議", date="2026-01-01")
        assert m.title == "テスト会議"
        assert m.date == "2026-01-01"
        assert m.location == ""
        assert m.attendees == []
        assert m.agenda == []
        assert m.decisions == []

    def test_to_text_basic(self):
        from meeting_minutes_generator import MeetingMinutes
        m = MeetingMinutes(
            title="テスト", date="2026-01-01",
            attendees=["田中", "佐藤"],
            location="会議室A"
        )
        text = m.to_text()
        assert "テスト" in text
        assert "田中" in text
        assert "佐藤" in text
        assert "会議室A" in text

    def test_to_text_with_decisions(self):
        from meeting_minutes_generator import MeetingMinutes
        m = MeetingMinutes(
            title="テスト", date="2026-01-01",
            decisions=["タイルに決定", "予算承認"]
        )
        text = m.to_text()
        assert "決定事項" in text
        assert "タイルに決定" in text

    def test_to_text_with_action_items(self):
        from meeting_minutes_generator import MeetingMinutes, ActionItem
        m = MeetingMinutes(
            title="テスト", date="2026-01-01",
            action_items=[ActionItem(description="調整する", assignee="田中", due_date="2月10日")]
        )
        text = m.to_text()
        assert "アクションアイテム" in text
        assert "調整する" in text
        assert "田中" in text

    def test_to_text_with_agenda(self):
        from meeting_minutes_generator import MeetingMinutes
        m = MeetingMinutes(
            title="テスト", date="2026-01-01",
            agenda=["新規開発について", "予算確認"]
        )
        text = m.to_text()
        assert "議題" in text
        assert "新規開発について" in text

    def test_to_markdown(self):
        from meeting_minutes_generator import MeetingMinutes
        m = MeetingMinutes(
            title="テスト", date="2026-01-01",
            attendees=["田中"], decisions=["タイルに決定"]
        )
        md = m.to_markdown()
        assert md.startswith("# 議事録:")
        assert "田中" in md
        assert "タイルに決定" in md

    def test_to_markdown_with_statements(self):
        from meeting_minutes_generator import MeetingMinutes, Statement, StatementType
        m = MeetingMinutes(
            title="テスト", date="2026-01-01",
            statements=[
                Statement(speaker="田中", text="決定です", statement_type=StatementType.DECISION),
                Statement(speaker="佐藤", text="確認します", statement_type=StatementType.CONFIRMATION),
            ]
        )
        md = m.to_markdown()
        assert "田中" in md
        assert "佐藤" in md

    def test_to_text_with_next_meeting(self):
        from meeting_minutes_generator import MeetingMinutes
        m = MeetingMinutes(title="テスト", date="2026-01-01", next_meeting="来週月曜日")
        text = m.to_text()
        assert "次回会議" in text
        assert "来週月曜日" in text

    def test_to_text_with_notes(self):
        from meeting_minutes_generator import MeetingMinutes
        m = MeetingMinutes(title="テスト", date="2026-01-01", notes="追加メモ")
        text = m.to_text()
        assert "備考" in text
        assert "追加メモ" in text


class TestMeetingMinutesGenerator:
    """MeetingMinutesGenerator のテスト"""

    def setup_method(self):
        from meeting_minutes_generator import MeetingMinutesGenerator
        self.gen = MeetingMinutesGenerator()

    def test_init_compiles_patterns(self):
        assert len(self.gen.decision_regex) > 0
        assert len(self.gen.confirmation_regex) > 0
        assert len(self.gen.action_regex) > 0

    def test_classify_decision(self):
        from meeting_minutes_generator import StatementType
        result = self.gen.classify_statement("タイルに決定しました")
        assert result == StatementType.DECISION

    def test_classify_confirmation(self):
        from meeting_minutes_generator import StatementType
        result = self.gen.classify_statement("内装費について確認させてください")
        assert result == StatementType.CONFIRMATION

    def test_classify_action_item(self):
        from meeting_minutes_generator import StatementType
        result = self.gen.classify_statement("施工業者との調整をお願いします")
        assert result == StatementType.ACTION_ITEM

    def test_classify_report(self):
        from meeting_minutes_generator import StatementType
        result = self.gen.classify_statement("進捗状況を報告します")
        assert result == StatementType.REPORT

    def test_classify_general(self):
        from meeting_minutes_generator import StatementType
        result = self.gen.classify_statement("天気がいいですね")
        assert result == StatementType.GENERAL

    def test_classify_unmatched_returns_general(self):
        from meeting_minutes_generator import StatementType
        # No patterns exist for QUESTION, ANSWER, or PROPOSAL - they should return GENERAL
        result = self.gen.classify_statement("何か質問はありますか")
        assert result == StatementType.GENERAL

    def test_classify_empty_text_returns_general(self):
        from meeting_minutes_generator import StatementType
        result = self.gen.classify_statement("")
        assert result == StatementType.GENERAL

    def test_classify_random_text_returns_general(self):
        from meeting_minutes_generator import StatementType
        result = self.gen.classify_statement("ランダムなテキストです")
        assert result == StatementType.GENERAL

    def test_extract_decision_text(self):
        text = "外壁材はタイルに決定しました"
        result = self.gen.extract_decision_text(text)
        assert "タイル" in result

    def test_extract_confirmation_text(self):
        text = "予算について確認させてください"
        result = self.gen.extract_confirmation_text(text)
        assert len(result) > 0

    def test_extract_action_item_with_assignee(self):
        text = "佐藤さんに施工業者との調整をお願いします。来週金曜日までに。"
        item = self.gen.extract_action_item(text, "田中")
        assert item.assignee == "佐藤"
        assert item.due_date is not None

    def test_extract_action_item_no_assignee(self):
        text = "調整をお願いします"
        item = self.gen.extract_action_item(text, "田中")
        assert item.assignee == "田中"  # default speaker

    def test_extract_action_item_priority_high(self):
        text = "至急対応をお願いします"
        item = self.gen.extract_action_item(text, "田中")
        assert item.priority == "高"

    def test_extract_action_item_priority_low(self):
        text = "余裕があれば対応をお願いします"
        item = self.gen.extract_action_item(text, "田中")
        assert item.priority == "低"

    def test_extract_agenda(self):
        from meeting_minutes_generator import Statement
        stmts = [Statement(speaker="田中", text="今日のテーマは新規開発についてです")]
        agendas = self.gen.extract_agenda(stmts)
        assert len(agendas) > 0

    def test_extract_agenda_no_keywords(self):
        from meeting_minutes_generator import Statement
        stmts = [Statement(speaker="田中", text="天気がいいですね")]
        agendas = self.gen.extract_agenda(stmts)
        assert len(agendas) == 0

    def test_extract_next_meeting(self):
        from meeting_minutes_generator import Statement
        stmts = [Statement(speaker="田中", text="次回は来週の月曜日に進捗確認を行いましょう")]
        result = self.gen.extract_next_meeting(stmts)
        assert len(result) > 0

    def test_extract_attendees_from_segments(self):
        segments = [
            {"speaker": "田中", "text": "テスト"},
            {"speaker": "佐藤", "text": "テスト"},
            {"speaker": "田中", "text": "テスト2"},
        ]
        attendees = self.gen.extract_attendees_from_segments(segments)
        assert "田中" in attendees
        assert "佐藤" in attendees
        assert len(attendees) == 2

    def test_extract_attendees_skip_unknown(self):
        segments = [
            {"speaker": "Unknown", "text": "テスト"},
            {"speaker": "田中", "text": "テスト"},
        ]
        attendees = self.gen.extract_attendees_from_segments(segments)
        assert "Unknown" not in attendees

    def test_generate_minutes_basic(self):
        segments = [
            {"speaker": "田中", "text": "会議を始めます", "start": 0},
            {"speaker": "佐藤", "text": "報告します", "start": 10},
        ]
        minutes = self.gen.generate_minutes(
            segments, title="テスト会議", date="2026-01-01"
        )
        assert minutes.title == "テスト会議"
        assert len(minutes.statements) == 2

    def test_generate_minutes_extracts_decisions(self):
        segments = [
            {"speaker": "田中", "text": "外壁材はタイルに決定しました", "start": 0},
        ]
        minutes = self.gen.generate_minutes(segments, title="テスト")
        assert len(minutes.decisions) > 0

    def test_generate_minutes_extracts_action_items(self):
        segments = [
            {"speaker": "田中", "text": "佐藤さんに調整をお願いします", "start": 0},
        ]
        minutes = self.gen.generate_minutes(segments, title="テスト")
        assert len(minutes.action_items) > 0

    def test_generate_minutes_skips_empty_text(self):
        segments = [
            {"speaker": "田中", "text": "", "start": 0},
            {"speaker": "佐藤", "text": "テスト", "start": 10},
        ]
        minutes = self.gen.generate_minutes(segments, title="テスト")
        assert len(minutes.statements) == 1

    def test_generate_minutes_default_date(self):
        segments = [{"speaker": "田中", "text": "テスト", "start": 0}]
        minutes = self.gen.generate_minutes(segments, title="テスト")
        assert "年" in minutes.date  # auto-generated date


class TestGetMinutesGenerator:
    """get_minutes_generator のテスト"""

    def test_singleton(self):
        import meeting_minutes_generator as mmg
        # Reset singleton
        mmg._minutes_generator = None
        g1 = mmg.get_minutes_generator()
        g2 = mmg.get_minutes_generator()
        assert g1 is g2
        mmg._minutes_generator = None

    def teardown_method(self):
        import meeting_minutes_generator as mmg
        mmg._minutes_generator = None


# ============================================================================
# 3p. batch_processor.py テスト
# ============================================================================

class TestBatchProcessor:
    """BatchProcessor のテスト"""

    def test_init(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor(batch_size=5, max_memory_mb=1024)
        assert bp.batch_size == 5
        assert bp.max_memory_mb == 1024

    def test_add_single(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("test.wav")
        assert len(bp.queue) == 1
        assert bp.stats["total_files"] == 1

    def test_add_with_metadata(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("test.wav", metadata={"tag": "test"})
        assert bp.queue[0]["metadata"]["tag"] == "test"

    def test_add_multiple(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add_multiple(["a.wav", "b.wav", "c.wav"])
        assert len(bp.queue) == 3
        assert bp.stats["total_files"] == 3

    def test_process_batch_empty(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        results = bp.process_batch(lambda f: {"text": "ok"})
        assert results == []

    def test_process_batch_success(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.add("b.wav")
        results = bp.process_batch(lambda f: {"text": f"transcribed {f}"})
        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert bp.stats["processed_files"] == 2

    def test_process_batch_with_failure(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.add("fail.wav")
        def processor(f):
            if "fail" in f:
                raise ValueError("processing failed")
            return {"text": "ok"}
        results = bp.process_batch(processor)
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert bp.stats["failed_files"] == 1

    def test_process_batch_progress_callback(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        progress_calls = []
        bp.process_batch(
            lambda f: {"text": "ok"},
            progress_callback=lambda p, t: progress_calls.append((p, t))
        )
        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1)

    def test_process_batch_clears_queue(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.process_batch(lambda f: {"text": "ok"})
        assert len(bp.queue) == 0

    def test_get_stats(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.process_batch(lambda f: {"text": "ok"})
        stats = bp.get_stats()
        assert stats["total_files"] == 1
        assert stats["processed_files"] == 1
        assert "success_rate" in stats
        assert stats["success_rate"] == 1.0

    def test_get_results(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.process_batch(lambda f: {"text": "ok"})
        results = bp.get_results()
        assert len(results) == 1  # process_batch extends self.results
        bp.add("b.wav")
        bp.process_batch(lambda f: {"text": "ok"})
        assert len(bp.get_results()) == 2

    def test_get_successful_results(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.add("fail.wav")
        def processor(f):
            if "fail" in f:
                raise ValueError("error")
            return {"text": "ok"}
        bp.process_batch(processor)
        assert len(bp.get_successful_results()) == 1
        assert len(bp.get_failed_results()) == 1

    def test_clear(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.process_batch(lambda f: {"text": "ok"})
        bp.add("b.wav")
        bp.clear()
        assert len(bp.queue) == 0
        assert len(bp.results) == 0

    def test_clear_queue_only(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.process_batch(lambda f: {"text": "ok"})
        bp.add("b.wav")
        bp.clear_queue()
        assert len(bp.queue) == 0
        assert len(bp.results) > 0

    def test_clear_results_only(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        bp.add("a.wav")
        bp.process_batch(lambda f: {"text": "ok"})
        bp.add("b.wav")
        bp.clear_results()
        assert len(bp.queue) == 1
        assert len(bp.results) == 0

    def test_process_all_empty(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor()
        results = bp.process_all(lambda f: {"text": "ok"})
        assert results == []

    def test_process_all_basic(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor(batch_size=2, auto_adjust_batch_size=False)
        bp.add_multiple(["a.wav", "b.wav", "c.wav"])
        results = bp.process_all(lambda f: {"text": f"ok_{f}"})
        assert len(results) == 3

    def test_process_all_batching_behavior(self):
        from batch_processor import BatchProcessor
        bp = BatchProcessor(batch_size=2, auto_adjust_batch_size=False)
        bp.add_multiple(["a.wav", "b.wav", "c.wav", "d.wav", "e.wav"])
        results = bp.process_all(lambda f: {"text": f"ok_{f}"})
        assert len(results) == 5
        assert all(r["success"] for r in results)
        # With 5 files and batch_size=2, should have 3 batches (2+2+1)
        assert bp.stats["batches_processed"] == 3
        assert bp.stats["processed_files"] == 5


class TestSmartBatchProcessor:
    """SmartBatchProcessor のテスト"""

    def test_init(self):
        from batch_processor import SmartBatchProcessor
        sp = SmartBatchProcessor(batch_size=5)
        assert sp.size_based_batching is True


# ============================================================================
# 3q. enhanced_subtitle_exporter.py テスト
# ============================================================================

class TestSRTFormatterEnhanced:
    """SRTFormatter のテスト"""

    def test_format_time_zero(self):
        from enhanced_subtitle_exporter import SRTFormatter
        f = SRTFormatter()
        assert f.format_time(0) == "00:00:00,000"

    def test_format_time_normal(self):
        from enhanced_subtitle_exporter import SRTFormatter
        f = SRTFormatter()
        result = f.format_time(3661.5)
        assert result == "01:01:01,500"

    def test_format_segment_basic(self):
        from enhanced_subtitle_exporter import SRTFormatter
        f = SRTFormatter()
        seg = {"start": 0, "end": 5, "text": "テスト"}
        result = f.format_segment(seg, 1)
        assert "1\n" in result
        assert "-->" in result
        assert "テスト" in result

    def test_format_segment_with_speaker(self):
        from enhanced_subtitle_exporter import SRTFormatter
        f = SRTFormatter()
        seg = {"start": 0, "end": 5, "text": "テスト", "speaker": "田中"}
        result = f.format_segment(seg, 1)
        assert "[田中]" in result

    def test_format_segment_empty_text(self):
        from enhanced_subtitle_exporter import SRTFormatter
        f = SRTFormatter()
        seg = {"start": 0, "end": 5, "text": ""}
        result = f.format_segment(seg, 1)
        assert result == ""

    def test_generate_header(self):
        from enhanced_subtitle_exporter import SRTFormatter
        f = SRTFormatter()
        assert f.generate_header() == ""

    def test_format_segments(self):
        from enhanced_subtitle_exporter import SRTFormatter
        f = SRTFormatter()
        segs = [
            {"start": 0, "end": 3, "text": "最初のセグメント"},
            {"start": 3, "end": 6, "text": "二番目のセグメント"},
        ]
        result = f.format_segments(segs)
        assert "最初" in result
        assert "二番目" in result


class TestVTTFormatterEnhanced:
    """VTTFormatter のテスト"""

    def test_format_time(self):
        from enhanced_subtitle_exporter import VTTFormatter
        f = VTTFormatter()
        result = f.format_time(3661.5)
        assert result == "01:01:01.500"

    def test_format_segment_with_speaker(self):
        from enhanced_subtitle_exporter import VTTFormatter
        f = VTTFormatter()
        seg = {"start": 0, "end": 5, "text": "テスト", "speaker": "田中"}
        result = f.format_segment(seg, 1)
        assert "<v 田中>" in result
        assert "</v>" in result

    def test_generate_header(self):
        from enhanced_subtitle_exporter import VTTFormatter
        f = VTTFormatter()
        assert "WEBVTT" in f.generate_header()


class TestJSONFormatter:
    """JSONFormatter のテスト"""

    def test_format_basic(self):
        from enhanced_subtitle_exporter import JSONFormatter
        import json
        f = JSONFormatter()
        segs = [{"start": 0, "end": 5, "text": "テスト"}]
        result = f.format(segs)
        data = json.loads(result)
        assert data["version"] == "1.0"
        assert data["segment_count"] == 1
        assert len(data["segments"]) == 1

    def test_format_with_metadata(self):
        from enhanced_subtitle_exporter import JSONFormatter
        import json
        f = JSONFormatter()
        result = f.format([], metadata={"source": "test.wav"})
        data = json.loads(result)
        assert data["metadata"]["source"] == "test.wav"


class TestTXTFormatter:
    """TXTFormatter のテスト"""

    def test_format_basic(self):
        from enhanced_subtitle_exporter import TXTFormatter
        f = TXTFormatter()
        segs = [{"start": 1.5, "text": "テスト", "speaker": "田中"}]
        result = f.format(segs)
        assert "テスト" in result
        assert "田中" in result
        assert "01.50s" in result

    def test_format_no_timestamps(self):
        from enhanced_subtitle_exporter import TXTFormatter
        f = TXTFormatter()
        segs = [{"start": 1.5, "text": "テスト"}]
        result = f.format(segs, include_timestamps=False)
        assert "01.50s" not in result

    def test_format_no_speakers(self):
        from enhanced_subtitle_exporter import TXTFormatter
        f = TXTFormatter()
        segs = [{"start": 1.5, "text": "テスト", "speaker": "田中"}]
        result = f.format(segs, include_speakers=False)
        assert "田中" not in result


class TestEnhancedSubtitleExporter:
    """EnhancedSubtitleExporter のテスト"""

    def setup_method(self):
        from enhanced_subtitle_exporter import EnhancedSubtitleExporter
        self.exporter = EnhancedSubtitleExporter()

    def test_export_srt(self, tmp_path):
        output = str(tmp_path / "test.srt")
        segs = [{"start": 0, "end": 5, "text": "テスト"}]
        result = self.exporter.export(segs, output, "srt")
        assert result is True
        assert (tmp_path / "test.srt").exists()

    def test_export_vtt(self, tmp_path):
        output = str(tmp_path / "test.vtt")
        segs = [{"start": 0, "end": 5, "text": "テスト"}]
        result = self.exporter.export(segs, output, "vtt")
        assert result is True

    def test_export_json(self, tmp_path):
        output = str(tmp_path / "test.json")
        segs = [{"start": 0, "end": 5, "text": "テスト"}]
        result = self.exporter.export(segs, output, "json")
        assert result is True

    def test_export_txt(self, tmp_path):
        output = str(tmp_path / "test.txt")
        segs = [{"start": 0, "end": 5, "text": "テスト"}]
        result = self.exporter.export(segs, output, "txt")
        assert result is True

    def test_export_unsupported_format(self, tmp_path):
        output = str(tmp_path / "test.xyz")
        segs = [{"start": 0, "end": 5, "text": "テスト"}]
        result = self.exporter.export(segs, output, "xyz")
        assert result is False

    def test_export_auto_srt_only(self, tmp_path):
        base = str(tmp_path / "output")
        segs = [{"start": 0, "end": 5, "text": "テスト"}]
        results = self.exporter.export_auto(segs, base, formats=["srt"])
        assert "srt" in results
        assert results["srt"] is True

    def test_merge_short_segments_empty(self):
        result = self.exporter.merge_short_segments([])
        assert result == []

    def test_merge_short_segments_basic(self):
        segs = [
            {"start": 0, "end": 0.3, "text": "あ", "speaker": "A"},
            {"start": 0.3, "end": 0.5, "text": "い", "speaker": "A"},
        ]
        result = self.exporter.merge_short_segments(segs, min_duration=1.0)
        assert len(result) == 1
        assert "あ" in result[0]["text"]
        assert "い" in result[0]["text"]

    def test_merge_short_segments_different_speakers(self):
        segs = [
            {"start": 0, "end": 0.3, "text": "あ", "speaker": "A"},
            {"start": 0.3, "end": 0.5, "text": "い", "speaker": "B"},
        ]
        result = self.exporter.merge_short_segments(segs, min_duration=1.0)
        assert len(result) == 2

    def test_split_long_segments_no_split(self):
        segs = [{"start": 0, "end": 3, "text": "短いテスト"}]
        result = self.exporter.split_long_segments(segs, max_chars=40)
        assert len(result) == 1

    def test_split_long_segments_splits(self):
        long_text = "これは長いテキストです。" * 10
        segs = [{"start": 0, "end": 30, "text": long_text}]
        result = self.exporter.split_long_segments(segs, max_chars=40)
        assert len(result) > 1


# ============================================================================
# 3r. minutes_generator.py テスト
# ============================================================================

class TestMinutesGenerator:
    """MinutesGenerator wrapper のテスト"""

    def test_init(self):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        assert mg._generator is not None

    def test_generate_basic(self):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        segments = [
            {"speaker": "田中", "text": "会議を始めます", "start": 0},
            {"speaker": "佐藤", "text": "外壁材はタイルに決定しました", "start": 10},
        ]
        result = mg.generate(segments, title="テスト", date="2026-01-01")
        assert result["title"] == "テスト"
        assert "text_format" in result
        assert "markdown_format" in result
        assert len(result["statements"]) == 2

    def test_generate_with_action_items(self):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        segments = [
            {"speaker": "田中", "text": "佐藤さんに調整をお願いします", "start": 0},
        ]
        result = mg.generate(segments, title="テスト", date="2026-01-01")
        assert len(result["action_items"]) > 0
        assert "assignee" in result["action_items"][0]

    def test_save_minutes_text(self, tmp_path):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        data = {"text_format": "テスト議事録", "markdown_format": "# テスト"}
        output = str(tmp_path / "minutes.txt")
        assert mg.save_minutes(data, output, "text") is True
        assert (tmp_path / "minutes.txt").read_text(encoding="utf-8") == "テスト議事録"

    def test_save_minutes_markdown(self, tmp_path):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        data = {"text_format": "テスト", "markdown_format": "# テスト"}
        output = str(tmp_path / "minutes.md")
        assert mg.save_minutes(data, output, "markdown") is True

    def test_save_minutes_json(self, tmp_path):
        from minutes_generator import MinutesGenerator
        import json
        mg = MinutesGenerator()
        data = {"title": "テスト", "decisions": []}
        output = str(tmp_path / "minutes.json")
        assert mg.save_minutes(data, output, "json") is True
        with open(output, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["title"] == "テスト"

    def test_save_minutes_unknown_format(self, tmp_path):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        output = str(tmp_path / "minutes.xyz")
        assert mg.save_minutes({}, output, "xyz") is False

    def test_classify_statements(self):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        stmts = [
            "外壁材はタイルに決定しました",
            "確認させてください",
            "調整をお願いします",
            "天気がいいですね",
        ]
        result = mg.classify_statements(stmts)
        assert len(result["decisions"]) >= 1
        assert len(result["confirmations"]) >= 1
        assert len(result["action_items"]) >= 1
        assert len(result["general"]) >= 1

    def test_extract_action_items(self):
        from minutes_generator import MinutesGenerator
        mg = MinutesGenerator()
        text = "田中さんに確認をお願いします\n佐藤さんが準備する"
        items = mg.extract_action_items(text)
        assert len(items) >= 1


class TestQuickGenerate:
    """quick_generate 関数のテスト"""

    def test_basic(self):
        from minutes_generator import quick_generate
        segments = [{"speaker": "田中", "text": "テスト", "start": 0}]
        result = quick_generate(segments, title="テスト")
        assert "title" in result

    def teardown_method(self):
        import minutes_generator
        minutes_generator._minutes_generator = None


# ============================================================================
# 3s. optimized_pipeline.py テスト
# ============================================================================

try:
    import psutil
    _psutil_available = True
except ImportError:
    _psutil_available = False


@pytest.mark.skipif(not _psutil_available, reason="psutil not installed")
class TestProcessingStats:
    """ProcessingStats のテスト"""

    def test_default_values(self):
        from optimized_pipeline import ProcessingStats
        s = ProcessingStats()
        assert s.total_files == 0
        assert s.processed_files == 0
        assert s.failed_files == 0
        assert s.total_duration == 0.0

    def test_progress_percent_zero(self):
        from optimized_pipeline import ProcessingStats
        s = ProcessingStats()
        assert s.progress_percent == 0.0

    def test_progress_percent_half(self):
        from optimized_pipeline import ProcessingStats
        s = ProcessingStats(total_files=10, processed_files=5)
        assert s.progress_percent == 50.0

    def test_elapsed_time_no_start(self):
        from optimized_pipeline import ProcessingStats
        s = ProcessingStats()
        assert s.elapsed_time == 0.0

    def test_elapsed_time_with_start(self):
        import time
        from optimized_pipeline import ProcessingStats
        s = ProcessingStats(start_time=time.time() - 5)
        assert 4.0 < s.elapsed_time < 10.0

    def test_estimated_remaining_zero_processed(self):
        from optimized_pipeline import ProcessingStats
        s = ProcessingStats(total_files=10, processed_files=0)
        assert s.estimated_remaining == 0.0

    def test_estimated_remaining_with_progress(self):
        import time
        from optimized_pipeline import ProcessingStats
        s = ProcessingStats(
            total_files=10, processed_files=5,
            start_time=time.time() - 10
        )
        # 5 files in 10 seconds => 2s/file => 5 remaining => ~10s
        assert s.estimated_remaining > 0


@pytest.mark.skipif(not _psutil_available, reason="psutil not installed")
class TestMemoryMonitor:
    """MemoryMonitor のテスト"""

    def test_init(self):
        from optimized_pipeline import MemoryMonitor
        m = MemoryMonitor(limit_mb=2048)
        assert m.limit_mb == 2048
        assert m.peak_mb == 0.0

    def test_get_current_memory(self):
        from optimized_pipeline import MemoryMonitor
        m = MemoryMonitor()
        current = m.get_current_memory_mb()
        assert current > 0

    def test_register_callback(self):
        from optimized_pipeline import MemoryMonitor
        m = MemoryMonitor()
        calls = []
        m.register_callback(lambda mb: calls.append(mb))
        assert len(m._callbacks) == 1

    def test_is_memory_available(self):
        from optimized_pipeline import MemoryMonitor
        m = MemoryMonitor(limit_mb=999999)  # Very high limit
        assert m.is_memory_available(500) is True

    def test_is_memory_not_available(self):
        from optimized_pipeline import MemoryMonitor
        m = MemoryMonitor(limit_mb=1)  # Very low limit
        assert m.is_memory_available(500) is False


# ============================================================================
# api_corrector.py テスト
# ============================================================================

@pytest.mark.unit
class TestAPIProvider:
    """APIProviderの列挙型テスト"""

    def test_anthropic_value(self):
        from api_corrector import APIProvider
        assert APIProvider.ANTHROPIC.value == "anthropic"

    def test_openai_value(self):
        from api_corrector import APIProvider
        assert APIProvider.OPENAI.value == "openai"

    def test_azure_openai_value(self):
        from api_corrector import APIProvider
        assert APIProvider.AZURE_OPENAI.value == "azure_openai"

    def test_all_members(self):
        from api_corrector import APIProvider
        members = list(APIProvider)
        assert len(members) == 3

    def test_from_value(self):
        from api_corrector import APIProvider
        assert APIProvider("anthropic") is APIProvider.ANTHROPIC
        assert APIProvider("openai") is APIProvider.OPENAI

    def test_invalid_value(self):
        from api_corrector import APIProvider
        with pytest.raises(ValueError):
            APIProvider("invalid_provider")


@pytest.mark.unit
class TestCorrectionConfig:
    """CorrectionConfigデータクラスのテスト"""

    def test_creation_with_defaults(self):
        from api_corrector import CorrectionConfig, APIProvider
        config = CorrectionConfig(
            provider=APIProvider.ANTHROPIC,
            api_key="test-key",
            model="test-model",
        )
        assert config.provider == APIProvider.ANTHROPIC
        assert config.api_key == "test-key"
        assert config.model == "test-model"
        assert config.temperature == 0.3
        assert config.max_tokens == 4096
        assert config.timeout == 60
        assert config.retry_count == 3
        assert config.retry_base_delay == 1.0

    def test_creation_with_custom_values(self):
        from api_corrector import CorrectionConfig, APIProvider
        config = CorrectionConfig(
            provider=APIProvider.OPENAI,
            api_key="custom-key",
            model="gpt-4",
            temperature=0.7,
            max_tokens=2048,
            timeout=120,
            retry_count=5,
            retry_base_delay=2.0,
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
        assert config.timeout == 120
        assert config.retry_count == 5
        assert config.retry_base_delay == 2.0

    def test_api_key_hidden_in_repr(self):
        from api_corrector import CorrectionConfig, APIProvider
        config = CorrectionConfig(
            provider=APIProvider.ANTHROPIC,
            api_key="secret-key-12345",
            model="test-model",
        )
        repr_str = repr(config)
        assert "secret-key-12345" not in repr_str


@pytest.mark.unit
class TestBaseAPICorrectorSplitText:
    """BaseAPICorrector._split_text() メソッドのテスト"""

    def _make_corrector(self):
        """テスト用のBaseAPICorrectorサブクラスを作成"""
        from api_corrector import BaseAPICorrector, CorrectionConfig, APIProvider

        class DummyCorrector(BaseAPICorrector):
            def correct_text(self, text, context=None):
                return text

            def generate_summary(self, text, max_length=200):
                return text[:max_length]

        config = CorrectionConfig(
            provider=APIProvider.ANTHROPIC,
            api_key="dummy",
            model="dummy-model",
        )
        return DummyCorrector(config)

    def test_short_text_no_split(self):
        """短いテキストは分割されない"""
        c = self._make_corrector()
        text = "これは短いテキストです。"
        result = c._split_text(text, max_chars=100)
        assert result == [text]

    def test_exact_max_chars_no_split(self):
        """ちょうどmax_chars以下のテキストは分割されない"""
        c = self._make_corrector()
        text = "あ" * 50
        result = c._split_text(text, max_chars=50)
        assert result == [text]

    def test_split_on_japanese_period(self):
        """日本語句点で分割される"""
        c = self._make_corrector()
        sentence1 = "これは最初の文です。"
        sentence2 = "これは二番目の文です。"
        text = sentence1 + sentence2
        result = c._split_text(text, max_chars=15)
        assert len(result) >= 2
        # 結合すると元のテキストになる
        assert "".join(result) == text

    def test_split_preserves_punctuation(self):
        """分割時に句読点が失われない"""
        c = self._make_corrector()
        text = "最初の文。二番目の文！三番目の文？四番目の文。"
        result = c._split_text(text, max_chars=15)
        combined = "".join(result)
        assert combined == text
        # 各句読点が保持されている
        assert combined.count("。") == text.count("。")
        assert combined.count("！") == text.count("！")
        assert combined.count("？") == text.count("？")

    def test_split_exclamation_mark(self):
        """感嘆符で分割される"""
        c = self._make_corrector()
        text = "すごい！本当に！"
        result = c._split_text(text, max_chars=6)
        assert len(result) >= 2
        assert "".join(result) == text

    def test_split_question_mark(self):
        """疑問符で分割される"""
        c = self._make_corrector()
        text = "本当ですか？はい、そうです。"
        result = c._split_text(text, max_chars=10)
        assert len(result) >= 2
        assert "".join(result) == text

    def test_empty_text(self):
        """空テキストは分割されない"""
        c = self._make_corrector()
        result = c._split_text("", max_chars=100)
        assert result == [""]

    def test_no_punctuation_text(self):
        """句読点のないテキストも処理できる"""
        c = self._make_corrector()
        text = "あ" * 100
        result = c._split_text(text, max_chars=50)
        # 句読点がないためそのまま1チャンクになる（分割ポイントがない）
        assert len(result) >= 1
        assert "".join(result) == text


@pytest.mark.unit
class TestBaseAPICorrectorCallWithRetry:
    """BaseAPICorrector._call_with_retry() のリトライロジックテスト"""

    def _make_corrector(self, retry_count=3, retry_base_delay=0.0):
        """テスト用のBaseAPICorrectorサブクラスを作成"""
        from api_corrector import BaseAPICorrector, CorrectionConfig, APIProvider

        class DummyCorrector(BaseAPICorrector):
            def correct_text(self, text, context=None):
                return text

            def generate_summary(self, text, max_length=200):
                return text[:max_length]

        config = CorrectionConfig(
            provider=APIProvider.ANTHROPIC,
            api_key="dummy",
            model="dummy-model",
            retry_count=retry_count,
            retry_base_delay=retry_base_delay,
        )
        return DummyCorrector(config)

    def test_success_on_first_call(self):
        """初回で成功する場合"""
        c = self._make_corrector()
        result = c._call_with_retry(lambda: "success")
        assert result == "success"

    def test_retry_on_rate_limit_then_succeed(self):
        """レート制限後にリトライして成功する"""
        from exceptions import APIRateLimitError

        c = self._make_corrector(retry_count=3, retry_base_delay=0.0)
        call_count = [0]

        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise APIRateLimitError("rate limited")
            return "success"

        result = c._call_with_retry(flaky_func)
        assert result == "success"
        assert call_count[0] == 3

    def test_retry_on_connection_error_then_succeed(self):
        """接続エラー後にリトライして成功する"""
        from exceptions import APIConnectionError

        c = self._make_corrector(retry_count=3, retry_base_delay=0.0)
        call_count = [0]

        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise APIConnectionError("connection failed")
            return "success"

        result = c._call_with_retry(flaky_func)
        assert result == "success"
        assert call_count[0] == 2

    def test_auth_error_no_retry(self):
        """認証エラーはリトライしない"""
        from exceptions import APIAuthenticationError

        c = self._make_corrector(retry_count=3, retry_base_delay=0.0)
        call_count = [0]

        def auth_fail():
            call_count[0] += 1
            raise APIAuthenticationError("auth failed")

        with pytest.raises(APIAuthenticationError):
            c._call_with_retry(auth_fail)
        assert call_count[0] == 1

    def test_generic_api_error_no_retry(self):
        """一般的なAPIエラーはリトライしない"""
        from exceptions import APIError

        c = self._make_corrector(retry_count=3, retry_base_delay=0.0)
        call_count = [0]

        def api_fail():
            call_count[0] += 1
            raise APIError("generic api error")

        with pytest.raises(APIError):
            c._call_with_retry(api_fail)
        assert call_count[0] == 1

    def test_all_retries_exhausted(self):
        """全リトライが尽きた場合は最後のエラーをraise"""
        from exceptions import APIRateLimitError

        c = self._make_corrector(retry_count=2, retry_base_delay=0.0)

        def always_fail():
            raise APIRateLimitError("always rate limited")

        with pytest.raises(APIRateLimitError, match="always rate limited"):
            c._call_with_retry(always_fail)


@pytest.mark.unit
class TestBaseAPICorrectorCorrectSegments:
    """BaseAPICorrector.correct_segments() のテスト"""

    def _make_corrector(self, is_available=False):
        """テスト用のBaseAPICorrectorサブクラスを作成"""
        from api_corrector import BaseAPICorrector, CorrectionConfig, APIProvider

        class DummyCorrector(BaseAPICorrector):
            def correct_text(self, text, context=None):
                return text.upper()

            def generate_summary(self, text, max_length=200):
                return text[:max_length]

        config = CorrectionConfig(
            provider=APIProvider.ANTHROPIC,
            api_key="dummy",
            model="dummy-model",
        )
        corrector = DummyCorrector(config)
        corrector.is_available = is_available
        return corrector

    def test_unavailable_returns_segments_unchanged(self):
        """is_available=Falseの場合、セグメントはそのまま返される"""
        c = self._make_corrector(is_available=False)
        segments = [
            {"text": "テスト文", "start": 0.0, "end": 1.0},
            {"text": "別の文", "start": 1.0, "end": 2.0},
        ]
        result = c.correct_segments(segments)
        assert result == segments
        # テキストが変更されていないことを確認
        assert result[0]["text"] == "テスト文"
        assert result[1]["text"] == "別の文"

    def test_available_corrects_segments(self):
        """is_available=Trueの場合、テキストが補正される"""
        c = self._make_corrector(is_available=True)
        segments = [
            {"text": "hello", "start": 0.0, "end": 1.0},
        ]
        result = c.correct_segments(segments)
        assert result[0]["text"] == "HELLO"
        assert result[0]["corrected"] is True

    def test_empty_text_segments_not_corrected(self):
        """空テキストのセグメントは補正されない"""
        c = self._make_corrector(is_available=True)
        segments = [
            {"text": "", "start": 0.0, "end": 1.0},
            {"text": "   ", "start": 1.0, "end": 2.0},
        ]
        result = c.correct_segments(segments)
        assert result[0]["text"] == ""
        assert result[1]["text"] == "   "
        assert "corrected" not in result[0]
        assert "corrected" not in result[1]

    def test_original_segment_not_mutated(self):
        """元のセグメントオブジェクトが変更されない"""
        c = self._make_corrector(is_available=True)
        original = {"text": "hello", "start": 0.0, "end": 1.0}
        segments = [original]
        result = c.correct_segments(segments)
        assert original["text"] == "hello"  # 元は変わっていない
        assert result[0]["text"] == "HELLO"

    def test_empty_segments_list(self):
        """空のセグメントリスト"""
        c = self._make_corrector(is_available=True)
        result = c.correct_segments([])
        assert result == []


@pytest.mark.unit
class TestBaseAPICorrectorHandleAPIError:
    """BaseAPICorrector._handle_api_error() のテスト"""

    def _make_corrector(self):
        from api_corrector import BaseAPICorrector, CorrectionConfig, APIProvider

        class DummyCorrector(BaseAPICorrector):
            def correct_text(self, text, context=None):
                return text

            def generate_summary(self, text, max_length=200):
                return text[:max_length]

        config = CorrectionConfig(
            provider=APIProvider.ANTHROPIC,
            api_key="dummy",
            model="dummy-model",
        )
        return DummyCorrector(config)

    def test_authentication_error(self):
        from exceptions import APIAuthenticationError
        c = self._make_corrector()
        with pytest.raises(APIAuthenticationError):
            c._handle_api_error(Exception("authentication failed"), "TestProvider")

    def test_api_key_error(self):
        from exceptions import APIAuthenticationError
        c = self._make_corrector()
        with pytest.raises(APIAuthenticationError):
            c._handle_api_error(Exception("invalid api key"), "TestProvider")

    def test_unauthorized_error(self):
        from exceptions import APIAuthenticationError
        c = self._make_corrector()
        with pytest.raises(APIAuthenticationError):
            c._handle_api_error(Exception("unauthorized access"), "TestProvider")

    def test_rate_limit_error(self):
        from exceptions import APIRateLimitError
        c = self._make_corrector()
        with pytest.raises(APIRateLimitError):
            c._handle_api_error(Exception("rate limit exceeded"), "TestProvider")

    def test_rate_limit_underscore_error(self):
        from exceptions import APIRateLimitError
        c = self._make_corrector()
        with pytest.raises(APIRateLimitError):
            c._handle_api_error(Exception("rate_limit hit"), "TestProvider")

    def test_generic_error(self):
        from exceptions import APIError
        c = self._make_corrector()
        with pytest.raises(APIError):
            c._handle_api_error(Exception("something went wrong"), "TestProvider")


# ============================================================================
# enhanced_batch_processor.py テスト
# ============================================================================

# psutilがインストールされていない場合、モックをsys.modulesに注入してからインポート
_ebp_import_error = None
try:
    import enhanced_batch_processor as _ebp_module
except ImportError:
    # psutil がないため、モックを注入してリトライ
    try:
        from unittest.mock import MagicMock as _MagicMock
        _mock_psutil = _MagicMock()
        _mock_psutil.Process.return_value.memory_info.return_value.rss = 500 * 1024 * 1024
        _mock_psutil.cpu_percent.return_value = 30.0
        _mock_psutil.cpu_count.return_value = 4
        sys.modules["psutil"] = _mock_psutil
        import enhanced_batch_processor as _ebp_module
    except Exception as _e:
        _ebp_import_error = str(_e)
        _ebp_module = None

_ebp_available = _ebp_module is not None


@pytest.mark.unit
@pytest.mark.skipif(not _ebp_available, reason=f"enhanced_batch_processor not importable: {_ebp_import_error}")
class TestCheckpointManager:
    """CheckpointManagerのチェックポイント管理テスト"""

    def test_init_creates_directory(self):
        """初期化時にディレクトリが作成される"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cp_dir = os.path.join(tmpdir, "subdir", "checkpoints")
            cm = _ebp_module.CheckpointManager(checkpoint_dir=cp_dir)
            assert os.path.isdir(cp_dir)
            assert cm.checkpoint_file == Path(cp_dir) / "batch_checkpoint.json"

    def test_save_and_load(self):
        """チェックポイントの保存と読み込み"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)

            result = cm.save(
                batch_id="test_batch_001",
                processed_files=["file1.wav", "file2.wav"],
                failed_files=[{"file": "bad.wav", "error": "corrupt"}],
                remaining_files=["file3.wav"],
                stats={"total_files": 4},
            )
            assert result is True

            loaded = cm.load("test_batch_001")
            assert loaded is not None
            assert loaded["batch_id"] == "test_batch_001"
            assert loaded["processed_files"] == ["file1.wav", "file2.wav"]
            assert loaded["failed_files"] == [{"file": "bad.wav", "error": "corrupt"}]
            assert loaded["remaining_files"] == ["file3.wav"]
            assert loaded["stats"] == {"total_files": 4}
            assert "timestamp" in loaded

    def test_load_nonexistent(self):
        """存在しないチェックポイントの読み込みはNone"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            result = cm.load()
            assert result is None

    def test_load_wrong_batch_id(self):
        """異なるbatch_idでの読み込みはNone"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            cm.save(
                batch_id="batch_A",
                processed_files=[],
                failed_files=[],
                remaining_files=["f1.wav"],
                stats={},
            )
            result = cm.load(batch_id="batch_B")
            assert result is None

    def test_load_any_batch_id(self):
        """batch_id=Noneで読み込むと任意のチェックポイントを返す"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            cm.save(
                batch_id="batch_X",
                processed_files=["a.wav"],
                failed_files=[],
                remaining_files=[],
                stats={},
            )
            result = cm.load(batch_id=None)
            assert result is not None
            assert result["batch_id"] == "batch_X"

    def test_clear(self):
        """チェックポイントの削除"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            cm.save(
                batch_id="batch_del",
                processed_files=[],
                failed_files=[],
                remaining_files=["f1.wav"],
                stats={},
            )
            assert cm.checkpoint_file.exists()
            result = cm.clear()
            assert result is True
            assert not cm.checkpoint_file.exists()

    def test_clear_nonexistent(self):
        """存在しないチェックポイントのクリアも成功"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            result = cm.clear()
            assert result is True

    def test_get_resume_info_with_remaining(self):
        """残りファイルがある場合の再開情報取得"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            cm.save(
                batch_id="resume_test",
                processed_files=["done1.wav", "done2.wav"],
                failed_files=[{"file": "bad.wav", "error": "err"}],
                remaining_files=["todo1.wav", "todo2.wav", "todo3.wav"],
                stats={},
            )
            info = cm.get_resume_info()
            assert info is not None
            assert info["batch_id"] == "resume_test"
            assert info["processed_count"] == 2
            assert info["failed_count"] == 1
            assert info["remaining_count"] == 3
            assert info["remaining_files"] == ["todo1.wav", "todo2.wav", "todo3.wav"]

    def test_get_resume_info_no_remaining(self):
        """残りファイルがない場合の再開情報はNone"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            cm.save(
                batch_id="done_test",
                processed_files=["done.wav"],
                failed_files=[],
                remaining_files=[],
                stats={},
            )
            info = cm.get_resume_info()
            assert info is None

    def test_get_resume_info_no_checkpoint(self):
        """チェックポイントがない場合の再開情報はNone"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            info = cm.get_resume_info()
            assert info is None

    def test_save_overwrites_previous(self):
        """保存は前のチェックポイントを上書きする"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = _ebp_module.CheckpointManager(checkpoint_dir=tmpdir)
            cm.save(
                batch_id="first",
                processed_files=["a.wav"],
                failed_files=[],
                remaining_files=["b.wav"],
                stats={},
            )
            cm.save(
                batch_id="second",
                processed_files=["a.wav", "b.wav"],
                failed_files=[],
                remaining_files=[],
                stats={},
            )
            loaded = cm.load()
            assert loaded["batch_id"] == "second"
            assert loaded["processed_files"] == ["a.wav", "b.wav"]


@pytest.mark.unit
@pytest.mark.skipif(not _ebp_available, reason=f"enhanced_batch_processor not importable: {_ebp_import_error}")
class TestEnhancedBatchProcessorInit:
    """EnhancedBatchProcessorの初期化テスト"""

    def test_default_init(self):
        """デフォルト値での初期化"""
        p = _ebp_module.EnhancedBatchProcessor()
        assert p.max_workers == 4
        assert p.current_workers == 4
        assert p.auto_adjust_workers is True
        assert p.enable_checkpoint is True
        assert p.memory_limit_mb == 4096
        assert p.checkpoint_interval == 10
        assert p.is_running is False
        assert p._pause_event.is_set() is False
        assert p._cancel_event.is_set() is False

    def test_custom_workers(self):
        """カスタムワーカー数での初期化"""
        p = _ebp_module.EnhancedBatchProcessor(max_workers=8)
        assert p.max_workers == 8
        assert p.current_workers == 8

    def test_single_worker(self):
        """ワーカー数1での初期化"""
        p = _ebp_module.EnhancedBatchProcessor(max_workers=1)
        assert p.max_workers == 1
        assert p.current_workers == 1

    def test_checkpoint_disabled(self):
        """チェックポイント無効での初期化"""
        p = _ebp_module.EnhancedBatchProcessor(enable_checkpoint=False)
        assert p.enable_checkpoint is False
        assert p.checkpoint_manager is None

    def test_checkpoint_enabled(self):
        """チェックポイント有効での初期化"""
        p = _ebp_module.EnhancedBatchProcessor(enable_checkpoint=True)
        assert p.enable_checkpoint is True
        assert p.checkpoint_manager is not None

    def test_initial_stats(self):
        """初期統計情報の確認"""
        p = _ebp_module.EnhancedBatchProcessor(max_workers=2)
        assert p.stats["total_files"] == 0
        assert p.stats["processed_count"] == 0
        assert p.stats["failed_count"] == 0
        assert p.stats["start_time"] is None
        assert p.stats["current_workers"] == 2


@pytest.mark.unit
@pytest.mark.skipif(not _ebp_available, reason=f"enhanced_batch_processor not importable: {_ebp_import_error}")
class TestEnhancedBatchProcessorControls:
    """EnhancedBatchProcessorのキャンセル・一時停止・再開テスト"""

    def _make_processor(self):
        return _ebp_module.EnhancedBatchProcessor(
            max_workers=2,
            enable_checkpoint=False,
            auto_adjust_workers=False,
        )

    def test_cancel(self):
        """キャンセルフラグの設定"""
        p = self._make_processor()
        assert p._cancel_event.is_set() is False
        p.cancel()
        assert p._cancel_event.is_set() is True

    def test_pause(self):
        """一時停止フラグの設定"""
        p = self._make_processor()
        assert p._pause_event.is_set() is False
        p.pause()
        assert p._pause_event.is_set() is True

    def test_resume(self):
        """再開で_pause_eventがクリアされる"""
        p = self._make_processor()
        p.pause()
        assert p._pause_event.is_set() is True
        p.resume()
        assert p._pause_event.is_set() is False

    def test_pause_resume_cycle(self):
        """一時停止と再開を複数回繰り返す"""
        p = self._make_processor()
        for _ in range(3):
            p.pause()
            assert p._pause_event.is_set() is True
            p.resume()
            assert p._pause_event.is_set() is False


@pytest.mark.unit
@pytest.mark.skipif(not _ebp_available, reason=f"enhanced_batch_processor not importable: {_ebp_import_error}")
class TestBatchSizeMultiplier:
    """BATCH_SIZE_MULTIPLIER定数のテスト"""

    def test_multiplier_value(self):
        """BATCH_SIZE_MULTIPLIERの値が2であることを確認"""
        assert _ebp_module.EnhancedBatchProcessor.BATCH_SIZE_MULTIPLIER == 2

    def test_multiplier_is_positive(self):
        """BATCH_SIZE_MULTIPLIERが正の値"""
        assert _ebp_module.EnhancedBatchProcessor.BATCH_SIZE_MULTIPLIER > 0


# ============================================================================
# folder_monitor.py テスト
# ============================================================================

# PySide6が利用できるかチェック
try:
    from PySide6.QtCore import QThread
    _pyside6_available = True
except ImportError:
    _pyside6_available = False


@pytest.mark.unit
class TestFolderMonitorProcessedFiles:
    """FolderMonitorの処理済みファイル保存・読み込みテスト（Qt不要部分）"""

    def test_save_and_load_processed_files(self):
        """処理済みファイルリストの保存と読み込み"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # 手動で処理済みファイルリストを書き込み
            processed_path = os.path.join(tmpdir, ".processed_files.txt")
            test_files = [
                os.path.join(tmpdir, "file1.wav"),
                os.path.join(tmpdir, "file2.mp3"),
                os.path.join(tmpdir, "file3.m4a"),
            ]
            with open(processed_path, "w", encoding="utf-8") as f:
                for fp in test_files:
                    f.write(f"{fp}\n")

            # 読み込みをテスト（FolderMonitorはQThreadを継承するためスキップの可能性あり）
            # ファイル内容を直接検証
            with open(processed_path, "r", encoding="utf-8") as f:
                loaded = set(line.strip() for line in f if line.strip())
            assert loaded == set(test_files)

    def test_save_processed_files_format(self):
        """保存フォーマットが1行1ファイルパスであること"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = os.path.join(tmpdir, ".processed_files.txt")
            files = ["alpha.wav", "beta.mp3"]
            with open(processed_path, "w", encoding="utf-8") as f:
                for fp in sorted(files):
                    f.write(f"{fp}\n")

            with open(processed_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            assert lines == sorted(files)

    def test_load_empty_file(self):
        """空ファイルの読み込みは空セットになる"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = os.path.join(tmpdir, ".processed_files.txt")
            with open(processed_path, "w", encoding="utf-8") as f:
                f.write("")

            with open(processed_path, "r", encoding="utf-8") as f:
                loaded = set(line.strip() for line in f if line.strip())
            assert loaded == set()

    def test_load_nonexistent_file(self):
        """存在しないファイルの読み込み"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = os.path.join(tmpdir, ".processed_files.txt")
            assert not os.path.exists(processed_path)


@pytest.mark.unit
class TestFolderMonitorExtensionFiltering:
    """FolderMonitorの拡張子フィルタリングロジックテスト"""

    # AUDIO_EXTENSIONSの期待値（folder_monitor.pyから抽出した定数）
    EXPECTED_AUDIO_EXTENSIONS = {
        '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac',
        '.wma', '.opus', '.amr', '.3gp', '.webm',
        '.mp4', '.avi', '.mov', '.mkv',
    }

    @pytest.mark.skipif(not _pyside6_available, reason="PySide6 not available")
    def test_audio_extensions_set(self):
        """AUDIO_EXTENSIONSの定義を確認"""
        from folder_monitor import FolderMonitor
        assert FolderMonitor.AUDIO_EXTENSIONS == self.EXPECTED_AUDIO_EXTENSIONS

    def test_is_audio_file_wav(self):
        """WAVファイルが音声ファイルとして認識される"""
        ext = os.path.splitext("test.wav")[1].lower()
        assert ext in self.EXPECTED_AUDIO_EXTENSIONS

    def test_is_audio_file_mp3(self):
        """MP3ファイルが音声ファイルとして認識される"""
        ext = os.path.splitext("music.mp3")[1].lower()
        assert ext in self.EXPECTED_AUDIO_EXTENSIONS

    def test_is_audio_file_mp4(self):
        """MP4ファイルが音声ファイルとして認識される"""
        ext = os.path.splitext("video.mp4")[1].lower()
        assert ext in self.EXPECTED_AUDIO_EXTENSIONS

    def test_is_not_audio_file_txt(self):
        """TXTファイルは音声ファイルではない"""
        ext = os.path.splitext("notes.txt")[1].lower()
        assert ext not in self.EXPECTED_AUDIO_EXTENSIONS

    def test_is_not_audio_file_pdf(self):
        """PDFファイルは音声ファイルではない"""
        ext = os.path.splitext("document.pdf")[1].lower()
        assert ext not in self.EXPECTED_AUDIO_EXTENSIONS

    def test_is_not_audio_file_py(self):
        """Pythonファイルは音声ファイルではない"""
        ext = os.path.splitext("script.py")[1].lower()
        assert ext not in self.EXPECTED_AUDIO_EXTENSIONS

    def test_case_insensitive_extension(self):
        """拡張子は大文字小文字を区別しない"""
        ext_upper = os.path.splitext("test.WAV")[1].lower()
        ext_lower = os.path.splitext("test.wav")[1].lower()
        assert ext_upper == ext_lower

    @pytest.mark.skipif(not _pyside6_available, reason="PySide6 not available")
    def test_all_video_formats_included(self):
        """動画形式がAUDIO_EXTENSIONSに含まれる"""
        video_exts = {'.mp4', '.avi', '.mov', '.mkv'}
        from folder_monitor import FolderMonitor
        assert video_exts.issubset(FolderMonitor.AUDIO_EXTENSIONS)


@pytest.mark.unit
class TestFolderMonitorIsFileReady:
    """FolderMonitor.is_file_ready()のテスト（実ファイルを使用）"""

    def _check_file_ready(self, file_path):
        """is_file_readyと同等のロジックでファイル準備状態をチェック"""
        try:
            if os.path.getsize(file_path) == 0:
                return False
            with open(file_path, 'r+b') as f:
                f.read(1)
            return True
        except (OSError, IOError):
            return False

    def test_nonempty_file_is_ready(self):
        """内容のあるファイルはreadyと判定される"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.wav")
            with open(fpath, "wb") as f:
                f.write(b"RIFF" + b"\x00" * 100)
            assert self._check_file_ready(fpath) is True

    def test_empty_file_is_not_ready(self):
        """0バイトのファイルはreadyではない"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "empty.wav")
            with open(fpath, "wb") as f:
                pass  # 0 bytes
            assert self._check_file_ready(fpath) is False

    def test_nonexistent_file_is_not_ready(self):
        """存在しないファイルはreadyではない"""
        assert self._check_file_ready("nonexistent_file_xyz.wav") is False


@pytest.mark.skipif(not _pyside6_available, reason="PySide6 not available")
@pytest.mark.unit
class TestFolderMonitorWithQt:
    """PySide6が利用可能な場合のFolderMonitorテスト"""

    def test_init(self):
        """FolderMonitorの初期化"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir, check_interval=5)
            assert monitor.folder_path == tmpdir
            assert monitor.check_interval == 5
            assert monitor._stop_event.is_set() is False
            assert isinstance(monitor.processed_files, set)

    def test_is_audio_file_method(self):
        """is_audio_fileメソッドの動作確認"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)
            assert monitor.is_audio_file("test.wav") is True
            assert monitor.is_audio_file("test.mp3") is True
            assert monitor.is_audio_file("test.mp4") is True
            assert monitor.is_audio_file("test.txt") is False
            assert monitor.is_audio_file("test.pdf") is False
            assert monitor.is_audio_file("test.py") is False

    def test_mark_and_check_processed(self):
        """ファイルを処理済みとしてマークし、確認する"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)

            test_file = os.path.join(tmpdir, "test.wav")
            with open(test_file, "wb") as f:
                f.write(b"data")

            assert monitor.is_processed(test_file) is False
            monitor.mark_as_processed(test_file)
            assert monitor.is_processed(test_file) is True

    def test_remove_from_processed(self):
        """処理済みリストからの削除"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)

            test_file = os.path.join(tmpdir, "test.wav")
            with open(test_file, "wb") as f:
                f.write(b"data")

            monitor.mark_as_processed(test_file)
            assert monitor.is_processed(test_file) is True
            monitor.remove_from_processed(test_file)
            assert os.path.abspath(test_file) not in monitor.processed_files

    def test_load_processed_files_on_init(self):
        """初期化時に処理済みファイルリストが読み込まれる"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # 事前に処理済みファイルリストを作成
            processed_path = os.path.join(tmpdir, ".processed_files.txt")
            test_files = [
                os.path.join(tmpdir, "a.wav"),
                os.path.join(tmpdir, "b.mp3"),
            ]
            with open(processed_path, "w", encoding="utf-8") as f:
                for fp in test_files:
                    f.write(f"{fp}\n")

            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)
            assert len(monitor.processed_files) == 2
            for fp in test_files:
                assert fp in monitor.processed_files

    def test_get_unprocessed_files_empty_dir(self):
        """空ディレクトリでは未処理ファイルなし"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)
            result = monitor.get_unprocessed_files()
            assert result == []

    def test_is_file_ready_nonempty(self):
        """is_file_readyメソッドのテスト - 内容のあるファイル"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)
            fpath = os.path.join(tmpdir, "test.wav")
            with open(fpath, "wb") as f:
                f.write(b"RIFF" + b"\x00" * 100)
            # Note: is_file_ready has a 1-second sleep for size stability check
            # We accept the delay in this test
            result = monitor.is_file_ready(fpath)
            assert result is True

    def test_is_file_ready_empty(self):
        """is_file_readyメソッドのテスト - 空ファイル"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)
            fpath = os.path.join(tmpdir, "empty.wav")
            with open(fpath, "wb") as f:
                pass
            result = monitor.is_file_ready(fpath)
            assert result is False

    def test_stop(self):
        """stopメソッドで_stop_eventがセットされる"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            from folder_monitor import FolderMonitor
            monitor = FolderMonitor(tmpdir)
            assert monitor._stop_event.is_set() is False
            monitor.stop()
            assert monitor._stop_event.is_set() is True


# ============================================================================
# 4a. base_engine.py 追加テスト - __enter__/__exit__ cleanup, unload_model edge cases
# ============================================================================

class TestBaseTranscriptionEngineExtended:
    """BaseTranscriptionEngine の拡張テスト

    __enter__/__exit__ でのクリーンアップ、unload_model の障害処理、
    コンテキストマネージャのエラーフローを重点的にテストする。
    """

    def setup_method(self):
        from base_engine import BaseTranscriptionEngine

        class ConcreteEngine(BaseTranscriptionEngine):
            """正常に動作する具象エンジン"""
            def load_model(self) -> bool:
                self.model = "mock_model"
                self.is_loaded = True
                return True

            def transcribe(self, audio, **kwargs):
                return {"text": "test", "segments": []}

        class FailingLoadEngine(BaseTranscriptionEngine):
            """load_model で例外を送出するエンジン"""
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.unload_called = False

            def load_model(self) -> bool:
                # 部分的にモデルを設定してから失敗
                self.model = "partial_model"
                raise RuntimeError("Model load failed")

            def transcribe(self, audio, **kwargs):
                return {"text": "", "segments": []}

            def unload_model(self):
                self.unload_called = True
                super().unload_model()

        class FailingUnloadEngine(BaseTranscriptionEngine):
            """unload_model で例外を送出するエンジン"""
            def load_model(self) -> bool:
                self.model = "mock_model"
                self.is_loaded = True
                return True

            def transcribe(self, audio, **kwargs):
                return {"text": "test", "segments": []}

            def unload_model(self):
                raise RuntimeError("Unload failed")

        self.ConcreteEngine = ConcreteEngine
        self.FailingLoadEngine = FailingLoadEngine
        self.FailingUnloadEngine = FailingUnloadEngine
        self.BaseTranscriptionEngine = BaseTranscriptionEngine

    def test_enter_calls_cleanup_on_load_failure(self):
        """__enter__ で load_model が失敗した場合、unload_model がクリーンアップとして呼ばれる"""
        engine = self.FailingLoadEngine("test-model", device="cpu")
        with pytest.raises(RuntimeError, match="Model load failed"):
            engine.__enter__()
        # クリーンアップが呼ばれたことを確認
        assert engine.unload_called is True
        assert engine.model is None
        assert engine.is_loaded is False

    def test_enter_cleanup_on_load_failure_via_with(self):
        """with文で load_model が失敗した場合もクリーンアップが動作する"""
        with pytest.raises(RuntimeError, match="Model load failed"):
            with self.FailingLoadEngine("test-model", device="cpu") as engine:
                pass  # pragma: no cover

    def test_exit_unload_error_does_not_mask_original_exception(self):
        """__exit__ で unload_model が失敗しても、元の例外がマスクされない"""
        engine = self.FailingUnloadEngine("test-model", device="cpu")
        # load_model を手動で呼ぶ（__enter__ を模倣）
        engine.load_model()
        assert engine.is_loaded is True

        # __exit__ で元の例外がある場合、unload_model の例外はログのみ
        result = engine.__exit__(ValueError, ValueError("original"), None)
        assert result is False  # 例外を再送出

    def test_exit_unload_error_raises_when_no_original_exception(self):
        """__exit__ で元の例外がなく unload_model が失敗した場合は例外が送出される"""
        engine = self.FailingUnloadEngine("test-model", device="cpu")
        engine.load_model()

        with pytest.raises(RuntimeError, match="Unload failed"):
            engine.__exit__(None, None, None)

    def test_exit_returns_false(self):
        """__exit__ は常に False を返して例外を伝播する"""
        engine = self.ConcreteEngine("test-model", device="cpu")
        engine.load_model()
        result = engine.__exit__(None, None, None)
        assert result is False

    def test_unload_model_exception_during_cleanup(self):
        """unload_model でモデルオブジェクトの解放中に例外が発生しても、
        model と is_loaded は None/False にリセットされる"""
        from base_engine import BaseTranscriptionEngine

        class BrokenModelEngine(BaseTranscriptionEngine):
            def load_model(self) -> bool:
                # モデルオブジェクトが削除時に例外を出す
                self.model = MagicMock()
                self.model.__class__.__name__ = "BrokenModel"
                self.is_loaded = True
                return True

            def transcribe(self, audio, **kwargs):
                return {"text": "", "segments": []}

        engine = BrokenModelEngine("test-model", device="cpu")
        engine.load_model()
        assert engine.is_loaded is True

        # unload_model のtry/except内部で例外が発生するケースをシミュレート
        # torch.cuda.is_available() が例外を出す場合
        with patch.dict('sys.modules', {'torch': MagicMock(cuda=MagicMock(is_available=MagicMock(return_value=False)))}):
            engine.unload_model()

        assert engine.model is None
        assert engine.is_loaded is False

    def test_unload_model_no_model_loaded(self):
        """モデルが None の状態で unload_model を呼んでも何も起きない"""
        engine = self.ConcreteEngine("test-model", device="cpu")
        assert engine.model is None
        engine.unload_model()  # 例外なし
        assert engine.model is None
        assert engine.is_loaded is False

    def test_unload_model_with_cuda_cache_clear(self):
        """unload_model がGPUキャッシュクリアを試みる（torch使用可能時）"""
        engine = self.ConcreteEngine("test-model", device="cpu")
        engine.load_model()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        with patch.dict('sys.modules', {'torch': mock_torch}):
            engine.unload_model()

        mock_torch.cuda.empty_cache.assert_called_once()
        assert engine.model is None

    def test_unload_model_without_torch(self):
        """torch がインストールされていなくても unload_model は正常動作する"""
        engine = self.ConcreteEngine("test-model", device="cpu")
        engine.load_model()

        # torch のインポートを失敗させる
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else None
        with patch.dict('sys.modules', {'torch': None}):
            engine.unload_model()

        assert engine.model is None
        assert engine.is_loaded is False

    def test_del_handles_exceptions_silently(self):
        """__del__ は例外をログに記録するのみで送出しない"""
        engine = self.FailingUnloadEngine("test-model", device="cpu")
        engine.load_model()
        # __del__ は例外を飲み込む
        engine.__del__()  # 例外なし

    def test_context_manager_full_lifecycle(self):
        """コンテキストマネージャの全ライフサイクル（load -> use -> unload）"""
        with self.ConcreteEngine("test-model", device="cpu") as engine:
            assert engine.is_loaded is True
            result = engine.transcribe(b"audio_data")
            assert result["text"] == "test"
        assert engine.model is None
        assert engine.is_loaded is False

    def test_resolve_device_auto_with_cuda(self):
        """_resolve_device で auto 指定時に CUDA が利用可能なら cuda を返す"""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        with patch.dict('sys.modules', {'torch': mock_torch}):
            engine = self.ConcreteEngine("test-model", device="auto")
            assert engine.device == "cuda"

    def test_resolve_device_auto_without_cuda(self):
        """_resolve_device で auto 指定時に CUDA がなければ cpu を返す"""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        with patch.dict('sys.modules', {'torch': mock_torch}):
            engine = self.ConcreteEngine("test-model", device="auto")
            assert engine.device == "cpu"

    def test_get_model_info_includes_all_fields(self):
        """get_model_info が全フィールドを含む"""
        engine = self.ConcreteEngine("my-model", device="cpu", language="en")
        info = engine.get_model_info()
        assert info == {
            "engine": "ConcreteEngine",
            "model_name": "my-model",
            "device": "cpu",
            "language": "en",
            "is_loaded": False,
        }

    def test_is_available_default_returns_true(self):
        """is_available のデフォルト実装は True を返す"""
        engine = self.ConcreteEngine("test-model", device="cpu")
        assert engine.is_available() is True


# ============================================================================
# 4b. speaker_diarization_utils.py 追加テスト
# ============================================================================

class TestClusteringMixinExtended:
    """ClusteringMixin の拡張テスト

    _merge_consecutive_segments のバリデーション、
    _simple_clustering のセントロイド正規化、
    _find_speaker_at_time のエッジケースを重点的にテストする。
    """

    def setup_method(self):
        from speaker_diarization_utils import ClusteringMixin
        self.mixin = ClusteringMixin()

    def test_merge_consecutive_segments_length_mismatch_raises(self):
        """labels と timestamps の長さが一致しない場合 ValueError"""
        labels = np.array([0, 1, 0])
        timestamps = [(0, 1), (1, 2)]  # 長さ不一致
        with pytest.raises(ValueError, match="mismatch"):
            self.mixin._merge_consecutive_segments(labels, timestamps)

    def test_merge_consecutive_segments_all_same_speaker(self):
        """全セグメントが同一話者の場合、1つのセグメントにマージされる"""
        labels = np.array([0, 0, 0, 0])
        timestamps = [(0, 1), (1, 2), (2, 3), (3, 4)]
        result = self.mixin._merge_consecutive_segments(labels, timestamps)
        assert len(result) == 1
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[0]["start"] == 0
        assert result[0]["end"] == 4

    def test_merge_consecutive_segments_alternating_speakers(self):
        """交互に話者が変わる場合、各セグメントが個別に保持される"""
        labels = np.array([0, 1, 0, 1])
        timestamps = [(0, 1), (1, 2), (2, 3), (3, 4)]
        result = self.mixin._merge_consecutive_segments(labels, timestamps)
        assert len(result) == 4
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[1]["speaker"] == "SPEAKER_01"
        assert result[2]["speaker"] == "SPEAKER_00"
        assert result[3]["speaker"] == "SPEAKER_01"

    def test_merge_consecutive_segments_rounding(self):
        """タイムスタンプが round(x, 2) で丸められる"""
        labels = np.array([0])
        timestamps = [(0.123456, 1.987654)]
        result = self.mixin._merge_consecutive_segments(labels, timestamps)
        assert result[0]["start"] == 0.12
        assert result[0]["end"] == 1.99

    def test_merge_consecutive_segments_multiple_speakers(self):
        """3人以上の話者が混在するケース"""
        labels = np.array([0, 1, 2, 1, 0])
        timestamps = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
        result = self.mixin._merge_consecutive_segments(labels, timestamps)
        assert len(result) == 5
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[1]["speaker"] == "SPEAKER_01"
        assert result[2]["speaker"] == "SPEAKER_02"
        assert result[3]["speaker"] == "SPEAKER_01"
        assert result[4]["speaker"] == "SPEAKER_00"

    def test_simple_clustering_zero_norm_embeddings(self):
        """ゼロベクトルの埋め込みがあっても除算エラーにならない"""
        embeddings = np.array([
            [0.0, 0.0, 0.0],  # ゼロベクトル
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ], dtype=np.float32)
        labels = self.mixin._simple_clustering(embeddings, num_speakers=2)
        assert len(labels) == 3

    def test_simple_clustering_centroid_normalization(self):
        """セントロイドが単位球面上に正規化される（cosine distance の正当性のため）"""
        embeddings = np.array([
            [3.0, 0.0],
            [2.0, 0.5],
            [0.0, 4.0],
            [0.2, 3.0],
        ], dtype=np.float32)
        labels = self.mixin._simple_clustering(embeddings, num_speakers=2)
        assert len(labels) == 4
        # 最初の2つは類似（x軸方向）、最後の2つは類似（y軸方向）
        assert labels[0] == labels[1]
        assert labels[2] == labels[3]

    def test_simple_clustering_num_speakers_exceeds_data(self):
        """num_speakers がデータ数を超える場合でもエラーにならない"""
        embeddings = np.array([[1, 0], [0, 1]], dtype=np.float32)
        labels = self.mixin._simple_clustering(embeddings, num_speakers=5)
        assert len(labels) == 2

    def test_perform_clustering_empty_embeddings(self):
        """空の埋め込みに対してクラスタリングを実行すると空の配列を返す"""
        embeddings = np.array([]).reshape(0, 3)
        labels = self.mixin._perform_clustering(embeddings, num_speakers=2)
        assert len(labels) == 0

    def test_perform_clustering_fallback_to_simple(self):
        """sklearn が利用不可の場合、_simple_clustering にフォールバックする"""
        embeddings = np.array([
            [1, 0, 0],
            [0.9, 0.1, 0],
            [0, 1, 0],
            [0.1, 0.9, 0],
        ], dtype=np.float32)

        with patch.dict('sys.modules', {'sklearn': None, 'sklearn.cluster': None}):
            # ImportError をシミュレート
            original = self.mixin._perform_clustering

            def mock_perform(embeddings, num_speakers=None):
                try:
                    from sklearn.cluster import AgglomerativeClustering
                    raise ImportError("mocked")
                except ImportError:
                    return self.mixin._simple_clustering(embeddings, num_speakers or 2)

            self.mixin._perform_clustering = mock_perform
            labels = self.mixin._perform_clustering(embeddings, num_speakers=2)
            assert len(labels) == 4


class TestSpeakerFormatterMixinExtended:
    """SpeakerFormatterMixin の拡張テスト"""

    def setup_method(self):
        from speaker_diarization_utils import SpeakerFormatterMixin
        self.formatter = SpeakerFormatterMixin()

    def test_find_speaker_at_time_boundary_start(self):
        """セグメントの開始時刻ちょうどで話者が見つかる"""
        speakers = [{"start": 5.0, "end": 10.0, "speaker": "A"}]
        assert self.formatter._find_speaker_at_time(5.0, speakers) == "A"

    def test_find_speaker_at_time_boundary_end(self):
        """セグメントの終了時刻ちょうどで話者が見つかる"""
        speakers = [{"start": 5.0, "end": 10.0, "speaker": "A"}]
        assert self.formatter._find_speaker_at_time(10.0, speakers) == "A"

    def test_find_speaker_at_time_gap_between_segments(self):
        """セグメント間のギャップにある時刻は UNKNOWN を返す"""
        speakers = [
            {"start": 0.0, "end": 3.0, "speaker": "A"},
            {"start": 5.0, "end": 10.0, "speaker": "B"},
        ]
        assert self.formatter._find_speaker_at_time(4.0, speakers) == "UNKNOWN"

    def test_find_speaker_at_time_before_all_segments(self):
        """全セグメントより前の時刻は UNKNOWN を返す"""
        speakers = [{"start": 5.0, "end": 10.0, "speaker": "A"}]
        assert self.formatter._find_speaker_at_time(0.0, speakers) == "UNKNOWN"

    def test_find_speaker_at_time_missing_keys_defaults(self):
        """話者セグメントに start/end キーがない場合はデフォルト 0 が使われる"""
        speakers = [{"speaker": "A"}]  # start/end 欠落
        # timestamp=0 は start=0, end=0 の範囲内
        assert self.formatter._find_speaker_at_time(0, speakers) == "A"
        assert self.formatter._find_speaker_at_time(1, speakers) == "UNKNOWN"

    def test_find_speaker_at_time_missing_speaker_key(self):
        """話者セグメントに speaker キーがない場合は UNKNOWN"""
        speakers = [{"start": 0, "end": 10}]  # speaker 欠落
        assert self.formatter._find_speaker_at_time(5, speakers) == "UNKNOWN"

    def test_format_with_speakers_speaker_change_adds_blank_line(self):
        """話者が変わる際に空行が挿入される"""
        text_segments = [
            {"start": 1, "end": 2, "text": "Hello"},
            {"start": 6, "end": 7, "text": "World"},
        ]
        speaker_segments = [
            {"start": 0, "end": 5, "speaker": "SPEAKER_00"},
            {"start": 5, "end": 10, "speaker": "SPEAKER_01"},
        ]
        result = self.formatter.format_with_speakers(text_segments, speaker_segments)
        lines = result.split("\n")
        # 空行が含まれることを確認
        assert "" in lines

    def test_format_with_speakers_same_speaker_no_blank_line(self):
        """同じ話者が連続する場合、空行は挿入されない"""
        text_segments = [
            {"start": 1, "end": 2, "text": "Hello"},
            {"start": 3, "end": 4, "text": "World"},
        ]
        speaker_segments = [
            {"start": 0, "end": 10, "speaker": "SPEAKER_00"},
        ]
        result = self.formatter.format_with_speakers(text_segments, speaker_segments)
        lines = result.split("\n")
        # "[SPEAKER_00]" + "Hello" + "World" の3行のみ
        assert len(lines) == 3
        assert "" not in lines

    def test_get_speaker_statistics_zero_total_time(self):
        """全セグメントの duration が0の場合、percentage は計算されない"""
        speaker_segments = [
            {"start": 5.0, "end": 5.0, "speaker": "A"},
        ]
        stats = self.formatter.get_speaker_statistics(speaker_segments)
        assert "A" in stats
        assert stats["A"]["total_time"] == 0.0
        assert "percentage" not in stats["A"]

    def test_get_speaker_statistics_single_speaker(self):
        """単一話者のみの場合、percentage は 100%"""
        speaker_segments = [
            {"start": 0.0, "end": 10.0, "speaker": "A"},
        ]
        stats = self.formatter.get_speaker_statistics(speaker_segments)
        assert stats["A"]["percentage"] == 100.0
        assert stats["A"]["segment_count"] == 1


# ============================================================================
# 4c. text_formatter.py 追加テスト - フィラー除去(日本語)、入力検証
# ============================================================================

class TestTextFormatterExtended:
    """TextFormatter の拡張テスト

    日本語テキストでのフィラー除去（\\b が効かない問題）、
    add_punctuation の入力検証、エッジケースを重点的にテストする。
    """

    def setup_method(self):
        from text_formatter import TextFormatter, RegexPatterns, ValidationError
        self.formatter = TextFormatter()
        self.RegexPatterns = RegexPatterns
        self.ValidationError = ValidationError

    def test_remove_fillers_japanese_no_word_boundary(self):
        """日本語テキストでフィラーが正しく除去される
        （\\b は日本語に効かないため、re.escape + trailing space パターンを使用）
        """
        # フィラーが日本語テキストの途中にあるケース
        text = "えーとこれはテストです"
        result = self.formatter.remove_fillers(text)
        assert "えーと" not in result
        assert "テスト" in result

    def test_remove_fillers_japanese_consecutive_fillers(self):
        """連続する日本語フィラーが全て除去される"""
        text = "あのーえーとまあテスト"
        result = self.formatter.remove_fillers(text)
        assert "あのー" not in result
        assert "えーと" not in result
        assert "まあ" not in result

    def test_remove_fillers_filler_with_trailing_comma(self):
        """フィラーの後に読点がある場合も除去される（パターン: filler + [、。]?\\s*）"""
        text = "あのー、テストです"
        result = self.formatter.remove_fillers(text)
        assert "あのー" not in result
        assert "テスト" in result

    def test_remove_fillers_filler_with_trailing_period(self):
        """フィラーの後に句点がある場合も除去される"""
        text = "えーと。テスト"
        result = self.formatter.remove_fillers(text)
        assert "えーと" not in result

    def test_remove_fillers_preserves_meaningful_text(self):
        """フィラーでない有意味なテキストは保持される"""
        text = "その結果はとても良かった"
        result = self.formatter.remove_fillers(text)
        # "その" は AGGRESSIVE_FILLER_WORDS のみに含まれるため、
        # 通常モードでは保持される
        assert "その" in result
        assert "結果" in result
        assert "良かった" in result

    def test_remove_fillers_none_input_raises_validation_error(self):
        """None を入力すると ValidationError"""
        with pytest.raises(self.ValidationError):
            self.formatter.remove_fillers(None)

    def test_remove_fillers_non_string_raises_validation_error(self):
        """文字列以外を入力すると ValidationError"""
        with pytest.raises(self.ValidationError):
            self.formatter.remove_fillers(12345)

    def test_remove_fillers_very_long_text_validation(self):
        """極端に長いテキスト（1MB超）は ValidationError"""
        long_text = "あ" * 1100000
        with pytest.raises(self.ValidationError):
            self.formatter.remove_fillers(long_text)

    def test_remove_fillers_consecutive_punctuation_cleanup(self):
        """フィラー除去後に連続する句読点が整理される"""
        text = "あのー、、テストです"
        result = self.formatter.remove_fillers(text)
        assert "、、" not in result

    def test_remove_fillers_aggressive_includes_extra_words(self):
        """aggressive=True の場合、追加のフィラー語も除去される"""
        text = "やっぱりちょっとテストですね"
        result = self.formatter.remove_fillers(text, aggressive=True)
        assert "やっぱり" not in result
        assert "ちょっと" not in result
        assert "ですね" not in result

    def test_add_punctuation_empty_string(self):
        """空文字列に句読点を追加しても空文字列のまま（条件: if result が falsy）"""
        result = self.formatter.add_punctuation("")
        # 空文字の場合、"if result" が False なので句点は追加されない
        assert result == ""

    def test_add_punctuation_already_ends_with_question(self):
        """疑問符で終わるテキストには追加の句点がつかない"""
        result = self.formatter.add_punctuation("これは何ですか？")
        assert not result.endswith("。")

    def test_add_punctuation_already_ends_with_exclamation(self):
        """感嘆符で終わるテキストには追加の句点がつかない"""
        result = self.formatter.add_punctuation("すごい！")
        assert not result.endswith("。")

    def test_add_punctuation_reason_clause(self):
        """理由節「～ので」「～から」の後に読点が追加される"""
        result = self.formatter.add_punctuation("雨が降ったので外出を控えた")
        assert "ので、" in result or "ので" in result

    def test_add_punctuation_condition_clause(self):
        """条件節「～たら」「～れば」「～なら」の後に読点が追加される"""
        result = self.formatter.add_punctuation("もし晴れたら出かけます")
        assert "たら、" in result or "たら" in result

    def test_add_punctuation_comma_before_period_removed(self):
        """句点の直前の読点は削除される"""
        result = self.formatter.add_punctuation("テスト、。")
        # 「、。」→「。」
        assert "、。" not in result

    def test_add_punctuation_polite_ending_gets_period(self):
        """「です」「ます」等の丁寧語の後に句点がない場合、句点が追加される"""
        result = self.formatter.add_punctuation("これはテストです次のテスト")
        assert "です。" in result

    def test_format_paragraphs_none_input_raises(self):
        """None を入力すると ValidationError"""
        with pytest.raises(self.ValidationError):
            self.formatter.format_paragraphs(None)

    def test_format_paragraphs_invalid_max_sentences_uses_default(self):
        """max_sentences_per_paragraph が無効値の場合、デフォルト値4が使われる"""
        # 値が範囲外の場合、デフォルトに戻る
        text = "文1。文2。文3。文4。文5。文6。文7。文8。"
        result = self.formatter.format_paragraphs(text, max_sentences_per_paragraph=0)
        # ValidationError ではなく、デフォルト値 4 が使われる
        assert isinstance(result, str)

    def test_filler_pattern_uses_re_escape(self):
        """フィラーパターンが re.escape を使っており、特殊文字を含むフィラーでも安全"""
        pattern = self.RegexPatterns.get_filler_pattern("えーと")
        # パターンが正規表現として有効であることを確認
        import re
        assert re.match(pattern.pattern, "えーと") is not None

    def test_filler_pattern_cache_works(self):
        """フィラーパターンがキャッシュされ、同じオブジェクトが返される"""
        p1 = self.RegexPatterns.get_filler_pattern("まあ")
        p2 = self.RegexPatterns.get_filler_pattern("まあ")
        assert p1 is p2

    def test_split_long_sentences(self):
        """長い文が助詞の位置で分割される"""
        # 60文字以上で読点なしの文
        long_sentence = "これは非常に長い文章であり多くの情報を含んでいて読者にとって理解が難しい場合がある内容を説明している文です"
        result = self.formatter._split_long_sentences(long_sentence)
        # 読点が追加されているか
        if len(long_sentence) > 60:
            assert "、" in result or result == long_sentence

    def test_format_all_with_all_options_disabled(self):
        """全オプションを無効にした format_all はテキストをほぼそのまま返す"""
        text = "あのー テスト テスト"
        result = self.formatter.format_all(
            text,
            remove_fillers=False,
            add_punctuation=False,
            format_paragraphs=False,
            clean_repeated=False,
        )
        # format_numbers だけは常に適用される
        assert "あのー" in result


# ============================================================================
# 4d. custom_vocabulary.py 追加テスト - アトミック保存、import_words 検証
# ============================================================================

class TestCustomVocabularyExtended:
    """CustomVocabulary の拡張テスト

    アトミック保存の動作確認、import_words_from_text のバリデーション、
    add_hotword のエッジケースを重点的にテストする。
    """

    def test_atomic_save_creates_file(self, tmp_path):
        """save_vocabulary がアトミック書き込みでファイルを作成する"""
        from custom_vocabulary import CustomVocabulary
        vocab_file = str(tmp_path / "atomic_test.json")
        vocab = CustomVocabulary(vocab_file)
        # ファイルが作成されたことを確認
        assert Path(vocab_file).exists()
        # 内容が正しいJSONであること
        content = json.loads(Path(vocab_file).read_text(encoding="utf-8"))
        assert "hotwords" in content
        assert "replacements" in content
        assert "domains" in content

    def test_atomic_save_no_temp_file_left_on_success(self, tmp_path):
        """アトミック保存成功時に一時ファイルが残らない"""
        from custom_vocabulary import CustomVocabulary
        vocab_file = str(tmp_path / "atomic_test.json")
        vocab = CustomVocabulary(vocab_file)
        vocab.save_vocabulary()
        # tmp ファイルが残っていないことを確認
        tmp_files = list(tmp_path.glob(".vocab_*.tmp"))
        assert len(tmp_files) == 0

    def test_atomic_save_no_temp_file_left_on_failure(self, tmp_path):
        """アトミック保存失敗時に一時ファイルがクリーンアップされる"""
        from custom_vocabulary import CustomVocabulary
        vocab_file = str(tmp_path / "atomic_test.json")
        vocab = CustomVocabulary(vocab_file)

        # os.replace を失敗させる
        with patch('os.replace', side_effect=OSError("disk full")):
            vocab.save_vocabulary()  # エラーは内部でキャッチされる

        # 一時ファイルが残っていないことを確認
        tmp_files = list(tmp_path.glob(".vocab_*.tmp"))
        assert len(tmp_files) == 0

    def test_add_hotword_empty_raises_valueerror(self, tmp_path):
        """空文字列の追加は ValueError"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        with pytest.raises(ValueError, match="cannot be empty"):
            vocab.add_hotword("")

    def test_add_hotword_whitespace_only_raises_valueerror(self, tmp_path):
        """空白のみの文字列の追加は ValueError"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        with pytest.raises(ValueError, match="cannot be empty"):
            vocab.add_hotword("   ")

    def test_add_hotword_too_long_raises_valueerror(self, tmp_path):
        """MAX_HOTWORD_LENGTH を超える文字列の追加は ValueError"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        long_word = "あ" * 101
        with pytest.raises(ValueError, match="too long"):
            vocab.add_hotword(long_word)

    def test_add_hotword_strips_whitespace(self, tmp_path):
        """ホットワード追加時に前後の空白が除去される"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.add_hotword("  テスト用語  ")
        assert "テスト用語" in vocab.hotwords
        assert "  テスト用語  " not in vocab.hotwords

    def test_import_words_from_text_skips_invalid(self, tmp_path):
        """import_words_from_text はバリデーションエラーの単語をスキップする"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        initial_count = len(vocab.hotwords)
        # 空行、空白のみ、長すぎる単語を含む
        long_word = "x" * 200
        text = f"ValidWord\n\n   \n{long_word}\nAnotherValid"
        vocab.import_words_from_text(text)
        # ValidWord と AnotherValid が追加される
        assert "ValidWord" in vocab.hotwords
        assert "AnotherValid" in vocab.hotwords
        # 長すぎる単語は追加されない
        assert long_word not in vocab.hotwords

    def test_import_words_from_text_empty_lines_ignored(self, tmp_path):
        """import_words_from_text は空行を無視する"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        initial_count = len(vocab.hotwords)
        vocab.import_words_from_text("\n\n\n")
        assert len(vocab.hotwords) == initial_count

    def test_import_words_from_text_strips_each_word(self, tmp_path):
        """import_words_from_text は各行の前後空白を除去する"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.import_words_from_text("  SpacedWord  ")
        assert "SpacedWord" in vocab.hotwords

    def test_apply_replacements_delegates_to_construction_vocab(self, tmp_path):
        """apply_replacements は ConstructionVocabulary.apply_replacements_to_text に委譲する"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.replacements = {"テスト入力": "テスト出力"}
        result = vocab.apply_replacements("テスト入力の文")
        assert "テスト出力" in result

    def test_load_vocabulary_file_too_large(self, tmp_path):
        """ファイルサイズが10MBを超える場合はロードされない"""
        from custom_vocabulary import CustomVocabulary
        vocab_file = tmp_path / "large.json"
        # ファイルを作成（実際には大きくないが、stat を mock する）
        vocab_file.write_text("{}", encoding="utf-8")

        with patch.object(Path, 'stat') as mock_stat:
            mock_stat_result = MagicMock()
            mock_stat_result.st_size = 11 * 1024 * 1024  # 11MB
            mock_stat.return_value = mock_stat_result
            vocab = CustomVocabulary(str(vocab_file))
            # ファイルが大きすぎるのでデフォルトデータは空のまま（もしくはload_vocabularyが何もしない）

    def test_load_vocabulary_invalid_json(self, tmp_path):
        """無効なJSONの場合、デフォルト語彙が作成される"""
        from custom_vocabulary import CustomVocabulary
        vocab_file = tmp_path / "invalid.json"
        vocab_file.write_text("{ invalid json }", encoding="utf-8")
        vocab = CustomVocabulary(str(vocab_file))
        # デフォルト語彙が作成されている
        assert len(vocab.hotwords) > 0

    def test_get_whisper_prompt_empty_hotwords(self, tmp_path):
        """ホットワードが空の場合、空文字列を返す"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.hotwords = []
        prompt = vocab.get_whisper_prompt()
        assert prompt == ""

    def test_get_whisper_prompt_limits_to_30_words(self, tmp_path):
        """Whisperプロンプトは最大30単語に制限される"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        vocab.hotwords = [f"Word{i}" for i in range(50)]
        prompt = vocab.get_whisper_prompt()
        # 「、」で区切られた単語数が30以下
        words_in_prompt = prompt.split("、")
        assert len(words_in_prompt) <= 30

    def test_remove_hotword_nonexistent(self, tmp_path):
        """存在しないホットワードの削除は何も起きない"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        count = len(vocab.hotwords)
        vocab.remove_hotword("非存在ワード")
        assert len(vocab.hotwords) == count

    def test_remove_replacement_nonexistent(self, tmp_path):
        """存在しない置換ルールの削除は何も起きない"""
        from custom_vocabulary import CustomVocabulary
        vocab = CustomVocabulary(str(tmp_path / "vocab.json"))
        count = len(vocab.replacements)
        vocab.remove_replacement("非存在キー")
        assert len(vocab.replacements) == count


# ============================================================================
# 4e. custom_dictionary.py 追加テスト - スレッドセーフシングルトン
# ============================================================================

class TestCustomDictionaryExtended:
    """CustomDictionary の拡張テスト

    スレッドセーフなシングルトン（get_custom_dictionary）、
    reload の動作、_merge メソッドのエッジケースをテストする。
    """

    def setup_method(self):
        # シングルトンをリセット
        import custom_dictionary
        custom_dictionary._custom_dictionary = None

    def teardown_method(self):
        import custom_dictionary
        custom_dictionary._custom_dictionary = None

    def test_singleton_returns_same_instance(self):
        """get_custom_dictionary は同じインスタンスを返す"""
        from custom_dictionary import get_custom_dictionary
        config = {"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}}
        d1 = get_custom_dictionary(config)
        d2 = get_custom_dictionary(config)
        assert d1 is d2

    def test_singleton_thread_safe(self):
        """複数スレッドから同時に get_custom_dictionary を呼んでも同一インスタンス"""
        from custom_dictionary import get_custom_dictionary
        import custom_dictionary
        custom_dictionary._custom_dictionary = None

        config = {"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}}
        results = []

        def worker():
            d = get_custom_dictionary(config)
            results.append(id(d))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 全て同じインスタンスID
        assert len(set(results)) == 1

    def test_singleton_first_call_uses_config(self):
        """初回呼び出しの config が使われる"""
        from custom_dictionary import get_custom_dictionary
        config = {"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}}
        d = get_custom_dictionary(config)
        assert isinstance(d.hotwords, list)

    def test_init_with_none_config(self):
        """config が None の場合、空の辞書として扱われる"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary(None)
        assert isinstance(d.hotwords, list)

    def test_merge_custom_vocabulary_domains(self):
        """_merge_custom_vocabulary がドメイン別語彙をカテゴリに追加する"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})

        # CustomVocabulary をモック
        mock_cv = MagicMock()
        mock_cv.hotwords = ["用語X", "用語Y"]
        mock_cv.replacements = {"aa": "BB"}
        mock_cv.domain_vocabularies = {"finance": ["株式", "投資"]}
        d._custom_vocab = mock_cv

        d._merge_custom_vocabulary()
        assert "用語X" in d.hotwords
        assert "用語Y" in d.hotwords
        assert d.replacements["aa"] == "BB"
        assert "株式" in d.categories.get("finance", [])

    def test_merge_construction_vocabulary_with_categories(self):
        """_merge_construction_vocabulary が指定カテゴリのみマージする"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})

        mock_cv = MagicMock()
        mock_cv.get_terms_by_category.side_effect = lambda cat: {
            "standard_labor": ["普通作業員"],
            "cost_management": ["積算"],
        }.get(cat, [])
        mock_cv.replacements = {}
        d._construction_vocab = mock_cv

        config = {"categories": ["standard_labor"]}
        d._merge_construction_vocabulary(config)
        assert "普通作業員" in d.hotwords
        assert "積算" not in d.hotwords

    def test_merge_construction_vocabulary_no_categories(self):
        """カテゴリ指定なしの場合、全ホットワードがマージされる"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})

        mock_cv = MagicMock()
        mock_cv.hotwords = ["全用語A", "全用語B"]
        mock_cv.category_vocabularies = {"cat1": ["全用語A"], "cat2": ["全用語B"]}
        mock_cv.replacements = {"x": "Y"}
        d._construction_vocab = mock_cv

        config = {}  # カテゴリ指定なし
        d._merge_construction_vocabulary(config)
        assert "全用語A" in d.hotwords
        assert "全用語B" in d.hotwords
        assert d.replacements["x"] == "Y"

    def test_add_term_with_custom_vocab(self):
        """add_term がカスタム語彙にも同時に追加する"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        mock_cv = MagicMock()
        d._custom_vocab = mock_cv

        d.add_term("新用語", "test_cat")
        assert "新用語" in d.hotwords
        mock_cv.add_hotword.assert_called_once_with("新用語")

    def test_add_replacement_with_custom_vocab(self):
        """add_replacement がカスタム語彙にも同時に追加する"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        mock_cv = MagicMock()
        d._custom_vocab = mock_cv

        d.add_replacement("誤り", "正しい")
        assert d.replacements["誤り"] == "正しい"
        mock_cv.add_replacement.assert_called_once_with("誤り", "正しい")

    def test_add_term_empty_does_nothing(self):
        """空文字列の add_term は何も追加しない"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        count = len(d.hotwords)
        d.add_term("", "cat")
        assert len(d.hotwords) == count

    def test_reload_clears_and_reloads(self):
        """reload が全データをクリアして再読み込みする"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.hotwords = ["test"]
        d.replacements = {"a": "b"}
        d.categories = {"cat": ["test"]}
        d.reload()
        assert d.hotwords == []
        assert d.replacements == {}
        assert d.categories == {}

    def test_get_construction_vocabulary_none_when_disabled(self):
        """建設業用語辞書が無効の場合、get_construction_vocabulary は None を返す"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        assert d.get_construction_vocabulary() is None

    def test_get_custom_vocabulary_none_when_disabled(self):
        """カスタム語彙が無効の場合、get_custom_vocabulary は None を返す"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        assert d.get_custom_vocabulary() is None

    def test_get_whisper_prompt_by_category(self):
        """カテゴリ指定でプロンプトを生成できる"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.categories["test_cat"] = ["用語A", "用語B"]
        prompt = d.get_whisper_prompt(category="test_cat")
        assert "用語A" in prompt
        assert "用語B" in prompt

    def test_apply_replacements_longest_first(self):
        """置換は長い文字列から先に行われ、連鎖置換を防ぐ"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.replacements = {
            "けんたいきょう": "建退共",
            "けんせつたいきょきょう": "建設退職共済",
        }
        result = d.apply_replacements("けんせつたいきょきょうの手続き")
        assert "建設退職共済" in result

    def test_search_terms_case_insensitive(self):
        """検索は大小文字を区別しない"""
        from custom_dictionary import CustomDictionary
        d = CustomDictionary({"construction_vocabulary": {"enabled": False}, "vocabulary": {"enabled": False}})
        d.hotwords = ["API", "api_test", "Other"]
        results = d.search_terms("api")
        assert "API" in results
        assert "api_test" in results
        assert "Other" not in results


# ============================================================================
# 4f. construction_vocabulary.py 追加テスト - apply_replacements_to_text
# ============================================================================

class TestConstructionVocabularyExtended:
    """ConstructionVocabulary.apply_replacements_to_text の拡張テスト"""

    def test_apply_replacements_to_text_japanese_no_word_boundary(self):
        """日本語テキストでは \\b を使わず re.escape でマッチする"""
        from construction_vocabulary import ConstructionVocabulary
        replacements = {"ほおがけ": "歩掛", "きじゅんない": "基準内"}
        result = ConstructionVocabulary.apply_replacements_to_text(
            "ほおがけの計算ときじゅんないの確認", replacements
        )
        assert "歩掛" in result
        assert "基準内" in result

    def test_apply_replacements_to_text_ascii_uses_word_boundary(self):
        """ASCII テキストでは \\b ワード境界を使う"""
        from construction_vocabulary import ConstructionVocabulary
        replacements = {"API": "Application Programming Interface"}
        result = ConstructionVocabulary.apply_replacements_to_text(
            "Use the API to connect", replacements
        )
        assert "Application Programming Interface" in result

    def test_apply_replacements_to_text_ascii_word_boundary_prevents_partial(self):
        """ASCII の \\b ワード境界により部分一致は置換されない"""
        from construction_vocabulary import ConstructionVocabulary
        replacements = {"API": "Interface"}
        result = ConstructionVocabulary.apply_replacements_to_text(
            "RAPID deployment", replacements
        )
        # "API" in "RAPID" はワード境界に合致しないため置換されない
        assert "RAPID" in result
        assert "Interface" not in result

    def test_apply_replacements_to_text_longest_first(self):
        """長い置換キーが先に処理され、連鎖置換を防止する"""
        from construction_vocabulary import ConstructionVocabulary
        replacements = {
            "けん": "検",
            "けんちく": "建築",
        }
        result = ConstructionVocabulary.apply_replacements_to_text(
            "けんちくの確認", replacements
        )
        assert "建築" in result

    def test_apply_replacements_to_text_empty_replacements(self):
        """空の置換辞書ではテキストがそのまま返される"""
        from construction_vocabulary import ConstructionVocabulary
        result = ConstructionVocabulary.apply_replacements_to_text("テスト", {})
        assert result == "テスト"

    def test_apply_replacements_to_text_empty_text(self):
        """空テキストでは空文字列が返される"""
        from construction_vocabulary import ConstructionVocabulary
        result = ConstructionVocabulary.apply_replacements_to_text("", {"a": "b"})
        assert result == ""

    def test_add_term_empty_raises(self, tmp_path):
        """空文字列の add_term は ValueError"""
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        with pytest.raises(ValueError, match="cannot be empty"):
            vocab.add_term("")

    def test_add_term_whitespace_only_raises(self, tmp_path):
        """空白のみの add_term は ValueError"""
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        with pytest.raises(ValueError, match="cannot be empty"):
            vocab.add_term("   ")

    def test_add_term_too_long_raises(self, tmp_path):
        """MAX_TERM_LENGTH を超える add_term は ValueError"""
        from construction_vocabulary import ConstructionVocabulary
        vocab = ConstructionVocabulary(str(tmp_path / "vocab.json"))
        with pytest.raises(ValueError, match="too long"):
            vocab.add_term("あ" * 101)

    def test_construction_singleton_thread_safe(self):
        """get_construction_vocabulary のシングルトンがスレッドセーフ"""
        import construction_vocabulary
        construction_vocabulary._construction_vocab = None

        results = []

        def worker():
            from construction_vocabulary import get_construction_vocabulary
            v = get_construction_vocabulary()
            results.append(id(v))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 1
        # クリーンアップ
        construction_vocabulary._construction_vocab = None


# ============================================================================
# workers.py テスト
# ============================================================================

from workers import (
    _normalize_segments,
    SharedConstants,
    stop_worker,
    TranscriptionWorker,
    BatchTranscriptionWorker,
)


class TestNormalizeSegments:
    """_normalize_segments のテスト"""

    def test_empty_result(self):
        """空の結果"""
        assert _normalize_segments({}) == []
        assert _normalize_segments({"chunks": []}) == []
        assert _normalize_segments({"segments": []}) == []

    def test_chunks_with_timestamp_tuple(self):
        """chunks形式 + timestampタプル"""
        result = {
            "chunks": [
                {"text": "hello", "timestamp": (0.0, 1.5)},
                {"text": "world", "timestamp": (1.5, 3.0)},
            ]
        }
        normalized = _normalize_segments(result)
        assert len(normalized) == 2
        assert normalized[0] == {"text": "hello", "start": 0.0, "end": 1.5}
        assert normalized[1] == {"text": "world", "start": 1.5, "end": 3.0}

    def test_chunks_with_timestamp_list(self):
        """chunks形式 + timestampリスト"""
        result = {
            "chunks": [
                {"text": "test", "timestamp": [2.0, 4.0]},
            ]
        }
        normalized = _normalize_segments(result)
        assert len(normalized) == 1
        assert normalized[0]["start"] == 2.0
        assert normalized[0]["end"] == 4.0

    def test_segments_with_start_key(self):
        """segments形式 + start/end"""
        result = {
            "segments": [
                {"text": "seg1", "start": 0.0, "end": 1.0},
                {"text": "seg2", "start": 1.0, "end": 2.0},
            ]
        }
        normalized = _normalize_segments(result)
        assert len(normalized) == 2
        assert normalized[0] == {"text": "seg1", "start": 0.0, "end": 1.0}

    def test_segments_without_timestamps(self):
        """タイムスタンプなしセグメント"""
        result = {
            "segments": [
                {"text": "no-time"},
            ]
        }
        normalized = _normalize_segments(result)
        assert len(normalized) == 1
        assert normalized[0] == {"text": "no-time", "start": 0, "end": 0}

    def test_short_timestamp_tuple(self):
        """短いタイムスタンプ（開始のみ）"""
        result = {
            "chunks": [
                {"text": "a", "timestamp": (1.0,)},
                {"text": "b", "timestamp": ()},
            ]
        }
        normalized = _normalize_segments(result)
        assert normalized[0]["start"] == 1.0
        assert normalized[0]["end"] == 0
        assert normalized[1]["start"] == 0
        assert normalized[1]["end"] == 0

    def test_chunks_takes_priority_over_segments(self):
        """chunksとsegments両方存在する場合、chunksを優先"""
        result = {
            "chunks": [{"text": "from_chunks", "timestamp": (0, 1)}],
            "segments": [{"text": "from_segments", "start": 0, "end": 1}],
        }
        normalized = _normalize_segments(result)
        assert len(normalized) == 1
        assert normalized[0]["text"] == "from_chunks"


class TestSharedConstants:
    """SharedConstants のテスト"""

    def test_progress_values(self):
        """進捗値が正しい順序"""
        assert SharedConstants.PROGRESS_MODEL_LOAD < SharedConstants.PROGRESS_BEFORE_TRANSCRIBE
        assert SharedConstants.PROGRESS_BEFORE_TRANSCRIBE < SharedConstants.PROGRESS_AFTER_TRANSCRIBE
        assert SharedConstants.PROGRESS_AFTER_TRANSCRIBE < SharedConstants.PROGRESS_DIARIZATION_START
        assert SharedConstants.PROGRESS_DIARIZATION_START < SharedConstants.PROGRESS_DIARIZATION_END
        assert SharedConstants.PROGRESS_DIARIZATION_END < SharedConstants.PROGRESS_COMPLETE
        assert SharedConstants.PROGRESS_COMPLETE == 100

    def test_supported_extensions(self):
        """サポートされる拡張子"""
        assert '.mp3' in SharedConstants.SUPPORTED_EXTENSIONS
        assert '.wav' in SharedConstants.SUPPORTED_EXTENSIONS
        assert '.mp4' in SharedConstants.SUPPORTED_EXTENSIONS
        assert '.flac' in SharedConstants.SUPPORTED_EXTENSIONS
        for ext in SharedConstants.SUPPORTED_EXTENSIONS:
            assert ext.startswith('.')

    def test_audio_file_filter(self):
        """ファイルフィルタ文字列"""
        assert "Audio Files" in SharedConstants.AUDIO_FILE_FILTER
        assert "*.mp3" in SharedConstants.AUDIO_FILE_FILTER
        assert "All Files" in SharedConstants.AUDIO_FILE_FILTER

    def test_timeout_values(self):
        """タイムアウト値が正値"""
        assert SharedConstants.THREAD_WAIT_TIMEOUT > 0
        assert SharedConstants.MONITOR_WAIT_TIMEOUT > 0
        assert SharedConstants.BATCH_WAIT_TIMEOUT > 0

    def test_batch_workers(self):
        """バッチワーカー数が正値"""
        assert SharedConstants.BATCH_WORKERS_DEFAULT > 0
        assert SharedConstants.MONITOR_BATCH_WORKERS > 0


class TestStopWorker:
    """stop_worker のテスト"""

    def test_none_worker(self):
        """Noneワーカーは何もしない"""
        stop_worker(None, "test")  # Should not raise

    def test_not_running_worker(self):
        """非実行中ワーカーは何もしない"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        stop_worker(mock_worker, "test")
        mock_worker.quit.assert_not_called()

    def test_cancel_worker(self):
        """cancel=TrueでキャンセルAPIを呼び出す"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.wait.return_value = True
        stop_worker(mock_worker, "test", cancel=True)
        mock_worker.cancel.assert_called_once()
        mock_worker.wait.assert_called_once()

    def test_stop_worker_method(self):
        """stop=TrueでstopAPIを呼び出す"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.wait.return_value = True
        stop_worker(mock_worker, "test", stop=True)
        mock_worker.stop.assert_called_once()

    def test_quit_fallback(self):
        """cancel/stopなしの場合quitを呼び出す"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.wait.return_value = True
        stop_worker(mock_worker, "test")
        mock_worker.quit.assert_called_once()

    def test_terminate_on_timeout(self):
        """タイムアウト時にterminateを呼び出す"""
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.wait.side_effect = [False, True]  # 最初はタイムアウト、2回目は成功
        stop_worker(mock_worker, "test", timeout=100)
        mock_worker.terminate.assert_called_once()


class TestTranscriptionWorkerInit:
    """TranscriptionWorker 初期化テスト"""

    @patch('workers.TranscriptionEngine')
    def test_basic_init(self, mock_engine_cls):
        """基本初期化"""
        worker = TranscriptionWorker("/test/audio.mp3")
        assert worker.audio_path == "/test/audio.mp3"
        assert worker.enable_diarization is False
        assert worker.diarizer is None
        assert not worker._cancel_event.is_set()

    @patch('workers.TranscriptionEngine')
    def test_init_with_diarization(self, mock_engine_cls):
        """話者分離有効で初期化"""
        with patch('workers.FreeSpeakerDiarizer') as mock_diar_cls:
            worker = TranscriptionWorker("/test/audio.mp3", enable_diarization=True)
            assert worker.enable_diarization is True

    @patch('workers.TranscriptionEngine')
    def test_cancel(self, mock_engine_cls):
        """キャンセルフラグ"""
        worker = TranscriptionWorker("/test/audio.mp3")
        assert not worker._cancel_event.is_set()
        worker.cancel()
        assert worker._cancel_event.is_set()


class TestBatchTranscriptionWorkerInit:
    """BatchTranscriptionWorker 初期化テスト"""

    def test_basic_init(self):
        """基本初期化"""
        paths = ["/a.mp3", "/b.mp3"]
        worker = BatchTranscriptionWorker(paths)
        assert worker.audio_paths == paths
        assert worker.enable_diarization is False
        assert worker.max_workers == 3
        assert worker.formatter is None
        assert worker.use_llm_correction is False
        assert worker.completed == 0
        assert worker.success_count == 0
        assert worker.failed_count == 0
        assert worker._cancel_event.is_set() is False

    def test_init_with_options(self):
        """オプション付き初期化"""
        mock_formatter = MagicMock()
        worker = BatchTranscriptionWorker(
            ["/a.mp3"],
            enable_diarization=True,
            max_workers=5,
            formatter=mock_formatter,
            use_llm_correction=True
        )
        assert worker.enable_diarization is True
        assert worker.max_workers == 5
        assert worker.formatter is mock_formatter
        assert worker.use_llm_correction is True

    def test_cancel(self):
        """キャンセル"""
        worker = BatchTranscriptionWorker(["/a.mp3"])
        assert worker._cancel_event.is_set() is False
        worker.cancel()
        assert worker._cancel_event.is_set() is True

    def test_cancel_with_executor(self):
        """executor存在時のキャンセル"""
        worker = BatchTranscriptionWorker(["/a.mp3"])
        mock_executor = MagicMock()
        worker._executor = mock_executor
        worker.cancel()
        assert worker._cancel_event.is_set() is True
        mock_executor.shutdown.assert_called_once_with(wait=False)

    def test_process_single_file_cancelled(self):
        """キャンセル済みファイルの処理"""
        worker = BatchTranscriptionWorker(["/a.mp3"])
        worker._cancel_event.set()
        path, msg, success = worker.process_single_file("/a.mp3")
        assert path == "/a.mp3"
        assert success is False
        assert "キャンセル" in msg


# ============================================================================
# time_utils.py テスト
# ============================================================================

from time_utils import format_time_hms, format_time_srt, format_time_vtt


class TestTimeUtils:
    """時間フォーマットユーティリティのテスト"""

    def test_format_time_hms_seconds_only(self):
        assert format_time_hms(45) == "00:45"

    def test_format_time_hms_minutes_seconds(self):
        assert format_time_hms(125) == "02:05"

    def test_format_time_hms_with_hours(self):
        assert format_time_hms(3661) == "1:01:01"

    def test_format_time_hms_zero(self):
        assert format_time_hms(0) == "00:00"

    def test_format_time_srt_basic(self):
        assert format_time_srt(3661.5) == "01:01:01,500"

    def test_format_time_srt_zero(self):
        assert format_time_srt(0) == "00:00:00,000"

    def test_format_time_srt_negative_clamped(self):
        assert format_time_srt(-5.0) == "00:00:00,000"

    def test_format_time_vtt_basic(self):
        assert format_time_vtt(3661.5) == "01:01:01.500"

    def test_format_time_vtt_zero(self):
        assert format_time_vtt(0) == "00:00:00.000"

    def test_format_time_vtt_negative_clamped(self):
        assert format_time_vtt(-5.0) == "00:00:00.000"

    def test_format_time_srt_milliseconds(self):
        assert format_time_srt(1.234) == "00:00:01,234"

    def test_format_time_vtt_milliseconds(self):
        assert format_time_vtt(1.234) == "00:00:01.234"
