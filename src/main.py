"""
KotobaTranscriber - メインアプリケーション
日本語音声文字起こしアプリケーション
"""

import sys
import os
import shutil
from datetime import datetime
from typing import Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QFileDialog, QLabel, QProgressBar, QMessageBox,
    QCheckBox, QGroupBox, QListWidget, QListWidgetItem, QSystemTrayIcon, QMenu, QAction,
    QSpinBox, QFrame, QTabWidget, QComboBox, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QThreadPool, QRunnable, pyqtSlot
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from transcription_engine import TranscriptionEngine
from text_formatter import TextFormatter
from speaker_diarization_free import FreeSpeakerDiarizer
from llm_corrector_standalone import SimpleLLMCorrector, StandaloneLLMCorrector
from folder_monitor import FolderMonitor
from realtime_transcriber import RealtimeTranscriber
from realtime_audio_capture import RealtimeAudioCapture
from simple_vad import AdaptiveVAD
from faster_whisper_engine import FasterWhisperEngine
from app_settings import AppSettings

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealtimeTranscriberFactory:
    """
    RealtimeTranscriberインスタンスを生成するファクトリクラス

    依存性注入パターンを使用し、具体的な実装をカプセル化する
    """

    @staticmethod
    def create(model_size: str = "base",
               device: str = "auto",
               device_index: Optional[int] = None,
               enable_vad: bool = True,
               vad_threshold: float = 0.01) -> RealtimeTranscriber:
        """
        RealtimeTranscriberインスタンスを作成

        Args:
            model_size: Whisperモデルサイズ ("tiny", "base", "small", "medium")
            device: 実行デバイス ("cpu", "cuda", "auto")
            device_index: マイクデバイスインデックス（Noneで自動選択）
            enable_vad: VAD有効化フラグ
            vad_threshold: VAD閾値（0.005〜0.050）

        Returns:
            RealtimeTranscriber: 設定済みのRealtimeTranscriberインスタンス
        """
        # 音声キャプチャコンポーネントを作成
        audio_capture = RealtimeAudioCapture(
            device_index=device_index,
            sample_rate=16000,
            buffer_duration=3.0
        )

        # 文字起こしエンジンを作成
        whisper_engine = FasterWhisperEngine(
            model_size=model_size,
            device=device,
            language="ja"
        )

        # VADコンポーネントを作成（オプション）
        vad = None
        if enable_vad:
            vad = AdaptiveVAD(
                initial_threshold=vad_threshold,
                min_silence_duration=1.0,
                sample_rate=16000
            )

        # RealtimeTranscriberを依存性注入で作成
        transcriber = RealtimeTranscriber(
            audio_capture=audio_capture,
            whisper_engine=whisper_engine,
            vad=vad
        )

        logger.info(
            f"RealtimeTranscriber created via factory: "
            f"model={model_size}, device={device}, vad={enable_vad}"
        )

        return transcriber


class BatchTranscriptionWorker(QThread):
    """複数ファイルの並列文字起こし処理"""
    progress = pyqtSignal(int, int, str)  # (完了数, 総数, ファイル名)
    file_finished = pyqtSignal(str, str, bool)  # (ファイルパス, 結果テキスト, 成功/失敗)
    all_finished = pyqtSignal(int, int)  # (成功数, 失敗数)
    error = pyqtSignal(str)

    def __init__(self, audio_paths: list, enable_diarization: bool = False,
                 max_workers: int = 3, formatter=None, simple_corrector=None,
                 use_llm_correction: bool = False):
        super().__init__()
        self.audio_paths = audio_paths
        self.enable_diarization = enable_diarization
        self.max_workers = max_workers
        self.formatter = formatter
        self.simple_corrector = simple_corrector
        self.use_llm_correction = use_llm_correction
        self.completed = 0
        self.success_count = 0
        self.failed_count = 0
        self.lock = threading.Lock()

    def process_single_file(self, audio_path: str):
        """単一ファイルを処理"""
        try:
            logger.info(f"Processing: {audio_path}")

            # 文字起こしエンジン（各スレッドで独立）
            engine = TranscriptionEngine()
            engine.load_model()

            # 文字起こし実行
            result = engine.transcribe(audio_path, return_timestamps=True)
            text = result.get("text", "")

            # 話者分離（オプション）
            if self.enable_diarization:
                try:
                    diarizer = FreeSpeakerDiarizer()
                    diar_segments = diarizer.diarize(audio_path)
                    trans_segments = result.get("chunks", [])
                    text = diarizer.format_with_speakers(text, diar_segments, trans_segments)
                except Exception as e:
                    logger.warning(f"Speaker diarization failed for {audio_path}: {e}")

            # テキスト整形
            if self.formatter:
                formatted_text = self.formatter.format_all(
                    text,
                    remove_fillers=True,
                    add_punctuation=not self.use_llm_correction,
                    format_paragraphs=True,
                    clean_repeated=True
                )
            else:
                formatted_text = text

            # AI補正
            if self.use_llm_correction and self.simple_corrector:
                formatted_text = self.simple_corrector.correct_text(formatted_text)

            # 自動保存
            base_name = os.path.splitext(audio_path)[0]
            output_file = f"{base_name}_文字起こし.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(formatted_text)

            logger.info(f"Completed: {audio_path} -> {output_file}")
            return audio_path, formatted_text, True

        except Exception as e:
            error_msg = f"Error processing {audio_path}: {str(e)}"
            logger.error(error_msg)
            return audio_path, error_msg, False

    def run(self):
        """並列処理実行"""
        try:
            total = len(self.audio_paths)

            # ThreadPoolExecutorで並列処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 全ファイルを投入
                future_to_path = {
                    executor.submit(self.process_single_file, path): path
                    for path in self.audio_paths
                }

                # 完了したものから処理
                for future in as_completed(future_to_path):
                    audio_path, result_text, success = future.result()

                    with self.lock:
                        self.completed += 1
                        if success:
                            self.success_count += 1
                        else:
                            self.failed_count += 1

                    # 進捗通知
                    filename = os.path.basename(audio_path)
                    self.progress.emit(self.completed, total, filename)
                    self.file_finished.emit(audio_path, result_text, success)

            # 全完了通知
            self.all_finished.emit(self.success_count, self.failed_count)
            logger.info(f"Batch processing completed: {self.success_count} success, {self.failed_count} failed")

        except Exception as e:
            error_msg = f"Batch processing error: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)


class TranscriptionWorker(QThread):
    """文字起こし処理を別スレッドで実行"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, audio_path: str, enable_diarization: bool = False):
        super().__init__()
        self.audio_path = audio_path
        self.engine = TranscriptionEngine()
        self.enable_diarization = enable_diarization
        self.diarizer = None

        if enable_diarization:
            try:
                from speaker_diarization_free import FreeSpeakerDiarizer
                self.diarizer = FreeSpeakerDiarizer()
            except Exception as e:
                logger.warning(f"Failed to initialize speaker diarization: {e}")

    def run(self):
        """文字起こし実行"""
        try:
            self.progress.emit(20)
            logger.info(f"Starting transcription for: {self.audio_path}")

            # モデルロード
            self.engine.load_model()
            self.progress.emit(40)

            # 文字起こし実行
            result = self.engine.transcribe(self.audio_path, return_timestamps=True)
            self.progress.emit(70)

            # 結果取得
            text = result.get("text", "")

            # 話者分離が有効な場合
            if self.enable_diarization and self.diarizer:
                try:
                    logger.info("Running speaker diarization...")
                    self.progress.emit(75)

                    # 話者分離実行
                    diar_segments = self.diarizer.diarize(self.audio_path)
                    self.progress.emit(85)

                    # タイムスタンプ付き文字起こしセグメント
                    trans_segments = result.get("chunks", [])

                    # 話者情報を追加
                    text = self.diarizer.format_with_speakers(
                        text,
                        diar_segments,
                        trans_segments if trans_segments else None
                    )

                    # 統計情報をログに出力
                    stats = self.diarizer.get_speaker_statistics(diar_segments)
                    logger.info(f"Speaker statistics: {stats}")

                except Exception as e:
                    logger.warning(f"Speaker diarization failed: {e}")
                    # 話者分離に失敗しても文字起こし結果は返す

            self.progress.emit(100)
            self.finished.emit(text)
            logger.info("Transcription completed successfully")

        except Exception as e:
            error_msg = f"エラーが発生しました: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)


class MainWindow(QMainWindow):
    """メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.batch_worker = None
        self.formatter = TextFormatter()
        self.diarizer = None  # 話者分離は必要時に初期化
        self.simple_corrector = SimpleLLMCorrector()  # 軽量補正（常に利用可能）
        self.advanced_corrector = None  # 高度な補正（オプション）
        self.batch_files = []  # バッチ処理用ファイルリスト

        # フォルダ監視関連
        self.folder_monitor = None  # フォルダ監視
        self.monitored_folders = []  # 複数フォルダ監視リスト
        self.monitored_folder = None  # 現在の主監視フォルダ
        self.monitor_check_interval = 10  # 監視間隔（秒）
        self.processing_files = set()  # 処理中ファイルのセット（重複防止）

        # 統計情報
        self.total_processed = 0  # 総処理件数
        self.total_failed = 0  # 総失敗件数
        self.session_start_time = None  # セッション開始時刻

        # 自動移動設定
        self.auto_move_completed = False  # 完了後自動移動
        self.completed_folder = None  # 完了ファイル移動先

        # リアルタイム文字起こし
        self.realtime_transcriber = None  # RealtimeTranscriberインスタンス

        # 設定管理
        self.settings = AppSettings()
        self.settings.load()  # 設定を読み込む

        self.init_ui()
        self.init_tray_icon()  # システムトレイアイコン初期化
        self.check_startup_status()  # Windows起動設定状態をチェック
        # 設定を復元（UIコンポーネント初期化後）
        self.load_ui_settings()

    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("KotobaTranscriber - 日本語音声文字起こし")
        self.setGeometry(100, 100, 900, 700)

        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # タイトル
        title_label = QLabel("KotobaTranscriber")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # タブウィジェット作成
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # ファイル処理タブ
        file_tab = QWidget()
        layout = QVBoxLayout(file_tab)
        self.tab_widget.addTab(file_tab, "ファイル処理")

        # リアルタイム文字起こしタブ
        realtime_tab = self.create_realtime_tab()
        self.tab_widget.addTab(realtime_tab, "🎤 リアルタイム")

        # ファイル選択ボタン
        file_button_layout = QHBoxLayout()

        self.file_button = QPushButton("単一ファイル選択")
        self.file_button.setStyleSheet("font-size: 14px; padding: 10px;")
        self.file_button.clicked.connect(self.select_file)
        file_button_layout.addWidget(self.file_button)

        self.batch_file_button = QPushButton("複数ファイル選択（バッチ処理）")
        self.batch_file_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #2196F3; color: white;")
        self.batch_file_button.clicked.connect(self.select_batch_files)
        file_button_layout.addWidget(self.batch_file_button)

        layout.addLayout(file_button_layout)

        # フォルダ監視ボタン
        folder_monitor_layout = QHBoxLayout()

        self.monitor_folder_button = QPushButton("フォルダ監視開始")
        self.monitor_folder_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #FF9800; color: white;")
        self.monitor_folder_button.clicked.connect(self.toggle_folder_monitor)
        folder_monitor_layout.addWidget(self.monitor_folder_button)

        self.select_monitor_folder_button = QPushButton("監視フォルダ選択")
        self.select_monitor_folder_button.setStyleSheet("font-size: 12px; padding: 8px;")
        self.select_monitor_folder_button.clicked.connect(self.select_monitor_folder)
        folder_monitor_layout.addWidget(self.select_monitor_folder_button)

        layout.addLayout(folder_monitor_layout)

        # 監視フォルダ表示
        self.monitor_folder_label = QLabel("監視フォルダ: 未設定")
        self.monitor_folder_label.setStyleSheet("margin: 5px; font-size: 11px; color: #666;")
        layout.addWidget(self.monitor_folder_label)

        # 統計情報表示
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("background-color: #f5f5f5; border-radius: 5px; padding: 10px; margin: 5px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(10, 5, 10, 5)

        self.stats_label = QLabel("処理済み: 0件 | 失敗: 0件 | 処理中: 0件")
        self.stats_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #333;")
        stats_layout.addWidget(self.stats_label)

        layout.addWidget(stats_frame)

        # 選択ファイル表示
        self.file_label = QLabel("ファイル: 未選択")
        self.file_label.setStyleSheet("margin: 5px;")
        layout.addWidget(self.file_label)

        # バッチファイルリスト
        self.batch_file_list = QListWidget()
        self.batch_file_list.setMaximumHeight(100)
        self.batch_file_list.setVisible(False)
        layout.addWidget(self.batch_file_list)

        # バッチリストクリアボタン
        self.clear_batch_button = QPushButton("リストをクリア")
        self.clear_batch_button.setStyleSheet("font-size: 12px; padding: 5px;")
        self.clear_batch_button.clicked.connect(self.clear_batch_list)
        self.clear_batch_button.setVisible(False)
        layout.addWidget(self.clear_batch_button)

        # テキスト整形オプション
        format_group = QGroupBox("テキスト整形オプション")
        format_layout = QVBoxLayout()

        self.remove_fillers_check = QCheckBox("フィラー語を削除 (あー、えー、その、など)")
        self.remove_fillers_check.setChecked(True)
        format_layout.addWidget(self.remove_fillers_check)

        self.add_punctuation_check = QCheckBox("句読点を整形")
        self.add_punctuation_check.setChecked(True)
        format_layout.addWidget(self.add_punctuation_check)

        self.format_paragraphs_check = QCheckBox("段落を整形")
        self.format_paragraphs_check.setChecked(True)
        format_layout.addWidget(self.format_paragraphs_check)

        self.enable_diarization_check = QCheckBox("話者分離を有効化（完全無料）")
        self.enable_diarization_check.setChecked(False)
        self.enable_diarization_check.setToolTip("複数の話者を識別します。speechbrainまたはresemblyzerを使用。完全無料、トークン不要。")
        format_layout.addWidget(self.enable_diarization_check)

        self.enable_llm_correction_check = QCheckBox("AI文章補正を有効化（句読点も賢く処理）")
        self.enable_llm_correction_check.setChecked(False)
        self.enable_llm_correction_check.setToolTip("インテリジェントなAI補正で文章と句読点を自然な日本語に。モデル不要で即座に動作します。")
        format_layout.addWidget(self.enable_llm_correction_check)

        self.use_advanced_llm_check = QCheckBox("高度なAI補正を使用 (初回: 310MBダウンロード)")
        self.use_advanced_llm_check.setChecked(False)
        self.use_advanced_llm_check.setToolTip("transformersベースの高度な補正。初回のみrinna/japanese-gpt2-mediumをダウンロードします。")
        format_layout.addWidget(self.use_advanced_llm_check)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # 高度な設定グループ
        advanced_group = QGroupBox("高度な設定")
        advanced_layout = QVBoxLayout()

        # 監視間隔設定
        interval_layout = QHBoxLayout()
        interval_label = QLabel("監視間隔:")
        interval_layout.addWidget(interval_label)

        self.monitor_interval_spinbox = QSpinBox()
        self.monitor_interval_spinbox.setRange(5, 60)
        self.monitor_interval_spinbox.setValue(10)
        self.monitor_interval_spinbox.setSuffix(" 秒")
        self.monitor_interval_spinbox.setToolTip("フォルダ監視のチェック間隔（5〜60秒）")
        self.monitor_interval_spinbox.valueChanged.connect(self.on_monitor_interval_changed)
        interval_layout.addWidget(self.monitor_interval_spinbox)
        interval_layout.addStretch()

        advanced_layout.addLayout(interval_layout)

        # Windows起動時に自動起動
        self.startup_check = QCheckBox("Windows起動時に自動起動")
        self.startup_check.setChecked(False)
        self.startup_check.setToolTip("Windowsスタートアップに登録します")
        self.startup_check.clicked.connect(self.on_startup_toggled)
        advanced_layout.addWidget(self.startup_check)

        # 完了ファイル自動移動
        self.auto_move_check = QCheckBox("完了ファイルを自動移動")
        self.auto_move_check.setChecked(False)
        self.auto_move_check.setToolTip("文字起こし完了後、ファイルを指定フォルダに移動します")
        self.auto_move_check.clicked.connect(self.on_auto_move_toggled)
        advanced_layout.addWidget(self.auto_move_check)

        # 移動先フォルダ選択
        move_folder_layout = QHBoxLayout()
        self.select_completed_folder_button = QPushButton("移動先フォルダ選択")
        self.select_completed_folder_button.setStyleSheet("font-size: 11px; padding: 5px;")
        self.select_completed_folder_button.clicked.connect(self.select_completed_folder)
        self.select_completed_folder_button.setEnabled(False)
        move_folder_layout.addWidget(self.select_completed_folder_button)

        self.completed_folder_label = QLabel("未設定")
        self.completed_folder_label.setStyleSheet("font-size: 11px; color: #666;")
        move_folder_layout.addWidget(self.completed_folder_label)
        move_folder_layout.addStretch()

        advanced_layout.addLayout(move_folder_layout)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # 文字起こしボタン
        self.transcribe_button = QPushButton("文字起こし開始")
        self.transcribe_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #4CAF50; color: white;")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.start_transcription)
        layout.addWidget(self.transcribe_button)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 結果表示エリア
        result_label = QLabel("文字起こし結果:")
        result_label.setStyleSheet("font-size: 14px; margin-top: 10px;")
        layout.addWidget(result_label)

        self.result_text = QTextEdit()
        self.result_text.setPlaceholderText("文字起こし結果がここに表示されます...")
        self.result_text.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.result_text)

        # 保存ボタン
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("テキストを保存")
        self.save_button.setStyleSheet("font-size: 12px; padding: 8px;")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_text)
        button_layout.addWidget(self.save_button)

        self.clear_button = QPushButton("クリア")
        self.clear_button.setStyleSheet("font-size: 12px; padding: 8px;")
        self.clear_button.clicked.connect(self.clear_results)
        button_layout.addWidget(self.clear_button)

        layout.addLayout(button_layout)

        # ステータスバー
        self.statusBar().showMessage("準備完了")

        logger.info("UI initialized")

    def select_file(self):
        """音声ファイル選択"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "音声ファイルを選択",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma *.opus *.amr *.3gp *.webm *.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )

        if file_path:
            self.selected_file = file_path
            filename = os.path.basename(file_path)
            self.file_label.setText(f"ファイル: {filename}")
            self.transcribe_button.setEnabled(True)
            self.statusBar().showMessage(f"ファイル選択: {filename}")
            logger.info(f"File selected: {file_path}")

    def start_transcription(self):
        """文字起こし開始（バッチ/単一を自動判定）"""
        # バッチ処理モードかチェック
        if self.batch_files:
            self.start_batch_transcription()
            return

        # 単一ファイル処理
        if not hasattr(self, 'selected_file'):
            QMessageBox.warning(self, "警告", "音声ファイルを選択してください")
            return

        # UI状態変更
        self.transcribe_button.setEnabled(False)
        self.file_button.setEnabled(False)
        self.batch_file_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("文字起こし中...")

        # ワーカースレッド開始
        enable_diarization = self.enable_diarization_check.isChecked()
        self.worker = TranscriptionWorker(self.selected_file, enable_diarization=enable_diarization)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.transcription_finished)
        self.worker.error.connect(self.transcription_error)
        self.worker.start()

        logger.info("Transcription started")

    def update_progress(self, value):
        """進捗更新"""
        self.progress_bar.setValue(value)

    def transcription_finished(self, text):
        """文字起こし完了"""
        # AI補正が有効な場合、句読点もAI補正で処理
        use_llm_for_punctuation = self.enable_llm_correction_check.isChecked()

        # テキスト整形オプションを適用
        formatted_text = self.formatter.format_all(
            text,
            remove_fillers=self.remove_fillers_check.isChecked(),
            add_punctuation=self.add_punctuation_check.isChecked() and not use_llm_for_punctuation,  # AI補正時は無効化
            format_paragraphs=self.format_paragraphs_check.isChecked(),
            clean_repeated=True
        )

        # AI補正を適用（オプション）
        if self.enable_llm_correction_check.isChecked():
            try:
                # 高度な補正を使用する場合
                if self.use_advanced_llm_check.isChecked():
                    logger.info("Applying advanced LLM correction...")

                    # 高度な補正器を初期化（初回のみ）
                    if self.advanced_corrector is None:
                        self.statusBar().showMessage("AIモデルをダウンロード中... (初回のみ310MB、数分かかります)")
                        QApplication.processEvents()  # UI更新

                        try:
                            self.advanced_corrector = StandaloneLLMCorrector()
                            self.advanced_corrector.load_model()
                        except Exception as e:
                            logger.error(f"Failed to load advanced corrector: {e}")
                            QMessageBox.warning(
                                self,
                                "警告",
                                f"高度なAI補正のロードに失敗しました: {str(e)}\n軽量版のAI補正を使用します。"
                            )
                            # 軽量版にフォールバック
                            self.statusBar().showMessage("AIで文章を補正中（軽量版）...")
                            formatted_text = self.simple_corrector.correct_text(formatted_text)
                            logger.info("Fallback to simple LLM correction completed")
                            # 早期リターン
                            self.result_text.setPlainText(formatted_text)
                            self.save_button.setEnabled(True)
                            self.transcribe_button.setEnabled(True)
                            self.file_button.setEnabled(True)
                            self.progress_bar.setVisible(False)
                            self.auto_save_text(formatted_text)
                            self.statusBar().showMessage("文字起こし完了!")
                            QMessageBox.information(self, "完了", "文字起こしが完了しました")
                            logger.info("Transcription finished successfully")
                            return

                    self.statusBar().showMessage("高度なAIで文章を補正中...")
                    QApplication.processEvents()  # UI更新
                    formatted_text = self.advanced_corrector.correct_text(formatted_text)
                    logger.info("Advanced LLM correction completed")

                # 軽量補正を使用する場合（デフォルト）
                else:
                    self.statusBar().showMessage("AIで文章を補正中...")
                    logger.info("Applying simple LLM correction...")
                    formatted_text = self.simple_corrector.correct_text(formatted_text)
                    logger.info("Simple LLM correction completed")

            except Exception as e:
                logger.error(f"LLM correction failed: {e}")
                QMessageBox.warning(
                    self,
                    "警告",
                    f"AI補正に失敗しました: {str(e)}\n元のテキストを使用します。"
                )

        self.result_text.setPlainText(formatted_text)
        self.save_button.setEnabled(True)
        self.transcribe_button.setEnabled(True)
        self.file_button.setEnabled(True)
        self.batch_file_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        # 自動保存
        self.auto_save_text(formatted_text)

        self.statusBar().showMessage("文字起こし完了!")
        QMessageBox.information(self, "完了", "文字起こしが完了しました")
        logger.info("Transcription finished successfully")

    def transcription_error(self, error_msg):
        """エラー処理"""
        self.transcribe_button.setEnabled(True)
        self.file_button.setEnabled(True)
        self.batch_file_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("エラー発生")
        QMessageBox.critical(self, "エラー", error_msg)
        logger.error(f"Transcription error: {error_msg}")

    def auto_save_text(self, text: str):
        """文字起こし結果を自動保存"""
        try:
            # 元の音声ファイル名から出力ファイル名を生成
            if hasattr(self, 'selected_file'):
                base_name = os.path.splitext(self.selected_file)[0]
                output_file = f"{base_name}_文字起こし.txt"

                # ファイルに保存
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)

                logger.info(f"Auto-saved transcription to: {output_file}")
                self.statusBar().showMessage(f"自動保存: {os.path.basename(output_file)}")
        except Exception as e:
            logger.error(f"Auto-save failed: {e}")
            # 自動保存失敗はエラーダイアログを表示しない（ユーザー体験を損なわないため）

    def save_text(self):
        """テキスト保存（手動保存）"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "テキストを保存",
            "",
            "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.result_text.toPlainText())
                self.statusBar().showMessage(f"保存完了: {os.path.basename(file_path)}")
                QMessageBox.information(self, "保存完了", "テキストを保存しました")
                logger.info(f"Text saved to: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"保存に失敗しました: {str(e)}")
                logger.error(f"Failed to save text: {e}")

    def clear_results(self):
        """結果クリア"""
        self.result_text.clear()
        self.file_label.setText("ファイル: 未選択")
        self.transcribe_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.statusBar().showMessage("クリアしました")
        if hasattr(self, 'selected_file'):
            delattr(self, 'selected_file')
        logger.info("Results cleared")

    def select_batch_files(self):
        """複数ファイル選択"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "複数の音声ファイルを選択",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.wma *.opus *.amr *.3gp *.webm *.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )

        if file_paths:
            self.batch_files = file_paths
            self.batch_file_list.clear()
            for path in file_paths:
                filename = os.path.basename(path)
                self.batch_file_list.addItem(filename)

            self.batch_file_list.setVisible(True)
            self.clear_batch_button.setVisible(True)
            self.file_label.setText(f"バッチファイル: {len(file_paths)}個選択")
            self.transcribe_button.setEnabled(True)
            self.transcribe_button.setText(f"バッチ処理開始 ({len(file_paths)}ファイル)")
            self.statusBar().showMessage(f"{len(file_paths)}個のファイルを選択しました")
            logger.info(f"Batch files selected: {len(file_paths)} files")

    def clear_batch_list(self):
        """バッチリストクリア"""
        self.batch_files = []
        self.batch_file_list.clear()
        self.batch_file_list.setVisible(False)
        self.clear_batch_button.setVisible(False)
        self.file_label.setText("ファイル: 未選択")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.setText("文字起こし開始")
        self.statusBar().showMessage("バッチリストをクリアしました")
        logger.info("Batch list cleared")

    def start_batch_transcription(self):
        """バッチ処理開始"""
        if not self.batch_files:
            QMessageBox.warning(self, "警告", "ファイルが選択されていません")
            return

        # UI状態変更
        self.transcribe_button.setEnabled(False)
        self.file_button.setEnabled(False)
        self.batch_file_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage(f"バッチ処理中... (0/{len(self.batch_files)})")

        # バッチワーカー開始
        enable_diarization = self.enable_diarization_check.isChecked()
        use_llm = self.enable_llm_correction_check.isChecked()

        self.batch_worker = BatchTranscriptionWorker(
            self.batch_files,
            enable_diarization=enable_diarization,
            max_workers=3,  # 並列処理数（CPU/GPUに応じて調整可能）
            formatter=self.formatter,
            simple_corrector=self.simple_corrector if use_llm else None,
            use_llm_correction=use_llm
        )

        self.batch_worker.progress.connect(self.update_batch_progress)
        self.batch_worker.file_finished.connect(self.batch_file_finished)
        self.batch_worker.all_finished.connect(self.batch_all_finished)
        self.batch_worker.error.connect(self.transcription_error)
        self.batch_worker.start()

        logger.info(f"Batch processing started: {len(self.batch_files)} files")

    def update_batch_progress(self, completed: int, total: int, filename: str):
        """バッチ処理進捗更新"""
        progress_percent = int((completed / total) * 100)
        self.progress_bar.setValue(progress_percent)
        self.statusBar().showMessage(f"処理中: {filename} ({completed}/{total})")

    def batch_file_finished(self, file_path: str, result: str, success: bool):
        """個別ファイル完了"""
        filename = os.path.basename(file_path)
        if success:
            logger.info(f"Batch file completed: {filename}")
        else:
            logger.error(f"Batch file failed: {filename} - {result}")

    def batch_all_finished(self, success_count: int, failed_count: int):
        """バッチ処理全完了"""
        total = success_count + failed_count

        # UI状態復元
        self.transcribe_button.setEnabled(True)
        self.file_button.setEnabled(True)
        self.batch_file_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        # 結果表示
        result_message = f"バッチ処理完了!\n\n"
        result_message += f"総ファイル数: {total}\n"
        result_message += f"成功: {success_count}\n"
        result_message += f"失敗: {failed_count}\n\n"
        result_message += f"各ファイルは元のファイルと同じフォルダに保存されています。"

        self.result_text.setPlainText(result_message)
        self.save_button.setEnabled(False)  # バッチ処理では手動保存不要

        self.statusBar().showMessage(f"バッチ処理完了: {success_count}成功, {failed_count}失敗")
        QMessageBox.information(self, "完了", result_message)
        logger.info(f"Batch processing finished: {success_count} success, {failed_count} failed")

    def init_tray_icon(self):
        """システムトレイアイコン初期化"""
        # トレイアイコン作成
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_tray_icon())
        self.tray_icon.setToolTip("KotobaTranscriber - 日本語音声文字起こし")

        # トレイメニュー作成
        tray_menu = QMenu()

        show_action = QAction("表示", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        hide_action = QAction("非表示", self)
        hide_action.triggered.connect(self.hide_window)
        tray_menu.addAction(hide_action)

        tray_menu.addSeparator()

        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # トレイアイコンクリックでウィンドウ表示/非表示
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        # トレイアイコン表示
        self.tray_icon.show()
        logger.info("System tray icon initialized")

    def create_tray_icon(self):
        """トレイアイコン画像作成"""
        # シンプルな円形アイコン
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景円（青）
        painter.setBrush(QColor(33, 150, 243))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)

        # 白い「K」マーク（KotobaTranscriberの頭文字）
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(painter.font())
        font = painter.font()
        font.setPointSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "K")

        painter.end()

        return QIcon(pixmap)

    def on_tray_icon_activated(self, reason):
        """トレイアイコンクリック時の処理"""
        if reason == QSystemTrayIcon.Trigger:  # 左クリック
            if self.isVisible():
                self.hide_window()
            else:
                self.show_window()

    def show_window(self):
        """ウィンドウを表示"""
        self.show()
        self.activateWindow()
        logger.info("Window shown")

    def hide_window(self):
        """ウィンドウを非表示"""
        self.hide()
        logger.info("Window hidden to tray")

    def quit_application(self):
        """アプリケーション終了"""
        # 設定を保存
        self.save_ui_settings()

        # リアルタイム文字起こし停止
        if self.realtime_transcriber and self.realtime_transcriber.isRunning():
            self.realtime_transcriber.cleanup()
            self.realtime_transcriber.wait()

        # フォルダ監視停止
        if self.folder_monitor and self.folder_monitor.isRunning():
            self.folder_monitor.stop()
            self.folder_monitor.wait()

        # トレイアイコン非表示
        self.tray_icon.hide()

        logger.info("Application quitting")
        QApplication.quit()

    def closeEvent(self, event):
        """ウィンドウを閉じる時の処理（トレイに最小化）"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "KotobaTranscriber",
            "アプリはトレイで実行中です。完全に終了するには右クリックメニューから「終了」を選択してください。",
            QSystemTrayIcon.Information,
            2000
        )
        logger.info("Window closed to tray")

    def select_monitor_folder(self):
        """監視フォルダ選択"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "監視するフォルダを選択",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder_path:
            self.monitored_folder = folder_path
            folder_name = os.path.basename(folder_path)
            self.monitor_folder_label.setText(f"監視フォルダ: {folder_name}")
            self.statusBar().showMessage(f"監視フォルダ設定: {folder_name}")
            logger.info(f"Monitor folder selected: {folder_path}")

    def toggle_folder_monitor(self):
        """フォルダ監視開始/停止"""
        # 監視中の場合は停止
        if self.folder_monitor and self.folder_monitor.isRunning():
            self.folder_monitor.stop()
            self.folder_monitor.wait()
            self.folder_monitor = None

            self.monitor_folder_button.setText("フォルダ監視開始")
            self.monitor_folder_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #FF9800; color: white;")
            self.statusBar().showMessage("フォルダ監視を停止しました")
            logger.info("Folder monitoring stopped")
            return

        # 監視フォルダが未設定の場合
        if not self.monitored_folder:
            QMessageBox.warning(self, "警告", "監視フォルダを選択してください")
            return

        # 監視開始
        try:
            self.folder_monitor = FolderMonitor(
                self.monitored_folder,
                check_interval=10  # 10秒ごとにチェック
            )

            # シグナル接続
            self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
            self.folder_monitor.status_update.connect(self.on_monitor_status)

            # 監視スレッド開始
            self.folder_monitor.start()

            self.monitor_folder_button.setText("フォルダ監視停止")
            self.monitor_folder_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #F44336; color: white;")
            self.statusBar().showMessage(f"フォルダ監視開始: {os.path.basename(self.monitored_folder)}")
            logger.info(f"Folder monitoring started: {self.monitored_folder}")

            # トレイ通知
            self.tray_icon.showMessage(
                "フォルダ監視開始",
                f"{os.path.basename(self.monitored_folder)} を監視中...",
                QSystemTrayIcon.Information,
                2000
            )

        except Exception as e:
            error_msg = f"フォルダ監視の開始に失敗しました: {str(e)}"
            QMessageBox.critical(self, "エラー", error_msg)
            logger.error(error_msg)

    def on_monitor_new_files(self, files: list):
        """監視フォルダで新規ファイル検出時の処理"""
        logger.info(f"New files detected: {len(files)} files")

        # 重複処理防止: 既に処理中のファイルをフィルタ
        new_files = [f for f in files if f not in self.processing_files]

        if not new_files:
            logger.info("All detected files are already being processed")
            return

        # 処理中リストに追加
        for f in new_files:
            self.processing_files.add(f)

        # 統計情報表示を更新
        self.update_stats_display()

        logger.info(f"Processing {len(new_files)} new files (filtered from {len(files)})")

        # トレイ通知
        self.tray_icon.showMessage(
            "新規ファイル検出",
            f"{len(new_files)}個のファイルを自動文字起こし中...",
            QSystemTrayIcon.Information,
            3000
        )

        # バッチ処理で自動文字起こし
        enable_diarization = self.enable_diarization_check.isChecked()
        use_llm = self.enable_llm_correction_check.isChecked()

        self.batch_worker = BatchTranscriptionWorker(
            new_files,
            enable_diarization=enable_diarization,
            max_workers=2,  # 監視時は控えめに2並列
            formatter=self.formatter,
            simple_corrector=self.simple_corrector if use_llm else None,
            use_llm_correction=use_llm
        )

        self.batch_worker.progress.connect(self.on_monitor_progress)
        self.batch_worker.file_finished.connect(self.on_monitor_file_finished)
        self.batch_worker.all_finished.connect(self.on_monitor_all_finished)
        self.batch_worker.error.connect(self.transcription_error)
        self.batch_worker.start()

        # ステータス更新
        self.statusBar().showMessage(f"監視フォルダから{len(new_files)}ファイルを自動処理中...")

    def on_monitor_progress(self, completed: int, total: int, filename: str):
        """監視自動処理の進捗更新"""
        self.statusBar().showMessage(f"自動処理中: {filename} ({completed}/{total})")

    def on_monitor_file_finished(self, file_path: str, result: str, success: bool):
        """監視自動処理の個別ファイル完了"""
        filename = os.path.basename(file_path)

        # 処理中リストから削除
        if file_path in self.processing_files:
            self.processing_files.remove(file_path)

        # 統計情報表示を更新
        self.update_stats_display()

        if success:
            logger.info(f"Monitor auto-processing completed: {filename}")

            # 統計情報更新
            self.total_processed += 1
            self.update_stats_display()

            # 成功した場合のみ処理済みとしてマーク
            if self.folder_monitor:
                self.folder_monitor.mark_as_processed(file_path)

            # 自動移動が有効な場合
            if self.auto_move_completed and self.completed_folder:
                try:
                    from advanced_features import FileOrganizer
                    if FileOrganizer.move_completed_file(file_path, self.completed_folder):
                        logger.info(f"File moved to completed folder: {filename}")
                except Exception as e:
                    logger.error(f"Failed to move completed file: {e}")

        else:
            logger.error(f"Monitor auto-processing failed: {filename}")

            # 統計情報更新
            self.total_failed += 1
            self.update_stats_display()

            # エラー通知（トレイ）
            self.tray_icon.showMessage(
                "文字起こし失敗",
                f"{filename}\nエラー: {result[:100]}",
                QSystemTrayIcon.Critical,
                5000
            )

            # 失敗した場合はマークしない→次回の監視で再処理される

    def on_monitor_all_finished(self, success_count: int, failed_count: int):
        """監視自動処理の全完了"""
        # トレイ通知
        self.tray_icon.showMessage(
            "自動文字起こし完了",
            f"成功: {success_count}件, 失敗: {failed_count}件",
            QSystemTrayIcon.Information,
            3000
        )

        self.statusBar().showMessage(f"自動処理完了: {success_count}成功, {failed_count}失敗")
        logger.info(f"Monitor auto-processing finished: {success_count} success, {failed_count} failed")

    def on_monitor_status(self, status: str):
        """監視ステータス更新"""
        logger.info(f"Monitor status: {status}")

    def update_stats_display(self):
        """統計情報表示を更新"""
        processing_count = len(self.processing_files)
        self.stats_label.setText(
            f"処理済み: {self.total_processed}件 | 失敗: {self.total_failed}件 | 処理中: {processing_count}件"
        )

    def on_monitor_interval_changed(self, value: int):
        """監視間隔変更"""
        self.monitor_check_interval = value
        logger.info(f"Monitor interval changed to: {value}s")

        # デバウンス付き保存
        self.settings.set('monitor_interval', value)
        self.settings.save_debounced()

        # 監視中の場合は再起動
        if self.folder_monitor and self.folder_monitor.isRunning():
            self.folder_monitor.stop()
            self.folder_monitor.wait()

            self.folder_monitor = FolderMonitor(
                self.monitored_folder,
                check_interval=value
            )

            self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
            self.folder_monitor.status_update.connect(self.on_monitor_status)
            self.folder_monitor.start()

            logger.info(f"Folder monitor restarted with new interval: {value}s")
            self.statusBar().showMessage(f"監視間隔を{value}秒に変更しました")

    def on_startup_toggled(self, checked: bool):
        """Windows起動時の自動起動設定"""
        try:
            from advanced_features import StartupManager

            if checked:
                if StartupManager.enable_startup():
                    logger.info("Startup enabled")
                    self.statusBar().showMessage("Windows起動時に自動起動するように設定しました")
                else:
                    self.startup_check.setChecked(False)
                    QMessageBox.warning(self, "警告", "スタートアップの設定に失敗しました")
            else:
                if StartupManager.disable_startup():
                    logger.info("Startup disabled")
                    self.statusBar().showMessage("自動起動を無効にしました")
                else:
                    self.startup_check.setChecked(True)
                    QMessageBox.warning(self, "警告", "スタートアップの解除に失敗しました")

        except Exception as e:
            logger.error(f"Failed to toggle startup: {e}")
            QMessageBox.critical(self, "エラー", f"スタートアップ設定に失敗しました: {str(e)}")
            self.startup_check.setChecked(not checked)

    def on_auto_move_toggled(self, checked: bool):
        """自動移動設定トグル"""
        self.auto_move_completed = checked
        self.select_completed_folder_button.setEnabled(checked)

        if checked:
            logger.info("Auto-move enabled")
            self.statusBar().showMessage("完了ファイルの自動移動を有効にしました")
        else:
            logger.info("Auto-move disabled")
            self.statusBar().showMessage("完了ファイルの自動移動を無効にしました")

    def select_completed_folder(self):
        """完了ファイル移動先フォルダ選択"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "完了ファイルの移動先フォルダを選択",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder_path:
            self.completed_folder = folder_path
            folder_name = os.path.basename(folder_path)
            self.completed_folder_label.setText(folder_name)
            self.statusBar().showMessage(f"移動先フォルダ設定: {folder_name}")
            logger.info(f"Completed folder selected: {folder_path}")

    def create_realtime_tab(self):
        """リアルタイム文字起こしタブを作成"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 説明ラベル
        info_label = QLabel("🎤 リアルタイム文字起こし - マイクから直接音声を文字起こしします")
        info_label.setStyleSheet("font-size: 13px; margin: 10px; color: #2196F3;")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        # マイクデバイス選択
        device_group = QGroupBox("マイク設定")
        device_layout = QVBoxLayout()

        device_select_layout = QHBoxLayout()
        device_label = QLabel("マイクデバイス:")
        device_select_layout.addWidget(device_label)

        self.realtime_device_combo = QComboBox()
        self.realtime_device_combo.setMinimumWidth(300)
        device_select_layout.addWidget(self.realtime_device_combo)

        self.refresh_devices_button = QPushButton("デバイス更新")
        self.refresh_devices_button.setStyleSheet("padding: 5px;")
        self.refresh_devices_button.clicked.connect(self.refresh_audio_devices)
        device_select_layout.addWidget(self.refresh_devices_button)
        device_select_layout.addStretch()

        device_layout.addLayout(device_select_layout)
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # VAD設定
        vad_group = QGroupBox("音声検出設定 (VAD)")
        vad_layout = QVBoxLayout()

        self.realtime_vad_enable_check = QCheckBox("音声検出 (VAD) を有効化")
        self.realtime_vad_enable_check.setChecked(True)
        self.realtime_vad_enable_check.setToolTip("無音時の処理をスキップして効率化します")
        vad_layout.addWidget(self.realtime_vad_enable_check)

        # VAD感度スライダー
        vad_sensitivity_layout = QHBoxLayout()
        vad_sensitivity_label = QLabel("感度:")
        vad_sensitivity_layout.addWidget(vad_sensitivity_label)

        self.realtime_vad_slider = QSlider(Qt.Horizontal)
        self.realtime_vad_slider.setRange(5, 50)  # 0.005 ~ 0.050
        self.realtime_vad_slider.setValue(10)  # 0.010 default
        self.realtime_vad_slider.setToolTip("音声検出の感度 (低い値 = 高感度)")
        vad_sensitivity_layout.addWidget(self.realtime_vad_slider)

        self.vad_value_label = QLabel("0.010")
        vad_sensitivity_layout.addWidget(self.vad_value_label)
        self.realtime_vad_slider.valueChanged.connect(
            lambda v: self.vad_value_label.setText(f"{v/1000:.3f}")
        )

        vad_layout.addLayout(vad_sensitivity_layout)
        vad_group.setLayout(vad_layout)
        layout.addWidget(vad_group)

        # モデル設定
        model_group = QGroupBox("Whisperモデル設定")
        model_layout = QHBoxLayout()

        model_label = QLabel("モデルサイズ:")
        model_layout.addWidget(model_label)

        self.realtime_model_combo = QComboBox()
        self.realtime_model_combo.addItems(["tiny", "base", "small", "medium"])
        self.realtime_model_combo.setCurrentText("base")
        self.realtime_model_combo.setToolTip("base推奨 (精度と速度のバランス)")
        model_layout.addWidget(self.realtime_model_combo)
        model_layout.addStretch()

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # 録音コントロール
        control_layout = QHBoxLayout()

        self.realtime_start_button = QPushButton("🎤 録音開始")
        self.realtime_start_button.setStyleSheet(
            "font-size: 16px; padding: 12px; background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.realtime_start_button.clicked.connect(self.start_realtime_recording)
        control_layout.addWidget(self.realtime_start_button)

        self.realtime_stop_button = QPushButton("⏹ 録音停止")
        self.realtime_stop_button.setStyleSheet(
            "font-size: 16px; padding: 12px; background-color: #F44336; color: white; font-weight: bold;"
        )
        self.realtime_stop_button.setEnabled(False)
        self.realtime_stop_button.clicked.connect(self.stop_realtime_recording)
        control_layout.addWidget(self.realtime_stop_button)

        layout.addLayout(control_layout)

        # ステータス表示
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setStyleSheet("background-color: #f5f5f5; border-radius: 5px; padding: 8px;")
        status_layout = QHBoxLayout(status_frame)

        self.realtime_status_label = QLabel("状態: 準備完了")
        self.realtime_status_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        status_layout.addWidget(self.realtime_status_label)

        self.realtime_vad_indicator = QLabel("🔇")
        self.realtime_vad_indicator.setStyleSheet("font-size: 20px;")
        self.realtime_vad_indicator.setToolTip("音声検出インジケーター")
        status_layout.addWidget(self.realtime_vad_indicator)

        status_layout.addStretch()

        layout.addWidget(status_frame)

        # 文字起こし結果表示エリア
        result_label = QLabel("文字起こし結果:")
        result_label.setStyleSheet("font-size: 14px; margin-top: 10px;")
        layout.addWidget(result_label)

        self.realtime_result_text = QTextEdit()
        self.realtime_result_text.setPlaceholderText("録音を開始すると、リアルタイムで文字起こし結果が表示されます...")
        self.realtime_result_text.setStyleSheet("font-size: 13px; font-family: 'Meiryo', sans-serif;")
        layout.addWidget(self.realtime_result_text)

        # 統計情報表示
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("background-color: #e8f5e9; border-radius: 5px; padding: 8px;")
        stats_layout = QHBoxLayout(stats_frame)

        self.realtime_stats_label = QLabel("処理チャンク: 0 | 平均RTF: 0.00x")
        self.realtime_stats_label.setStyleSheet("font-size: 11px; color: #333;")
        stats_layout.addWidget(self.realtime_stats_label)

        layout.addWidget(stats_frame)

        # 保存/クリアボタン
        button_layout = QHBoxLayout()

        self.realtime_save_button = QPushButton("結果を保存")
        self.realtime_save_button.setStyleSheet("font-size: 12px; padding: 8px;")
        self.realtime_save_button.setEnabled(False)
        self.realtime_save_button.clicked.connect(self.save_realtime_transcription)
        button_layout.addWidget(self.realtime_save_button)

        self.realtime_clear_button = QPushButton("クリア")
        self.realtime_clear_button.setStyleSheet("font-size: 12px; padding: 8px;")
        self.realtime_clear_button.clicked.connect(self.clear_realtime_results)
        button_layout.addWidget(self.realtime_clear_button)

        layout.addLayout(button_layout)

        # 初期化: デバイスリストを読み込む
        self.refresh_audio_devices()

        return tab

    def refresh_audio_devices(self):
        """オーディオデバイスリストを更新"""
        try:
            # 一時的なRealtimeAudioCaptureインスタンスを作成してデバイス一覧取得
            from realtime_audio_capture import RealtimeAudioCapture
            temp_capture = RealtimeAudioCapture()
            devices = temp_capture.list_devices()
            temp_capture.cleanup()

            self.realtime_device_combo.clear()
            for device in devices:
                device_text = f"[{device['index']}] {device['name']}"
                self.realtime_device_combo.addItem(device_text, device['index'])

            logger.info(f"Audio devices refreshed: {len(devices)} devices found")

        except Exception as e:
            logger.error(f"Failed to refresh audio devices: {e}")
            QMessageBox.warning(self, "警告", f"デバイスリストの取得に失敗しました: {str(e)}")

    def start_realtime_recording(self):
        """リアルタイム録音開始"""
        try:
            # デバイスインデックス取得
            device_index = self.realtime_device_combo.currentData()
            if device_index is None:
                QMessageBox.warning(self, "警告", "マイクデバイスを選択してください")
                return

            # VAD設定
            enable_vad = self.realtime_vad_enable_check.isChecked()
            vad_threshold = self.realtime_vad_slider.value() / 1000  # 0.005 ~ 0.050

            # モデルサイズ
            model_size = self.realtime_model_combo.currentText()

            # ファクトリを使用してRealtimeTranscriberを作成（依存性注入パターン）
            self.realtime_transcriber = RealtimeTranscriberFactory.create(
                model_size=model_size,
                device="auto",
                device_index=device_index,
                enable_vad=enable_vad,
                vad_threshold=vad_threshold
            )

            # シグナル接続
            self.realtime_transcriber.transcription_update.connect(self.on_realtime_transcription)
            self.realtime_transcriber.status_update.connect(self.on_realtime_status)
            self.realtime_transcriber.error_occurred.connect(self.on_realtime_error)
            self.realtime_transcriber.critical_error_occurred.connect(self.on_realtime_error)  # 致命的エラーも処理
            self.realtime_transcriber.vad_status_changed.connect(self.on_realtime_vad)

            # スレッド開始
            self.realtime_transcriber.start()

            # 録音開始
            if not self.realtime_transcriber.start_recording():
                QMessageBox.critical(self, "エラー", "録音の開始に失敗しました")
                return

            # UI状態変更
            self.realtime_start_button.setEnabled(False)
            self.realtime_stop_button.setEnabled(True)
            self.realtime_device_combo.setEnabled(False)
            self.realtime_model_combo.setEnabled(False)
            self.refresh_devices_button.setEnabled(False)
            self.realtime_save_button.setEnabled(False)
            self.realtime_result_text.clear()

            self.realtime_status_label.setText("状態: 🎤 録音中...")
            self.statusBar().showMessage("リアルタイム文字起こし開始")
            logger.info("Realtime recording started")

        except Exception as e:
            error_msg = f"録音開始に失敗しました: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "エラー", error_msg)

    def stop_realtime_recording(self):
        """リアルタイム録音停止"""
        try:
            if self.realtime_transcriber:
                self.realtime_transcriber.stop_recording()

                # UI状態復元
                self.realtime_start_button.setEnabled(True)
                self.realtime_stop_button.setEnabled(False)
                self.realtime_device_combo.setEnabled(True)
                self.realtime_model_combo.setEnabled(True)
                self.refresh_devices_button.setEnabled(True)
                self.realtime_save_button.setEnabled(True)

                self.realtime_status_label.setText("状態: 停止")
                self.realtime_vad_indicator.setText("🔇")

                # 統計情報表示
                stats = self.realtime_transcriber.get_statistics()
                self.realtime_stats_label.setText(
                    f"処理チャンク: {stats['chunks_processed']} | "
                    f"平均RTF: {stats['average_rtf']:.2f}x | "
                    f"音声時間: {stats['audio_duration']:.1f}秒"
                )

                self.statusBar().showMessage("録音停止")
                logger.info(f"Realtime recording stopped - Stats: {stats}")

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            QMessageBox.critical(self, "エラー", f"録音停止に失敗しました: {str(e)}")

    def on_realtime_transcription(self, text: str, is_final: bool):
        """リアルタイム文字起こし結果の受信"""
        cursor = self.realtime_result_text.textCursor()

        if is_final:
            # 確定テキスト（黒色、太字）
            cursor.movePosition(cursor.End)
            html = f'<span style="color: black; font-weight: bold;">{text}</span> '
            self.realtime_result_text.insertHtml(html)
        else:
            # 保留中テキスト（灰色、イタリック）
            cursor.movePosition(cursor.End)
            html = f'<span style="color: gray; font-style: italic;">[処理中: {text}]</span><br>'
            self.realtime_result_text.insertHtml(html)

        # 自動スクロール
        self.realtime_result_text.ensureCursorVisible()

    def on_realtime_status(self, status: str):
        """リアルタイムステータス更新"""
        self.realtime_status_label.setText(f"状態: {status}")

    def on_realtime_error(self, error: str):
        """リアルタイムエラー"""
        logger.error(f"Realtime error: {error}")
        self.realtime_status_label.setText(f"エラー: {error}")
        QMessageBox.warning(self, "エラー", error)

    def on_realtime_vad(self, is_speech: bool, energy: float):
        """VADステータス更新"""
        if is_speech:
            self.realtime_vad_indicator.setText("🎤")
            self.realtime_vad_indicator.setStyleSheet("font-size: 20px; color: #4CAF50;")
        else:
            self.realtime_vad_indicator.setText("🔇")
            self.realtime_vad_indicator.setStyleSheet("font-size: 20px; color: #999;")

    def save_realtime_transcription(self):
        """リアルタイム文字起こし結果を保存"""
        if not self.realtime_transcriber:
            return

        try:
            # ファイル保存ダイアログ
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"リアルタイム文字起こし_{timestamp}.txt"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "文字起こし結果を保存",
                default_filename,
                "Text Files (*.txt);;All Files (*)"
            )

            if file_path:
                # 全文字起こし結果を取得
                full_text = self.realtime_transcriber.get_full_transcription()

                # 統計情報を追加
                stats = self.realtime_transcriber.get_statistics()
                stats_text = (
                    f"\n\n--- 統計情報 ---\n"
                    f"処理チャンク数: {stats['chunks_processed']}\n"
                    f"音声時間: {stats['audio_duration']:.2f}秒\n"
                    f"処理時間: {stats['processing_time']:.2f}秒\n"
                    f"平均RTF: {stats['average_rtf']:.2f}x\n"
                )

                # ファイルに保存
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                    f.write(stats_text)

                self.statusBar().showMessage(f"保存完了: {os.path.basename(file_path)}")
                QMessageBox.information(self, "保存完了", "文字起こし結果を保存しました")
                logger.info(f"Realtime transcription saved: {file_path}")

        except Exception as e:
            logger.error(f"Failed to save realtime transcription: {e}")
            QMessageBox.critical(self, "エラー", f"保存に失敗しました: {str(e)}")

    def clear_realtime_results(self):
        """リアルタイム結果をクリア"""
        self.realtime_result_text.clear()
        if self.realtime_transcriber:
            self.realtime_transcriber.clear_transcription()
        self.realtime_stats_label.setText("処理チャンク: 0 | 平均RTF: 0.00x")
        self.statusBar().showMessage("クリアしました")
        logger.info("Realtime results cleared")

    def check_startup_status(self):
        """Windows起動設定の状態をチェック"""
        try:
            from advanced_features import StartupManager

            if StartupManager.is_startup_enabled():
                self.startup_check.setChecked(True)
                logger.info("Startup is enabled")
            else:
                self.startup_check.setChecked(False)
                logger.info("Startup is disabled")

        except Exception as e:
            logger.warning(f"Failed to check startup status: {e}")

    def load_ui_settings(self):
        """UI設定を復元（検証付き）"""
        try:
            # ウィンドウジオメトリを検証して復元
            width = self.settings.get('window.width', 900)
            height = self.settings.get('window.height', 700)
            x = self.settings.get('window.x', 100)
            y = self.settings.get('window.y', 100)

            # 範囲検証
            width = max(400, min(3840, width))
            height = max(300, min(2160, height))
            x = max(0, min(3000, x))
            y = max(0, min(2000, y))

            # 画面内に収まるかチェック
            from PyQt5.QtWidgets import QApplication
            desktop = QApplication.desktop()
            if desktop:
                screen_geometry = desktop.availableGeometry()

                # ウィンドウが画面外に出る場合は調整
                if x + width > screen_geometry.width():
                    x = max(0, screen_geometry.width() - width)
                if y + height > screen_geometry.height():
                    y = max(0, screen_geometry.height() - height)

            self.setGeometry(x, y, width, height)
            logger.info(f"Window geometry restored: {width}x{height} at ({x}, {y})")

            # フォルダ設定を復元（存在チェック付き）
            monitored_folder = self.settings.get('monitored_folder')
            if monitored_folder:
                from pathlib import Path
                if Path(monitored_folder).exists() and Path(monitored_folder).is_dir():
                    self.monitored_folder = monitored_folder
                    folder_name = os.path.basename(monitored_folder)
                    self.monitor_folder_label.setText(f"監視フォルダ: {folder_name}")
                    logger.info(f"Restored monitored folder: {monitored_folder}")
                else:
                    logger.warning(f"Monitored folder no longer exists: {monitored_folder}")

            completed_folder = self.settings.get('completed_folder')
            if completed_folder:
                from pathlib import Path
                if Path(completed_folder).exists() and Path(completed_folder).is_dir():
                    self.completed_folder = completed_folder
                    folder_name = os.path.basename(completed_folder)
                    self.completed_folder_label.setText(folder_name)
                    logger.info(f"Restored completed folder: {completed_folder}")
                else:
                    logger.warning(f"Completed folder no longer exists: {completed_folder}")

            # 監視間隔を復元（範囲検証）
            monitor_interval = self.settings.get('monitor_interval', 10)
            monitor_interval = max(5, min(60, monitor_interval))
            self.monitor_interval_spinbox.setValue(monitor_interval)

            # 自動移動設定を復元
            auto_move = self.settings.get('auto_move_completed', False)
            if isinstance(auto_move, bool):
                self.auto_move_check.setChecked(auto_move)
                self.auto_move_completed = auto_move
                self.select_completed_folder_button.setEnabled(auto_move)

            # テキスト整形オプションを復元
            self.remove_fillers_check.setChecked(
                bool(self.settings.get('remove_fillers', True))
            )
            self.add_punctuation_check.setChecked(
                bool(self.settings.get('add_punctuation', True))
            )
            self.format_paragraphs_check.setChecked(
                bool(self.settings.get('format_paragraphs', True))
            )
            self.enable_diarization_check.setChecked(
                bool(self.settings.get('enable_diarization', False))
            )
            self.enable_llm_correction_check.setChecked(
                bool(self.settings.get('enable_llm_correction', False))
            )
            self.use_advanced_llm_check.setChecked(
                bool(self.settings.get('use_advanced_llm', False))
            )

            # リアルタイム設定を復元（検証付き）
            model_size = self.settings.get('realtime.model_size', 'base')
            valid_models = ['tiny', 'base', 'small', 'medium']
            if model_size not in valid_models:
                logger.warning(f"Invalid model size '{model_size}', using 'base'")
                model_size = 'base'

            index = self.realtime_model_combo.findText(model_size)
            if index >= 0:
                self.realtime_model_combo.setCurrentIndex(index)

            vad_enabled = self.settings.get('realtime.vad_enabled', True)
            if isinstance(vad_enabled, bool):
                self.realtime_vad_enable_check.setChecked(vad_enabled)

            vad_threshold = self.settings.get('realtime.vad_threshold', 10)
            vad_threshold = max(5, min(50, vad_threshold))
            self.realtime_vad_slider.setValue(vad_threshold)

            # デバイスインデックスは保存するが復元はしない（デバイス構成が変わる可能性があるため）

            logger.info("UI settings restored successfully")

        except Exception as e:
            logger.error(f"Failed to load UI settings: {e}", exc_info=True)
            # エラー時はデフォルトジオメトリに設定
            self.setGeometry(100, 100, 900, 700)

    def save_ui_settings(self):
        """UI設定を保存"""
        try:
            # フォルダ設定を保存
            self.settings.set('monitored_folder', self.monitored_folder)
            self.settings.set('completed_folder', self.completed_folder)
            self.settings.set('monitor_interval', self.monitor_interval_spinbox.value())
            self.settings.set('auto_move_completed', self.auto_move_completed)

            # テキスト整形オプションを保存
            self.settings.set('remove_fillers', self.remove_fillers_check.isChecked())
            self.settings.set('add_punctuation', self.add_punctuation_check.isChecked())
            self.settings.set('format_paragraphs', self.format_paragraphs_check.isChecked())
            self.settings.set('enable_diarization', self.enable_diarization_check.isChecked())
            self.settings.set('enable_llm_correction', self.enable_llm_correction_check.isChecked())
            self.settings.set('use_advanced_llm', self.use_advanced_llm_check.isChecked())

            # リアルタイム設定を保存
            device_index = self.realtime_device_combo.currentData()
            self.settings.set('realtime.device_index', device_index)
            self.settings.set('realtime.model_size', self.realtime_model_combo.currentText())
            self.settings.set('realtime.vad_enabled', self.realtime_vad_enable_check.isChecked())
            self.settings.set('realtime.vad_threshold', self.realtime_vad_slider.value())

            # ウィンドウサイズ・位置を保存
            self.settings.set('window.width', self.width())
            self.settings.set('window.height', self.height())
            self.settings.set('window.x', self.x())
            self.settings.set('window.y', self.y())

            # 即座にファイルに保存（アプリ終了時なので）
            self.settings.save_immediate()
            logger.info("UI settings saved successfully")

        except Exception as e:
            logger.error(f"Failed to save UI settings: {e}")


def main():
    """メイン関数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # モダンなスタイル

    # トレイに最小化できるよう、最後のウィンドウが閉じてもアプリを終了しない
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    logger.info("Application started")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
