"""
リアルタイム文字起こしコーディネーター
音声キャプチャ、VAD、faster-whisperを統合

依存性注入パターンを使用してテスタビリティを向上
"""

import logging
import numpy as np
import numpy.typing as npt
from typing import Optional, Callable, List, Dict, Any
from PyQt5.QtCore import QThread, pyqtSignal
import time
import threading

from exceptions import (
    AudioDeviceNotFoundError,
    AudioStreamError,
    ModelLoadingError,
    TranscriptionFailedError
)
from protocols import AudioCaptureProtocol, VADProtocol, TranscriptionEngineProtocol
from faster_whisper_engine import FASTER_WHISPER_AVAILABLE

logger = logging.getLogger(__name__)


class RealtimeTranscriber(QThread):
    """リアルタイム文字起こしスレッド"""

    # クラス定数 - エラー回復戦略
    MAX_CONSECUTIVE_ERRORS = 5  # 連続エラーの最大許容回数
    ERROR_COOLDOWN_TIME = 2.0  # エラー後のクールダウン時間（秒）

    # シグナル
    transcription_update = pyqtSignal(str, bool)  # (テキスト, 確定フラグ)
    status_update = pyqtSignal(str)  # ステータスメッセージ
    error_occurred = pyqtSignal(str)  # エラーメッセージ
    critical_error_occurred = pyqtSignal(str)  # 致命的エラーメッセージ
    vad_status_changed = pyqtSignal(bool, float)  # (音声検出フラグ, エネルギー)

    def __init__(self,
                 audio_capture: AudioCaptureProtocol,
                 whisper_engine: TranscriptionEngineProtocol,
                 vad: Optional[VADProtocol] = None):
        """
        初期化（依存性注入パターン）

        Args:
            audio_capture: 音声キャプチャコンポーネント（AudioCaptureProtocol準拠）
            whisper_engine: 文字起こしエンジン（TranscriptionEngineProtocol準拠）
            vad: VADコンポーネント（VADProtocol準拠、Noneの場合はVAD無効）
        """
        super().__init__()

        # 依存コンポーネント（外部から注入）
        self.audio_capture = audio_capture
        self.whisper_engine = whisper_engine
        self.vad = vad

        # 状態管理
        self.is_running = False
        self.is_recording = False
        self.enable_vad = vad is not None

        # 文字起こし結果の蓄積
        self.accumulated_text: List[str] = []
        self.pending_text = ""

        # 統計情報
        self.total_chunks_processed = 0
        self.total_audio_duration = 0.0
        self.total_processing_time = 0.0

        # スレッドセーフティのためのロック
        self._text_lock = threading.Lock()  # accumulated_text, pending_textの保護用
        self._error_lock = threading.Lock()  # エラーカウンターの保護用

        # エラー回復戦略の状態管理
        self._consecutive_errors = 0
        self._last_error_time = 0.0

        logger.info("RealtimeTranscriber initialized with injected dependencies")

    def run(self) -> None:
        """スレッド実行"""
        self.is_running = True

        # Whisperモデルをロード
        self.status_update.emit("モデルをロード中...")
        if not self.whisper_engine.load_model():
            self.error_occurred.emit("Whisperモデルのロードに失敗しました")
            self.is_running = False
            return

        self.status_update.emit("準備完了 - 録音開始してください")
        logger.info("RealtimeTranscriber thread started")

        # メインループ
        while self.is_running:
            time.sleep(0.1)  # CPU負荷軽減

        logger.info("RealtimeTranscriber thread stopped")

    def start_recording(self) -> bool:
        """録音開始"""
        if self.is_recording:
            logger.warning("Already recording")
            return False

        # VADリセット
        if self.vad:
            self.vad.reset()

        # エラーカウンターをリセット
        self._reset_error_counter()

        # 音声キャプチャ開始
        self.audio_capture.on_audio_chunk = self._on_audio_chunk
        if not self.audio_capture.start_capture():
            self.error_occurred.emit("マイクの起動に失敗しました")
            return False

        self.is_recording = True
        self.accumulated_text = []
        self.pending_text = ""

        self.status_update.emit("🎤 録音中...")
        logger.info("Recording started")
        return True

    def stop_recording(self) -> bool:
        """録音停止"""
        if not self.is_recording:
            logger.warning("Not recording")
            return False

        # 音声キャプチャ停止
        self.audio_capture.stop_capture()
        self.is_recording = False

        # 保留中のテキストを確定（ロックで保護）
        with self._text_lock:
            if self.pending_text:
                self.accumulated_text.append(self.pending_text)
                self.transcription_update.emit(self.pending_text, True)
                self.pending_text = ""

        self.status_update.emit("録音停止")
        logger.info("Recording stopped")
        return True

    def _reset_error_counter(self) -> None:
        """エラーカウンターをリセット"""
        with self._error_lock:
            if self._consecutive_errors > 0:
                logger.info(f"Error counter reset (was {self._consecutive_errors})")
                self._consecutive_errors = 0
                self._last_error_time = 0.0

    def _handle_processing_error(self, error: Exception) -> bool:
        """
        エラーハンドリングと回復戦略

        Args:
            error: 発生した例外

        Returns:
            bool: 処理を継続すべきかどうか (False=停止すべき)
        """
        current_time = time.time()

        with self._error_lock:
            self._consecutive_errors += 1
            self._last_error_time = current_time

            error_msg = f"処理エラー ({self._consecutive_errors}/{self.MAX_CONSECUTIVE_ERRORS}): {str(error)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

            # 連続エラーが許容回数を超えた場合
            if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                critical_msg = (
                    f"連続エラーが{self.MAX_CONSECUTIVE_ERRORS}回に達しました。"
                    "録音を自動停止します。"
                )
                logger.critical(critical_msg)
                self.critical_error_occurred.emit(critical_msg)

                # 録音を自動停止
                if self.is_recording:
                    self.stop_recording()

                return False  # 処理停止

            # クールダウン時間待機
            if self.ERROR_COOLDOWN_TIME > 0:
                logger.info(f"Error cooldown: waiting {self.ERROR_COOLDOWN_TIME}s")
                time.sleep(self.ERROR_COOLDOWN_TIME)

            return True  # 処理継続

    def _on_audio_chunk(self, audio_chunk: npt.NDArray[np.float32]) -> None:
        """音声チャンクのコールバック"""
        try:
            # VADチェック
            if self.vad:
                is_speech, energy = self.vad.is_speech_present(audio_chunk)
                self.vad_status_changed.emit(is_speech, energy)

                if not is_speech:
                    # 無音時は処理スキップ
                    return

            # 文字起こし実行
            start_time = time.time()
            text = self.whisper_engine.transcribe_stream(audio_chunk, sample_rate=16000)
            processing_time = time.time() - start_time

            if text and text.strip():
                # 空白のみでないテキスト
                text = text.strip()

                # 統計更新
                self.total_chunks_processed += 1
                self.total_audio_duration += len(audio_chunk) / 16000
                self.total_processing_time += processing_time

                # 保留中のテキストとして保存（次のチャンクで確定）
                # テキストの更新をロックで保護
                with self._text_lock:
                    if self.pending_text:
                        # 前回の保留テキストを確定
                        self.accumulated_text.append(self.pending_text)
                        self.transcription_update.emit(self.pending_text, True)

                    self.pending_text = text
                    # 保留中テキストとして表示（確定フラグ=False）
                    self.transcription_update.emit(text, False)

                # パフォーマンス情報をログ
                rtf = processing_time / (len(audio_chunk) / 16000)
                logger.debug(f"Transcribed: '{text}' (RTF: {rtf:.2f}x)")

                # 成功時はエラーカウンターをリセット
                self._reset_error_counter()

        except Exception as e:
            # エラーハンドリングと回復戦略を実行
            should_continue = self._handle_processing_error(e)
            if not should_continue:
                logger.warning("Stopping audio processing due to excessive errors")
                return

    def get_full_transcription(self) -> str:
        """全文字起こし結果を取得（スレッドセーフ）"""
        with self._text_lock:
            all_text = self.accumulated_text.copy()
            if self.pending_text:
                all_text.append(self.pending_text)
        return " ".join(all_text)

    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        avg_rtf = (
            self.total_processing_time / self.total_audio_duration
            if self.total_audio_duration > 0 else 0
        )

        return {
            "chunks_processed": self.total_chunks_processed,
            "audio_duration": self.total_audio_duration,
            "processing_time": self.total_processing_time,
            "average_rtf": avg_rtf,
            "accumulated_lines": len(self.accumulated_text)
        }

    def save_recording(self, filepath: str) -> bool:
        """録音データを保存"""
        return self.audio_capture.save_recording(filepath)

    def clear_transcription(self) -> None:
        """文字起こし結果をクリア（スレッドセーフ）"""
        with self._text_lock:
            self.accumulated_text = []
            self.pending_text = ""
        self.audio_capture.clear_recording()
        logger.info("Transcription cleared")

    def list_devices(self) -> List[Dict]:
        """利用可能なマイクデバイス一覧"""
        return self.audio_capture.list_devices()

    def set_device(self, device_index: int) -> bool:
        """マイクデバイスを変更"""
        if self.is_recording:
            logger.warning("Cannot change device while recording")
            return False

        self.audio_capture.device_index = device_index
        logger.info(f"Device changed to index: {device_index}")
        return True

    def cleanup(self) -> None:
        """クリーンアップ"""
        self.stop_recording()
        self.is_running = False
        self.audio_capture.cleanup()
        self.whisper_engine.unload_model()
        logger.info("RealtimeTranscriber cleaned up")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    from PyQt5.QtWidgets import QApplication
    from realtime_audio_capture import RealtimeAudioCapture
    from simple_vad import AdaptiveVAD
    from faster_whisper_engine import FasterWhisperEngine
    import sys

    app = QApplication(sys.argv)

    # faster-whisperの確認
    if not FASTER_WHISPER_AVAILABLE:
        print("ERROR: faster-whisper not available")
        print("Install with: pip install faster-whisper")
        sys.exit(1)

    print("\n=== RealtimeTranscriber Test ===")

    # 依存コンポーネントを作成
    audio_capture = RealtimeAudioCapture(
        device_index=None,
        sample_rate=16000,
        buffer_duration=3.0
    )

    whisper_engine = FasterWhisperEngine(
        model_size="tiny",  # テスト用に軽量モデル
        device="auto",
        language="ja"
    )

    vad = AdaptiveVAD(
        initial_threshold=0.01,
        min_silence_duration=1.0,
        sample_rate=16000
    )

    # RealtimeTranscriberを依存性注入で作成
    transcriber = RealtimeTranscriber(
        audio_capture=audio_capture,
        whisper_engine=whisper_engine,
        vad=vad
    )

    # デバイス一覧表示
    print("\n利用可能なマイクデバイス:")
    devices = transcriber.list_devices()
    for device in devices:
        print(f"  [{device['index']}] {device['name']}")

    # コールバック設定
    def on_transcription(text, is_final):
        status = "確定" if is_final else "処理中"
        print(f"[{status}] {text}")

    def on_status(status):
        print(f"Status: {status}")

    def on_error(error):
        print(f"ERROR: {error}")

    def on_critical_error(error):
        print(f"CRITICAL ERROR: {error}")

    def on_vad(is_speech, energy):
        if is_speech:
            print(f"🎤 音声検出 (energy: {energy:.4f})")

    transcriber.transcription_update.connect(on_transcription)
    transcriber.status_update.connect(on_status)
    transcriber.error_occurred.connect(on_error)
    transcriber.critical_error_occurred.connect(on_critical_error)
    transcriber.vad_status_changed.connect(on_vad)

    # スレッド開始
    transcriber.start()

    print("\n5秒後に録音を開始します...")
    import time
    time.sleep(5)

    print("\n録音開始 - 10秒間録音します...")
    transcriber.start_recording()
    time.sleep(10)

    print("\n録音停止...")
    transcriber.stop_recording()

    # 結果表示
    print("\n=== 文字起こし結果 ===")
    print(transcriber.get_full_transcription())

    # 統計情報
    stats = transcriber.get_statistics()
    print("\n=== 統計情報 ===")
    print(f"処理チャンク数: {stats['chunks_processed']}")
    print(f"音声時間: {stats['audio_duration']:.2f}s")
    print(f"処理時間: {stats['processing_time']:.2f}s")
    print(f"平均RTF: {stats['average_rtf']:.2f}x")

    # クリーンアップ
    transcriber.cleanup()
    transcriber.wait()

    print("\nテスト完了")
    sys.exit(0)
