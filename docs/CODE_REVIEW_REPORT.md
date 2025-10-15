# コードレビュー報告書 - リアルタイム文字起こし機能

**レビュー日**: 2025-10-15
**レビュー対象**: リアルタイム文字起こし機能の実装
**レビュアー**: Senior Code Reviewer + Python Backend Engineer
**総合評価**: 7.5/10 → 9.0/10（改善後の見込み）

## エグゼクティブサマリー

リアルタイム文字起こし機能の実装は、全体的に**良好な品質**で完了しています。アーキテクチャ設計は適切であり、モジュール分離もよく考えられています。しかし、以下の4つの**高優先度の問題**が発見されました：

1. **スレッドセーフティの問題** - 共有リソースへの同期制御が不足
2. **リソースリークの可能性** - 適切なクリーンアップ処理の欠如
3. **エラー回復戦略の不備** - 連続エラー時の自動停止機能がない
4. **カスタム例外の欠如** - 汎用例外を使用しており、エラー処理が不明確

これらの問題を修正することで、**9.0/10の品質**に到達可能です。

## 詳細レビュー結果

### 1. 全体評価

| 評価項目 | スコア | コメント |
|---------|--------|---------|
| **アーキテクチャ設計** | 8/10 | モジュール分離が適切。依存性注入の導入で9/10に |
| **コード品質** | 7/10 | 可読性は良好。型ヒントの完全化で8/10に |
| **スレッドセーフティ** | 5/10 | ⚠️ 重大な問題あり。ロック機構の追加で9/10に |
| **エラーハンドリング** | 6/10 | 基本的な処理はあるが、回復戦略が不足 |
| **パフォーマンス** | 8/10 | VADによる最適化が効果的 |
| **テスタビリティ** | 6/10 | 依存性注入の導入で8/10に |
| **ドキュメント** | 9/10 | 非常に充実している |
| **総合評価** | **7.5/10** | **改善後: 9.0/10** |

---

## 高優先度の問題（即座に修正推奨）

### 問題1: スレッドセーフティの欠如 🔴

**重大度**: 高
**影響範囲**: `realtime_audio_capture.py`, `realtime_transcriber.py`
**推定修正時間**: 4-6時間

#### 問題の詳細

**現状の問題点**:
```python
# realtime_audio_capture.py - 現在のコード（問題あり）
class RealtimeAudioCapture:
    def __init__(self):
        self.audio_buffer = deque(maxlen=...)  # スレッド間で共有されるが保護されていない

    def _audio_callback(self, in_data, ...):
        # PyAudioスレッドから呼ばれる
        self.audio_buffer.extend(audio_chunk)  # ⚠️ ロックなし

    def _capture_loop(self):
        # 別スレッドから呼ばれる
        chunk = list(self.audio_buffer)[start:end]  # ⚠️ ロックなし、競合状態発生可能
```

**問題の影響**:
- データ競合によるクラッシュの可能性
- 音声データの破損・欠落
- 予測不可能な動作

#### 推奨される修正

```python
# realtime_audio_capture.py - 修正後
import threading
from collections import deque
from typing import Optional
import logging

class RealtimeAudioCapture:
    def __init__(self, device_index: Optional[int] = None,
                 sample_rate: int = 16000,
                 buffer_duration: float = 3.0):
        self.audio_buffer = deque(maxlen=int(sample_rate * buffer_duration * 2))
        self._buffer_lock = threading.Lock()  # ✅ ロックを追加
        self._is_capturing = False
        self.logger = logging.getLogger(__name__)

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudioコールバック（別スレッドから呼ばれる）"""
        try:
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            audio_chunk = audio_data.astype(np.float32) / 32768.0

            with self._buffer_lock:  # ✅ スレッドセーフな書き込み
                self.audio_buffer.extend(audio_chunk)

            return (None, pyaudio.paContinue)
        except Exception as e:
            self.logger.error(f"Audio callback error: {e}", exc_info=True)
            return (None, pyaudio.paAbort)

    def _capture_loop(self):
        """キャプチャループ（メインスレッドで動作）"""
        chunk_size_samples = int(self.sample_rate * 3.0)
        overlap_samples = chunk_size_samples // 2

        while self._is_capturing:
            with self._buffer_lock:  # ✅ スレッドセーフな読み取り
                if len(self.audio_buffer) >= chunk_size_samples:
                    # バッファのスナップショットを取得
                    buffer_snapshot = list(self.audio_buffer)
                else:
                    buffer_snapshot = None

            if buffer_snapshot and len(buffer_snapshot) >= chunk_size_samples:
                # チャンクを抽出（ロックの外で処理）
                start_pos = len(buffer_snapshot) - chunk_size_samples
                audio_chunk = np.array(buffer_snapshot[start_pos:], dtype=np.float32)

                # コールバックを呼び出す
                if self.audio_chunk_callback:
                    self.audio_chunk_callback(audio_chunk)

                # オーバーラップ処理
                time.sleep(1.5)  # 50%オーバーラップ
            else:
                time.sleep(0.1)  # バッファが不足している場合は待機
```

**修正のポイント**:
1. `threading.Lock()`を使用して共有バッファを保護
2. `with self._buffer_lock:`コンテキストマネージャで自動的にロック取得・解放
3. バッファのスナップショットを取得し、ロックの外で処理を行う（ロック時間の最小化）
4. エラーハンドリングを追加

---

### 問題2: リソースリークの可能性 🟡

**重大度**: 中-高
**影響範囲**: `realtime_audio_capture.py`, `faster_whisper_engine.py`
**推定修正時間**: 6-8時間

#### 問題の詳細

**現状の問題点**:
```python
# realtime_audio_capture.py - 現在のコード（問題あり）
class RealtimeAudioCapture:
    def stop_capture(self):
        self._is_capturing = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            # ⚠️ capture_threadの終了を待たない
        # ⚠️ self.audioのクリーンアップがない
```

**問題の影響**:
- PyAudioリソースが解放されない
- スレッドがハング状態で残る可能性
- メモリリークの発生

#### 推奨される修正

```python
# realtime_audio_capture.py - 修正後（コンテキストマネージャ対応）
import threading
import pyaudio
import numpy as np
from collections import deque
from typing import Optional, Callable
import logging

class RealtimeAudioCapture:
    """リアルタイム音声キャプチャクラス（コンテキストマネージャ対応）"""

    def __init__(self, device_index: Optional[int] = None,
                 sample_rate: int = 16000,
                 buffer_duration: float = 3.0):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.buffer_duration = buffer_duration

        self.audio: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None
        self.capture_thread: Optional[threading.Thread] = None

        self.audio_buffer = deque(maxlen=int(sample_rate * buffer_duration * 2))
        self._buffer_lock = threading.Lock()
        self._is_capturing = False

        self.audio_chunk_callback: Optional[Callable] = None
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        """コンテキストマネージャ: withブロック開始時"""
        self.audio = pyaudio.PyAudio()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャ: withブロック終了時（確実にクリーンアップ）"""
        self.stop_capture()

        # PyAudioのクリーンアップ
        if self.audio:
            try:
                self.audio.terminate()
                self.logger.info("PyAudio terminated successfully")
            except Exception as e:
                self.logger.error(f"Error terminating PyAudio: {e}", exc_info=True)
            finally:
                self.audio = None

        return False  # 例外を再送出

    def start_capture(self, callback: Callable[[np.ndarray], None]):
        """音声キャプチャ開始"""
        if self._is_capturing:
            self.logger.warning("Capture already in progress")
            return

        if not self.audio:
            raise RuntimeError("PyAudio not initialized. Use 'with' statement.")

        self.audio_chunk_callback = callback
        self._is_capturing = True

        # ストリーム開始
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            self.logger.info(f"Audio stream started (device: {self.device_index})")
        except Exception as e:
            self._is_capturing = False
            self.logger.error(f"Failed to start audio stream: {e}", exc_info=True)
            raise

        # キャプチャスレッド開始
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        self.logger.info("Capture thread started")

    def stop_capture(self):
        """音声キャプチャ停止（確実なクリーンアップ）"""
        if not self._is_capturing:
            return

        self.logger.info("Stopping capture...")
        self._is_capturing = False

        # ストリームのクリーンアップ
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.logger.info("Audio stream closed")
            except Exception as e:
                self.logger.error(f"Error closing stream: {e}", exc_info=True)
            finally:
                self.stream = None

        # スレッドの終了を待つ（タイムアウト付き）
        if self.capture_thread and self.capture_thread.is_alive():
            self.logger.info("Waiting for capture thread to finish...")
            self.capture_thread.join(timeout=5.0)  # ✅ 最大5秒待機
            if self.capture_thread.is_alive():
                self.logger.warning("Capture thread did not finish in time")
            else:
                self.logger.info("Capture thread finished")
            self.capture_thread = None

        # バッファクリア
        with self._buffer_lock:
            self.audio_buffer.clear()

        self.logger.info("Capture stopped successfully")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudioコールバック（別スレッドから呼ばれる）"""
        if status:
            self.logger.warning(f"PyAudio callback status: {status}")

        try:
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            audio_chunk = audio_data.astype(np.float32) / 32768.0

            with self._buffer_lock:
                self.audio_buffer.extend(audio_chunk)

            return (None, pyaudio.paContinue)
        except Exception as e:
            self.logger.error(f"Audio callback error: {e}", exc_info=True)
            return (None, pyaudio.paAbort)

    def _capture_loop(self):
        """キャプチャループ（メインスレッドで動作）"""
        chunk_size_samples = int(self.sample_rate * 3.0)
        overlap_samples = chunk_size_samples // 2

        self.logger.info("Capture loop started")

        while self._is_capturing:
            try:
                with self._buffer_lock:
                    if len(self.audio_buffer) >= chunk_size_samples:
                        buffer_snapshot = list(self.audio_buffer)
                    else:
                        buffer_snapshot = None

                if buffer_snapshot and len(buffer_snapshot) >= chunk_size_samples:
                    start_pos = len(buffer_snapshot) - chunk_size_samples
                    audio_chunk = np.array(buffer_snapshot[start_pos:], dtype=np.float32)

                    if self.audio_chunk_callback:
                        self.audio_chunk_callback(audio_chunk)

                    time.sleep(1.5)  # 50%オーバーラップ
                else:
                    time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}", exc_info=True)
                time.sleep(0.1)

        self.logger.info("Capture loop finished")

# ✅ 使用例（コンテキストマネージャ）
with RealtimeAudioCapture(device_index=0) as capture:
    capture.start_capture(callback=my_callback)
    time.sleep(10)
    # withブロックを抜けると自動的にクリーンアップされる
```

**修正のポイント**:
1. `__enter__` / `__exit__` メソッドでコンテキストマネージャに対応
2. `stop_capture()` で確実にリソースを解放
3. スレッドの終了を `join(timeout=5.0)` で待機
4. 例外発生時も確実にクリーンアップされる

---

### 問題3: エラー回復戦略の不備 🟡

**重大度**: 中
**影響範囲**: `realtime_transcriber.py`
**推定修正時間**: 4時間

#### 問題の詳細

**現状の問題点**:
```python
# realtime_transcriber.py - 現在のコード（問題あり）
def _on_audio_chunk(self, audio_chunk: np.ndarray):
    try:
        # VADチェック
        is_speech, energy = self.vad.is_speech_present(audio_chunk)
        if not is_speech:
            return

        # 文字起こし
        text = self.whisper_engine.transcribe_stream(audio_chunk)
        # ...
    except Exception as e:
        self.logger.error(f"Error processing chunk: {e}")
        # ⚠️ エラーが続いても処理を続行してしまう
```

**問題の影響**:
- エラーが連続発生しても停止しない
- リソースを無駄に消費し続ける
- ユーザーが問題に気づかない可能性

#### 推奨される修正

```python
# realtime_transcriber.py - 修正後
class RealtimeTranscriber(QThread):
    # 既存のシグナル
    transcription_update = pyqtSignal(str, bool)
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    vad_status_changed = pyqtSignal(bool, float)

    # ✅ 新しいシグナル
    critical_error_occurred = pyqtSignal(str)  # 重大なエラー発生時

    # エラー回復設定
    MAX_CONSECUTIVE_ERRORS = 5  # 連続エラーの最大回数
    ERROR_COOLDOWN_TIME = 2.0   # エラー後の待機時間（秒）

    def __init__(self, device_index: Optional[int] = None,
                 model_size: str = "base",
                 enable_vad: bool = True,
                 vad_threshold: float = 0.01):
        super().__init__()
        # ... 既存の初期化コード ...

        # ✅ エラー追跡用
        self._consecutive_errors = 0
        self._last_error_time = 0.0
        self._error_lock = threading.Lock()

    def _on_audio_chunk(self, audio_chunk: np.ndarray):
        """音声チャンク処理（エラー回復機能付き）"""
        try:
            # VADチェック
            if self.vad and self.enable_vad:
                is_speech, energy = self.vad.is_speech_present(audio_chunk)
                self.vad_status_changed.emit(is_speech, energy)

                if not is_speech:
                    self._reset_error_counter()  # ✅ 成功時はカウンターをリセット
                    return

            # 文字起こし
            start_time = time.time()
            text = self.whisper_engine.transcribe_stream(audio_chunk, self.sample_rate)
            processing_time = time.time() - start_time

            # RTF更新
            audio_duration = len(audio_chunk) / self.sample_rate
            rtf = processing_time / audio_duration if audio_duration > 0 else 0
            self.rtf_values.append(rtf)

            # 結果の蓄積と発信
            if self.pending_text:
                with self._text_lock:
                    self.accumulated_text.append(self.pending_text)
                self.transcription_update.emit(self.pending_text, True)

            self.pending_text = text
            self.transcription_update.emit(text, False)

            self.chunks_processed += 1
            self.total_audio_duration += audio_duration

            # ✅ 成功したのでエラーカウンターをリセット
            self._reset_error_counter()

        except Exception as e:
            # ✅ エラー回復処理
            self._handle_processing_error(e)

    def _reset_error_counter(self):
        """エラーカウンターをリセット"""
        with self._error_lock:
            if self._consecutive_errors > 0:
                self.logger.info(f"Error counter reset (was {self._consecutive_errors})")
            self._consecutive_errors = 0

    def _handle_processing_error(self, error: Exception):
        """エラーハンドリングと回復戦略"""
        with self._error_lock:
            self._consecutive_errors += 1
            current_error_count = self._consecutive_errors

        # ログ出力
        self.logger.error(
            f"Error processing chunk (consecutive errors: {current_error_count}): {error}",
            exc_info=True
        )

        # ユーザーに通知
        error_msg = f"処理エラー ({current_error_count}/{self.MAX_CONSECUTIVE_ERRORS}): {str(error)}"
        self.error_occurred.emit(error_msg)

        # 連続エラーが閾値を超えた場合
        if current_error_count >= self.MAX_CONSECUTIVE_ERRORS:
            critical_msg = (
                f"連続エラーが{self.MAX_CONSECUTIVE_ERRORS}回発生しました。"
                "リアルタイム文字起こしを自動停止します。"
            )
            self.logger.critical(critical_msg)
            self.critical_error_occurred.emit(critical_msg)

            # 自動停止
            self.stop()
        else:
            # クールダウン期間
            time.sleep(self.ERROR_COOLDOWN_TIME)
```

**修正のポイント**:
1. `_consecutive_errors` でエラーカウントを追跡
2. 成功時に `_reset_error_counter()` でカウンターをリセット
3. 連続エラーが5回を超えたら自動停止
4. `critical_error_occurred` シグナルでUIに通知

---

### 問題4: カスタム例外の欠如 🟢

**重大度**: 中
**影響範囲**: 全モジュール
**推定修正時間**: 2時間

#### 問題の詳細

**現状の問題点**:
```python
# 現在のコード（問題あり）
raise Exception("Failed to initialize PyAudio")  # ⚠️ 汎用例外
raise RuntimeError("Model loading failed")       # ⚠️ 曖昧
raise ValueError("Invalid device index")         # ⚠️ 用途が不明確
```

**問題の影響**:
- エラーの種類が不明確
- 適切なエラーハンドリングが困難
- デバッグが難しい

#### 推奨される修正

```python
# exceptions.py - 新規ファイル
"""
カスタム例外クラス定義

リアルタイム文字起こし機能用の例外階層を定義します。
"""

class RealtimeTranscriptionError(Exception):
    """リアルタイム文字起こし機能の基底例外クラス"""
    pass

# === 音声キャプチャ関連 ===
class AudioCaptureError(RealtimeTranscriptionError):
    """音声キャプチャエラーの基底クラス"""
    pass

class AudioDeviceNotFoundError(AudioCaptureError):
    """音声デバイスが見つからない"""
    def __init__(self, device_index: int):
        self.device_index = device_index
        super().__init__(f"Audio device not found: index={device_index}")

class AudioStreamError(AudioCaptureError):
    """音声ストリームエラー"""
    def __init__(self, message: str, device_index: int = None):
        self.device_index = device_index
        super().__init__(f"Audio stream error: {message}")

class PyAudioInitializationError(AudioCaptureError):
    """PyAudio初期化エラー"""
    def __init__(self, original_error: Exception):
        self.original_error = original_error
        super().__init__(f"Failed to initialize PyAudio: {original_error}")

# === VAD関連 ===
class VADError(RealtimeTranscriptionError):
    """VADエラーの基底クラス"""
    pass

class InvalidVADThresholdError(VADError):
    """VAD閾値が無効"""
    def __init__(self, threshold: float, valid_range: tuple):
        self.threshold = threshold
        self.valid_range = valid_range
        super().__init__(
            f"Invalid VAD threshold: {threshold} (valid range: {valid_range})"
        )

# === 文字起こしエンジン関連 ===
class TranscriptionEngineError(RealtimeTranscriptionError):
    """文字起こしエンジンエラーの基底クラス"""
    pass

class ModelLoadingError(TranscriptionEngineError):
    """モデル読み込みエラー"""
    def __init__(self, model_name: str, original_error: Exception):
        self.model_name = model_name
        self.original_error = original_error
        super().__init__(
            f"Failed to load model '{model_name}': {original_error}"
        )

class TranscriptionFailedError(TranscriptionEngineError):
    """文字起こし失敗"""
    def __init__(self, message: str, audio_duration: float = None):
        self.audio_duration = audio_duration
        super().__init__(f"Transcription failed: {message}")

class UnsupportedModelError(TranscriptionEngineError):
    """サポートされていないモデル"""
    def __init__(self, model_name: str, supported_models: list):
        self.model_name = model_name
        self.supported_models = supported_models
        super().__init__(
            f"Unsupported model: {model_name}. "
            f"Supported models: {', '.join(supported_models)}"
        )

# === リソース管理関連 ===
class ResourceError(RealtimeTranscriptionError):
    """リソースエラーの基底クラス"""
    pass

class ResourceNotAvailableError(ResourceError):
    """リソースが利用不可"""
    def __init__(self, resource_name: str):
        self.resource_name = resource_name
        super().__init__(f"Resource not available: {resource_name}")

class MemoryError(ResourceError):
    """メモリ不足エラー"""
    def __init__(self, required_mb: float, available_mb: float):
        self.required_mb = required_mb
        self.available_mb = available_mb
        super().__init__(
            f"Insufficient memory: required {required_mb}MB, "
            f"available {available_mb}MB"
        )

# === 設定関連 ===
class ConfigurationError(RealtimeTranscriptionError):
    """設定エラーの基底クラス"""
    pass

class InvalidConfigurationError(ConfigurationError):
    """無効な設定"""
    def __init__(self, param_name: str, param_value, reason: str):
        self.param_name = param_name
        self.param_value = param_value
        super().__init__(
            f"Invalid configuration: {param_name}={param_value} ({reason})"
        )
```

**使用例**:

```python
# realtime_audio_capture.py - 修正後
from exceptions import (
    AudioDeviceNotFoundError,
    AudioStreamError,
    PyAudioInitializationError
)

class RealtimeAudioCapture:
    def __enter__(self):
        try:
            self.audio = pyaudio.PyAudio()
            return self
        except Exception as e:
            raise PyAudioInitializationError(e)  # ✅ カスタム例外

    def start_capture(self, callback):
        # デバイス存在確認
        device_count = self.audio.get_device_count()
        if self.device_index >= device_count:
            raise AudioDeviceNotFoundError(self.device_index)  # ✅ カスタム例外

        try:
            self.stream = self.audio.open(...)
            self.stream.start_stream()
        except Exception as e:
            raise AudioStreamError(str(e), self.device_index)  # ✅ カスタム例外

# faster_whisper_engine.py - 修正後
from exceptions import (
    ModelLoadingError,
    UnsupportedModelError,
    TranscriptionFailedError
)

class FasterWhisperEngine:
    SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]

    def load_model(self):
        if self.model_size not in self.SUPPORTED_MODELS:
            raise UnsupportedModelError(self.model_size, self.SUPPORTED_MODELS)  # ✅

        try:
            self.model = WhisperModel(...)
        except Exception as e:
            raise ModelLoadingError(self.model_size, e)  # ✅

    def transcribe_stream(self, audio_chunk, sample_rate=16000):
        try:
            # ... 文字起こし処理 ...
            return result["text"]
        except Exception as e:
            audio_duration = len(audio_chunk) / sample_rate
            raise TranscriptionFailedError(str(e), audio_duration)  # ✅

# main.py - UIでのエラーハンドリング
from exceptions import (
    AudioDeviceNotFoundError,
    ModelLoadingError,
    ResourceNotAvailableError
)

class MainWindow(QMainWindow):
    def on_realtime_error(self, error_msg: str):
        """リアルタイムエラーハンドリング"""
        # エラーの種類に応じて適切に処理
        if "AudioDeviceNotFoundError" in error_msg:
            QMessageBox.warning(
                self,
                "デバイスエラー",
                "選択された音声デバイスが見つかりません。\n"
                "デバイスを確認してください。"
            )
        elif "ModelLoadingError" in error_msg:
            QMessageBox.critical(
                self,
                "モデルエラー",
                "Whisperモデルの読み込みに失敗しました。\n"
                "インターネット接続を確認してください。"
            )
        else:
            QMessageBox.warning(self, "エラー", error_msg)
```

**修正のポイント**:
1. 階層的な例外クラスを定義（`RealtimeTranscriptionError`が基底）
2. 各例外に適切なコンテキスト情報を含める（デバイスインデックス、モデル名など）
3. 例外の種類に応じた適切なエラーハンドリングが可能に

---

## 中優先度の改善提案

### 提案1: 依存性注入（DI）の導入

**目的**: テスタビリティと保守性の向上

**推定時間**: 12-16時間

**現状**:
```python
# 現在のコード - ハードコーディングされた依存関係
class RealtimeTranscriber(QThread):
    def __init__(self, device_index=None, model_size="base", ...):
        self.audio_capture = RealtimeAudioCapture(device_index)  # 直接インスタンス化
        self.vad = AdaptiveVAD(initial_threshold=vad_threshold)  # 直接インスタンス化
        self.whisper_engine = FasterWhisperEngine(model_size=model_size)  # 直接インスタンス化
```

**問題点**:
- ユニットテストが困難（モックに置き換えられない）
- 実装の変更が難しい（例: VADアルゴリズムの切り替え）
- 柔軟性が低い

**推奨される修正**:

```python
# protocols.py - インターフェース定義（Protocolベース）
from typing import Protocol, Callable, Optional
import numpy as np

class AudioCaptureProtocol(Protocol):
    """音声キャプチャのインターフェース"""

    def start_capture(self, callback: Callable[[np.ndarray], None]) -> None:
        """音声キャプチャ開始"""
        ...

    def stop_capture(self) -> None:
        """音声キャプチャ停止"""
        ...

    def get_device_list(self) -> list:
        """デバイスリスト取得"""
        ...

class VADProtocol(Protocol):
    """VADのインターフェース"""

    def is_speech_present(self, audio: np.ndarray) -> tuple[bool, float]:
        """音声検出"""
        ...

class TranscriptionEngineProtocol(Protocol):
    """文字起こしエンジンのインターフェース"""

    def transcribe_stream(self, audio_chunk: np.ndarray, sample_rate: int) -> str:
        """ストリーミング文字起こし"""
        ...

    def load_model(self) -> None:
        """モデル読み込み"""
        ...

    def unload_model(self) -> None:
        """モデル解放"""
        ...

# realtime_transcriber.py - DI対応版
from protocols import AudioCaptureProtocol, VADProtocol, TranscriptionEngineProtocol

class RealtimeTranscriber(QThread):
    """リアルタイム文字起こしコーディネーター（DI対応）"""

    def __init__(self,
                 audio_capture: AudioCaptureProtocol,  # ✅ インターフェースで依存
                 whisper_engine: TranscriptionEngineProtocol,  # ✅
                 vad: Optional[VADProtocol] = None,  # ✅
                 enable_vad: bool = True):
        super().__init__()

        # 依存オブジェクトを外部から注入
        self.audio_capture = audio_capture
        self.whisper_engine = whisper_engine
        self.vad = vad
        self.enable_vad = enable_vad and vad is not None

        # ... その他の初期化 ...

# main.py - ファクトリパターンでの使用
class RealtimeTranscriberFactory:
    """RealtimeTranscriberのファクトリ"""

    @staticmethod
    def create(device_index: Optional[int] = None,
               model_size: str = "base",
               enable_vad: bool = True,
               vad_threshold: float = 0.01) -> RealtimeTranscriber:
        """RealtimeTranscriberインスタンスを生成"""

        # 依存オブジェクトを個別に生成
        audio_capture = RealtimeAudioCapture(
            device_index=device_index,
            sample_rate=16000,
            buffer_duration=3.0
        )

        whisper_engine = FasterWhisperEngine(
            model_size=model_size,
            device="auto",
            compute_type="auto",
            language="ja"
        )

        vad = AdaptiveVAD(
            initial_threshold=vad_threshold,
            min_speech_duration=0.3,
            min_silence_duration=1.0,
            adaptation_rate=0.1
        ) if enable_vad else None

        # DIでインジェクション
        transcriber = RealtimeTranscriber(
            audio_capture=audio_capture,
            whisper_engine=whisper_engine,
            vad=vad,
            enable_vad=enable_vad
        )

        return transcriber

# テストコード例（モックを使用）
import unittest
from unittest.mock import MagicMock
import numpy as np

class TestRealtimeTranscriberWithDI(unittest.TestCase):
    def setUp(self):
        # モックオブジェクトを作成
        self.mock_audio_capture = MagicMock(spec=AudioCaptureProtocol)
        self.mock_whisper_engine = MagicMock(spec=TranscriptionEngineProtocol)
        self.mock_vad = MagicMock(spec=VADProtocol)

        # トランスクライバーを作成（モックを注入）
        self.transcriber = RealtimeTranscriber(
            audio_capture=self.mock_audio_capture,
            whisper_engine=self.mock_whisper_engine,
            vad=self.mock_vad,
            enable_vad=True
        )

    def test_on_audio_chunk_with_speech(self):
        """音声ありの場合のテスト"""
        # モックの振る舞いを設定
        self.mock_vad.is_speech_present.return_value = (True, 0.05)
        self.mock_whisper_engine.transcribe_stream.return_value = "こんにちは"

        # テスト実行
        audio_chunk = np.random.randn(16000 * 3).astype(np.float32)
        self.transcriber._on_audio_chunk(audio_chunk)

        # 検証
        self.mock_vad.is_speech_present.assert_called_once()
        self.mock_whisper_engine.transcribe_stream.assert_called_once()

    def test_on_audio_chunk_without_speech(self):
        """音声なしの場合のテスト"""
        # モックの振る舞いを設定
        self.mock_vad.is_speech_present.return_value = (False, 0.002)

        # テスト実行
        audio_chunk = np.random.randn(16000 * 3).astype(np.float32)
        self.transcriber._on_audio_chunk(audio_chunk)

        # 検証（VADがFalseなので文字起こしは呼ばれない）
        self.mock_vad.is_speech_present.assert_called_once()
        self.mock_whisper_engine.transcribe_stream.assert_not_called()
```

**メリット**:
1. ユニットテストが容易（モックで置き換え可能）
2. 実装の切り替えが簡単（例: 異なるVADアルゴリズムを試す）
3. 依存関係が明確
4. ファクトリパターンで生成ロジックを分離

---

### 提案2: 型ヒントの完全化

**目的**: コードの可読性と静的解析の精度向上

**推定時間**: 6-8時間

**現状**:
```python
# 現在のコード - 型ヒントが不完全
def get_device_list(self):  # 戻り値の型が不明
    devices = []
    # ...
    return devices

def _on_audio_chunk(self, audio_chunk):  # 引数の型が不明
    # ...
```

**推奨される修正**:

```python
# realtime_audio_capture.py - 完全な型ヒント
from typing import Optional, Callable, List, Dict, Any
import numpy as np
import numpy.typing as npt

class RealtimeAudioCapture:
    """リアルタイム音声キャプチャクラス"""

    def __init__(self,
                 device_index: Optional[int] = None,
                 sample_rate: int = 16000,
                 buffer_duration: float = 3.0) -> None:
        self.device_index: Optional[int] = device_index
        self.sample_rate: int = sample_rate
        self.buffer_duration: float = buffer_duration

        self.audio: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None
        self.capture_thread: Optional[threading.Thread] = None

        self.audio_buffer: deque = deque(maxlen=int(sample_rate * buffer_duration * 2))
        self._buffer_lock: threading.Lock = threading.Lock()
        self._is_capturing: bool = False

        self.audio_chunk_callback: Optional[Callable[[npt.NDArray[np.float32]], None]] = None
        self.logger: logging.Logger = logging.getLogger(__name__)

    def get_device_list(self) -> List[Dict[str, Any]]:
        """
        利用可能な音声デバイスのリストを取得

        Returns:
            List[Dict[str, Any]]: デバイス情報のリスト
                各要素は {"index": int, "name": str, "channels": int} の辞書
        """
        if not self.audio:
            return []

        devices: List[Dict[str, Any]] = []
        device_count: int = self.audio.get_device_count()

        for i in range(device_count):
            try:
                info: Dict[str, Any] = self.audio.get_device_info_by_index(i)
                if info["maxInputChannels"] > 0:
                    devices.append({
                        "index": i,
                        "name": info["name"],
                        "channels": info["maxInputChannels"]
                    })
            except Exception as e:
                self.logger.warning(f"Failed to get device info for index {i}: {e}")

        return devices

    def start_capture(self, callback: Callable[[npt.NDArray[np.float32]], None]) -> None:
        """
        音声キャプチャを開始

        Args:
            callback: 音声チャンクを受け取るコールバック関数
                      シグネチャ: callback(audio_chunk: np.ndarray[float32])

        Raises:
            RuntimeError: PyAudioが初期化されていない場合
            AudioStreamError: ストリーム開始に失敗した場合
        """
        # ... 実装 ...

    def _audio_callback(self,
                       in_data: bytes,
                       frame_count: int,
                       time_info: Dict[str, float],
                       status: int) -> tuple[None, int]:
        """
        PyAudioコールバック（別スレッドから呼ばれる）

        Args:
            in_data: 音声データ（バイト列）
            frame_count: フレーム数
            time_info: タイミング情報
            status: ストリームステータス

        Returns:
            tuple[None, int]: (出力データ, 継続フラグ)
        """
        # ... 実装 ...

# faster_whisper_engine.py - 完全な型ヒント
from typing import Optional, Dict, Any, Literal
import numpy as np
import numpy.typing as npt

ModelSize = Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"]
ComputeType = Literal["int8", "int8_float16", "int16", "float16", "float32"]
DeviceType = Literal["auto", "cpu", "cuda"]

class FasterWhisperEngine:
    """faster-whisper文字起こしエンジン"""

    def __init__(self,
                 model_size: ModelSize = "base",
                 device: DeviceType = "auto",
                 compute_type: ComputeType = "auto",
                 language: str = "ja") -> None:
        self.model_size: ModelSize = model_size
        self.device: str = device
        self.compute_type: ComputeType = compute_type
        self.language: str = language

        self.model: Optional[WhisperModel] = None
        self.logger: logging.Logger = logging.getLogger(__name__)

    def transcribe_stream(self,
                         audio_chunk: npt.NDArray[np.float32],
                         sample_rate: int = 16000) -> str:
        """
        音声チャンクをストリーミング文字起こし

        Args:
            audio_chunk: 音声データ（float32, -1.0～1.0に正規化）
            sample_rate: サンプリングレート（Hz）

        Returns:
            str: 文字起こし結果テキスト

        Raises:
            TranscriptionFailedError: 文字起こしに失敗した場合
        """
        # ... 実装 ...
```

**メリット**:
1. IDEの補完機能が強化される
2. mypy / pylance による静的解析が可能に
3. コードの意図が明確になる
4. リファクタリングが安全に

---

### 提案3: パフォーマンス最適化

**目的**: レイテンシ削減とCPU使用率の改善

**推定時間**: 8-10時間

**最適化箇所**:

#### 1. バッファコピーの削減

**現状**:
```python
# 現在のコード - 毎回リスト変換とコピーが発生
def _capture_loop(self):
    while self._is_capturing:
        with self._buffer_lock:
            buffer_snapshot = list(self.audio_buffer)  # ⚠️ O(n)のコピー

        if len(buffer_snapshot) >= chunk_size_samples:
            audio_chunk = np.array(buffer_snapshot[start_pos:], dtype=np.float32)  # ⚠️ 再度コピー
```

**最適化後**:
```python
# 最適化版 - 必要な部分だけコピー
def _capture_loop(self):
    while self._is_capturing:
        with self._buffer_lock:
            if len(self.audio_buffer) >= chunk_size_samples:
                # 必要な範囲だけ直接抽出（isliceでイテレータ使用）
                from itertools import islice
                start_idx = len(self.audio_buffer) - chunk_size_samples
                chunk_iterator = islice(self.audio_buffer, start_idx, None)
                audio_chunk = np.fromiter(chunk_iterator, dtype=np.float32, count=chunk_size_samples)
            else:
                audio_chunk = None

        if audio_chunk is not None:
            # ... 処理 ...
```

#### 2. Whisperバッチ処理

**現状**:
```python
# 1チャンクずつ処理
text = self.whisper_engine.transcribe_stream(audio_chunk)
```

**最適化後**:
```python
# faster_whisper_engine.py - バッチ処理対応
class FasterWhisperEngine:
    def transcribe_batch(self,
                        audio_chunks: List[npt.NDArray[np.float32]],
                        sample_rate: int = 16000) -> List[str]:
        """
        複数チャンクをバッチ処理（高速化）

        Args:
            audio_chunks: 音声チャンクのリスト
            sample_rate: サンプリングレート

        Returns:
            List[str]: 各チャンクの文字起こし結果
        """
        if not self.model:
            raise RuntimeError("Model not loaded")

        results = []
        for chunk in audio_chunks:
            # GPUの場合、複数チャンクを連結して一度に処理すると高速化
            segments, info = self.model.transcribe(
                chunk,
                beam_size=1,
                language=self.language,
                vad_filter=False
            )

            text = "".join([seg.text for seg in segments])
            results.append(text)

        return results
```

#### 3. 非同期UI更新

**現状**:
```python
# 毎回即座にUI更新 → オーバーヘッド大
self.transcription_update.emit(text, False)
```

**最適化後**:
```python
# realtime_transcriber.py - UI更新のバッファリング
class RealtimeTranscriber(QThread):
    UI_UPDATE_INTERVAL = 0.5  # 秒（UI更新間隔）

    def __init__(self, ...):
        # ... 既存の初期化 ...
        self._ui_update_timer = 0.0
        self._pending_ui_updates = []

    def _on_audio_chunk(self, audio_chunk: np.ndarray):
        # ... 文字起こし処理 ...

        # UI更新をバッファに追加
        self._pending_ui_updates.append((text, False))

        # 一定間隔でまとめて更新
        current_time = time.time()
        if current_time - self._ui_update_timer >= self.UI_UPDATE_INTERVAL:
            self._flush_ui_updates()
            self._ui_update_timer = current_time

    def _flush_ui_updates(self):
        """バッファされたUI更新を一括送信"""
        if not self._pending_ui_updates:
            return

        # 最新の更新のみ送信（古い更新は破棄）
        latest_text, is_final = self._pending_ui_updates[-1]
        self.transcription_update.emit(latest_text, is_final)
        self._pending_ui_updates.clear()
```

---

## 低優先度の改善提案

### 1. 重複テキストのマージロジック（6-8時間）
### 2. 高度なVAD統合（8-12時間）
### 3. ストリーミング最適化（12-16時間）
### 4. モニタリングとメトリクス（8時間）

---

## 実装ロードマップ

### フェーズ1: 高優先度修正（2-3日）

**目標**: 本番環境に安全にデプロイ可能な品質に到達

1. **スレッドセーフティ修正** (4-6時間)
   - `realtime_audio_capture.py` にロック追加
   - `realtime_transcriber.py` にロック追加
   - 単体テスト作成

2. **リソースリーク修正** (6-8時間)
   - コンテキストマネージャ実装
   - `__exit__` でのクリーンアップ
   - リソーステスト作成

3. **エラー回復戦略** (4時間)
   - エラーカウンター実装
   - 自動停止機能追加
   - 統合テスト

4. **カスタム例外** (2時間)
   - `exceptions.py` 作成
   - 全モジュールに適用

**完了基準**:
- 全ユニットテストが成功
- 1時間連続動作テストで問題なし
- メモリリークなし

### フェーズ2: 中優先度改善（1-2週間）

**目標**: 保守性とテスタビリティの向上

1. **依存性注入** (12-16時間)
   - Protocol定義
   - ファクトリパターン実装
   - モックを使用したテスト

2. **型ヒント完全化** (6-8時間)
   - 全関数に型ヒント追加
   - mypy検証

3. **パフォーマンス最適化** (8-10時間)
   - バッファコピー削減
   - バッチ処理実装
   - ベンチマーク測定

4. **設定外部化** (4時間)
   - YAML/JSON設定ファイル
   - 環境変数サポート

**完了基準**:
- コードカバレッジ80%以上
- mypy検証成功
- RTF 10%改善

### フェーズ3: 低優先度改善（1-2ヶ月）

**目標**: 機能強化とユーザー体験向上

1. **重複テキストマージ** (6-8時間)
2. **高度なVAD統合** (8-12時間)
3. **ストリーミング最適化** (12-16時間)
4. **モニタリング** (8時間)

### フェーズ4: 長期改善（3ヶ月以上）

1. 話者識別機能
2. タイムスタンプ付き出力
3. WebSocketストリーミング
4. クラウドモデル対応

---

## 総括

### 現状の評価

**良い点**:
- ✅ モジュール分離が適切
- ✅ ドキュメントが充実
- ✅ VADによる最適化が効果的
- ✅ PyQt5のシグナル/スロットを正しく使用

**改善が必要な点**:
- ⚠️ スレッドセーフティの問題（重要）
- ⚠️ リソースリークの可能性（重要）
- ⚠️ エラー回復戦略の不足
- ⚠️ カスタム例外の欠如

### 推奨される次のステップ

1. **即座に実施**:
   - フェーズ1の高優先度修正（2-3日）
   - 統合テストの実施

2. **短期（1-2週間）**:
   - フェーズ2の中優先度改善
   - パフォーマンスベンチマーク

3. **中期（1-2ヶ月）**:
   - フェーズ3の低優先度改善
   - ユーザーフィードバック収集

4. **長期（3ヶ月以上）**:
   - フェーズ4の機能追加
   - 多言語対応

### 見込まれる改善効果

| 項目 | 現状 | フェーズ1後 | フェーズ2後 |
|------|------|-------------|-------------|
| **品質スコア** | 7.5/10 | 8.5/10 | 9.0/10 |
| **安定性** | 中 | 高 | 非常に高 |
| **保守性** | 中 | 中-高 | 高 |
| **テスタビリティ** | 低-中 | 中 | 高 |
| **パフォーマンス** | 良 | 良 | 非常に良 |

---

## 付録: コードレビューチェックリスト

### ✅ 合格項目

- [x] モジュール分離が適切
- [x] PyQt5シグナル/スロットの正しい使用
- [x] VADによるCPU削減
- [x] ドキュメントの充実
- [x] ロギングの実装
- [x] 基本的なエラーハンドリング

### ⚠️ 要改善項目

- [ ] スレッドセーフティ（ロック機構）
- [ ] リソースクリーンアップ（コンテキストマネージャ）
- [ ] エラー回復戦略（連続エラー対応）
- [ ] カスタム例外（階層的例外クラス）
- [ ] 依存性注入（テスタビリティ）
- [ ] 型ヒント完全化（静的解析）

---

**レポート作成日**: 2025-10-15
**次回レビュー推奨日**: フェーズ1完了後（2-3日後）

**連絡先**: GitHub Issues または project@example.com
