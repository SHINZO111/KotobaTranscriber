"""
Qt-free リアルタイム文字起こしワーカー
threading.Thread + EventBus による音声キャプチャ・リアルタイム文字起こし。
"""

import logging
import threading
import time
from typing import Optional

import numpy as np

from api.event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)

# faster-whisper インポート
try:
    from faster_whisper_engine import FasterWhisperEngine

    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available")

# PyAudio インポート
try:
    import pyaudio
    import webrtcvad

    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("pyaudio or webrtcvad not available")


class RealtimeWorker(threading.Thread):
    """
    リアルタイム文字起こしワーカー（Qt非依存）。
    EventBus 経由で text_ready / volume_changed / status_changed / error イベントを発行。
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        sample_rate: int = 16000,
        buffer_duration: float = 3.0,
        vad_threshold: float = 0.5,
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__(daemon=True)

        self.model_size = model_size
        self.device = device
        self.sample_rate = sample_rate
        self.buffer_duration = buffer_duration
        self.vad_threshold = vad_threshold

        self.engine: Optional[FasterWhisperEngine] = None
        self._running_event = threading.Event()
        self._paused_event = threading.Event()

        self.audio = None
        self.stream = None
        self.vad = None

        self._buffer_lock = threading.Lock()
        self.buffer_samples = int(sample_rate * buffer_duration)
        self._max_buffer_samples = sample_rate * 60
        # NumPyリングバッファ: float32 (4B/要素) vs Pythonリスト (28B/要素) で約7倍メモリ効率改善
        self._ring_buffer = np.zeros(self._max_buffer_samples, dtype=np.float32)
        self._write_pos = 0  # 現在のバッファ内有効サンプル数（兼書き込みポインタ）

        self._bus = event_bus or get_event_bus()
        self._last_volume_emit = 0.0  # volume_changed スロットリング用

    def initialize(self) -> bool:
        """エンジンとオーディオを初期化"""
        try:
            if FASTER_WHISPER_AVAILABLE:
                self.engine = FasterWhisperEngine(model_size=self.model_size, device=self.device, language="ja")
                self._bus.emit("status_changed", {"status": "モデルをロード中..."})
                if not self.engine.load_model():
                    self._bus.emit("error", {"message": "モデルのロードに失敗しました"})
                    return False
            else:
                self._bus.emit("error", {"message": "faster-whisper がインストールされていません"})
                return False

            if PYAUDIO_AVAILABLE:
                self.audio = pyaudio.PyAudio()
                self.vad = webrtcvad.Vad(2)
            else:
                self._bus.emit("error", {"message": "PyAudio がインストールされていません"})
                return False

            return True

        except Exception as e:
            if self.engine is not None:
                try:
                    self.engine.unload_model()
                except Exception:
                    pass  # nosec B110 - cleanup in error handler, safe to ignore
                self.engine = None
            if self.audio is not None:
                try:
                    self.audio.terminate()
                except Exception:
                    pass  # nosec B110 - cleanup in error handler, safe to ignore
                self.audio = None
            logger.error(f"初期化エラー: {e}", exc_info=True)
            self._bus.emit("error", {"message": "初期化エラーが発生しました"})
            return False

    def run(self):
        """メインループ"""
        if not self.initialize():
            return

        self._paused_event.clear()  # 前回の一時停止状態をリセット
        self._running_event.set()
        self._bus.emit("status_changed", {"status": "録音中..."})

        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=int(self.sample_rate * 0.03),  # 30ms chunks
            )

            while self._running_event.is_set():
                if self._paused_event.is_set():
                    time.sleep(0.1)
                    continue

                try:
                    data = self.stream.read(int(self.sample_rate * 0.03), exception_on_overflow=False)

                    audio_chunk = np.frombuffer(data, dtype=np.int16)
                    audio_float = audio_chunk.astype(np.float32) / 32768.0

                    volume = float(np.abs(audio_float).mean())
                    # ~10Hz にスロットリング（30ms×3≒100ms間隔）
                    now = time.monotonic()
                    if now - self._last_volume_emit >= 0.1:
                        self._bus.emit("volume_changed", {"level": volume})
                        self._last_volume_emit = now

                    with self._buffer_lock:
                        n = len(audio_float)
                        space = self._max_buffer_samples - self._write_pos
                        if n <= space:
                            self._ring_buffer[self._write_pos : self._write_pos + n] = audio_float
                            self._write_pos += n
                        else:
                            # バッファが溢れる場合: 古いデータを捨てて末尾のみ保持
                            if n >= self._max_buffer_samples:
                                # 新データだけでバッファ全体を超える場合
                                self._ring_buffer[:] = audio_float[-self._max_buffer_samples :]
                                self._write_pos = self._max_buffer_samples
                            else:
                                # 既存データをシフトして新データを追加
                                keep = self._max_buffer_samples - n
                                self._ring_buffer[:keep] = self._ring_buffer[self._write_pos - keep : self._write_pos]
                                self._ring_buffer[keep : keep + n] = audio_float
                                self._write_pos = self._max_buffer_samples

                    is_speech = self._check_vad(data)

                    with self._buffer_lock:
                        buf_len = self._write_pos
                    if buf_len >= self.buffer_samples or (not is_speech and buf_len > self.sample_rate * 0.5):
                        if buf_len > self.sample_rate * 0.3:
                            self._process_buffer()
                        else:
                            with self._buffer_lock:
                                self._write_pos = 0

                except Exception as e:
                    logger.error(f"Audio processing error: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"録音エラー: {e}", exc_info=True)
            self._bus.emit("error", {"message": "録音エラーが発生しました"})
        finally:
            try:
                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
            except Exception as e:
                logger.debug(f"Stream cleanup failed: {e}")
            try:
                if self.audio:
                    self.audio.terminate()
            except Exception as e:
                logger.debug(f"Audio cleanup failed: {e}")
            try:
                if self.engine is not None:
                    self.engine.unload_model()
            except Exception as e:
                logger.debug(f"Engine unload failed: {e}")

        self._bus.emit("status_changed", {"status": "停止しました"})

    def _check_vad(self, data: bytes) -> bool:
        """VADで音声を検出"""
        if not self.vad:
            return True
        try:
            return self.vad.is_speech(data, self.sample_rate)
        except Exception:
            return True

    def _process_buffer(self):
        """バッファの音声を処理"""
        if not self.engine:
            return

        with self._buffer_lock:
            if self._write_pos == 0:
                return
            audio_data = self._ring_buffer[: self._write_pos].copy()
            self._write_pos = 0

        try:
            result = self.engine.transcribe(audio_data, sample_rate=self.sample_rate, beam_size=1, temperature=0.0)
            text = result.get("text", "").strip()
            if text:
                self._bus.emit("text_ready", {"text": text})
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)

    def stop(self):
        """停止"""
        self._running_event.clear()
        if threading.current_thread() is not self:
            self.join(timeout=3.0)
            if self.is_alive():
                logger.warning("RealtimeWorker did not stop within timeout")

    def is_paused(self) -> bool:
        """一時停止中かどうか"""
        return self._paused_event.is_set()

    def pause(self):
        """一時停止"""
        self._paused_event.set()
        self._bus.emit("status_changed", {"status": "一時停止中"})

    def resume(self):
        """再開"""
        self._paused_event.clear()
        self._bus.emit("status_changed", {"status": "録音中..."})
