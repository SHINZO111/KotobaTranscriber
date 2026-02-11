"""
カスタム例外クラス - KotobaTranscriber Custom Exception Classes

このモジュールは、KotobaTranscriberアプリケーション全体で使用されるカスタム例外を定義します。
各種エラーを適切に分類し、デバッグを容易にし、エラーハンドリングを改善します。

This module defines custom exceptions used throughout the KotobaTranscriber application.
It classifies various errors appropriately to facilitate debugging and improve error handling.

Exception Hierarchy:
    KotobaTranscriberError (Base)
    ├── FileProcessingError
    │   ├── AudioFormatError
    │   ├── AudioTooShortError
    │   └── AudioTooLongError
    ├── TranscriptionError
    │   ├── TranscriptionFailedError
    │   ├── ModelLoadError
    │   └── ModelNotLoadedError
    ├── ConfigurationError
    │   └── InvalidConfigValueError
    ├── BatchProcessingError
    │   └── BatchCancelledError
    ├── ResourceError
    │   ├── InsufficientMemoryError
    │   └── InsufficientDiskSpaceError
    ├── RealtimeProcessingError
    │   ├── AudioDeviceError
    │   ├── AudioCaptureError
    │   ├── AudioStreamError
    │   ├── PyAudioInitializationError
    │   └── VADError
    │       └── InvalidVADThresholdError
    ├── APIError
    │   ├── APIConnectionError
    │   ├── APIAuthenticationError
    │   └── APIRateLimitError
    ├── ExportError
    │   └── SubtitleExportError
    └── SecurityError
        ├── PathTraversalError
        └── UnsafePathError

Author: KotobaTranscriber Development Team
Date: 2025-10-18
Version: 2.2.0
"""

from typing import Optional

__all__ = [
    # Base exception
    'KotobaTranscriberError',

    # File processing exceptions
    'FileProcessingError',
    'AudioFormatError',
    'AudioTooShortError',
    'AudioTooLongError',

    # Transcription exceptions
    'TranscriptionError',
    'TranscriptionFailedError',
    'ModelLoadError',
    'ModelNotLoadedError',

    # Configuration exceptions
    'ConfigurationError',
    'InvalidConfigValueError',

    # Batch processing exceptions
    'BatchProcessingError',
    'BatchCancelledError',

    # Resource exceptions
    'ResourceError',
    'InsufficientMemoryError',
    'InsufficientDiskSpaceError',

    # Real-time processing exceptions
    'RealtimeProcessingError',
    'AudioDeviceError',
    'AudioCaptureError',
    'AudioStreamError',
    'PyAudioInitializationError',
    'VADError',
    'InvalidVADThresholdError',

    # API exceptions
    'APIError',
    'APIConnectionError',
    'APIAuthenticationError',
    'APIRateLimitError',

    # Export exceptions
    'ExportError',
    'SubtitleExportError',

    # Security exceptions
    'SecurityError',
    'PathTraversalError',
    'UnsafePathError',

    # Utility functions
    'is_kotoba_error',
    'get_error_category',
]


# ============================================================================
# Base Exception
# ============================================================================

class KotobaTranscriberError(Exception):
    """
    KotobaTranscriberの全例外の基底クラス
    Base exception class for all KotobaTranscriber errors.

    すべてのカスタム例外はこのクラスを継承します。
    これにより、アプリケーション固有のエラーを一括でキャッチできます。

    All custom exceptions inherit from this class, allowing application-specific
    errors to be caught collectively.

    Example:
        try:
            # KotobaTranscriber operation
            pass
        except KotobaTranscriberError as e:
            # Handle any KotobaTranscriber-specific error
            print(f"Application error: {e}")
    """
    pass


# ============================================================================
# ファイル処理関連エラー - File Processing Errors
# ============================================================================

class FileProcessingError(KotobaTranscriberError):
    """
    ファイル処理中のエラー基底クラス
    Base exception for file processing failures.

    音声ファイルの読み込み、変換、保存などの処理で発生するエラーの基底クラスです。
    Base class for errors occurring during audio file loading, conversion, and saving.

    Example:
        raise FileProcessingError("Failed to process audio file: corrupted data")
    """
    pass


class AudioFormatError(FileProcessingError):
    """
    音声フォーマットエラー
    Invalid audio format or unsupported codec.

    サポートされていない音声フォーマット、不正なコーデック、
    または破損した音声ファイルを検出した場合に発生します。

    Raised when an unsupported audio format, invalid codec, or corrupted
    audio file is detected.

    Example:
        raise AudioFormatError(f"Unsupported audio format: {format_name}")
    """
    pass


class AudioTooShortError(FileProcessingError):
    """
    音声が短すぎるエラー
    Audio duration too short for processing.

    文字起こしに必要な最小時間に満たない音声ファイルを処理しようとした場合に発生します。
    Raised when attempting to process audio shorter than the minimum required duration.

    Attributes:
        duration (float): 実際の音声の長さ（秒）- Actual audio duration in seconds
        minimum (float): 必要な最小の長さ（秒）- Required minimum duration in seconds

    Example:
        raise AudioTooShortError("Audio too short", duration=1.5, minimum=3.0)
    """
    def __init__(self, message: str = "", duration: float = 0.0, minimum: float = 0.0, **kwargs):
        super().__init__(message, **kwargs)
        self.duration = duration
        self.minimum = minimum


class AudioTooLongError(FileProcessingError):
    """
    音声が長すぎるエラー
    Audio duration exceeds maximum limit.

    処理可能な最大時間を超える音声ファイルを処理しようとした場合に発生します。
    メモリ制限やタイムアウトを防ぐために使用されます。

    Raised when attempting to process audio exceeding the maximum allowed duration.
    Used to prevent memory limitations and timeouts.

    Attributes:
        duration (float): 実際の音声の長さ（秒）- Actual audio duration in seconds
        maximum (float): 許可される最大の長さ（秒）- Maximum allowed duration in seconds

    Example:
        raise AudioTooLongError("Audio too long", duration=7200, maximum=3600)
    """
    def __init__(self, message: str = "", duration: float = 0.0, maximum: float = 0.0, **kwargs):
        super().__init__(message, **kwargs)
        self.duration = duration
        self.maximum = maximum


# ============================================================================
# 文字起こし関連エラー - Transcription Errors
# ============================================================================

class TranscriptionError(KotobaTranscriberError):
    """
    文字起こしエラー基底クラス
    Base exception for transcription failures.

    音声認識、モデル処理、テキスト生成などの文字起こし処理で発生する
    エラーの基底クラスです。

    Base class for errors occurring during speech recognition, model processing,
    and text generation.

    Example:
        raise TranscriptionError("Transcription process encountered an error")
    """
    pass


class TranscriptionFailedError(TranscriptionError):
    """
    文字起こし失敗エラー
    Transcription process failed.

    音声認識処理が完全に失敗した場合、または結果が生成できなかった場合に発生します。
    Raised when the speech recognition process fails completely or cannot generate results.

    Attributes:
        audio_duration (Optional[float]): 音声の長さ（秒）- Audio duration in seconds

    Example:
        raise TranscriptionFailedError("Failed to transcribe audio", audio_duration=120.5)
    """

    def __init__(self, message: str, audio_duration: Optional[float] = None):
        self.audio_duration = audio_duration
        super().__init__(message)


class ModelLoadError(TranscriptionError):
    """
    モデル読み込みエラー
    Failed to load ML model.

    Whisperモデルのダウンロード、初期化、またはメモリへの読み込みが
    失敗した場合に発生します。

    Raised when Whisper model download, initialization, or loading into memory fails.

    Example:
        raise ModelLoadError(f"Failed to load model {model_name}: {error_message}")
    """
    pass


class ModelNotLoadedError(TranscriptionError):
    """
    モデル未読み込みエラー
    Model not loaded before use.

    モデルが初期化されていない状態で文字起こしを実行しようとした場合に発生します。
    Raised when attempting to perform transcription without initializing the model.

    Example:
        raise ModelNotLoadedError("Model must be loaded before transcription. Call load_model() first.")
    """
    pass


# ============================================================================
# 設定関連エラー - Configuration Errors
# ============================================================================

class ConfigurationError(KotobaTranscriberError):
    """
    設定エラー基底クラス
    Configuration file or settings error.

    設定ファイルの読み込み、パース、検証などで発生するエラーの基底クラスです。
    Base class for errors in configuration file loading, parsing, and validation.

    Example:
        raise ConfigurationError("Failed to load configuration file")
    """
    pass


class InvalidConfigValueError(ConfigurationError):
    """
    無効な設定値エラー
    Invalid value in configuration.

    設定ファイルまたはユーザー入力に不正な値が含まれている場合に発生します。
    Raised when configuration file or user input contains invalid values.

    Attributes:
        key (str): 設定キー名 - Configuration key name
        value (Any): 不正な値 - Invalid value
        expected (str): 期待される値の説明 - Description of expected value

    Example:
        raise InvalidConfigValueError(f"Invalid value for '{key}': {value}. Expected: {expected}")
    """
    pass


# ============================================================================
# バッチ処理関連エラー - Batch Processing Errors
# ============================================================================

class BatchProcessingError(KotobaTranscriberError):
    """
    バッチ処理エラー基底クラス
    Batch processing failure.

    複数ファイルの一括処理で発生するエラーの基底クラスです。
    Base class for errors occurring during batch processing of multiple files.

    Example:
        raise BatchProcessingError("Batch processing failed after 5 files")
    """
    pass


class BatchCancelledError(BatchProcessingError):
    """
    バッチキャンセルエラー
    Batch processing was cancelled.

    ユーザーまたはシステムによってバッチ処理が中断された場合に発生します。
    Raised when batch processing is interrupted by user or system.

    Attributes:
        processed_count (int): 処理済みファイル数 - Number of files processed
        total_count (int): 総ファイル数 - Total number of files

    Example:
        raise BatchCancelledError(f"Batch cancelled: {processed_count}/{total_count} files processed")
    """
    pass


# ============================================================================
# リソース関連エラー - Resource Errors
# ============================================================================

class ResourceError(KotobaTranscriberError):
    """
    リソースエラー基底クラス
    Resource allocation or management error.

    メモリ、ディスク容量、GPUなどのシステムリソースに関連するエラーの基底クラスです。
    Base class for errors related to system resources like memory, disk space, and GPU.

    Example:
        raise ResourceError("Insufficient system resources")
    """
    pass


class InsufficientMemoryError(ResourceError):
    """
    メモリ不足エラー
    Insufficient memory for operation.

    処理に必要なメモリが不足している場合に発生します。
    Raised when there is insufficient memory available for the operation.

    Attributes:
        required_mb (int): 必要なメモリ量（MB）- Required memory in MB
        available_mb (int): 利用可能なメモリ量（MB）- Available memory in MB

    Example:
        raise InsufficientMemoryError(required_mb=4096, available_mb=2048)
    """

    def __init__(self, required_mb: int = 0, available_mb: int = 0, message: Optional[str] = None):
        self.required_mb = required_mb
        self.available_mb = available_mb
        if message is None:
            message = f"Insufficient memory: need {required_mb}MB but only {available_mb}MB available"
        super().__init__(message)


class InsufficientDiskSpaceError(ResourceError):
    """
    ディスク容量不足エラー
    Insufficient disk space.

    ファイル保存に必要なディスク容量が不足している場合に発生します。
    Raised when there is insufficient disk space for saving files.

    Attributes:
        required_mb (int): 必要なディスク容量（MB）- Required disk space in MB
        available_mb (int): 利用可能なディスク容量（MB）- Available disk space in MB
        path (str): 対象のパス - Target path

    Example:
        raise InsufficientDiskSpaceError(f"Need {required_mb}MB but only {available_mb}MB free on {path}")
    """
    pass


# ============================================================================
# リアルタイム処理関連エラー - Real-time Processing Errors
# ============================================================================

class RealtimeProcessingError(KotobaTranscriberError):
    """
    リアルタイム処理エラー基底クラス
    Real-time processing error.

    マイクからのリアルタイム音声入力および処理で発生するエラーの基底クラスです。
    Base class for errors in real-time audio input and processing from microphone.

    Example:
        raise RealtimeProcessingError("Real-time processing interrupted")
    """
    pass


class AudioDeviceError(RealtimeProcessingError):
    """
    音声デバイスエラー
    Audio device not found or unavailable.

    マイクなどの音声入力デバイスが見つからない、または使用できない場合に発生します。
    Raised when audio input device (microphone) is not found or unavailable.

    Attributes:
        device_name (str): デバイス名 - Device name
        device_index (Optional[int]): デバイスインデックス - Device index

    Example:
        raise AudioDeviceError(f"Audio device not found: index={device_index}")
    """

    def __init__(self, message: str, device_index: Optional[int] = None):
        self.device_index = device_index
        error_msg = message
        if device_index is not None:
            error_msg = f"{message} (device index: {device_index})"
        super().__init__(error_msg)


class AudioCaptureError(RealtimeProcessingError):
    """
    音声キャプチャエラー
    Failed to capture audio.

    音声デバイスからの音声キャプチャが失敗した場合に発生します。
    デバイスの権限不足、ドライバーエラーなどが原因となります。

    Raised when audio capture from device fails. Causes include insufficient permissions
    or driver errors.

    Example:
        raise AudioCaptureError("Failed to capture audio: permission denied")
    """
    pass


class AudioStreamError(RealtimeProcessingError):
    """
    音声ストリームエラー
    Audio stream error.

    PyAudioストリームの開始、停止、または操作中にエラーが発生した場合に発生します。
    Raised when errors occur during PyAudio stream start, stop, or operations.

    Attributes:
        detail (str): エラー詳細メッセージ - Error detail message
        device_index (Optional[int]): デバイスインデックス - Device index (if known)

    Example:
        raise AudioStreamError("Stream overflow detected", device_index=0)
    """

    def __init__(self, message: str, device_index: Optional[int] = None):
        self.detail = message
        self.device_index = device_index
        error_msg = f"Audio stream error: {message}"
        if device_index is not None:
            error_msg += f" (device={device_index})"
        super().__init__(error_msg)


class PyAudioInitializationError(RealtimeProcessingError):
    """
    PyAudio初期化エラー
    PyAudio initialization error.

    PyAudioオブジェクトの初期化に失敗した場合に発生します。
    通常、システムの音声ドライバーやライブラリの問題が原因です。

    Raised when PyAudio object initialization fails. Usually caused by system
    audio driver or library issues.

    Attributes:
        original_error (Exception): 元の例外オブジェクト - Original exception

    Example:
        raise PyAudioInitializationError(original_error)
    """

    def __init__(self, original_error: Exception):
        self.original_error = original_error
        super().__init__(f"Failed to initialize PyAudio: {original_error}")


class VADError(RealtimeProcessingError):
    """
    VAD（Voice Activity Detection）エラー基底クラス
    Base class for VAD (Voice Activity Detection) errors.

    音声検出機能に関連するエラーはこのクラスを継承します。
    Errors related to voice detection functionality inherit from this class.

    Example:
        raise VADError("VAD processing failed")
    """
    pass


class InvalidVADThresholdError(VADError):
    """
    VAD閾値が無効
    Invalid VAD threshold.

    VAD閾値が有効範囲外の値に設定された場合に発生します。
    Raised when VAD threshold is set to a value outside the valid range.

    Attributes:
        threshold (float): 指定された無効な閾値 - Specified invalid threshold
        valid_range (tuple): 有効な閾値の範囲 (min, max) - Valid threshold range

    Example:
        raise InvalidVADThresholdError(0.1, (0.005, 0.050))
    """

    def __init__(self, threshold: float, valid_range: tuple):
        self.threshold = threshold
        self.valid_range = valid_range
        super().__init__(
            f"Invalid VAD threshold: {threshold} "
            f"(valid range: {valid_range[0]} ~ {valid_range[1]})"
        )


# ============================================================================
# API関連エラー - API Errors
# ============================================================================

class APIError(KotobaTranscriberError):
    """
    API呼び出しエラー基底クラス
    Base exception for API call failures.

    Claude API、OpenAI APIなどの外部APIとの通信で発生するエラーの基底クラスです。
    Base class for errors occurring during communication with external APIs
    like Claude API and OpenAI API.

    Example:
        raise APIError("API call failed: unexpected response")
    """
    pass


class APIConnectionError(APIError):
    """
    API接続エラー
    Failed to connect to API endpoint.

    APIエンドポイントへの接続が失敗した場合に発生します。
    ネットワーク障害やタイムアウトが原因となります。

    Raised when connection to API endpoint fails. Caused by network failures
    or timeouts.

    Example:
        raise APIConnectionError("Connection to Claude API timed out")
    """
    pass


class APIAuthenticationError(APIError):
    """
    API認証エラー
    API authentication failed.

    APIキーが無効、期限切れ、または未設定の場合に発生します。
    Raised when API key is invalid, expired, or not configured.

    Example:
        raise APIAuthenticationError("Invalid API key for OpenAI")
    """
    pass


class APIRateLimitError(APIError):
    """
    APIレート制限エラー
    API rate limit exceeded.

    APIのレート制限を超過した場合に発生します。
    Raised when API rate limit is exceeded.

    Example:
        raise APIRateLimitError("Rate limit exceeded, retry after 60 seconds")
    """
    pass


# ============================================================================
# エクスポート関連エラー - Export Errors
# ============================================================================

class ExportError(KotobaTranscriberError):
    """
    エクスポートエラー基底クラス
    Base exception for export failures.

    ファイルエクスポート処理で発生するエラーの基底クラスです。
    Base class for errors occurring during file export operations.

    Example:
        raise ExportError("Failed to export file")
    """
    pass


class SubtitleExportError(ExportError):
    """
    字幕エクスポートエラー
    Subtitle export failed.

    SRT/VTT等の字幕ファイルのエクスポートが失敗した場合に発生します。
    Raised when SRT/VTT subtitle file export fails.

    Example:
        raise SubtitleExportError("Failed to export SRT file: permission denied")
    """
    pass


# ============================================================================
# セキュリティ関連エラー - Security Errors
# ============================================================================

class SecurityError(KotobaTranscriberError):
    """
    セキュリティエラー基底クラス
    Security violation detected.

    セキュリティ上の脅威や不正なアクセスを検出した場合のエラーの基底クラスです。
    Base class for errors when security threats or unauthorized access is detected.

    Example:
        raise SecurityError("Security violation detected")
    """
    pass


class PathTraversalError(SecurityError):
    """
    パストラバーサルエラー
    Path traversal attack detected.

    パストラバーサル攻撃（../../などを使用した不正なパスアクセス）を検出した場合に発生します。
    Raised when path traversal attack (unauthorized path access using ../../ etc.) is detected.

    Attributes:
        attempted_path (str): 試行されたパス - Attempted path

    Example:
        raise PathTraversalError(f"Path traversal detected: {attempted_path}")
    """
    pass


class UnsafePathError(SecurityError):
    """
    安全でないパスエラー
    Potentially unsafe path detected.

    システムの重要なディレクトリや予期しない場所へのアクセスを検出した場合に発生します。
    Raised when access to critical system directories or unexpected locations is detected.

    Attributes:
        path (str): 安全でないパス - Unsafe path
        reason (str): 理由 - Reason

    Example:
        raise UnsafePathError(f"Unsafe path '{path}': {reason}")
    """
    pass


# ============================================================================
# Utility Functions for Exception Handling
# ============================================================================

def is_kotoba_error(exception: Exception) -> bool:
    """
    例外がKotobaTranscriberのカスタム例外かどうかを判定
    Check if an exception is a KotobaTranscriber custom exception.

    Args:
        exception: チェックする例外 - Exception to check

    Returns:
        bool: カスタム例外の場合True - True if custom exception

    Example:
        try:
            raise AudioFormatError("Invalid format")
        except Exception as e:
            if is_kotoba_error(e):
                print("This is a KotobaTranscriber error")
    """
    return isinstance(exception, KotobaTranscriberError)


def get_error_category(exception: Exception) -> str:
    """
    例外のカテゴリ名を取得
    Get the category name of an exception.

    Args:
        exception: 例外オブジェクト - Exception object

    Returns:
        str: カテゴリ名（例: "FileProcessing", "Transcription"）
            Category name (e.g., "FileProcessing", "Transcription")

    Example:
        try:
            raise AudioFormatError("Invalid")
        except Exception as e:
            category = get_error_category(e)  # Returns "FileProcessing"
    """
    if isinstance(exception, FileProcessingError):
        return "FileProcessing"
    elif isinstance(exception, TranscriptionError):
        return "Transcription"
    elif isinstance(exception, ConfigurationError):
        return "Configuration"
    elif isinstance(exception, BatchProcessingError):
        return "BatchProcessing"
    elif isinstance(exception, ResourceError):
        return "Resource"
    elif isinstance(exception, RealtimeProcessingError):
        return "RealtimeProcessing"
    elif isinstance(exception, APIError):
        return "API"
    elif isinstance(exception, ExportError):
        return "Export"
    elif isinstance(exception, SecurityError):
        return "Security"
    elif isinstance(exception, KotobaTranscriberError):
        return "General"
    else:
        return "Unknown"


# ============================================================================
# Test Code
# ============================================================================

if __name__ == "__main__":
    """例外クラスのテストコード - Test code for exception classes"""

    print("=" * 70)
    print("KotobaTranscriber Custom Exceptions Test")
    print("=" * 70)
    print()

    # Test 1: FileProcessingError hierarchy
    print("[Test 1] FileProcessingError Hierarchy")
    try:
        raise AudioFormatError("Unsupported format: .xyz")
    except AudioFormatError as e:
        print(f"  ✓ {e}")
        print(f"    Category: {get_error_category(e)}")
        print(f"    Is KotobaTranscriberError: {is_kotoba_error(e)}")
    print()

    # Test 2: TranscriptionError hierarchy
    print("[Test 2] TranscriptionError Hierarchy")
    try:
        raise ModelLoadError("Failed to load kotoba-whisper-v2.2")
    except ModelLoadError as e:
        print(f"  ✓ {e}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 3: RealtimeProcessingError hierarchy - AudioDeviceError
    print("[Test 3] RealtimeProcessingError - AudioDeviceError")
    try:
        raise AudioDeviceError("Device not found", device_index=5)
    except AudioDeviceError as e:
        print(f"  ✓ {e}")
        print(f"    Device index: {e.device_index}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 4: VADError hierarchy
    print("[Test 4] VADError Hierarchy")
    try:
        raise InvalidVADThresholdError(0.1, (0.005, 0.050))
    except InvalidVADThresholdError as e:
        print(f"  ✓ {e}")
        print(f"    Threshold: {e.threshold}")
        print(f"    Valid range: {e.valid_range}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 5: ResourceError hierarchy
    print("[Test 5] ResourceError Hierarchy")
    try:
        raise InsufficientMemoryError(required_mb=4096, available_mb=2048)
    except InsufficientMemoryError as e:
        print(f"  ✓ {e}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 6: SecurityError hierarchy
    print("[Test 6] SecurityError Hierarchy")
    try:
        raise PathTraversalError("Path traversal detected: ../../etc/passwd")
    except PathTraversalError as e:
        print(f"  ✓ {e}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 7: BatchProcessingError hierarchy
    print("[Test 7] BatchProcessingError Hierarchy")
    try:
        raise BatchCancelledError("Batch cancelled: 3/10 files processed")
    except BatchCancelledError as e:
        print(f"  ✓ {e}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 8: AudioStreamError with device_index
    print("[Test 8] AudioStreamError with device_index")
    try:
        raise AudioStreamError("Stream overflow", device_index=0)
    except AudioStreamError as e:
        print(f"  ✓ {e}")
        print(f"    Detail: {e.detail}")
        print(f"    Device index: {e.device_index}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 9: PyAudioInitializationError
    print("[Test 9] PyAudioInitializationError")
    try:
        original = OSError("PortAudio library not found")
        raise PyAudioInitializationError(original)
    except PyAudioInitializationError as e:
        print(f"  ✓ {e}")
        print(f"    Original error: {e.original_error}")
        print(f"    Category: {get_error_category(e)}")
    print()

    # Test 10: Exception hierarchy validation
    print("[Test 10] Exception Hierarchy Validation")
    errors_to_test = [
        (AudioFormatError("test"), FileProcessingError),
        (ModelLoadError("test"), TranscriptionError),
        (AudioDeviceError("test"), RealtimeProcessingError),
        (PathTraversalError("test"), SecurityError),
        (InsufficientMemoryError(message="test"), ResourceError),
        (BatchCancelledError("test"), BatchProcessingError),
        (InvalidConfigValueError("test"), ConfigurationError),
    ]

    all_valid = True
    for error_instance, parent_class in errors_to_test:
        if not isinstance(error_instance, parent_class):
            print(f"  ✗ {type(error_instance).__name__} is not an instance of {parent_class.__name__}")
            all_valid = False
        if not isinstance(error_instance, KotobaTranscriberError):
            print(f"  ✗ {type(error_instance).__name__} is not an instance of KotobaTranscriberError")
            all_valid = False

    if all_valid:
        print("  ✓ All exception hierarchies are correctly structured")
    print()

    print("=" * 70)
    print("All exception tests completed! ✅")
    print("=" * 70)
