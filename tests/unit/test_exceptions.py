"""
exceptions.py の単体テスト

カバレッジ目標: 100%
全ての例外クラスとユーティリティ関数をテスト
"""

import pytest
import sys
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from exceptions import (
    # Base
    RealtimeTranscriptionError,
    # Audio
    AudioCaptureError,
    AudioDeviceNotFoundError,
    AudioStreamError,
    PyAudioInitializationError,
    # VAD
    VADError,
    InvalidVADThresholdError,
    # Transcription
    TranscriptionEngineError,
    ModelLoadingError,
    TranscriptionFailedError,
    UnsupportedModelError,
    # Resource
    ResourceError,
    ResourceNotAvailableError,
    InsufficientMemoryError,
    # Configuration
    ConfigurationError,
    InvalidConfigurationError,
    # Utilities
    is_realtime_transcription_error,
    get_error_category
)


# ==================== Base Exception Tests ====================

@pytest.mark.unit
class TestRealtimeTranscriptionError:
    """基底例外クラスのテスト"""

    def test_can_be_raised(self):
        """例外が発生できることを確認"""
        with pytest.raises(RealtimeTranscriptionError):
            raise RealtimeTranscriptionError("Test error")

    def test_error_message(self):
        """エラーメッセージが正しく設定されることを確認"""
        error_msg = "Test error message"
        error = RealtimeTranscriptionError(error_msg)
        assert str(error) == error_msg

    def test_inheritance(self):
        """Exceptionを継承していることを確認"""
        error = RealtimeTranscriptionError("Test")
        assert isinstance(error, Exception)


# ==================== Audio Exception Tests ====================

@pytest.mark.unit
class TestAudioCaptureError:
    """音声キャプチャエラーのテスト"""

    def test_inheritance(self):
        """継承関係の確認"""
        error = AudioCaptureError("Test")
        assert isinstance(error, RealtimeTranscriptionError)
        assert isinstance(error, Exception)


@pytest.mark.unit
class TestAudioDeviceNotFoundError:
    """音声デバイス未検出エラーのテスト"""

    def test_initialization(self):
        """初期化とメッセージ生成"""
        device_index = 5
        error = AudioDeviceNotFoundError(device_index)

        assert error.device_index == device_index
        assert "Audio device not found" in str(error)
        assert "index=5" in str(error)

    def test_inheritance(self):
        """継承関係の確認"""
        error = AudioDeviceNotFoundError(0)
        assert isinstance(error, AudioCaptureError)
        assert isinstance(error, RealtimeTranscriptionError)

    def test_different_device_indices(self):
        """様々なデバイスインデックスでテスト"""
        for index in [0, 1, 10, 99]:
            error = AudioDeviceNotFoundError(index)
            assert error.device_index == index
            assert f"index={index}" in str(error)


@pytest.mark.unit
class TestAudioStreamError:
    """音声ストリームエラーのテスト"""

    def test_initialization_without_device_index(self):
        """デバイスインデックスなしで初期化"""
        message = "Stream failed to open"
        error = AudioStreamError(message)

        assert error.device_index is None
        assert "Audio stream error" in str(error)
        assert message in str(error)

    def test_initialization_with_device_index(self):
        """デバイスインデックスありで初期化"""
        message = "Stream failed to open"
        device_index = 3
        error = AudioStreamError(message, device_index)

        assert error.device_index == device_index
        assert "Audio stream error" in str(error)
        assert message in str(error)
        assert "device=3" in str(error)

    def test_inheritance(self):
        """継承関係の確認"""
        error = AudioStreamError("Test")
        assert isinstance(error, AudioCaptureError)


@pytest.mark.unit
class TestPyAudioInitializationError:
    """PyAudio初期化エラーのテスト"""

    def test_initialization(self):
        """初期化と元のエラー保存"""
        original_error = ValueError("PortAudio not found")
        error = PyAudioInitializationError(original_error)

        assert error.original_error is original_error
        assert "Failed to initialize PyAudio" in str(error)
        assert "PortAudio not found" in str(error)

    def test_with_different_original_errors(self):
        """様々な元のエラーでテスト"""
        errors = [
            ValueError("Test ValueError"),
            RuntimeError("Test RuntimeError"),
            OSError("Test OSError")
        ]

        for orig_error in errors:
            error = PyAudioInitializationError(orig_error)
            assert error.original_error is orig_error
            assert str(orig_error) in str(error)


# ==================== VAD Exception Tests ====================

@pytest.mark.unit
class TestVADError:
    """VADエラーのテスト"""

    def test_inheritance(self):
        """継承関係の確認"""
        error = VADError("Test")
        assert isinstance(error, RealtimeTranscriptionError)


@pytest.mark.unit
class TestInvalidVADThresholdError:
    """VAD閾値無効エラーのテスト"""

    def test_initialization(self):
        """初期化とメッセージ生成"""
        threshold = 1.5
        valid_range = (0.0, 1.0)
        error = InvalidVADThresholdError(threshold, valid_range)

        assert error.threshold == threshold
        assert error.valid_range == valid_range
        assert "Invalid VAD threshold" in str(error)
        assert "1.5" in str(error)
        assert "0.0" in str(error)
        assert "1.0" in str(error)

    def test_negative_threshold(self):
        """負の閾値でテスト"""
        error = InvalidVADThresholdError(-0.5, (0.0, 1.0))
        assert error.threshold == -0.5
        assert "-0.5" in str(error)

    def test_inheritance(self):
        """継承関係の確認"""
        error = InvalidVADThresholdError(1.5, (0.0, 1.0))
        assert isinstance(error, VADError)


# ==================== Transcription Exception Tests ====================

@pytest.mark.unit
class TestTranscriptionEngineError:
    """文字起こしエンジンエラーのテスト"""

    def test_inheritance(self):
        """継承関係の確認"""
        error = TranscriptionEngineError("Test")
        assert isinstance(error, RealtimeTranscriptionError)


@pytest.mark.unit
class TestModelLoadingError:
    """モデル読み込みエラーのテスト"""

    def test_initialization(self):
        """初期化とメッセージ生成"""
        model_name = "kotoba-whisper-v2.2"
        original_error = ConnectionError("Network timeout")
        error = ModelLoadingError(model_name, original_error)

        assert error.model_name == model_name
        assert error.original_error is original_error
        assert "Failed to load model" in str(error)
        assert model_name in str(error)
        assert "Network timeout" in str(error)

    def test_different_models(self):
        """様々なモデル名でテスト"""
        models = ["base", "small", "medium", "large"]
        orig_error = ValueError("Invalid model")

        for model in models:
            error = ModelLoadingError(model, orig_error)
            assert error.model_name == model
            assert model in str(error)

    def test_inheritance(self):
        """継承関係の確認"""
        error = ModelLoadingError("test", ValueError("test"))
        assert isinstance(error, TranscriptionEngineError)


@pytest.mark.unit
class TestTranscriptionFailedError:
    """文字起こし失敗エラーのテスト"""

    def test_initialization_without_duration(self):
        """音声長なしで初期化"""
        message = "Transcription timeout"
        error = TranscriptionFailedError(message)

        assert error.audio_duration is None
        assert "Transcription failed" in str(error)
        assert message in str(error)

    def test_initialization_with_duration(self):
        """音声長ありで初期化"""
        message = "Transcription timeout"
        duration = 125.75
        error = TranscriptionFailedError(message, duration)

        assert error.audio_duration == duration
        assert "Transcription failed" in str(error)
        assert message in str(error)
        assert "125.75s" in str(error)

    def test_inheritance(self):
        """継承関係の確認"""
        error = TranscriptionFailedError("Test")
        assert isinstance(error, TranscriptionEngineError)


@pytest.mark.unit
class TestUnsupportedModelError:
    """サポート外モデルエラーのテスト"""

    def test_initialization(self):
        """初期化とメッセージ生成"""
        model_name = "huge"
        supported = ["tiny", "base", "small", "medium"]
        error = UnsupportedModelError(model_name, supported)

        assert error.model_name == model_name
        assert error.supported_models == supported
        assert "Unsupported model" in str(error)
        assert "huge" in str(error)
        assert "tiny" in str(error)
        assert "base" in str(error)

    def test_empty_supported_list(self):
        """サポートモデルリストが空の場合"""
        error = UnsupportedModelError("test", [])
        assert error.supported_models == []
        assert "Unsupported model" in str(error)

    def test_inheritance(self):
        """継承関係の確認"""
        error = UnsupportedModelError("test", [])
        assert isinstance(error, TranscriptionEngineError)


# ==================== Resource Exception Tests ====================

@pytest.mark.unit
class TestResourceError:
    """リソースエラーのテスト"""

    def test_inheritance(self):
        """継承関係の確認"""
        error = ResourceError("Test")
        assert isinstance(error, RealtimeTranscriptionError)


@pytest.mark.unit
class TestResourceNotAvailableError:
    """リソース利用不可エラーのテスト"""

    def test_initialization(self):
        """初期化とメッセージ生成"""
        resource_name = "CUDA GPU"
        error = ResourceNotAvailableError(resource_name)

        assert error.resource_name == resource_name
        assert "Resource not available" in str(error)
        assert resource_name in str(error)

    def test_different_resources(self):
        """様々なリソース名でテスト"""
        resources = ["GPU", "CPU", "Memory", "Disk"]
        for resource in resources:
            error = ResourceNotAvailableError(resource)
            assert error.resource_name == resource
            assert resource in str(error)

    def test_inheritance(self):
        """継承関係の確認"""
        error = ResourceNotAvailableError("Test")
        assert isinstance(error, ResourceError)


@pytest.mark.unit
class TestInsufficientMemoryError:
    """メモリ不足エラーのテスト"""

    def test_initialization(self):
        """初期化とメッセージ生成"""
        required = 2048.0
        available = 512.0
        error = InsufficientMemoryError(required, available)

        assert error.required_mb == required
        assert error.available_mb == available
        assert "Insufficient memory" in str(error)
        assert "2048" in str(error)
        assert "512" in str(error)

    def test_different_memory_values(self):
        """様々なメモリ値でテスト"""
        test_cases = [
            (1024.0, 256.0),
            (4096.5, 1024.3),
            (512.25, 128.75)
        ]

        for required, available in test_cases:
            error = InsufficientMemoryError(required, available)
            assert error.required_mb == required
            assert error.available_mb == available

    def test_inheritance(self):
        """継承関係の確認"""
        error = InsufficientMemoryError(100, 50)
        assert isinstance(error, ResourceError)


# ==================== Configuration Exception Tests ====================

@pytest.mark.unit
class TestConfigurationError:
    """設定エラーのテスト"""

    def test_inheritance(self):
        """継承関係の確認"""
        error = ConfigurationError("Test")
        assert isinstance(error, RealtimeTranscriptionError)


@pytest.mark.unit
class TestInvalidConfigurationError:
    """無効設定エラーのテスト"""

    def test_initialization(self):
        """初期化とメッセージ生成"""
        param = "sample_rate"
        value = -1
        reason = "must be positive"
        error = InvalidConfigurationError(param, value, reason)

        assert error.param_name == param
        assert error.param_value == value
        assert error.reason == reason
        assert "Invalid configuration" in str(error)
        assert param in str(error)
        assert str(value) in str(error)
        assert reason in str(error)

    def test_with_different_value_types(self):
        """様々な型の値でテスト"""
        test_cases = [
            ("threshold", 0.5, "out of range"),
            ("model", "invalid", "not supported"),
            ("enabled", None, "cannot be None"),
            ("count", [1, 2, 3], "must be integer")
        ]

        for param, value, reason in test_cases:
            error = InvalidConfigurationError(param, value, reason)
            assert error.param_name == param
            assert error.param_value == value
            assert error.reason == reason

    def test_inheritance(self):
        """継承関係の確認"""
        error = InvalidConfigurationError("test", "value", "reason")
        assert isinstance(error, ConfigurationError)


# ==================== Utility Function Tests ====================

@pytest.mark.unit
class TestIsRealtimeTranscriptionError:
    """is_realtime_transcription_error 関数のテスト"""

    def test_with_realtime_error(self):
        """リアルタイム文字起こしエラーの場合True"""
        error = RealtimeTranscriptionError("Test")
        assert is_realtime_transcription_error(error) is True

    def test_with_audio_error(self):
        """音声エラーの場合True"""
        error = AudioDeviceNotFoundError(0)
        assert is_realtime_transcription_error(error) is True

    def test_with_vad_error(self):
        """VADエラーの場合True"""
        error = InvalidVADThresholdError(1.5, (0.0, 1.0))
        assert is_realtime_transcription_error(error) is True

    def test_with_transcription_error(self):
        """文字起こしエラーの場合True"""
        error = TranscriptionFailedError("Test")
        assert is_realtime_transcription_error(error) is True

    def test_with_resource_error(self):
        """リソースエラーの場合True"""
        error = InsufficientMemoryError(100, 50)
        assert is_realtime_transcription_error(error) is True

    def test_with_configuration_error(self):
        """設定エラーの場合True"""
        error = InvalidConfigurationError("test", "value", "reason")
        assert is_realtime_transcription_error(error) is True

    def test_with_standard_exception(self):
        """標準例外の場合False"""
        assert is_realtime_transcription_error(ValueError("Test")) is False
        assert is_realtime_transcription_error(RuntimeError("Test")) is False
        assert is_realtime_transcription_error(TypeError("Test")) is False


@pytest.mark.unit
class TestGetErrorCategory:
    """get_error_category 関数のテスト"""

    def test_audio_category(self):
        """音声関連エラーは"audio"を返す"""
        errors = [
            AudioCaptureError("Test"),
            AudioDeviceNotFoundError(0),
            AudioStreamError("Test"),
            PyAudioInitializationError(ValueError("Test"))
        ]
        for error in errors:
            assert get_error_category(error) == "audio"

    def test_vad_category(self):
        """VAD関連エラーは"vad"を返す"""
        errors = [
            VADError("Test"),
            InvalidVADThresholdError(1.5, (0.0, 1.0))
        ]
        for error in errors:
            assert get_error_category(error) == "vad"

    def test_transcription_category(self):
        """文字起こし関連エラーは"transcription"を返す"""
        errors = [
            TranscriptionEngineError("Test"),
            ModelLoadingError("base", ValueError("Test")),
            TranscriptionFailedError("Test"),
            UnsupportedModelError("huge", ["base"])
        ]
        for error in errors:
            assert get_error_category(error) == "transcription"

    def test_resource_category(self):
        """リソース関連エラーは"resource"を返す"""
        errors = [
            ResourceError("Test"),
            ResourceNotAvailableError("GPU"),
            InsufficientMemoryError(100, 50)
        ]
        for error in errors:
            assert get_error_category(error) == "resource"

    def test_configuration_category(self):
        """設定関連エラーは"configuration"を返す"""
        errors = [
            ConfigurationError("Test"),
            InvalidConfigurationError("param", "value", "reason")
        ]
        for error in errors:
            assert get_error_category(error) == "configuration"

    def test_non_realtime_error(self):
        """リアルタイム文字起こし関連でないエラーはNoneを返す"""
        assert get_error_category(ValueError("Test")) is None
        assert get_error_category(RuntimeError("Test")) is None
        assert get_error_category(TypeError("Test")) is None
        assert get_error_category(Exception("Test")) is None


# ==================== Integration Tests ====================

@pytest.mark.unit
class TestExceptionHierarchy:
    """例外階層の統合テスト"""

    def test_all_custom_exceptions_inherit_from_base(self):
        """全てのカスタム例外が基底クラスを継承"""
        exceptions = [
            AudioCaptureError("Test"),
            VADError("Test"),
            TranscriptionEngineError("Test"),
            ResourceError("Test"),
            ConfigurationError("Test")
        ]

        for error in exceptions:
            assert isinstance(error, RealtimeTranscriptionError)
            assert isinstance(error, Exception)

    def test_exception_catching_with_base_class(self):
        """基底クラスで全てのカスタム例外をキャッチ可能"""
        def raise_audio_error():
            raise AudioDeviceNotFoundError(0)

        def raise_vad_error():
            raise InvalidVADThresholdError(1.5, (0.0, 1.0))

        with pytest.raises(RealtimeTranscriptionError):
            raise_audio_error()

        with pytest.raises(RealtimeTranscriptionError):
            raise_vad_error()
