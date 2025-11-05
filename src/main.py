"""
KotobaTranscriber - メインアプリケーション
日本語音声文字起こしアプリケーション
"""

import sys
import os
import shutil
from datetime import datetime
from typing import Optional
import argparse
import win32event
import win32api
import winerror
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QTextEdit, QFileDialog, QLabel, QProgressBar, QMessageBox,
    QCheckBox, QGroupBox, QListWidget, QListWidgetItem, QSystemTrayIcon, QMenu,
    QSpinBox, QFrame, QTabWidget, QComboBox, QSlider
)
from PySide6.QtCore import Qt, QThread, Signal, QThreadPool, QRunnable, Slot
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from transcription_engine import TranscriptionEngine
from text_formatter import TextFormatter
from speaker_diarization_free import FreeSpeakerDiarizer
from llm_corrector_standalone import StandaloneLLMCorrector
from folder_monitor import FolderMonitor
from faster_whisper_engine import FasterWhisperEngine
from app_settings import AppSettings
from validators import Validator, ValidationError
from runtime_config import RuntimeConfig
from exceptions import (
    FileProcessingError,
    AudioFormatError,
    ModelLoadError,
    TranscriptionFailedError,
    InsufficientMemoryError
)

# ロギング設定（インポートの前に初期化）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# オプション: カスタム語彙管理
try:
    from vocabulary_dialog import VocabularyDialog
    VOCABULARY_DIALOG_AVAILABLE = True
except ImportError:
    VOCABULARY_DIALOG_AVAILABLE = False
    logger.warning("vocabulary_dialog not available")


# UI定数の定義
class UIConstants:
    """UI関連の定数を管理（完全集約）"""
    # 進捗値
    PROGRESS_MODEL_LOAD = 20
    PROGRESS_BEFORE_TRANSCRIBE = 40
    PROGRESS_AFTER_TRANSCRIBE = 70
    PROGRESS_DIARIZATION_START = 75
    PROGRESS_DIARIZATION_END = 85
    PROGRESS_COMPLETE = 100

    # スライダー範囲
    VAD_SLIDER_MIN = 5
    VAD_SLIDER_MAX = 50
    VAD_SLIDER_DEFAULT = 10

    # 監視間隔範囲
    MONITOR_INTERVAL_MIN = 5
    MONITOR_INTERVAL_MAX = 60
    MONITOR_INTERVAL_DEFAULT = 10

    # 並列処理数
    BATCH_WORKERS_DEFAULT = 3
    MONITOR_BATCH_WORKERS = 2

    # ウィンドウサイズ制限
    WINDOW_MIN_WIDTH = 400
    WINDOW_MIN_HEIGHT = 300
    WINDOW_MAX_WIDTH = 3840
    WINDOW_MAX_HEIGHT = 2160

    # 段落整形デフォルト
    SENTENCES_PER_PARAGRAPH = 4

    # タイムアウト設定（ミリ秒）
    THREAD_WAIT_TIMEOUT = 10000  # 10秒
    MONITOR_WAIT_TIMEOUT = 5000   # 5秒
    BATCH_WAIT_TIMEOUT = 30000    # 30秒

    # 処理中ファイルTTL（秒）
    PROCESSING_FILES_TTL = 3600  # 1時間

    # ボタンスタイル
    BUTTON_STYLE_NORMAL = "font-size: 12px; padding: 5px; background-color: #4CAF50; color: white; font-weight: bold;"
    BUTTON_STYLE_MONITOR = "font-size: 12px; padding: 5px; background-color: #FF9800; color: white; font-weight: bold;"
    BUTTON_STYLE_STOP = "font-size: 12px; padding: 5px; background-color: #F44336; color: white; font-weight: bold;"

    # ステータスメッセージ表示時間（ミリ秒）
    STATUS_MESSAGE_TIMEOUT = 3000  # 3秒




class BatchTranscriptionWorker(QThread):
    """複数ファイルの並列文字起こし処理"""
    progress = Signal(int, int, str)  # (完了数, 総数, ファイル名)
    file_finished = Signal(str, str, bool)  # (ファイルパス, 結果テキスト, 成功/失敗)
    all_finished = Signal(int, int)  # (成功数, 失敗数)
    error = Signal(str)

    def __init__(self, audio_paths: list, enable_diarization: bool = False,
                 max_workers: int = 3, formatter=None,
                 use_llm_correction: bool = False):
        super().__init__()
        self.audio_paths = audio_paths
        self.enable_diarization = enable_diarization
        self.max_workers = max_workers
        self.formatter = formatter
        self.use_llm_correction = use_llm_correction
        self.completed = 0
        self.success_count = 0
        self.failed_count = 0
        self.lock = threading.Lock()
        self._cancelled = False  # キャンセルフラグ
        self._executor = None  # ThreadPoolExecutor参照保持

        # 共有TranscriptionEngineインスタンス（並列処理での再利用）
        self._shared_engine = None
        self._engine_lock = threading.Lock()  # エンジン使用の排他制御

    def cancel(self):
        """バッチ処理をキャンセル"""
        logger.info("Batch processing cancellation requested")
        self._cancelled = True
        # ThreadPoolExecutorのシャットダウン（実行中のタスクは完了を待つ）
        if self._executor:
            self._executor.shutdown(wait=False)

    def process_single_file(self, audio_path: str):
        """単一ファイルを処理"""
        # キャンセルチェック
        if self._cancelled:
            return audio_path, "処理がキャンセルされました", False

        try:
            logger.info(f"Processing file: {audio_path}")

            # Validate file path first
            try:
                validated_path = Validator.validate_file_path(
                    audio_path,
                    must_exist=True
                )
            except ValidationError as e:
                error_msg = f"ファイルパスが不正です: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e

            # Load transcription engine (shared instance with locking)
            try:
                # エンジンロックを取得（1つのファイルのみが同時にモデルを使用）
                with self._engine_lock:
                    # 共有エンジンが未初期化の場合はロード
                    if self._shared_engine is None:
                        logger.info("Initializing shared transcription engine...")
                        self._shared_engine = TranscriptionEngine()
                        self._shared_engine.load_model()
                        logger.info("Shared transcription engine loaded successfully")

                    # 文字起こし実行（ロック内で実行して並列実行を防ぐ）
                    result = self._shared_engine.transcribe(str(validated_path), return_timestamps=True)
                    text = result.get("text", "")
            except ModelLoadError as e:
                error_msg = f"モデルのロードに失敗しました: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except TranscriptionFailedError as e:
                error_msg = f"文字起こしに失敗しました: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except FileNotFoundError as e:
                error_msg = f"ファイルが見つかりません: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except PermissionError as e:
                error_msg = f"ファイルへのアクセス権限がありません: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except MemoryError as e:
                error_msg = f"メモリ不足です: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise InsufficientMemoryError(0, 0) from e
            except (IOError, OSError) as e:
                error_msg = f"ファイル読み込みエラー: {audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except ValueError as e:
                error_msg = f"音声フォーマットエラー: {audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                raise AudioFormatError(error_msg) from e
            except Exception as e:
                error_msg = f"予期しないエラー ({type(e).__name__}): {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e

            # Optional speaker diarization (failure is non-critical)
            if self.enable_diarization:
                try:
                    logger.debug(f"Applying speaker diarization to '{audio_path}'")
                    diarizer = FreeSpeakerDiarizer()
                    diar_segments = diarizer.diarize(str(validated_path))
                    trans_segments = result.get("chunks", [])
                    text = diarizer.format_with_speakers(text, diar_segments, trans_segments)
                    logger.info(f"Speaker diarization completed for '{audio_path}'")
                except ImportError as e:
                    logger.warning(
                        f"Speaker diarization library not available for '{audio_path}': {e}",
                        exc_info=False
                    )
                except (IOError, OSError) as e:
                    logger.warning(
                        f"I/O error during diarization for '{audio_path}': {e}",
                        exc_info=True
                    )
                except Exception as e:
                    logger.warning(
                        f"Speaker diarization failed for '{audio_path}': {type(e).__name__} - {e}",
                        exc_info=True
                    )
                    # Continue with non-diarized text

            # Text formatting（バッチ処理では常にルールベース句読点を使用）
            try:
                if self.formatter:
                    formatted_text = self.formatter.format_all(
                        text,
                        remove_fillers=True,
                        add_punctuation=True,  # バッチ処理ではルールベース句読点を使用
                        format_paragraphs=True,  # バッチ処理ではルールベース段落整形を使用
                        clean_repeated=True
                    )
                else:
                    formatted_text = text
            except ValidationError as e:
                logger.warning(f"Text formatting validation error for '{audio_path}': {e}")
                formatted_text = text  # Use unformatted text as fallback
            except Exception as e:
                logger.warning(
                    f"Text formatting failed for '{audio_path}': {type(e).__name__} - {e}",
                    exc_info=True
                )
                formatted_text = text  # Use unformatted text as fallback

            # バッチ処理ではLLM補正をスキップ（速度重視）
            # 単一ファイル処理でのみLLM補正を適用

            # Save output file
            try:
                base_name = os.path.splitext(audio_path)[0]
                output_file = f"{base_name}_文字起こし.txt"

                # Validate output path (path traversal protection)
                validated_output = Validator.validate_file_path(
                    output_file,
                    allowed_extensions=[".txt"],
                    must_exist=False
                )

                with open(str(validated_output), 'w', encoding='utf-8') as f:
                    f.write(formatted_text)

                logger.info(f"Successfully processed '{audio_path}' -> '{output_file}'")
                return audio_path, formatted_text, True

            except ValidationError as e:
                error_msg = f"出力パスが不正です: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except (IOError, OSError, PermissionError) as e:
                error_msg = f"出力ファイルの保存に失敗しました: {audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e

        except FileProcessingError as e:
            # Already logged and formatted
            return audio_path, str(e), False
        except InsufficientMemoryError as e:
            error_msg = f"メモリ不足です。ファイルサイズが大きすぎる可能性があります: {audio_path}"
            logger.error(error_msg, exc_info=True)
            return audio_path, error_msg, False
        except AudioFormatError as e:
            # Already logged
            return audio_path, str(e), False
        except Exception as e:
            # Unexpected error - last resort fallback
            error_msg = f"予期しないエラーが発生しました ({type(e).__name__}): {audio_path} - {e}"
            logger.error(error_msg, exc_info=True)
            return audio_path, error_msg, False

    def run(self):
        """並列処理実行"""
        try:
            total = len(self.audio_paths)

            # ThreadPoolExecutorで並列処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self._executor = executor  # 参照を保持（キャンセル用）

                # 全ファイルを投入
                future_to_path = {
                    executor.submit(self.process_single_file, path): path
                    for path in self.audio_paths
                }

                # 完了したものから処理
                for future in as_completed(future_to_path):
                    # キャンセルチェック
                    if self._cancelled:
                        logger.info("Batch processing cancelled by user")
                        break

                    try:
                        audio_path, result_text, success = future.result(timeout=600)  # 10分タイムアウト

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

                    except Exception as future_error:
                        logger.error(f"Future result error: {future_error}")
                        with self.lock:
                            self.completed += 1
                            self.failed_count += 1

                self._executor = None  # 参照をクリア

            # 全完了通知
            completion_msg = f"Batch processing completed: {self.success_count} success, {self.failed_count} failed"
            if self._cancelled:
                completion_msg += " (cancelled)"
            logger.info(completion_msg)
            self.all_finished.emit(self.success_count, self.failed_count)

        except Exception as e:
            error_msg = f"Batch processing error: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)
        finally:
            self._executor = None  # 確実にクリア


class TranscriptionWorker(QThread):
    """文字起こし処理を別スレッドで実行"""
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

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
            self.progress.emit(UIConstants.PROGRESS_MODEL_LOAD)
            logger.info(f"Starting transcription for: {self.audio_path}")

            # モデルロード
            try:
                self.engine.load_model()
                self.progress.emit(UIConstants.PROGRESS_BEFORE_TRANSCRIBE)
            except ModelLoadError as e:
                error_msg = f"モデルのロードに失敗しました: {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except (IOError, OSError) as e:
                error_msg = f"モデルファイルの読み込みエラー: {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except Exception as e:
                error_msg = f"予期しないモデルロードエラー: {type(e).__name__} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return

            # 文字起こし実行
            try:
                result = self.engine.transcribe(self.audio_path, return_timestamps=True)
                self.progress.emit(UIConstants.PROGRESS_AFTER_TRANSCRIBE)
            except ValidationError as e:
                error_msg = f"ファイルパスが不正です: {self.audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except TranscriptionFailedError as e:
                error_msg = f"文字起こしに失敗しました: {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except FileNotFoundError as e:
                error_msg = f"ファイルが見つかりません: {self.audio_path}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except PermissionError as e:
                error_msg = f"ファイルへのアクセス権限がありません: {self.audio_path}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except (IOError, OSError) as e:
                error_msg = f"ファイル読み込みエラー: {self.audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except MemoryError as e:
                error_msg = f"メモリ不足です。ファイルサイズが大きすぎる可能性があります: {self.audio_path}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except ValueError as e:
                error_msg = f"音声フォーマットエラー: {self.audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except Exception as e:
                error_msg = f"予期しない文字起こしエラー: {type(e).__name__} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return

            # 結果取得
            text = result.get("text", "")
            if not text:
                logger.warning(f"Transcription returned empty text for: {self.audio_path}")

            # 話者分離が有効な場合（非クリティカル処理）
            if self.enable_diarization and self.diarizer:
                try:
                    logger.info("Running speaker diarization...")
                    self.progress.emit(UIConstants.PROGRESS_DIARIZATION_START)

                    # 話者分離実行
                    diar_segments = self.diarizer.diarize(self.audio_path)
                    self.progress.emit(UIConstants.PROGRESS_DIARIZATION_END)

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

                except ImportError as e:
                    logger.warning(
                        f"Speaker diarization library not available: {e}",
                        exc_info=False
                    )
                except (IOError, OSError) as e:
                    logger.warning(
                        f"I/O error during speaker diarization: {e}",
                        exc_info=True
                    )
                except MemoryError as e:
                    logger.warning(
                        f"Memory error during speaker diarization: {e}",
                        exc_info=True
                    )
                except Exception as e:
                    logger.warning(
                        f"Speaker diarization failed: {type(e).__name__} - {e}",
                        exc_info=True
                    )
                    # 話者分離に失敗しても文字起こし結果は返す

            self.progress.emit(UIConstants.PROGRESS_COMPLETE)
            self.finished.emit(text)
            logger.info(f"Transcription completed successfully for: {self.audio_path}")

        except Exception as e:
            # 最後のフォールバック - 予期しないエラー
            error_msg = f"予期しないエラーが発生しました: {type(e).__name__} - {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)


class MainWindow(QMainWindow):
    """メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.batch_worker = None
        self.formatter = TextFormatter()
        self.diarizer = None  # 話者分離は必要時に初期化
        self.advanced_corrector = None  # 高度AI補正（常に使用）
        self.batch_files = []  # バッチ処理用ファイルリスト

        # フォルダ監視関連
        self.folder_monitor = None  # フォルダ監視
        self.monitored_folders = []  # 複数フォルダ監視リスト
        self.monitored_folder = None  # 現在の主監視フォルダ
        self.monitor_check_interval = 10  # 監視間隔（秒）
        self.processing_files = {}  # 処理中ファイルのDict（ファイルパス: 追加時刻）
        self.processing_files_lock = threading.Lock()  # 処理中ファイルのスレッドセーフなアクセス用ロック
        self.processing_files_ttl = 3600  # TTL: 1時間（秒）

        # 統計情報
        self.total_processed = 0  # 総処理件数
        self.total_failed = 0  # 総失敗件数
        self.session_start_time = None  # セッション開始時刻

        # 自動移動設定
        self.auto_move_completed = False  # 完了後自動移動
        self.completed_folder = None  # 完了ファイル移動先


        # 設定管理
        self.settings = AppSettings()
        self.settings.load()  # 設定を読み込む

        # Config Manager (YAML設定)
        self.config = get_config()

        self.init_ui()
        self.init_tray_icon()  # システムトレイアイコン初期化
        self.check_startup_status()  # Windows起動設定状態をチェック
        # 設定を復元（UIコンポーネント初期化後）
        self.load_ui_settings()

        # チェックボックスイベントを接続（UI初期化後）
        self.connect_config_sync()

    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("KotobaTranscriber - 日本語音声文字起こし")

        # アイコン設定
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setGeometry(100, 100, 280, 450)  # ウィンドウ幅最小化: 350 → 280

        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)  # マージン削減
        main_layout.setSpacing(3)  # スペース削減

        # タブウィジェット作成（タイトルラベル削除でスペース節約）
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # ファイル処理タブ
        file_tab = QWidget()
        layout = QVBoxLayout(file_tab)
        layout.setContentsMargins(5, 5, 5, 5)  # マージン削減
        layout.setSpacing(3)  # スペース削減
        self.tab_widget.addTab(file_tab, "ファイル処理")


        # ファイル選択ボタン
        file_button_layout = QHBoxLayout()

        self.file_button = QPushButton("単一")
        self.file_button.setStyleSheet("font-size: 12px; padding: 5px; font-weight: bold;")  # 280px対応
        self.file_button.setToolTip("単一の音声/動画ファイルを選択して文字起こしします")
        self.file_button.clicked.connect(self.select_file)
        file_button_layout.addWidget(self.file_button)

        self.batch_file_button = QPushButton("複数")
        self.batch_file_button.setStyleSheet("font-size: 12px; padding: 5px; background-color: #2196F3; color: white; font-weight: bold;")  # 280px対応
        self.batch_file_button.setToolTip("複数のファイルを一度に選択してバッチ処理します")
        self.batch_file_button.clicked.connect(self.select_batch_files)
        file_button_layout.addWidget(self.batch_file_button)

        layout.addLayout(file_button_layout)

        # フォルダ監視ボタン
        folder_monitor_layout = QHBoxLayout()

        self.monitor_folder_button = QPushButton("監視")
        self.monitor_folder_button.setStyleSheet("font-size: 12px; padding: 5px; background-color: #FF9800; color: white; font-weight: bold;")  # 280px対応
        self.monitor_folder_button.setToolTip("フォルダ監視を開始/停止します。監視中は新しいファイルを自動的に文字起こしします")
        self.monitor_folder_button.clicked.connect(self.toggle_folder_monitor)
        folder_monitor_layout.addWidget(self.monitor_folder_button)

        self.select_monitor_folder_button = QPushButton("フォルダ")
        self.select_monitor_folder_button.setStyleSheet("font-size: 12px; padding: 5px; font-weight: bold;")  # 280px対応
        self.select_monitor_folder_button.setToolTip("監視するフォルダを選択します")
        self.select_monitor_folder_button.clicked.connect(self.select_monitor_folder)
        folder_monitor_layout.addWidget(self.select_monitor_folder_button)

        layout.addLayout(folder_monitor_layout)

        # 監視フォルダ表示
        self.monitor_folder_label = QLabel("監視フォルダ: 未設定")
        self.monitor_folder_label.setStyleSheet("margin: 2px; font-size: 10px; color: #666;")  # コンパクト化
        layout.addWidget(self.monitor_folder_label)

        # 統計情報表示 (コンパクト化)
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("background-color: #f5f5f5; border-radius: 3px; padding: 5px; margin: 2px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(5, 3, 5, 3)

        self.stats_label = QLabel("処理済み: 0件 | 失敗: 0件 | 処理中: 0件")
        self.stats_label.setStyleSheet("font-size: 10px; font-weight: bold; color: #333;")  # コンパクト化
        stats_layout.addWidget(self.stats_label)

        layout.addWidget(stats_frame)

        # 選択ファイル表示
        self.file_label = QLabel("ファイル: 未選択")
        self.file_label.setStyleSheet("margin: 2px; font-size: 10px;")  # コンパクト化
        layout.addWidget(self.file_label)

        # バッチファイルリスト（コンパクト化）
        self.batch_file_list = QListWidget()
        self.batch_file_list.setMaximumHeight(80)  # 100 → 80
        self.batch_file_list.setVisible(False)
        layout.addWidget(self.batch_file_list)

        # バッチリストクリアボタン（コンパクト化）
        self.clear_batch_button = QPushButton("リストをクリア")
        self.clear_batch_button.setStyleSheet("font-size: 10px; padding: 3px;")  # コンパクト化
        self.clear_batch_button.clicked.connect(self.clear_batch_list)
        self.clear_batch_button.setVisible(False)
        layout.addWidget(self.clear_batch_button)

        # テキスト整形オプション (コンパクト化: 2カラムグリッドレイアウト)
        format_group = QGroupBox("テキスト整形オプション")
        format_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; }")  # タイトル縮小
        format_layout = QGridLayout()  # VBoxLayout → GridLayout
        format_layout.setSpacing(2)  # スペース削減 5 → 2
        format_layout.setContentsMargins(5, 5, 5, 5)  # マージン追加

        # チェックボックスのスタイル設定（コンパクト化）
        checkbox_style = "font-size: 12px;"

        # 左カラム
        self.remove_fillers_check = QCheckBox("フィラー語削除")
        self.remove_fillers_check.setStyleSheet(checkbox_style)
        self.remove_fillers_check.setChecked(True)
        self.remove_fillers_check.setToolTip("あー、えー、その、などを削除")
        format_layout.addWidget(self.remove_fillers_check, 0, 0)

        self.enable_diarization_check = QCheckBox("話者分離")
        self.enable_diarization_check.setStyleSheet(checkbox_style)
        self.enable_diarization_check.setChecked(False)
        self.enable_diarization_check.setToolTip("複数の話者を識別します。speechbrainまたはresemblyzerを使用。完全無料、トークン不要。")
        format_layout.addWidget(self.enable_diarization_check, 1, 0)

        # 右カラム - 精度向上機能
        self.enable_preprocessing_check = QCheckBox("音声前処理")
        self.enable_preprocessing_check.setStyleSheet(checkbox_style)
        self.enable_preprocessing_check.setChecked(False)
        self.enable_preprocessing_check.setToolTip("雑音の多い環境や小さい声の録音に有効。librosa/noisereduceが必要です。ノイズ除去・音量正規化。")
        format_layout.addWidget(self.enable_preprocessing_check, 0, 1)

        self.enable_vocabulary_check = QCheckBox("カスタム語彙")
        self.enable_vocabulary_check.setStyleSheet(checkbox_style)
        self.enable_vocabulary_check.setChecked(False)
        self.enable_vocabulary_check.setToolTip("専門用語をWhisperに提示して認識精度を向上させます。")
        format_layout.addWidget(self.enable_vocabulary_check, 1, 1)

        # 高度AI補正チェックボックス
        self.enable_llm_correction_check = QCheckBox("高度AI補正")
        self.enable_llm_correction_check.setStyleSheet(checkbox_style)
        self.enable_llm_correction_check.setChecked(True)  # デフォルトON
        self.enable_llm_correction_check.setToolTip("transformersベースの高度な補正。初回のみrinna/japanese-gpt2-mediumをダウンロードします (310MB)。句読点・段落・誤字・自然な表現をすべて補正します。")
        format_layout.addWidget(self.enable_llm_correction_check, 2, 1)

        # 語彙管理ボタン (グリッドレイアウトに適応)
        self.manage_vocabulary_button = QPushButton("📚 語彙管理")
        self.manage_vocabulary_button.setStyleSheet("font-size: 10px; padding: 4px;")  # さらにコンパクト化
        self.manage_vocabulary_button.setToolTip("ホットワードと置換ルールを管理")
        self.manage_vocabulary_button.clicked.connect(self.open_vocabulary_dialog)
        if not VOCABULARY_DIALOG_AVAILABLE:
            self.manage_vocabulary_button.setEnabled(False)
        format_layout.addWidget(self.manage_vocabulary_button, 4, 0, 1, 2)  # 2カラム跨ぎ

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # 高度な設定グループ（コンパクト化）
        advanced_group = QGroupBox("高度な設定")
        advanced_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; }")
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(2)  # スペース削減
        advanced_layout.setContentsMargins(5, 5, 5, 5)  # マージン削減

        # 監視間隔設定
        interval_layout = QHBoxLayout()
        interval_label = QLabel("監視間隔:")
        interval_label.setStyleSheet("font-size: 10px;")
        interval_layout.addWidget(interval_label)

        self.monitor_interval_spinbox = QSpinBox()
        self.monitor_interval_spinbox.setRange(
            UIConstants.MONITOR_INTERVAL_MIN,
            UIConstants.MONITOR_INTERVAL_MAX
        )
        self.monitor_interval_spinbox.setValue(UIConstants.MONITOR_INTERVAL_DEFAULT)
        self.monitor_interval_spinbox.setSuffix(" 秒")
        self.monitor_interval_spinbox.setToolTip(
            f"フォルダ監視のチェック間隔（{UIConstants.MONITOR_INTERVAL_MIN}〜{UIConstants.MONITOR_INTERVAL_MAX}秒）"
        )
        self.monitor_interval_spinbox.valueChanged.connect(self.on_monitor_interval_changed)
        interval_layout.addWidget(self.monitor_interval_spinbox)
        interval_layout.addStretch()

        advanced_layout.addLayout(interval_layout)

        # Windows起動時に自動起動
        self.startup_check = QCheckBox("Windows起動時に自動起動")
        self.startup_check.setStyleSheet("font-size: 10px;")  # コンパクト化
        self.startup_check.setChecked(False)
        self.startup_check.setToolTip("Windowsスタートアップに登録します")
        self.startup_check.clicked.connect(self.on_startup_toggled)
        advanced_layout.addWidget(self.startup_check)

        # 完了ファイル自動移動
        self.auto_move_check = QCheckBox("完了ファイルを自動移動")
        self.auto_move_check.setStyleSheet("font-size: 10px;")  # コンパクト化
        self.auto_move_check.setChecked(False)
        self.auto_move_check.setToolTip("文字起こし完了後、ファイルを指定フォルダに移動します")
        self.auto_move_check.clicked.connect(self.on_auto_move_toggled)
        advanced_layout.addWidget(self.auto_move_check)

        # 移動先フォルダ選択
        move_folder_layout = QHBoxLayout()
        self.select_completed_folder_button = QPushButton("移動先フォルダ選択")
        self.select_completed_folder_button.setStyleSheet("font-size: 10px; padding: 3px;")  # コンパクト化
        self.select_completed_folder_button.clicked.connect(self.select_completed_folder)
        self.select_completed_folder_button.setEnabled(False)
        move_folder_layout.addWidget(self.select_completed_folder_button)

        self.completed_folder_label = QLabel("未設定")
        self.completed_folder_label.setStyleSheet("font-size: 9px; color: #666;")  # コンパクト化
        move_folder_layout.addWidget(self.completed_folder_label)
        move_folder_layout.addStretch()

        advanced_layout.addLayout(move_folder_layout)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # 文字起こしボタン (280px対応)
        self.transcribe_button = QPushButton("開始")
        self.transcribe_button.setStyleSheet("font-size: 14px; padding: 8px; background-color: #4CAF50; color: white; font-weight: bold;")
        self.transcribe_button.setToolTip("選択したファイルの文字起こしを開始します（MP3, WAV, MP4などに対応）")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.start_transcription)
        layout.addWidget(self.transcribe_button)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 結果表示エリアと保存ボタンを削除（ファイル自動保存のため不要）
        # スペースを大幅に節約

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
        self.update_tray_tooltip()  # ツールチップ更新

        logger.info("Transcription started")

    def update_progress(self, value):
        """進捗更新"""
        self.progress_bar.setValue(value)

    def transcription_finished(self, text):
        """文字起こし完了"""
        # LLM補正が有効な場合は句読点・段落をLLMに任せる
        use_llm = self.enable_llm_correction_check.isChecked()

        # テキスト整形オプションを適用
        formatted_text = self.formatter.format_all(
            text,
            remove_fillers=self.remove_fillers_check.isChecked(),
            add_punctuation=not use_llm,  # LLM OFFの場合はルールベース句読点を使用
            format_paragraphs=not use_llm,  # LLM OFFの場合はルールベース段落整形を使用
            clean_repeated=True
        )

        # AI補正を適用（チェックボックスで制御）
        if self.enable_llm_correction_check.isChecked():
            try:
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
                            f"AI補正のロードに失敗しました: {str(e)}\n補正なしで続行します。"
                        )
                        # 補正なしで続行
                        self.transcribe_button.setEnabled(True)
                        self.file_button.setEnabled(True)
                        self.progress_bar.setVisible(False)
                        self.auto_save_text(formatted_text)
                        self.statusBar().showMessage("文字起こし完了!")
                        QMessageBox.information(self, "完了", "文字起こしが完了しました")
                        logger.info("Transcription finished successfully")
                        return

                self.statusBar().showMessage("AIで文章を補正中...")
                QApplication.processEvents()  # UI更新
                formatted_text = self.advanced_corrector.correct_text(formatted_text)
                logger.info("Advanced LLM correction completed")

            except Exception as e:
                logger.error(f"LLM correction failed: {e}")
                QMessageBox.warning(
                    self,
                    "警告",
                    f"AI補正に失敗しました: {str(e)}\n元のテキストを使用します。"
                )

        # 結果表示エリア削除（自動保存のみ）
        self.transcribe_button.setEnabled(True)
        self.file_button.setEnabled(True)
        self.batch_file_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.update_tray_tooltip()  # ツールチップ更新

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
        """文字起こし結果を自動保存（パストラバーサル対策済み）"""
        try:
            # 元の音声ファイル名から出力ファイル名を生成
            if hasattr(self, 'selected_file'):
                base_name = os.path.splitext(self.selected_file)[0]
                output_file = f"{base_name}_文字起こし.txt"

                # パストラバーサル脆弱性対策: パスを検証
                try:
                    # 出力ファイルパスを検証（存在しなくてもOK、.txt拡張子のみ許可）
                    validated_path = Validator.validate_file_path(
                        output_file,
                        allowed_extensions=[".txt"],
                        must_exist=False
                    )

                    # 実パスが元ファイルの親ディレクトリ内にあるか確認
                    original_dir = os.path.realpath(os.path.dirname(self.selected_file))
                    real_save_path = os.path.realpath(str(validated_path))
                    real_save_dir = os.path.dirname(real_save_path)

                    if not real_save_dir.startswith(original_dir):
                        raise ValidationError(f"Path traversal detected: {output_file}")

                    # ファイルに保存
                    with open(str(validated_path), 'w', encoding='utf-8') as f:
                        f.write(text)

                    logger.info(f"Auto-saved transcription to: {validated_path}")
                    self.statusBar().showMessage(f"自動保存: {os.path.basename(str(validated_path))}")

                except ValidationError as e:
                    logger.error(f"Invalid save path: {e}")
                    QMessageBox.warning(self, "エラー", f"保存パスが不正です: {e}")

        except Exception as e:
            logger.error(f"Auto-save failed: {e}")
            # 自動保存失敗はエラーダイアログを表示しない（ユーザー体験を損なわないため）

    # save_textとclear_resultsメソッドを削除（結果表示エリア削除のため不要）
    # 自動保存機能（auto_save_text）は残す

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

        self.batch_worker = BatchTranscriptionWorker(
            self.batch_files,
            enable_diarization=enable_diarization,
            max_workers=UIConstants.BATCH_WORKERS_DEFAULT,
            formatter=self.formatter,
            use_llm_correction=False  # バッチ処理ではLLM補正をスキップ
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

        # 結果表示（結果エリア削除、ダイアログのみ）
        result_message = f"バッチ処理完了!\n\n"
        result_message += f"総ファイル数: {total}\n"
        result_message += f"成功: {success_count}\n"
        result_message += f"失敗: {failed_count}\n\n"
        result_message += f"各ファイルは元のファイルと同じフォルダに保存されています。"

        self.statusBar().showMessage(f"バッチ処理完了: {success_count}成功, {failed_count}失敗")
        QMessageBox.information(self, "完了", result_message)
        logger.info(f"Batch processing finished: {success_count} success, {failed_count} failed")

    def init_tray_icon(self):
        """システムトレイアイコン初期化"""
        # トレイアイコン作成
        self.tray_icon = QSystemTrayIcon(self)

        # アイコンファイルが存在すればそれを使用、なければ自作アイコン
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
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

    def update_tray_tooltip(self):
        """システムトレイアイコンのツールチップを更新"""
        # 基本情報
        tooltip = "KotobaTranscriber\n"

        # フォルダ監視状態
        if self.folder_monitor and self.folder_monitor.running:
            tooltip += "📁 フォルダ監視: 実行中\n"
        else:
            tooltip += "📁 フォルダ監視: 停止中\n"

        # 処理中ファイル数
        processing_count = len(self.processing_files)
        if processing_count > 0:
            tooltip += f"⚙️ 処理中: {processing_count}ファイル\n"

        # 統計情報
        if self.total_processed > 0 or self.total_failed > 0:
            tooltip += f"✅ 完了: {self.total_processed}件"
            if self.total_failed > 0:
                tooltip += f" | ❌ 失敗: {self.total_failed}件"

        self.tray_icon.setToolTip(tooltip.strip())

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

        # 通常の文字起こしワーカー停止
        if self.worker and self.worker.isRunning():
            logger.info("Stopping transcription worker...")
            self.worker.quit()
            if not self.worker.wait(10000):  # 10秒タイムアウト
                logger.warning("Transcription worker did not finish within timeout, terminating...")
                self.worker.terminate()
                self.worker.wait()

        # バッチ処理ワーカー停止
        if self.batch_worker and self.batch_worker.isRunning():
            logger.info("Stopping batch worker...")
            self.batch_worker.cancel()  # キャンセルリクエスト
            if not self.batch_worker.wait(30000):  # 30秒タイムアウト (複数ファイル処理中の可能性)
                logger.warning("Batch worker did not finish within timeout, terminating...")
                self.batch_worker.terminate()
                self.batch_worker.wait()


        # フォルダ監視停止
        if self.folder_monitor and self.folder_monitor.isRunning():
            logger.info("Stopping folder monitor...")
            self.folder_monitor.stop()
            if not self.folder_monitor.wait(5000):  # 5秒タイムアウト
                logger.warning("Folder monitor did not finish within timeout, terminating...")
                self.folder_monitor.terminate()
                self.folder_monitor.wait()

        # トレイアイコン非表示
        self.tray_icon.hide()

        logger.info("Application quitting - all worker threads cleaned up")

        # Pythonプロセスを確実に終了
        QApplication.quit()
        sys.exit(0)

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

            # 設定を保存
            self.settings.set('monitored_folder', folder_path)
            self.settings.save_debounced()

    def toggle_folder_monitor(self):
        """フォルダ監視開始/停止"""
        # 監視中の場合は停止（並列終了で高速化）
        if self.folder_monitor and self.folder_monitor.isRunning():
            # 進行中のバッチ処理とフォルダ監視を並列停止
            if self.batch_worker and self.batch_worker.isRunning():
                logger.info("Stopping monitor batch worker and folder monitor in parallel...")
                self.batch_worker.cancel()
                self.folder_monitor.stop()

                # 両方のスレッドを並列で待機
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    batch_future = executor.submit(lambda: self.batch_worker.wait(10000))
                    monitor_future = executor.submit(lambda: self.folder_monitor.wait(5000))

                    # バッチワーカーの終了確認
                    if not batch_future.result():
                        logger.warning("Monitor batch worker did not finish, terminating...")
                        self.batch_worker.terminate()
                        self.batch_worker.wait()

                    # フォルダモニターの終了確認
                    if not monitor_future.result():
                        logger.warning("Folder monitor did not finish, terminating...")
                        self.folder_monitor.terminate()
                        self.folder_monitor.wait()

                self.batch_worker = None
            else:
                # バッチワーカーがない場合は通常の停止
                self.folder_monitor.stop()
                if not self.folder_monitor.wait(5000):
                    logger.warning("Folder monitor did not finish, terminating...")
                    self.folder_monitor.terminate()
                    self.folder_monitor.wait()

            self.folder_monitor = None

            self.monitor_folder_button.setText("監視")
            self.monitor_folder_button.setStyleSheet("font-size: 12px; padding: 5px; background-color: #FF9800; color: white; font-weight: bold;")
            self.statusBar().showMessage("フォルダ監視を停止しました")
            self.update_tray_tooltip()  # ツールチップ更新
            logger.info("Folder monitoring stopped")
            return

        # 監視フォルダが未設定の場合
        if not self.monitored_folder:
            reply = QMessageBox.question(
                self,
                "監視フォルダ未設定",
                "監視フォルダが設定されていません。\n今すぐフォルダを選択しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.select_monitor_folder()
                # フォルダ選択後も未設定なら中断
                if not self.monitored_folder:
                    return
            else:
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

            self.monitor_folder_button.setText("停止")
            self.monitor_folder_button.setStyleSheet("font-size: 12px; padding: 5px; background-color: #F44336; color: white; font-weight: bold;")
            self.statusBar().showMessage(f"フォルダ監視開始: {os.path.basename(self.monitored_folder)}")
            self.update_tray_tooltip()  # ツールチップ更新
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

    def cleanup_expired_processing_files(self):
        """TTLを超えた処理中ファイルをクリーンアップ"""
        current_time = datetime.now().timestamp()
        with self.processing_files_lock:
            expired_files = [
                file_path for file_path, added_time in self.processing_files.items()
                if current_time - added_time > self.processing_files_ttl
            ]
            for file_path in expired_files:
                del self.processing_files[file_path]
                logger.warning(f"Removed expired file from processing list (TTL exceeded): {file_path}")

    def on_monitor_new_files(self, files: list):
        """監視フォルダで新規ファイル検出時の処理"""
        logger.info(f"New files detected: {len(files)} files")

        # 既存のバッチ処理が実行中の場合はスキップ
        if self.batch_worker and self.batch_worker.isRunning():
            logger.warning("Previous batch worker is still running, skipping new files")
            self.statusBar().showMessage("前回の処理が完了していません。次回の監視で処理します...")
            return

        # TTL期限切れファイルをクリーンアップ
        self.cleanup_expired_processing_files()

        # 重複処理防止: 既に処理中のファイルをフィルタ（スレッドセーフ）
        current_time = datetime.now().timestamp()
        with self.processing_files_lock:
            new_files = [f for f in files if f not in self.processing_files]

            if not new_files:
                logger.info("All detected files are already being processed")
                return

            # 処理中リストに追加（タイムスタンプ付き）
            for f in new_files:
                self.processing_files[f] = current_time

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

        self.batch_worker = BatchTranscriptionWorker(
            new_files,
            enable_diarization=enable_diarization,
            max_workers=UIConstants.MONITOR_BATCH_WORKERS,
            formatter=self.formatter,
            use_llm_correction=False  # バッチ処理ではLLM補正をスキップ
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

        # 処理中リストから必ず削除（スレッドセーフ）
        with self.processing_files_lock:
            if file_path in self.processing_files:
                del self.processing_files[file_path]
                logger.debug(f"Removed from processing_files: {filename}")

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
                        # 移動したファイルを処理済みリストから削除
                        if self.folder_monitor:
                            self.folder_monitor.remove_from_processed(file_path)
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
        # 処理中リストのクリーンアップ（念のため）
        with self.processing_files_lock:
            if self.processing_files:
                logger.warning(f"Cleaning up {len(self.processing_files)} remaining files from processing list")
                self.processing_files.clear()

        # 統計情報表示を更新
        self.update_stats_display()

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

        # 設定を保存
        self.settings.set('auto_move_completed', checked)
        self.settings.save_debounced()

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

            # 設定を保存
            self.settings.set('completed_folder', folder_path)
            self.settings.save_debounced()

    def open_vocabulary_dialog(self):
        """カスタム語彙管理ダイアログを開く"""
        if not VOCABULARY_DIALOG_AVAILABLE:
            QMessageBox.warning(
                self,
                "利用不可",
                "カスタム語彙管理機能が利用できません。\nvocabulary_dialog.pyを確認してください。"
            )
            return

        try:
            dialog = VocabularyDialog(self)
            dialog.exec_()
            logger.info("Vocabulary dialog opened")
        except Exception as e:
            logger.error(f"Failed to open vocabulary dialog: {e}")
            QMessageBox.critical(
                self,
                "エラー",
                f"語彙管理ダイアログを開けませんでした:\n{str(e)}"
            )

    def connect_config_sync(self):
        """チェックボックスとconfig_managerの同期を設定"""
        # 音声前処理チェックボックス
        self.enable_preprocessing_check.stateChanged.connect(
            lambda state: self.config.set("audio.preprocessing.enabled", state == Qt.Checked)
        )

        # カスタム語彙チェックボックス
        self.enable_vocabulary_check.stateChanged.connect(
            lambda state: self.config.set("vocabulary.enabled", state == Qt.Checked)
        )

        logger.info("Config sync connected for preprocessing and vocabulary checkboxes")


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

    def _auto_start_monitoring_if_needed(self):
        """
        自動監視開始: 監視フォルダが設定されており、未処理ファイルが存在する場合に監視を開始
        """
        try:
            # 監視フォルダが設定されていない場合はスキップ
            if not self.monitored_folder:
                logger.debug("Auto-start skipped: No monitored folder configured")
                return

            # フォルダの存在確認
            from pathlib import Path
            folder_path = Path(self.monitored_folder)
            if not folder_path.exists() or not folder_path.is_dir():
                logger.warning(f"Auto-start skipped: Monitored folder does not exist: {self.monitored_folder}")
                return

            # 未処理ファイルの確認
            from folder_monitor import FolderMonitor
            audio_video_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma', '.opus', '.amr',
                                     '.mp4', '.avi', '.mov', '.mkv', '.3gp', '.webm']

            # サポートされている形式のファイルを検索
            all_files = []
            for ext in audio_video_extensions:
                all_files.extend(list(folder_path.glob(f'*{ext}')))
                all_files.extend(list(folder_path.glob(f'*{ext.upper()}')))

            # 処理済みファイルリストを読み込み
            processed_files_path = folder_path / ".processed_files.txt"
            processed_files = set()
            if processed_files_path.exists():
                try:
                    with open(processed_files_path, 'r', encoding='utf-8') as f:
                        processed_files = set(line.strip() for line in f if line.strip())
                except Exception as e:
                    logger.warning(f"Failed to load processed files list: {e}")

            # 未処理ファイルをフィルタ
            unprocessed_files = [str(f) for f in all_files if str(f) not in processed_files]

            if not unprocessed_files:
                logger.info("Auto-start skipped: No unprocessed files found in monitored folder")
                return

            # 未処理ファイルが存在する場合、自動的に監視を開始
            logger.info(f"Auto-starting monitoring: {len(unprocessed_files)} unprocessed files found")

            # 監視開始（既存のロジックを再利用）
            self.folder_monitor = FolderMonitor(
                self.monitored_folder,
                check_interval=self.monitor_interval_spinbox.value()
            )

            # シグナル接続
            self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
            self.folder_monitor.status_update.connect(self.on_monitor_status)

            # 監視スレッド開始
            self.folder_monitor.start()

            # UI更新
            self.monitor_folder_button.setText("フォルダ監視停止")
            self.monitor_folder_button.setStyleSheet("font-size: 12px; padding: 6px; background-color: #F44336; color: white;")
            self.statusBar().showMessage(f"自動監視開始: {os.path.basename(self.monitored_folder)} ({len(unprocessed_files)}個の未処理ファイル)")
            logger.info(f"Folder monitoring auto-started: {self.monitored_folder}")

            # トレイ通知
            self.tray_icon.showMessage(
                "自動監視開始",
                f"{os.path.basename(self.monitored_folder)}\n{len(unprocessed_files)}個の未処理ファイルを検出",
                QSystemTrayIcon.Information,
                3000
            )

        except Exception as e:
            logger.error(f"Failed to auto-start monitoring: {e}", exc_info=True)

    def load_ui_settings(self):
        """UI設定を復元（検証付き）"""
        try:
            # ウィンドウジオメトリを検証して復元
            width = self.settings.get('window.width', 900)
            height = self.settings.get('window.height', 700)
            x = self.settings.get('window.x', 100)
            y = self.settings.get('window.y', 100)

            # 範囲検証
            width = max(UIConstants.WINDOW_MIN_WIDTH, min(UIConstants.WINDOW_MAX_WIDTH, width))
            height = max(UIConstants.WINDOW_MIN_HEIGHT, min(UIConstants.WINDOW_MAX_HEIGHT, height))
            x = max(0, min(UIConstants.WINDOW_MAX_WIDTH, x))
            y = max(0, min(UIConstants.WINDOW_MAX_HEIGHT, y))

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
            monitor_interval = self.settings.get('monitor_interval', UIConstants.MONITOR_INTERVAL_DEFAULT)
            monitor_interval = max(UIConstants.MONITOR_INTERVAL_MIN, min(UIConstants.MONITOR_INTERVAL_MAX, monitor_interval))
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
            self.enable_diarization_check.setChecked(
                bool(self.settings.get('enable_diarization', False))
            )
            self.enable_llm_correction_check.setChecked(
                bool(self.settings.get('enable_llm_correction', True))  # デフォルトON
            )

            # 精度向上設定を復元
            self.enable_preprocessing_check.setChecked(
                bool(self.settings.get('enable_preprocessing', False))
            )
            self.enable_vocabulary_check.setChecked(
                bool(self.settings.get('enable_vocabulary', False))
            )

            logger.info("UI settings restored successfully")

            # 自動監視開始: 監視フォルダが設定されており、未処理ファイルが存在する場合
            self._auto_start_monitoring_if_needed()

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
            self.settings.set('enable_diarization', self.enable_diarization_check.isChecked())
            self.settings.set('enable_llm_correction', self.enable_llm_correction_check.isChecked())

            # 精度向上設定を保存
            self.settings.set('enable_preprocessing', self.enable_preprocessing_check.isChecked())
            self.settings.set('enable_vocabulary', self.enable_vocabulary_check.isChecked())

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
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='KotobaTranscriber - 日本語音声文字起こしアプリケーション',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--dangerously-skip-permissions',
        action='store_true',
        help='DANGEROUS: Skip all permission and security checks. Use only for development/debugging.'
    )
    args = parser.parse_args()

    # Set runtime configuration based on CLI arguments
    if args.dangerously_skip_permissions:
        RuntimeConfig.set_skip_permissions(True)
        logger.warning("⚠️  DANGEROUS: Permission checks are DISABLED. Use only for development!")

    # 多重起動防止
    mutex_name = "Global\\KotobaTranscriber_SingleInstance_Mutex"
    mutex = win32event.CreateMutex(None, False, mutex_name)

    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        # 既に起動中
        logger.warning("Application is already running")
        QApplication(sys.argv)  # メッセージボックス表示のため必要
        QMessageBox.warning(
            None,
            "多重起動エラー",
            "KotobaTranscriberは既に起動しています。\n\nシステムトレイにアイコンがある場合は、そちらをクリックしてウィンドウを表示してください。"
        )
        return

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # モダンなスタイル

    # トレイに最小化できるよう、最後のウィンドウが閉じてもアプリを終了しない
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    logger.info("Application started")

    try:
        sys.exit(app.exec_())
    finally:
        # ミューテックスの解放
        win32api.CloseHandle(mutex)


if __name__ == "__main__":
    main()
