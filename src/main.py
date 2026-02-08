"""
KotobaTranscriber - メインアプリケーション
日本語音声文字起こしアプリケーション（ファイル文字起こし専用）
フォルダ監視機能は monitor_app.py を参照
"""

import sys
import os
from pathlib import Path
from typing import Optional
import ctypes
import ctypes.wintypes
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QFileDialog, QLabel, QProgressBar, QMessageBox,
    QCheckBox, QGroupBox, QListWidget, QListWidgetItem, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import logging

from transcription_engine import TranscriptionEngine
from text_formatter import TextFormatter
from llm_corrector_standalone import StandaloneLLMCorrector
from app_settings import AppSettings
from config_manager import get_config
from validators import Validator, ValidationError
from workers import (
    TranscriptionWorker,
    BatchTranscriptionWorker,
    SharedConstants,
    stop_worker,
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


# UI定数の定義（メインアプリ固有）
class UIConstants(SharedConstants):
    """メインアプリ固有のUI定数"""
    # スライダー範囲
    VAD_SLIDER_MIN = 5
    VAD_SLIDER_MAX = 50
    VAD_SLIDER_DEFAULT = 10

    # ウィンドウサイズ制限
    WINDOW_MIN_WIDTH = 400
    WINDOW_MIN_HEIGHT = 300

    # 段落整形デフォルト
    SENTENCES_PER_PARAGRAPH = 4


class MainWindow(QMainWindow):
    """メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.batch_worker = None
        self.selected_file = None
        self.formatter = TextFormatter()
        self.diarizer = None  # 話者分離は必要時に初期化
        self.advanced_corrector = None  # 高度AI補正（常に使用）
        self.batch_files = []  # バッチ処理用ファイルリスト

        # 設定管理
        self.settings = AppSettings()
        self.settings.load()  # 設定を読み込む

        # Config Manager (YAML設定)
        self.config = get_config()

        self.init_ui()
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

        self.setGeometry(100, 100, 280, 400)

        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(3)

        # ファイル選択ボタン
        file_button_layout = QHBoxLayout()

        self.file_button = QPushButton("単一")
        self.file_button.setStyleSheet("font-size: 12px; padding: 5px; font-weight: bold;")
        self.file_button.setToolTip("単一の音声/動画ファイルを選択して文字起こしします")
        self.file_button.clicked.connect(self.select_file)
        file_button_layout.addWidget(self.file_button)

        self.batch_file_button = QPushButton("複数")
        self.batch_file_button.setStyleSheet("font-size: 12px; padding: 5px; background-color: #2196F3; color: white; font-weight: bold;")
        self.batch_file_button.setToolTip("複数のファイルを一度に選択してバッチ処理します")
        self.batch_file_button.clicked.connect(self.select_batch_files)
        file_button_layout.addWidget(self.batch_file_button)

        main_layout.addLayout(file_button_layout)

        # 選択ファイル表示
        self.file_label = QLabel("ファイル: 未選択")
        self.file_label.setStyleSheet("margin: 2px; font-size: 10px;")
        main_layout.addWidget(self.file_label)

        # バッチファイルリスト
        self.batch_file_list = QListWidget()
        self.batch_file_list.setMaximumHeight(80)
        self.batch_file_list.setVisible(False)
        main_layout.addWidget(self.batch_file_list)

        # バッチリストクリアボタン
        self.clear_batch_button = QPushButton("リストをクリア")
        self.clear_batch_button.setStyleSheet("font-size: 10px; padding: 3px;")
        self.clear_batch_button.clicked.connect(self.clear_batch_list)
        self.clear_batch_button.setVisible(False)
        main_layout.addWidget(self.clear_batch_button)

        # テキスト整形オプション (2カラムグリッドレイアウト)
        format_group = QGroupBox("テキスト整形オプション")
        format_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; }")
        format_layout = QGridLayout()
        format_layout.setSpacing(2)
        format_layout.setContentsMargins(5, 5, 5, 5)

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
        self.enable_llm_correction_check.setChecked(True)
        self.enable_llm_correction_check.setToolTip("transformersベースの高度な補正。初回のみrinna/japanese-gpt2-mediumをダウンロードします (310MB)。句読点・段落・誤字・自然な表現をすべて補正します。")
        format_layout.addWidget(self.enable_llm_correction_check, 2, 1)

        # 語彙管理ボタン
        self.manage_vocabulary_button = QPushButton("語彙管理")
        self.manage_vocabulary_button.setStyleSheet("font-size: 10px; padding: 4px;")
        self.manage_vocabulary_button.setToolTip("ホットワードと置換ルールを管理")
        self.manage_vocabulary_button.clicked.connect(self.open_vocabulary_dialog)
        if not VOCABULARY_DIALOG_AVAILABLE:
            self.manage_vocabulary_button.setEnabled(False)
        format_layout.addWidget(self.manage_vocabulary_button, 4, 0, 1, 2)

        format_group.setLayout(format_layout)
        main_layout.addWidget(format_group)

        # 文字起こしボタン
        self.transcribe_button = QPushButton("開始")
        self.transcribe_button.setStyleSheet("font-size: 14px; padding: 8px; background-color: #4CAF50; color: white; font-weight: bold;")
        self.transcribe_button.setToolTip("選択したファイルの文字起こしを開始します（MP3, WAV, MP4などに対応）")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.start_transcription)
        main_layout.addWidget(self.transcribe_button)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ステータスバー
        self.statusBar().showMessage("準備完了")

        logger.info("UI initialized")

    def select_file(self):
        """音声ファイル選択"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "音声ファイルを選択",
            "",
            UIConstants.AUDIO_FILE_FILTER
        )

        if file_path:
            self.selected_file = file_path
            filename = os.path.basename(file_path)
            self.file_label.setText(f"ファイル: {filename}")
            self.transcribe_button.setEnabled(True)
            self.statusBar().showMessage(f"ファイル選択: {filename}")
            logger.info(f"File selected: {file_path}")

    def _set_processing_ui(self, processing: bool):
        """処理中/待機中のUI状態を切り替え"""
        if processing:
            self.transcribe_button.setEnabled(False)
            self.file_button.setEnabled(False)
            self.batch_file_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
        else:
            has_file = bool(self.selected_file) or bool(getattr(self, 'batch_files', None))
            self.transcribe_button.setEnabled(has_file)
            self.file_button.setEnabled(True)
            self.batch_file_button.setEnabled(True)
            self.progress_bar.setVisible(False)

    def start_transcription(self):
        """文字起こし開始（バッチ/単一を自動判定）"""
        # バッチ処理モードかチェック
        if self.batch_files:
            self.start_batch_transcription()
            return

        # 単一ファイル処理
        if not self.selected_file:
            QMessageBox.warning(self, "警告", "音声ファイルを選択してください")
            return

        # UI状態変更
        self._set_processing_ui(True)
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
        # LLM補正が有効な場合は句読点・段落をLLMに任せる
        use_llm = self.enable_llm_correction_check.isChecked()

        # テキスト整形オプションを適用
        try:
            formatted_text = self.formatter.format_all(
                text,
                remove_fillers=self.remove_fillers_check.isChecked(),
                add_punctuation=not use_llm,
                format_paragraphs=not use_llm,
                clean_repeated=True
            )
        except Exception as e:
            logger.warning(f"Text formatting failed, using raw text: {e}")
            formatted_text = text

        # AI補正を適用（チェックボックスで制御）
        if self.enable_llm_correction_check.isChecked():
            try:
                logger.info("Applying advanced LLM correction...")

                # 高度な補正器を初期化（初回のみ）
                if self.advanced_corrector is None:
                    self.statusBar().showMessage("AIモデルをダウンロード中... (初回のみ310MB、数分かかります)")
                    QApplication.processEvents()

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
                        self._set_processing_ui(False)
                        self.auto_save_text(formatted_text)
                        self.statusBar().showMessage("文字起こし完了!")
                        QMessageBox.information(self, "完了", "文字起こしが完了しました")
                        logger.info("Transcription finished successfully")
                        return

                self.statusBar().showMessage("AIで文章を補正中...")
                QApplication.processEvents()
                formatted_text = self.advanced_corrector.correct_text(formatted_text)
                logger.info("Advanced LLM correction completed")

            except Exception as e:
                logger.error(f"LLM correction failed: {e}")
                QMessageBox.warning(
                    self,
                    "警告",
                    f"AI補正に失敗しました: {str(e)}\n元のテキストを使用します。"
                )

        self._set_processing_ui(False)

        # 自動保存
        self.auto_save_text(formatted_text)

        self.statusBar().showMessage("文字起こし完了!")
        QMessageBox.information(self, "完了", "文字起こしが完了しました")
        logger.info("Transcription finished successfully")
        self.worker = None

    def transcription_error(self, error_msg):
        """エラー処理"""
        self._set_processing_ui(False)
        self.statusBar().showMessage("エラー発生")
        QMessageBox.critical(self, "エラー", error_msg)
        logger.error(f"Transcription error: {error_msg}")
        self.worker = None

    def auto_save_text(self, text: str):
        """文字起こし結果を自動保存（パストラバーサル対策済み）"""
        try:
            if self.selected_file:
                base_name = os.path.splitext(self.selected_file)[0]
                output_file = f"{base_name}_文字起こし.txt"

                try:
                    validated_path = Validator.validate_file_path(
                        output_file,
                        allowed_extensions=[".txt"],
                        must_exist=False
                    )

                    original_dir = os.path.realpath(os.path.dirname(self.selected_file))
                    real_save_path = os.path.realpath(str(validated_path))
                    real_save_dir = os.path.dirname(real_save_path)

                    if not (real_save_dir + os.sep).startswith(original_dir + os.sep):
                        raise ValidationError(f"Path traversal detected: {output_file}")

                    with open(str(validated_path), 'w', encoding='utf-8') as f:
                        f.write(text)

                    logger.info(f"Auto-saved transcription to: {validated_path}")
                    self.statusBar().showMessage(f"自動保存: {os.path.basename(str(validated_path))}")

                except ValidationError as e:
                    logger.error(f"Invalid save path: {e}")
                    QMessageBox.warning(self, "エラー", f"保存パスが不正です: {e}")

        except Exception as e:
            logger.error(f"Auto-save failed: {e}")

    def select_batch_files(self):
        """複数ファイル選択"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "複数の音声ファイルを選択",
            "",
            UIConstants.AUDIO_FILE_FILTER
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

        self._set_processing_ui(True)
        self.statusBar().showMessage(f"バッチ処理中... (0/{len(self.batch_files)})")

        enable_diarization = self.enable_diarization_check.isChecked()

        self.batch_worker = BatchTranscriptionWorker(
            self.batch_files,
            enable_diarization=enable_diarization,
            max_workers=UIConstants.BATCH_WORKERS_DEFAULT,
            formatter=self.formatter,
            use_llm_correction=False
        )

        self.batch_worker.progress.connect(self.update_batch_progress)
        self.batch_worker.file_finished.connect(self.batch_file_finished)
        self.batch_worker.all_finished.connect(self.batch_all_finished)
        self.batch_worker.error.connect(self.transcription_error)
        self.batch_worker.start()

        logger.info(f"Batch processing started: {len(self.batch_files)} files")

    def update_batch_progress(self, completed: int, total: int, filename: str):
        """バッチ処理進捗更新"""
        progress_percent = int((completed / total) * 100) if total > 0 else 0
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

        self._set_processing_ui(False)

        result_message = f"バッチ処理完了!\n\n"
        result_message += f"総ファイル数: {total}\n"
        result_message += f"成功: {success_count}\n"
        result_message += f"失敗: {failed_count}\n\n"
        result_message += f"各ファイルは元のファイルと同じフォルダに保存されています。"

        self.statusBar().showMessage(f"バッチ処理完了: {success_count}成功, {failed_count}失敗")
        QMessageBox.information(self, "完了", result_message)
        logger.info(f"Batch processing finished: {success_count} success, {failed_count} failed")
        self.batch_worker = None

    def quit_application(self):
        """アプリケーション終了"""
        self.save_ui_settings()

        stop_worker(self.worker, "transcription worker",
                    timeout=UIConstants.THREAD_WAIT_TIMEOUT, cancel=True)
        stop_worker(self.batch_worker, "batch worker",
                    timeout=UIConstants.BATCH_WAIT_TIMEOUT, cancel=True)

        # LLMモデルの解放
        if self.advanced_corrector is not None:
            try:
                self.advanced_corrector.unload_model()
            except Exception as e:
                logger.debug(f"Advanced corrector unload failed: {e}")
            self.advanced_corrector = None

        logger.info("Application quitting - all worker threads cleaned up")
        QApplication.quit()

    def closeEvent(self, event):
        """ウィンドウを閉じる時の処理"""
        self.quit_application()
        event.accept()

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
            result = dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                logger.info("Vocabulary dialog: changes accepted")
            else:
                logger.info("Vocabulary dialog: cancelled")
        except Exception as e:
            logger.error(f"Failed to open vocabulary dialog: {e}")
            QMessageBox.critical(
                self,
                "エラー",
                f"語彙管理ダイアログを開けませんでした:\n{str(e)}"
            )

    def connect_config_sync(self):
        """チェックボックスとconfig_managerの同期を設定"""
        self.enable_preprocessing_check.stateChanged.connect(
            lambda state: self.config.set("audio.preprocessing.enabled", state == Qt.CheckState.Checked.value)
        )

        self.enable_vocabulary_check.stateChanged.connect(
            lambda state: self.config.set("vocabulary.enabled", state == Qt.CheckState.Checked.value)
        )

        logger.info("Config sync connected for preprocessing and vocabulary checkboxes")

    def load_ui_settings(self):
        """UI設定を復元（検証付き）"""
        try:
            # ウィンドウジオメトリを検証して復元
            width = self.settings.get('window.width', 280)
            height = self.settings.get('window.height', 400)
            x = self.settings.get('window.x', 100)
            y = self.settings.get('window.y', 100)

            # 範囲検証
            width = max(UIConstants.WINDOW_MIN_WIDTH, min(UIConstants.WINDOW_MAX_WIDTH, width))
            height = max(UIConstants.WINDOW_MIN_HEIGHT, min(UIConstants.WINDOW_MAX_HEIGHT, height))
            x = max(0, min(UIConstants.WINDOW_MAX_WIDTH, x))
            y = max(0, min(UIConstants.WINDOW_MAX_HEIGHT, y))

            # 画面内に収まるかチェック
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                if x + width > screen_geometry.width():
                    x = max(0, screen_geometry.width() - width)
                if y + height > screen_geometry.height():
                    y = max(0, screen_geometry.height() - height)

            self.setGeometry(x, y, width, height)
            logger.info(f"Window geometry restored: {width}x{height} at ({x}, {y})")

            # テキスト整形オプションを復元
            self.remove_fillers_check.setChecked(
                bool(self.settings.get('remove_fillers', True))
            )
            self.enable_diarization_check.setChecked(
                bool(self.settings.get('enable_diarization', False))
            )
            self.enable_llm_correction_check.setChecked(
                bool(self.settings.get('enable_llm_correction', True))
            )

            # 精度向上設定を復元
            self.enable_preprocessing_check.setChecked(
                bool(self.settings.get('enable_preprocessing', False))
            )
            self.enable_vocabulary_check.setChecked(
                bool(self.settings.get('enable_vocabulary', False))
            )

            logger.info("UI settings restored successfully")

        except Exception as e:
            logger.error(f"Failed to load UI settings: {e}", exc_info=True)
            self.setGeometry(100, 100, 280, 400)

    def save_ui_settings(self):
        """UI設定を保存"""
        try:
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
    # 多重起動防止（ctypesで確実にGetLastErrorを取得）
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    mutex_name = "Local\\KotobaTranscriber_Main_Mutex"
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.get_last_error()

    if last_error == ERROR_ALREADY_EXISTS:
        logger.warning("Application is already running")
        QApplication(sys.argv)
        QMessageBox.warning(
            None,
            "多重起動エラー",
            "KotobaTranscriberは既に起動しています。"
        )
        kernel32.CloseHandle(mutex)
        return

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    logger.info("Application started")

    try:
        sys.exit(app.exec())
    finally:
        kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
