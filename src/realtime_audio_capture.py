"""
リアルタイム音声キャプチャモジュール
マイクからの音声入力をキャプチャし、バッファリングする
"""

import pyaudio
import numpy as np
import numpy.typing as npt
import wave
import logging
from typing import Optional, Callable, List, Dict, Any, Tuple, Union
from collections import deque
from threading import Thread, Event, Lock
import time

from exceptions import (
    AudioDeviceNotFoundError,
    AudioStreamError,
    PyAudioInitializationError
)

logger = logging.getLogger(__name__)


class RealtimeAudioCapture:
    """
    リアルタイム音声キャプチャクラス

    コンテキストマネージャとして使用可能:
        with RealtimeAudioCapture() as capture:
            capture.start_capture()
            # ... 処理 ...
        # 自動的にクリーンアップされる
    """

    # 音声パラメータ
    SAMPLE_RATE = 16000  # Whisper標準
    CHANNELS = 1  # モノラル
    CHUNK_SIZE = 1024  # バッファサイズ
    FORMAT = pyaudio.paInt16  # 16bit

    def __init__(self,
                 device_index: Optional[int] = None,
                 sample_rate: int = 16000,
                 buffer_duration: float = 3.0):
        """
        初期化

        Args:
            device_index: マイクデバイスのインデックス（Noneで自動選択）
            sample_rate: サンプリングレート（Hz）
            buffer_duration: バッファ保持時間（秒）
        """
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.buffer_duration = buffer_duration

        # PyAudio初期化（遅延初期化に変更）
        self.audio: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None

        # バッファ（dequeで古いデータを自動削除）
        max_buffer_size = int(sample_rate * buffer_duration * 2)  # バイト数
        self.audio_buffer = deque(maxlen=max_buffer_size)

        # スレッドセーフティのためのロック
        self._buffer_lock = Lock()

        # 録音状態
        self.is_recording = False
        self.stop_event = Event()
        self.capture_thread: Optional[Thread] = None

        # コールバック関数
        self.on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None

        # 録音データ（全体保存用）
        self.full_recording = []

        logger.info(f"RealtimeAudioCapture initialized: SR={sample_rate}Hz, Buffer={buffer_duration}s")

    def __enter__(self) -> 'RealtimeAudioCapture':
        """コンテキストマネージャのエントリポイント"""
        logger.info("Entering RealtimeAudioCapture context")
        # PyAudioを初期化
        if self.audio is None:
            self.audio = pyaudio.PyAudio()
            logger.info("PyAudio initialized in context manager")
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> bool:
        """
        コンテキストマネージャのエグジットポイント

        Args:
            exc_type: 例外の型
            exc_val: 例外の値
            exc_tb: トレースバック

        Returns:
            False (例外を再送出)
        """
        logger.info("Exiting RealtimeAudioCapture context")
        try:
            self.cleanup()
        except Exception as e:
            logger.error(f"Error during context exit cleanup: {e}")

        # 例外が発生していた場合はログに記録
        if exc_type is not None:
            logger.error(f"Exception in context: {exc_type.__name__}: {exc_val}")

        # 例外を再送出（Falseを返す）
        return False

    def _ensure_pyaudio_initialized(self) -> None:
        """PyAudioが初期化されているか確認し、未初期化なら初期化する"""
        if self.audio is None:
            self.audio = pyaudio.PyAudio()
            logger.info("PyAudio initialized (lazy)")

    def _normalize_device_name(self, raw_name: Union[str, bytes]) -> str:
        """
        デバイス名を正規化してUTF-8文字列に変換

        Args:
            raw_name: 生のデバイス名（文字列またはバイト列）

        Returns:
            正規化されたUTF-8文字列
        """
        if isinstance(raw_name, bytes):
            # バイト列の場合、複数のエンコーディングを試行

            # まずUTF-8でデコード
            try:
                return raw_name.decode('utf-8')
            except UnicodeDecodeError:
                pass

            # システムエンコーディング（日本語Windowsの場合CP932）
            try:
                import locale
                system_encoding = locale.getpreferredencoding()
                return raw_name.decode(system_encoding)
            except (UnicodeDecodeError, LookupError):
                pass

            # Shift-JIS（日本語の可能性）
            try:
                return raw_name.decode('shift-jis')
            except UnicodeDecodeError:
                pass

            # 最終手段：エラーを置換
            return raw_name.decode('utf-8', errors='replace')

        elif isinstance(raw_name, str):
            # 既に文字列の場合
            # 文字化けの可能性があるため修正を試行
            try:
                # latin1でエンコード→UTF-8でデコード（mojibake修正）
                return raw_name.encode('latin1').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                # 修正できない場合はそのまま返す
                return raw_name

        else:
            # 予期しない型
            logger.warning(f"Unexpected device name type: {type(raw_name)}")
            return str(raw_name)

    def list_devices(self) -> List[Dict[str, Any]]:
        """利用可能な音声デバイス一覧を取得"""
        self._ensure_pyaudio_initialized()

        devices = []
        for i in range(self.audio.get_device_count()):
            try:
                info = self.audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:  # 入力デバイスのみ
                    # デバイス名を正規化（文字化け対策）
                    device_name = self._normalize_device_name(info['name'])

                    devices.append({
                        'index': i,
                        'name': device_name,
                        'channels': info['maxInputChannels'],
                        'sample_rate': int(info['defaultSampleRate'])
                    })
            except Exception as e:
                logger.warning(f"Failed to get device info for index {i}: {e}")

        return devices

    def get_default_device(self) -> Optional[int]:
        """デフォルト入力デバイスのインデックスを取得"""
        self._ensure_pyaudio_initialized()

        try:
            default_info = self.audio.get_default_input_device_info()
            return default_info['index']
        except Exception as e:
            logger.error(f"Failed to get default device: {e}")
            raise AudioDeviceNotFoundError(-1) from e

    def start_capture(self) -> bool:
        """音声キャプチャ開始"""
        if self.is_recording:
            logger.warning("Already recording")
            return False

        self._ensure_pyaudio_initialized()

        try:
            # デバイス選択
            if self.device_index is None:
                self.device_index = self.get_default_device()

            if self.device_index is None:
                logger.error("No input device available")
                raise AudioDeviceNotFoundError(-1)

            # ストリーム開始
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.CHUNK_SIZE,
                stream_callback=self._audio_callback
            )

            self.is_recording = True
            self.stop_event.clear()

            # キャプチャスレッド開始
            self.capture_thread = Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()

            logger.info(f"Audio capture started on device {self.device_index}")
            return True

        except Exception as e:
            raise AudioStreamError(f"Failed to start audio stream: {e}", self.device_index) from e

    def _audio_callback(self, in_data: bytes, frame_count: int, time_info: Dict[str, Any], status: int) -> Tuple[bytes, int]:
        """
        PyAudioコールバック（別スレッドで呼ばれる）

        スレッドセーフティ: buffer_lockで保護されたクリティカルセクション
        """
        if status:
            logger.warning(f"Audio callback status: {status}")

        # バッファへの書き込みをロックで保護
        with self._buffer_lock:
            # バッファに追加
            self.audio_buffer.extend(in_data)

            # 全体録音用にも保存
            self.full_recording.append(in_data)

        return (in_data, pyaudio.paContinue)

    def _capture_loop(self) -> None:
        """
        キャプチャループ（処理用のチャンク作成）

        スレッドセーフティ: buffer_lockでバッファアクセスを保護し、
        スナップショットパターンを使用してロックの外で処理を行う
        """
        chunk_size_samples = int(self.sample_rate * 3.0)  # 3秒分
        chunk_size_bytes = chunk_size_samples * 2  # 16bit = 2 bytes

        while not self.stop_event.is_set():
            try:
                # バッファのスナップショットを取得（ロック内で高速に実行）
                chunk_bytes = None

                with self._buffer_lock:
                    # バッファに十分なデータがあるかチェック
                    if len(self.audio_buffer) >= chunk_size_bytes:
                        # チャンクのスナップショットを取得
                        chunk_bytes = bytes(list(self.audio_buffer)[:chunk_size_bytes])

                # スナップショットが取得できた場合、ロックの外で処理
                if chunk_bytes is not None:
                    # NumPy配列に変換
                    audio_array = np.frombuffer(chunk_bytes, dtype=np.int16)

                    # float32に正規化 (-1.0 ~ 1.0)
                    audio_float = audio_array.astype(np.float32) / 32768.0

                    # コールバック実行（ロックの外で実行）
                    if self.on_audio_chunk:
                        self.on_audio_chunk(audio_float)

                    # 処理したデータをバッファから削除（再度ロックを取得）
                    # 50%オーバーラップのため、半分だけ削除
                    overlap_bytes = chunk_size_bytes // 2

                    with self._buffer_lock:
                        for _ in range(overlap_bytes):
                            if len(self.audio_buffer) > 0:
                                self.audio_buffer.popleft()

                # 短時間待機
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(0.5)

    def stop_capture(self) -> bool:
        """
        音声キャプチャ停止

        リソースリークを防ぐため、確実にストリームとスレッドをクリーンアップする
        """
        if not self.is_recording:
            logger.warning("Not recording")
            return False

        logger.info("Stopping audio capture...")
        cleanup_successful = True

        try:
            # 録音状態フラグを先に更新
            self.is_recording = False
            self.stop_event.set()

            # スレッド終了待機（タイムアウト5秒に延長）
            if self.capture_thread and self.capture_thread.is_alive():
                logger.info("Waiting for capture thread to finish...")
                self.capture_thread.join(timeout=5.0)

                # タイムアウト後もスレッドが生きている場合は警告
                if self.capture_thread.is_alive():
                    logger.warning("Capture thread did not finish within timeout")
                    cleanup_successful = False
                else:
                    logger.info("Capture thread finished successfully")

            # ストリーム停止（確実に実行）
            if self.stream:
                try:
                    # ストリームが開いているか確認
                    if self.stream.is_active():
                        logger.info("Stopping active stream...")
                        self.stream.stop_stream()

                    logger.info("Closing stream...")
                    self.stream.close()
                    logger.info("Stream closed successfully")
                except Exception as stream_error:
                    logger.error(f"Error closing stream: {stream_error}")
                    cleanup_successful = False
                finally:
                    # いずれにせよNoneに設定
                    self.stream = None

            # バッファクリア
            logger.info("Clearing audio buffers...")
            self.audio_buffer.clear()

            if cleanup_successful:
                logger.info("Audio capture stopped successfully")
            else:
                logger.warning("Audio capture stopped with warnings")

            return cleanup_successful

        except Exception as e:
            logger.error(f"Failed to stop audio capture: {e}")
            # エラーが発生してもストリームはNoneにする
            self.stream = None
            return False

    def get_full_recording(self) -> Optional[np.ndarray]:
        """録音した全体データを取得（NumPy配列）"""
        if not self.full_recording:
            return None

        try:
            # バイト列を結合
            audio_bytes = b''.join(self.full_recording)

            # NumPy配列に変換
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

            # float32に正規化
            audio_float = audio_array.astype(np.float32) / 32768.0

            return audio_float

        except Exception as e:
            logger.error(f"Failed to get full recording: {e}")
            return None

    def save_recording(self, filepath: str) -> bool:
        """録音データをWAVファイルとして保存"""
        audio_data = self.get_full_recording()

        if audio_data is None:
            logger.error("No recording data to save")
            return False

        self._ensure_pyaudio_initialized()

        try:
            # int16に戻す
            audio_int16 = (audio_data * 32768.0).astype(np.int16)

            # WAVファイルとして保存
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())

            logger.info(f"Recording saved to: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return False

    def clear_recording(self) -> None:
        """録音データをクリア"""
        self.full_recording = []
        self.audio_buffer.clear()
        logger.info("Recording data cleared")

    def cleanup(self) -> None:
        """
        クリーンアップ

        すべてのリソースを解放する。
        録音中の場合は停止してから解放する。
        """
        logger.info("Starting cleanup...")

        # 録音停止（録音中の場合）
        if self.is_recording:
            logger.info("Stopping active recording before cleanup...")
            self.stop_capture()

        # PyAudio終了処理
        if self.audio is not None:
            try:
                logger.info("Terminating PyAudio...")
                self.audio.terminate()
                logger.info("PyAudio terminated successfully")
            except Exception as e:
                logger.error(f"Error terminating PyAudio: {e}")
            finally:
                self.audio = None

        # バッファクリア
        self.audio_buffer.clear()
        self.full_recording = []

        logger.info("RealtimeAudioCapture cleaned up successfully")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # コンテキストマネージャとして使用
    print("\n=== RealtimeAudioCapture Context Manager Test ===")
    with RealtimeAudioCapture() as capture:
        # デバイス一覧表示
        print("\n=== 利用可能な音声デバイス ===")
        devices = capture.list_devices()
        for device in devices:
            print(f"[{device['index']}] {device['name']} - {device['channels']}ch @ {device['sample_rate']}Hz")

        # テストキャプチャ
        def on_chunk(audio_chunk):
            rms = np.sqrt(np.mean(audio_chunk**2))
            print(f"Audio chunk received: {len(audio_chunk)} samples, RMS: {rms:.4f}")

        capture.on_audio_chunk = on_chunk

        print("\n5秒間録音します...")
        capture.start_capture()
        time.sleep(5)
        capture.stop_capture()

        # 録音データ保存
        output_file = "test_recording.wav"
        if capture.save_recording(output_file):
            print(f"\n録音データを保存しました: {output_file}")

    # with ブロックを抜けると自動的にクリーンアップされる
    print("テスト完了（リソースは自動的にクリーンアップされました）")
