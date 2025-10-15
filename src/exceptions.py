"""
カスタム例外クラス定義

リアルタイム文字起こし機能用の例外階層を定義します。

階層構造:
RealtimeTranscriptionError (基底)
├── AudioCaptureError
│   ├── AudioDeviceNotFoundError
│   ├── AudioStreamError
│   └── PyAudioInitializationError
├── VADError
│   └── InvalidVADThresholdError
├── TranscriptionEngineError
│   ├── ModelLoadingError
│   ├── TranscriptionFailedError
│   └── UnsupportedModelError
├── ResourceError
│   ├── ResourceNotAvailableError
│   └── InsufficientMemoryError
└── ConfigurationError
    └── InvalidConfigurationError

Author: KotobaTranscriber Development Team
Date: 2025-10-15
Version: 1.0.0
"""

from typing import Optional, Any, List


class RealtimeTranscriptionError(Exception):
    """リアルタイム文字起こし機能の基底例外クラス

    全てのリアルタイム文字起こし関連の例外はこのクラスを継承します。
    """
    pass


# === 音声キャプチャ関連 ===

class AudioCaptureError(RealtimeTranscriptionError):
    """音声キャプチャエラーの基底クラス

    PyAudioやマイクデバイスに関連するエラーはこのクラスを継承します。
    """
    pass


class AudioDeviceNotFoundError(AudioCaptureError):
    """音声デバイスが見つからない

    指定されたデバイスインデックスに対応するマイクが存在しない場合に発生します。

    Attributes:
        device_index (int): 見つからなかったデバイスのインデックス
    """

    def __init__(self, device_index: int):
        self.device_index = device_index
        super().__init__(f"Audio device not found: index={device_index}")


class AudioStreamError(AudioCaptureError):
    """音声ストリームエラー

    PyAudioストリームの開始、停止、または操作中にエラーが発生した場合に発生します。

    Attributes:
        message (str): エラーメッセージ
        device_index (Optional[int]): デバイスインデックス（判明している場合）
    """

    def __init__(self, message: str, device_index: Optional[int] = None):
        self.device_index = device_index
        error_msg = f"Audio stream error: {message}"
        if device_index is not None:
            error_msg += f" (device={device_index})"
        super().__init__(error_msg)


class PyAudioInitializationError(AudioCaptureError):
    """PyAudio初期化エラー

    PyAudioオブジェクトの初期化に失敗した場合に発生します。
    通常、システムの音声ドライバーやライブラリの問題が原因です。

    Attributes:
        original_error (Exception): 元の例外オブジェクト
    """

    def __init__(self, original_error: Exception):
        self.original_error = original_error
        super().__init__(f"Failed to initialize PyAudio: {original_error}")


# === VAD関連 ===

class VADError(RealtimeTranscriptionError):
    """VAD（Voice Activity Detection）エラーの基底クラス

    音声検出機能に関連するエラーはこのクラスを継承します。
    """
    pass


class InvalidVADThresholdError(VADError):
    """VAD閾値が無効

    VAD閾値が有効範囲外の値に設定された場合に発生します。

    Attributes:
        threshold (float): 指定された無効な閾値
        valid_range (tuple): 有効な閾値の範囲 (min, max)
    """

    def __init__(self, threshold: float, valid_range: tuple):
        self.threshold = threshold
        self.valid_range = valid_range
        super().__init__(
            f"Invalid VAD threshold: {threshold} "
            f"(valid range: {valid_range[0]} ~ {valid_range[1]})"
        )


# === 文字起こしエンジン関連 ===

class TranscriptionEngineError(RealtimeTranscriptionError):
    """文字起こしエンジンエラーの基底クラス

    Whisperモデルや文字起こし処理に関連するエラーはこのクラスを継承します。
    """
    pass


class ModelLoadingError(TranscriptionEngineError):
    """モデル読み込みエラー

    Whisperモデルのダウンロードまたは読み込みに失敗した場合に発生します。

    Attributes:
        model_name (str): 読み込みに失敗したモデル名
        original_error (Exception): 元の例外オブジェクト
    """

    def __init__(self, model_name: str, original_error: Exception):
        self.model_name = model_name
        self.original_error = original_error
        super().__init__(
            f"Failed to load model '{model_name}': {original_error}"
        )


class TranscriptionFailedError(TranscriptionEngineError):
    """文字起こし失敗

    音声データの文字起こし処理中にエラーが発生した場合に発生します。

    Attributes:
        message (str): エラーメッセージ
        audio_duration (Optional[float]): 処理しようとした音声の長さ（秒）
    """

    def __init__(self, message: str, audio_duration: Optional[float] = None):
        self.audio_duration = audio_duration
        error_msg = f"Transcription failed: {message}"
        if audio_duration is not None:
            error_msg += f" (audio duration: {audio_duration:.2f}s)"
        super().__init__(error_msg)


class UnsupportedModelError(TranscriptionEngineError):
    """サポートされていないモデル

    指定されたモデル名がサポートされていない場合に発生します。

    Attributes:
        model_name (str): 指定された無効なモデル名
        supported_models (List[str]): サポートされているモデルのリスト
    """

    def __init__(self, model_name: str, supported_models: List[str]):
        self.model_name = model_name
        self.supported_models = supported_models
        super().__init__(
            f"Unsupported model: '{model_name}'. "
            f"Supported models: {', '.join(supported_models)}"
        )


# === リソース管理関連 ===

class ResourceError(RealtimeTranscriptionError):
    """リソースエラーの基底クラス

    メモリ、CPU、GPUなどのシステムリソースに関連するエラーはこのクラスを継承します。
    """
    pass


class ResourceNotAvailableError(ResourceError):
    """リソースが利用不可

    必要なリソース（GPU、メモリなど）が利用できない場合に発生します。

    Attributes:
        resource_name (str): 利用できないリソースの名前
    """

    def __init__(self, resource_name: str):
        self.resource_name = resource_name
        super().__init__(f"Resource not available: {resource_name}")


class InsufficientMemoryError(ResourceError):
    """メモリ不足エラー

    システムメモリが不足している場合に発生します。

    Attributes:
        required_mb (float): 必要なメモリ量（MB）
        available_mb (float): 利用可能なメモリ量（MB）
    """

    def __init__(self, required_mb: float, available_mb: float):
        self.required_mb = required_mb
        self.available_mb = available_mb
        super().__init__(
            f"Insufficient memory: required {required_mb:.0f}MB, "
            f"available {available_mb:.0f}MB"
        )


# === 設定関連 ===

class ConfigurationError(RealtimeTranscriptionError):
    """設定エラーの基底クラス

    アプリケーション設定やパラメータに関連するエラーはこのクラスを継承します。
    """
    pass


class InvalidConfigurationError(ConfigurationError):
    """無効な設定

    パラメータ値が無効な場合に発生します。

    Attributes:
        param_name (str): パラメータ名
        param_value (Any): 指定された無効な値
        reason (str): 無効である理由
    """

    def __init__(self, param_name: str, param_value: Any, reason: str):
        self.param_name = param_name
        self.param_value = param_value
        self.reason = reason
        super().__init__(
            f"Invalid configuration: {param_name}={param_value} ({reason})"
        )


# === ユーティリティ関数 ===

def is_realtime_transcription_error(error: Exception) -> bool:
    """例外がリアルタイム文字起こし関連のエラーかどうかを判定

    Args:
        error (Exception): 判定する例外オブジェクト

    Returns:
        bool: リアルタイム文字起こし関連のエラーの場合True
    """
    return isinstance(error, RealtimeTranscriptionError)


def get_error_category(error: Exception) -> Optional[str]:
    """例外のカテゴリを取得

    Args:
        error (Exception): 例外オブジェクト

    Returns:
        Optional[str]: エラーカテゴリ名（"audio", "vad", "transcription", "resource", "configuration"）
                      または None（リアルタイム文字起こし関連エラーでない場合）
    """
    if isinstance(error, AudioCaptureError):
        return "audio"
    elif isinstance(error, VADError):
        return "vad"
    elif isinstance(error, TranscriptionEngineError):
        return "transcription"
    elif isinstance(error, ResourceError):
        return "resource"
    elif isinstance(error, ConfigurationError):
        return "configuration"
    else:
        return None


if __name__ == "__main__":
    """例外クラスのテスト"""

    # テスト1: AudioDeviceNotFoundError
    try:
        raise AudioDeviceNotFoundError(5)
    except AudioDeviceNotFoundError as e:
        print(f"✓ {e}")
        print(f"  Device index: {e.device_index}")
        print(f"  Is RealtimeTranscriptionError: {isinstance(e, RealtimeTranscriptionError)}")
        print(f"  Category: {get_error_category(e)}")
        print()

    # テスト2: ModelLoadingError
    try:
        original = ValueError("Network timeout")
        raise ModelLoadingError("base", original)
    except ModelLoadingError as e:
        print(f"✓ {e}")
        print(f"  Model: {e.model_name}")
        print(f"  Original error: {e.original_error}")
        print(f"  Category: {get_error_category(e)}")
        print()

    # テスト3: InvalidVADThresholdError
    try:
        raise InvalidVADThresholdError(0.1, (0.005, 0.050))
    except InvalidVADThresholdError as e:
        print(f"✓ {e}")
        print(f"  Threshold: {e.threshold}")
        print(f"  Valid range: {e.valid_range}")
        print(f"  Category: {get_error_category(e)}")
        print()

    # テスト4: InsufficientMemoryError
    try:
        raise InsufficientMemoryError(2048, 512)
    except InsufficientMemoryError as e:
        print(f"✓ {e}")
        print(f"  Required: {e.required_mb}MB")
        print(f"  Available: {e.available_mb}MB")
        print(f"  Category: {get_error_category(e)}")
        print()

    # テスト5: UnsupportedModelError
    try:
        raise UnsupportedModelError("huge", ["tiny", "base", "small", "medium"])
    except UnsupportedModelError as e:
        print(f"✓ {e}")
        print(f"  Model: {e.model_name}")
        print(f"  Supported: {e.supported_models}")
        print(f"  Category: {get_error_category(e)}")
        print()

    print("All exception tests passed! ✅")
