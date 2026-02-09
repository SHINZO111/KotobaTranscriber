"""
リアルタイム文字起こしタブ
マイク入力によるライブ文字起こしUI
"""

import logging
import threading
import numpy as np
from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QComboBox, QProgressBar, QCheckBox, QGroupBox,
    QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer

logger = logging.getLogger(__name__)

# faster-whisperインポート
try:
    from faster_whisper_engine import FasterWhisperEngine
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available")

# PyAudioインポート
try:
    import pyaudio
    import webrtcvad
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logger.warning("pyaudio or webrtcvad not available")


class RealtimeTranscriptionWorker(QThread):
    """リアルタイム文字起こしワーカースレッド"""

    # シグナル定義
    text_ready = Signal(str)  # 認識されたテキスト
    partial_ready = Signal(str)  # 部分的な認識結果
    status_changed = Signal(str)  # ステータス変更
    error_occurred = Signal(str)  # エラー発生
    volume_changed = Signal(float)  # 音量レベル変更

    def __init__(self,
                 model_size: str = "base",
                 device: str = "auto",
                 sample_rate: int = 16000,
                 buffer_duration: float = 3.0,
                 vad_threshold: float = 0.5):
        super().__init__()

        self.model_size = model_size
        self.device = device
        self.sample_rate = sample_rate
        self.buffer_duration = buffer_duration
        self.vad_threshold = vad_threshold

        self.engine: Optional[FasterWhisperEngine] = None
        self._running_event = threading.Event()
        self._paused_event = threading.Event()

        # PyAudio関連
        self.audio = None
        self.stream = None
        self.vad = None

        # バッファ（最大60秒分でメモリを制限）
        self.audio_buffer = []
        self._buffer_lock = threading.Lock()
        self.buffer_samples = int(sample_rate * buffer_duration)
        self._max_buffer_samples = sample_rate * 60

    def initialize(self) -> bool:
        """エンジンとオーディオを初期化"""
        try:
            # faster-whisperエンジン初期化
            if FASTER_WHISPER_AVAILABLE:
                self.engine = FasterWhisperEngine(
                    model_size=self.model_size,
                    device=self.device,
                    language="ja"
                )
                self.status_changed.emit("モデルをロード中...")
                if not self.engine.load_model():
                    self.error_occurred.emit("モデルのロードに失敗しました")
                    return False

            # PyAudio初期化
            if PYAUDIO_AVAILABLE:
                self.audio = pyaudio.PyAudio()
                self.vad = webrtcvad.Vad(2)  # 感度レベル2（中程度）

            return True

        except Exception as e:
            # 部分的に初期化されたリソースをクリーンアップ
            if self.engine is not None:
                try:
                    self.engine.unload_model()
                except Exception:
                    pass
                self.engine = None
            if self.audio is not None:
                try:
                    self.audio.terminate()
                except Exception:
                    pass
                self.audio = None
            self.error_occurred.emit(f"初期化エラー: {str(e)}")
            return False

    def run(self):
        """メインループ"""
        if not self.initialize():
            return

        self._running_event.set()
        self.status_changed.emit("録音準備完了 - 開始ボタンをクリックしてください")

        # オーディオストリーム開始
        if PYAUDIO_AVAILABLE and self.audio:
            try:
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=int(self.sample_rate * 0.03)  # 30ms chunks
                )

                self.status_changed.emit("🎤 録音中...")

                while self._running_event.is_set():
                    if self._paused_event.is_set():
                        self.msleep(100)
                        continue

                    # オーディオデータ読み取り
                    try:
                        data = self.stream.read(
                            int(self.sample_rate * 0.03),
                            exception_on_overflow=False
                        )

                        # NumPy配列に変換
                        audio_chunk = np.frombuffer(data, dtype=np.int16)
                        audio_float = audio_chunk.astype(np.float32) / 32768.0

                        # 音量レベル計算
                        volume = np.abs(audio_float).mean()
                        self.volume_changed.emit(float(volume))

                        # バッファに追加（メモリ保護: 最大サイズを超えたら古いサンプルを破棄）
                        with self._buffer_lock:
                            self.audio_buffer.extend(audio_float)
                            if len(self.audio_buffer) > self._max_buffer_samples:
                                self.audio_buffer = self.audio_buffer[-self._max_buffer_samples:]

                        # VADチェック
                        is_speech = self._check_vad(data)

                        # バッファが満タンまたは音声終了時に処理
                        with self._buffer_lock:
                            buf_len = len(self.audio_buffer)
                        if buf_len >= self.buffer_samples or (not is_speech and buf_len > self.sample_rate * 0.5):
                            if buf_len > self.sample_rate * 0.3:  # 最低0.3秒
                                self._process_buffer()
                            else:
                                with self._buffer_lock:
                                    self.audio_buffer = []  # 短すぎる場合は破棄

                    except Exception as e:
                        logger.error(f"Audio processing error: {e}", exc_info=True)

            except Exception as e:
                self.error_occurred.emit(f"録音エラー: {str(e)}")
            finally:
                # 終了処理（例外時もリソースを確実に解放）
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
                # エンジンの解放
                try:
                    if hasattr(self, 'engine') and self.engine is not None:
                        self.engine.unload_model()
                except Exception as e:
                    logger.debug(f"Engine unload failed: {e}")

        self.status_changed.emit("停止しました")

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
            if not self.audio_buffer:
                return
            # NumPy配列に変換してバッファをクリア
            audio_data = np.array(self.audio_buffer, dtype=np.float32)
            self.audio_buffer = []

        try:
            # 文字起こし
            result = self.engine.transcribe(
                audio_data,
                sample_rate=self.sample_rate,
                beam_size=1,  # リアルタイム用に最小化
                temperature=0.0
            )

            text = result.get("text", "").strip()

            if text:
                self.text_ready.emit(text)

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)

    def stop(self):
        """停止"""
        self._running_event.clear()
        self.wait(3000)  # 最大3秒待機

    def is_paused(self) -> bool:
        """一時停止中かどうか（スレッドセーフ）"""
        return self._paused_event.is_set()

    def pause(self):
        """一時停止"""
        self._paused_event.set()
        self.status_changed.emit("⏸️ 一時停止中")

    def resume(self):
        """再開"""
        self._paused_event.clear()
        self.status_changed.emit("🎤 録音中...")


class RealtimeTab(QWidget):
    """リアルタイム文字起こしタブ"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.worker: Optional[RealtimeTranscriptionWorker] = None
        self.is_recording = False

        self.init_ui()

    def init_ui(self):
        """UI初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # === 設定グループ ===
        settings_group = QGroupBox("リアルタイム設定")
        settings_layout = QVBoxLayout()

        # モデル選択
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("モデル:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "tiny (最速・低精度)",
            "base (速い・普通)",
            "small (普通・良精度)",
            "medium (遅い・高精度)",
            "large-v3 (最遅・最高精度)"
        ])
        self.model_combo.setCurrentIndex(1)  # baseをデフォルト
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        settings_layout.addLayout(model_layout)

        # デバイス選択
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("デバイス:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["自動", "CPU", "CUDA (GPU)"])
        device_layout.addWidget(self.device_combo)
        device_layout.addStretch()
        settings_layout.addLayout(device_layout)

        # バッファ時間
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("バッファ時間:"))
        self.buffer_spin = QDoubleSpinBox()
        self.buffer_spin.setRange(1.0, 10.0)
        self.buffer_spin.setValue(3.0)
        self.buffer_spin.setSuffix(" 秒")
        buffer_layout.addWidget(self.buffer_spin)
        buffer_layout.addStretch()
        settings_layout.addLayout(buffer_layout)

        # VAD設定
        vad_layout = QHBoxLayout()
        self.vad_check = QCheckBox("音声検出 (VAD) を使用")
        self.vad_check.setChecked(True)
        vad_layout.addWidget(self.vad_check)
        settings_layout.addLayout(vad_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # === 録音コントロール ===
        control_layout = QHBoxLayout()

        self.start_button = QPushButton("▶️ 開始")
        self.start_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #4CAF50; color: white;")
        self.start_button.clicked.connect(self.toggle_recording)
        control_layout.addWidget(self.start_button)

        self.pause_button = QPushButton("⏸️ 一時停止")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        control_layout.addWidget(self.pause_button)

        self.clear_button = QPushButton("🗑️ クリア")
        self.clear_button.clicked.connect(self.clear_text)
        control_layout.addWidget(self.clear_button)

        layout.addLayout(control_layout)

        # === 音量メーター ===
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("音量:"))
        self.volume_bar = QProgressBar()
        self.volume_bar.setRange(0, 100)
        self.volume_bar.setValue(0)
        self.volume_bar.setTextVisible(False)
        volume_layout.addWidget(self.volume_bar)
        layout.addLayout(volume_layout)

        # === ステータス表示 ===
        self.status_label = QLabel("準備完了")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

        # === テキスト表示エリア ===
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("ここに文字起こし結果が表示されます...")
        self.text_edit.setMinimumHeight(200)
        layout.addWidget(self.text_edit)

        # === 保存ボタン ===
        save_layout = QHBoxLayout()

        self.save_txt_button = QPushButton("💾 TXT保存")
        self.save_txt_button.clicked.connect(lambda: self.save_text("txt"))
        save_layout.addWidget(self.save_txt_button)

        self.save_srt_button = QPushButton("🎬 SRT保存")
        self.save_srt_button.clicked.connect(lambda: self.save_text("srt"))
        save_layout.addWidget(self.save_srt_button)

        save_layout.addStretch()
        layout.addLayout(save_layout)

        # 利用不可メッセージ
        missing = []
        if not FASTER_WHISPER_AVAILABLE:
            missing.append("faster-whisper")
        if not PYAUDIO_AVAILABLE:
            missing.append("PyAudio")
        if missing:
            self.status_label.setText(f"⚠️ {', '.join(missing)}がインストールされていません")
            self.start_button.setEnabled(False)

    def toggle_recording(self):
        """録音開始/停止"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """録音開始"""
        # 設定取得
        model_size = self.model_combo.currentText().split()[0]
        device_map = {"自動": "auto", "CPU": "cpu", "CUDA (GPU)": "cuda"}
        device = device_map.get(self.device_combo.currentText(), "auto")
        buffer_duration = self.buffer_spin.value()

        # ワーカー作成
        self.worker = RealtimeTranscriptionWorker(
            model_size=model_size,
            device=device,
            buffer_duration=buffer_duration
        )

        # シグナル接続
        self.worker.text_ready.connect(self.on_text_ready)
        self.worker.status_changed.connect(self.on_status_changed)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.volume_changed.connect(self.on_volume_changed)

        # UI更新
        self.start_button.setText("⏹️ 停止")
        self.start_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #f44336; color: white;")
        self.pause_button.setEnabled(True)
        self.is_recording = True

        # 設定無効化
        self.model_combo.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.buffer_spin.setEnabled(False)

        # 開始
        self.worker.start()

    def stop_recording(self):
        """録音停止"""
        if self.worker:
            self.worker.stop()
            self.worker = None

        # UI更新
        self.start_button.setText("▶️ 開始")
        self.start_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #4CAF50; color: white;")
        self.pause_button.setEnabled(False)
        self.pause_button.setText("⏸️ 一時停止")
        self.is_recording = False

        # 設定有効化
        self.model_combo.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.buffer_spin.setEnabled(True)

        self.status_label.setText("停止しました")
        self.volume_bar.setValue(0)

    def toggle_pause(self):
        """一時停止/再開"""
        if not self.worker:
            return

        if self.worker.is_paused():
            self.worker.resume()
            self.pause_button.setText("⏸️ 一時停止")
        else:
            self.worker.pause()
            self.pause_button.setText("▶️ 再開")

    def on_text_ready(self, text: str):
        """文字起こし結果を受信"""
        current_text = self.text_edit.toPlainText()
        if current_text:
            self.text_edit.setPlainText(current_text + "\n" + text)
        else:
            self.text_edit.setPlainText(text)

        # 自動スクロール
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_status_changed(self, status: str):
        """ステータス変更を受信"""
        self.status_label.setText(status)

    def on_error(self, error_msg: str):
        """エラーを受信"""
        self.status_label.setText(f"❌ {error_msg}")
        self.stop_recording()

    def on_volume_changed(self, volume: float):
        """音量変更を受信"""
        # 音量を0-100の範囲に変換
        volume_percent = min(100, int(volume * 200))
        self.volume_bar.setValue(volume_percent)

    def clear_text(self):
        """テキストをクリア"""
        self.text_edit.clear()

    def save_text(self, format_type: str):
        """テキストを保存"""
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime

        text = self.text_edit.toPlainText()
        if not text:
            return

        default_name = f"リアルタイム文字起こし_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存",
            default_name,
            f"{format_type.upper()} Files (*.{format_type})"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.status_label.setText(f"✅ 保存しました: {file_path}")
            except Exception as e:
                self.status_label.setText(f"❌ 保存失敗: {str(e)}")


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)

    tab = RealtimeTab()
    tab.setWindowTitle("リアルタイム文字起こし - テスト")
    tab.resize(500, 600)
    tab.show()

    sys.exit(app.exec())
