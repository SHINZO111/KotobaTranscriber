"""
リアルタイム音声キャプチャモジュール
マイクからの音声入力をキャプチャし、バッファリングする
"""

import pyaudio
import numpy as np
import wave
import logging
from typing import Optional, Callable
from collections import deque
from threading import Thread, Event
import time

logger = logging.getLogger(__name__)


class RealtimeAudioCapture:
    """リアルタイム音声キャプチャクラス"""

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

        # PyAudio初期化
        self.audio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None

        # バッファ（dequeで古いデータを自動削除）
        max_buffer_size = int(sample_rate * buffer_duration * 2)  # バイト数
        self.audio_buffer = deque(maxlen=max_buffer_size)

        # 録音状態
        self.is_recording = False
        self.stop_event = Event()
        self.capture_thread: Optional[Thread] = None

        # コールバック関数
        self.on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None

        # 録音データ（全体保存用）
        self.full_recording = []

        logger.info(f"RealtimeAudioCapture initialized: SR={sample_rate}Hz, Buffer={buffer_duration}s")

    def list_devices(self):
        """利用可能な音声デバイス一覧を取得"""
        devices = []
        for i in range(self.audio.get_device_count()):
            try:
                info = self.audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:  # 入力デバイスのみ
                    devices.append({
                        'index': i,
                        'name': info['name'],
                        'channels': info['maxInputChannels'],
                        'sample_rate': int(info['defaultSampleRate'])
                    })
            except Exception as e:
                logger.warning(f"Failed to get device info for index {i}: {e}")

        return devices

    def get_default_device(self) -> Optional[int]:
        """デフォルト入力デバイスのインデックスを取得"""
        try:
            default_info = self.audio.get_default_input_device_info()
            return default_info['index']
        except Exception as e:
            logger.error(f"Failed to get default device: {e}")
            return None

    def start_capture(self) -> bool:
        """音声キャプチャ開始"""
        if self.is_recording:
            logger.warning("Already recording")
            return False

        try:
            # デバイス選択
            if self.device_index is None:
                self.device_index = self.get_default_device()

            if self.device_index is None:
                logger.error("No input device available")
                return False

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
            logger.error(f"Failed to start audio capture: {e}")
            return False

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudioコールバック（別スレッドで呼ばれる）"""
        if status:
            logger.warning(f"Audio callback status: {status}")

        # バッファに追加
        self.audio_buffer.extend(in_data)

        # 全体録音用にも保存
        self.full_recording.append(in_data)

        return (in_data, pyaudio.paContinue)

    def _capture_loop(self):
        """キャプチャループ（処理用のチャンク作成）"""
        chunk_size_samples = int(self.sample_rate * 3.0)  # 3秒分
        chunk_size_bytes = chunk_size_samples * 2  # 16bit = 2 bytes

        while not self.stop_event.is_set():
            try:
                # バッファに十分なデータがあるかチェック
                if len(self.audio_buffer) >= chunk_size_bytes:
                    # チャンクを取り出し
                    chunk_bytes = bytes(list(self.audio_buffer)[:chunk_size_bytes])

                    # NumPy配列に変換
                    audio_array = np.frombuffer(chunk_bytes, dtype=np.int16)

                    # float32に正規化 (-1.0 ~ 1.0)
                    audio_float = audio_array.astype(np.float32) / 32768.0

                    # コールバック実行
                    if self.on_audio_chunk:
                        self.on_audio_chunk(audio_float)

                    # 処理したデータをバッファから削除
                    # 50%オーバーラップのため、半分だけ削除
                    overlap_bytes = chunk_size_bytes // 2
                    for _ in range(overlap_bytes):
                        if len(self.audio_buffer) > 0:
                            self.audio_buffer.popleft()

                # 短時間待機
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(0.5)

    def stop_capture(self) -> bool:
        """音声キャプチャ停止"""
        if not self.is_recording:
            logger.warning("Not recording")
            return False

        try:
            self.is_recording = False
            self.stop_event.set()

            # スレッド終了待機
            if self.capture_thread:
                self.capture_thread.join(timeout=2.0)

            # ストリーム停止
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            logger.info("Audio capture stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop audio capture: {e}")
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

    def clear_recording(self):
        """録音データをクリア"""
        self.full_recording = []
        self.audio_buffer.clear()
        logger.info("Recording data cleared")

    def cleanup(self):
        """クリーンアップ"""
        self.stop_capture()
        self.audio.terminate()
        logger.info("RealtimeAudioCapture cleaned up")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    capture = RealtimeAudioCapture()

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

    capture.cleanup()
    print("テスト完了")
