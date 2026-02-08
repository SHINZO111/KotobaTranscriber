"""
メインウィンドウUIモジュール
会議モード・議事録生成・進捗表示改善を統合
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox,
    QMessageBox, QFileDialog, QProgressBar, QGroupBox,
    QTextEdit, QSplitter, QFrame, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

# 社内モジュール
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from meeting_mode import get_meeting_recorder, get_meeting_processor
from minutes_generator import get_minutes_generator
from custom_dictionary import get_custom_dictionary, create_dictionary_from_yaml
from export.excel_exporter import get_excel_exporter
from export.word_exporter import get_word_exporter

try:
    from realtime_tab import RealtimeTab
    REALTIME_AVAILABLE = True
except ImportError:
    REALTIME_AVAILABLE = False

try:
    from dark_theme import DarkTheme
    DARK_THEME_AVAILABLE = True
except ImportError:
    DARK_THEME_AVAILABLE = False

logger = logging.getLogger(__name__)


class ProgressWorker(QThread):
    """バックグラウンド処理ワーカー"""
    progress = Signal(int, int, str)  # current, total, message
    finished_signal = Signal(bool, str)  # success, message
    result_signal = Signal(dict)  # result data

    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.task_func(
                *self.args,
                progress_callback=self._emit_progress,
                **self.kwargs
            )
            self.result_signal.emit(result if isinstance(result, dict) else {})
            self.finished_signal.emit(True, "完了しました")
        except Exception as e:
            logger.error(f"Worker error: {e}")
            self.finished_signal.emit(False, str(e))

    def _emit_progress(self, current, total, message):
        self.progress.emit(current, total, message)


class MainWindow(QMainWindow):
    """メインウィンドウクラス（会議モード対応）"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KotobaTranscriber - AGEC版")
        self.setMinimumSize(1200, 800)

        # 設定読み込み
        self.config = self._load_config()

        # 各種インスタンス
        self.dictionary = create_dictionary_from_yaml()
        self.meeting_recorder = get_meeting_recorder(self.config.get('meeting_mode', {}))
        self.meeting_processor = get_meeting_processor(self.config.get('meeting_mode', {}))
        self.minutes_generator = get_minutes_generator()

        # 状態
        self.is_recording = False
        self.current_session = None
        self.last_transcription = None
        self.last_minutes = None
        self.selected_file = None

        # エンジンキャッシュ（モデルの再ロードを防止）
        self._engine = None

        # UI構築
        self.setup_ui()

        # タイマー
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_recording_status)
        self.status_timer.start(1000)  # 1秒ごとに更新

        logger.info("MainWindow initialized")

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        try:
            import yaml
            config_path = Path("config/config.yaml")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
        return {}

    def setup_ui(self):
        """UIを構築"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # === ヘッダー ===
        header = self._create_header()
        main_layout.addWidget(header)

        # === メインコンテンツ ===
        splitter = QSplitter(Qt.Horizontal)

        # 左パネル（コントロール）
        left_panel = self._create_control_panel()
        splitter.addWidget(left_panel)

        # 右パネル（プレビュー）
        right_panel = self._create_preview_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter, 1)

        # === ステータスバー ===
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")

    def _create_header(self) -> QFrame:
        """ヘッダーを作成"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)

        # タイトル
        title = QLabel("KotobaTranscriber")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # AGECロゴ/テキスト
        agec_label = QLabel("AGEC版")
        agec_label.setStyleSheet("color: #4472C4; font-weight: bold;")
        layout.addWidget(agec_label)

        layout.addStretch()

        # ダークモード切り替え
        if DARK_THEME_AVAILABLE:
            self.dark_mode_check = QCheckBox("🌙 ダークモード")
            self.dark_mode_check.stateChanged.connect(self.toggle_dark_mode)
            layout.addWidget(self.dark_mode_check)

        return frame

    def _create_control_panel(self) -> QWidget:
        """コントロールパネルを作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(15)

        # === 会議モードセクション ===
        meeting_group = QGroupBox("🎤 会議モード")
        meeting_layout = QVBoxLayout(meeting_group)

        # 会議タイトル
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("会議名:"))
        self.meeting_title_input = QLineEdit()
        self.meeting_title_input.setPlaceholderText("例：新規店舗開発会議")
        title_layout.addWidget(self.meeting_title_input)
        meeting_layout.addLayout(title_layout)

        # 録音ボタン
        rec_layout = QHBoxLayout()
        self.start_recording_btn = QPushButton("🔴 録音開始")
        self.start_recording_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; padding: 10px; font-size: 14px; }"
            "QPushButton:hover { background-color: #c0392b; }"
        )
        self.start_recording_btn.clicked.connect(self.start_meeting_recording)
        rec_layout.addWidget(self.start_recording_btn)

        self.stop_recording_btn = QPushButton("⏹ 録音停止")
        self.stop_recording_btn.setStyleSheet(
            "QPushButton { background-color: #95a5a6; color: white; padding: 10px; font-size: 14px; }"
            "QPushButton:hover { background-color: #7f8c8d; }"
        )
        self.stop_recording_btn.setEnabled(False)
        self.stop_recording_btn.clicked.connect(self.stop_meeting_recording)
        rec_layout.addWidget(self.stop_recording_btn)
        meeting_layout.addLayout(rec_layout)

        # 録音状態表示
        self.recording_status_label = QLabel("停止中")
        self.recording_status_label.setStyleSheet("color: gray;")
        meeting_layout.addWidget(self.recording_status_label)

        # 録音時間
        self.recording_time_label = QLabel("00:00:00")
        time_font = QFont()
        time_font.setPointSize(24)
        time_font.setBold(True)
        self.recording_time_label.setFont(time_font)
        self.recording_time_label.setAlignment(Qt.AlignCenter)
        meeting_layout.addWidget(self.recording_time_label)

        layout.addWidget(meeting_group)

        # === ファイル処理セクション ===
        file_group = QGroupBox("📁 ファイル処理")
        file_layout = QVBoxLayout(file_group)

        self.select_file_btn = QPushButton("📂 音声ファイルを選択")
        self.select_file_btn.clicked.connect(self.select_audio_file)
        file_layout.addWidget(self.select_file_btn)

        self.selected_file_label = QLabel("選択されたファイル: なし")
        self.selected_file_label.setWordWrap(True)
        file_layout.addWidget(self.selected_file_label)

        self.transcribe_btn = QPushButton("📝 書き起こし実行")
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.clicked.connect(self.start_transcription)
        file_layout.addWidget(self.transcribe_btn)

        layout.addWidget(file_group)

        # === 議事録生成セクション ===
        minutes_group = QGroupBox("📋 議事録生成")
        minutes_layout = QVBoxLayout(minutes_group)

        self.generate_minutes_btn = QPushButton("📄 議事録を生成")
        self.generate_minutes_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; padding: 10px; font-size: 14px; }"
            "QPushButton:hover { background-color: #229954; }"
        )
        self.generate_minutes_btn.setEnabled(False)
        self.generate_minutes_btn.clicked.connect(self.generate_minutes)
        minutes_layout.addWidget(self.generate_minutes_btn)

        # エクスポートボタン
        export_layout = QGridLayout()
        self.export_excel_btn = QPushButton("📊 Excel出力")
        self.export_excel_btn.setEnabled(False)
        self.export_excel_btn.clicked.connect(lambda: self.export_minutes("excel"))
        export_layout.addWidget(self.export_excel_btn, 0, 0)

        self.export_word_btn = QPushButton("📝 Word出力")
        self.export_word_btn.setEnabled(False)
        self.export_word_btn.clicked.connect(lambda: self.export_minutes("word"))
        export_layout.addWidget(self.export_word_btn, 0, 1)

        self.export_txt_btn = QPushButton("📄 テキスト出力")
        self.export_txt_btn.setEnabled(False)
        self.export_txt_btn.clicked.connect(lambda: self.export_minutes("text"))
        export_layout.addWidget(self.export_txt_btn, 1, 0)

        self.export_md_btn = QPushButton("📝 Markdown出力")
        self.export_md_btn.setEnabled(False)
        self.export_md_btn.clicked.connect(lambda: self.export_minutes("markdown"))
        export_layout.addWidget(self.export_md_btn, 1, 1)

        minutes_layout.addLayout(export_layout)
        layout.addWidget(minutes_group)

        # === 進捗表示セクション ===
        progress_group = QGroupBox("📊 進捗状況")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("待機中...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        self.time_remaining_label = QLabel("残り時間: --")
        self.time_remaining_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.time_remaining_label)

        layout.addWidget(progress_group)

        layout.addStretch()
        return panel

    def _create_preview_panel(self) -> QWidget:
        """プレビューパネルを作成"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # タブ切り替え風のボタン
        tab_layout = QHBoxLayout()
        self.preview_transcript_btn = QPushButton("📝 書き起こし")
        self.preview_transcript_btn.setCheckable(True)
        self.preview_transcript_btn.setChecked(True)
        self.preview_transcript_btn.clicked.connect(lambda: self.switch_preview("transcript"))
        tab_layout.addWidget(self.preview_transcript_btn)

        self.preview_minutes_btn = QPushButton("📋 議事録")
        self.preview_minutes_btn.setCheckable(True)
        self.preview_minutes_btn.clicked.connect(lambda: self.switch_preview("minutes"))
        tab_layout.addWidget(self.preview_minutes_btn)

        tab_layout.addStretch()
        layout.addLayout(tab_layout)

        # プレビューエリア
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("ここに結果が表示されます")
        layout.addWidget(self.preview_text, 1)

        return panel

    # === スロット ===

    def toggle_dark_mode(self, state):
        """ダークモードを切り替え"""
        if DARK_THEME_AVAILABLE:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if state == Qt.CheckState.Checked.value:
                DarkTheme.apply(app)
            else:
                app.setStyleSheet("")
                app.setPalette(app.style().standardPalette())

    def select_audio_file(self):
        """音声ファイルを選択"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "音声ファイルを選択",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg);;All Files (*)"
        )
        if file_path:
            self.selected_file = file_path
            self.selected_file_label.setText(f"選択されたファイル: {os.path.basename(file_path)}")
            self.transcribe_btn.setEnabled(True)

    def start_transcription(self):
        """書き起こしを開始"""
        if self.selected_file is None:
            QMessageBox.warning(self, "警告", "ファイルを選択してください")
            return

        self.progress_bar.setValue(0)
        self.progress_label.setText("書き起こしを開始...")

        # ワーカースレッドで実行
        self.worker = ProgressWorker(self._transcribe_task, self.selected_file)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_transcription_finished)
        self.worker.result_signal.connect(self.on_transcription_result)
        self.worker.start()

    def _get_engine(self):
        """キャッシュされたエンジンインスタンスを取得（モデル再ロード防止）"""
        if self._engine is None:
            from transcription_engine import TranscriptionEngine
            self._engine = TranscriptionEngine()
        if not self._engine.is_available():
            self._engine.load_model()
        return self._engine

    def _transcribe_task(self, file_path: str, progress_callback=None) -> Dict:
        """書き起こしタスク（バックグラウンド実行）"""
        engine = self._get_engine()

        if progress_callback:
            progress_callback(10, 100, "モデルを読み込み中...")

        result = engine.transcribe(file_path, return_timestamps=True)

        if progress_callback:
            progress_callback(100, 100, "書き起こし完了")

        return result

    def update_progress(self, current: int, total: int, message: str):
        """進捗を更新"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)

        # 残り時間推定
        if current > 0 and total > 0:
            # 簡易的な推定（実際には経過時間から計算）
            remaining_pct = 100 - percentage
            self.time_remaining_label.setText(f"進捗: {percentage}%")

    def on_transcription_result(self, result: Dict):
        """書き起こし結果を受信"""
        self.last_transcription = result

        # テキスト表示
        text = self._format_transcription(result)
        self.preview_text.setPlainText(text)

        # 議事録生成ボタンを有効化
        self.generate_minutes_btn.setEnabled(True)

    def on_transcription_finished(self, success: bool, message: str):
        """書き起こし完了時の処理"""
        if success:
            self.status_bar.showMessage("書き起こし完了", 5000)
        else:
            QMessageBox.critical(self, "エラー", f"書き起こしに失敗しました:\n{message}")
            self.progress_label.setText(f"エラー: {message}")

    def _format_transcription(self, result: Dict) -> str:
        """書き起こし結果を整形"""
        lines = []
        segments = result.get("segments", [])

        for segment in segments:
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "").strip()
            start = segment.get("start", 0)

            time_str = f"{int(start // 60):02d}:{int(start % 60):02d}"
            lines.append(f"[{time_str}] {speaker}: {text}")

        return "\n".join(lines)

    def generate_minutes(self):
        """議事録を生成"""
        if not self.last_transcription:
            QMessageBox.warning(self, "警告", "先に書き起こしを実行してください")
            return

        self.progress_bar.setValue(0)
        self.progress_label.setText("議事録を生成中...")

        segments = self.last_transcription.get("segments", [])
        title = self.meeting_title_input.text() or "会議"

        try:
            minutes = self.minutes_generator.generate(
                segments=segments,
                title=title,
            )
            self.last_minutes = minutes

            # 議事録を表示
            self.preview_text.setPlainText(minutes.get("text_format", ""))
            self.switch_preview("minutes")

            # エクスポートボタンを有効化
            self.export_excel_btn.setEnabled(True)
            self.export_word_btn.setEnabled(True)
            self.export_txt_btn.setEnabled(True)
            self.export_md_btn.setEnabled(True)

            self.progress_bar.setValue(100)
            self.progress_label.setText("議事録生成完了")
            self.status_bar.showMessage("議事録を生成しました", 5000)

        except Exception as e:
            logger.error(f"Minutes generation failed: {e}")
            QMessageBox.critical(self, "エラー", f"議事録生成に失敗しました:\n{str(e)}")

    def export_minutes(self, format_type: str):
        """議事録をエクスポート"""
        if not self.last_minutes:
            QMessageBox.warning(self, "警告", "議事録がありません")
            return

        # 出力先を選択
        filters = {
            "excel": "Excel Files (*.xlsx)",
            "word": "Word Files (*.docx)",
            "text": "Text Files (*.txt)",
            "markdown": "Markdown Files (*.md)",
        }
        ext = {"excel": ".xlsx", "word": ".docx", "text": ".txt", "markdown": ".md"}

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "議事録を保存",
            f"議事録{ext.get(format_type, '.txt')}",
            filters.get(format_type, "All Files (*)")
        )

        if not file_path:
            return

        try:
            if format_type == "excel":
                exporter = get_excel_exporter()
                success = exporter.export_meeting_minutes(self.last_minutes, file_path)
            elif format_type == "word":
                exporter = get_word_exporter()
                success = exporter.export_meeting_minutes(self.last_minutes, file_path)
            elif format_type == "text":
                content = self.last_minutes.get("text_format", "")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                success = True
            elif format_type == "markdown":
                content = self.last_minutes.get("markdown_format", "")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                success = True
            else:
                success = False

            if success:
                QMessageBox.information(self, "成功", f"議事録を保存しました:\n{file_path}")
                self.status_bar.showMessage(f"保存: {os.path.basename(file_path)}", 5000)
            else:
                QMessageBox.warning(self, "失敗", "ファイルの保存に失敗しました")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(self, "エラー", f"エクスポートに失敗しました:\n{str(e)}")

    def switch_preview(self, mode: str):
        """プレビューを切り替え"""
        if mode == "transcript":
            self.preview_transcript_btn.setChecked(True)
            self.preview_minutes_btn.setChecked(False)
            if self.last_transcription:
                text = self._format_transcription(self.last_transcription)
                self.preview_text.setPlainText(text)
        else:
            self.preview_transcript_btn.setChecked(False)
            self.preview_minutes_btn.setChecked(True)
            if self.last_minutes:
                self.preview_text.setPlainText(self.last_minutes.get("text_format", ""))

    def start_meeting_recording(self):
        """会議録音を開始"""
        title = self.meeting_title_input.text() or "会議"
        session_id = self.meeting_recorder.start_recording(title=title)

        if session_id:
            self.is_recording = True
            self.start_recording_btn.setEnabled(False)
            self.stop_recording_btn.setEnabled(True)
            self.recording_status_label.setText("🔴 録音中")
            self.recording_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.status_bar.showMessage(f"録音開始: {session_id}")

    def stop_meeting_recording(self):
        """会議録音を停止"""
        session = self.meeting_recorder.stop_recording()

        self.is_recording = False
        self.start_recording_btn.setEnabled(True)
        self.stop_recording_btn.setEnabled(False)
        self.recording_status_label.setText("停止中")
        self.recording_status_label.setStyleSheet("color: gray;")
        self.recording_time_label.setText("00:00:00")

        if session:
            self.status_bar.showMessage(f"録音停止: {len(session.segments)} セグメント", 5000)
            QMessageBox.information(
                self,
                "録音完了",
                f"会議録音が完了しました\nセグメント数: {len(session.segments)}"
            )

    def update_recording_status(self):
        """録音状態を更新"""
        if self.is_recording:
            status = self.meeting_recorder.get_current_status()
            if status.get("recording"):
                total_seconds = int(status.get("total_duration", 0))
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                self.recording_time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
