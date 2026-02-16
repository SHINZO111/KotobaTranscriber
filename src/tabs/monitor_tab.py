"""
フォルダ監視タブ
monitor_app.py の UI コンポーネントと機能を移植
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app_settings import AppSettings
from constants import SharedConstants
from folder_monitor import FolderMonitor
from text_formatter import TextFormatter
from workers import BatchTranscriptionWorker, stop_worker

logger = logging.getLogger(__name__)


class MonitorUIConstants(SharedConstants):
    """モニター固有のUI定数"""

    MONITOR_INTERVAL_MIN = 5
    MONITOR_INTERVAL_MAX = 9999
    MONITOR_INTERVAL_DEFAULT = 10

    WINDOW_MIN_WIDTH = 300
    WINDOW_MIN_HEIGHT = 400


class FolderMonitorTab(QWidget):
    """フォルダ監視タブ"""

    # カスタムシグナル: ステータスメッセージを親ウィンドウに通知
    status_message = Signal(str)
    # カスタムシグナル: 監視開始/停止通知
    monitoring_started = Signal()
    monitoring_stopped = Signal()

    def __init__(self):
        super().__init__()

        # フォルダ監視関連
        self.folder_monitor = None
        self.monitored_folder = None
        self.batch_worker = None
        self.formatter = TextFormatter()

        # 統計情報
        self.total_processed = 0
        self.total_failed = 0
        self.session_start_time = None

        # 処理中ファイル追跡（TTL機能付き）
        self.processing_files = {}
        self.processing_files_lock = threading.Lock()
        self.processing_files_ttl = SharedConstants.PROCESSING_FILES_TTL

        # 自動移動設定
        self.auto_move_completed = False
        self.completed_folder = None

        # 設定管理（統合アプリの unified_settings.json を使用）
        self.settings = AppSettings("unified_settings.json")
        self.settings.load()

        self.init_ui()
        self.load_ui_settings()

    def init_ui(self):
        """UI初期化"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # === フォルダ監視グループ ===
        monitor_group = QGroupBox("フォルダ監視")
        monitor_layout = QVBoxLayout()
        monitor_layout.setSpacing(8)
        monitor_layout.setContentsMargins(12, 16, 12, 12)

        # 監視ボタン行
        monitor_button_layout = QHBoxLayout()
        monitor_button_layout.setSpacing(8)

        self.monitor_folder_button = QPushButton("監視開始")
        self.monitor_folder_button.setObjectName("monitor")
        self.monitor_folder_button.setMinimumHeight(36)
        self.monitor_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.monitor_folder_button.setToolTip(
            "フォルダ監視を開始/停止します。監視中は新しいファイルを自動的に文字起こしします"
        )
        self.monitor_folder_button.clicked.connect(self.toggle_folder_monitor)
        monitor_button_layout.addWidget(self.monitor_folder_button)

        self.select_monitor_folder_button = QPushButton("フォルダ選択")
        self.select_monitor_folder_button.setObjectName("secondary")
        self.select_monitor_folder_button.setMinimumHeight(36)
        self.select_monitor_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_monitor_folder_button.setToolTip("監視するフォルダを選択します")
        self.select_monitor_folder_button.clicked.connect(self.select_monitor_folder)
        monitor_button_layout.addWidget(self.select_monitor_folder_button)

        monitor_layout.addLayout(monitor_button_layout)

        # 監視フォルダ表示
        self.monitor_folder_label = QLabel("監視フォルダ: 未設定")
        self.monitor_folder_label.setObjectName("subtitle")
        self.monitor_folder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        monitor_layout.addWidget(self.monitor_folder_label)

        # 監視間隔設定
        interval_layout = QHBoxLayout()
        interval_label = QLabel("監視間隔:")
        interval_layout.addWidget(interval_label)

        self.monitor_interval_spinbox = QSpinBox()
        self.monitor_interval_spinbox.setRange(
            MonitorUIConstants.MONITOR_INTERVAL_MIN, MonitorUIConstants.MONITOR_INTERVAL_MAX
        )
        self.monitor_interval_spinbox.setValue(MonitorUIConstants.MONITOR_INTERVAL_DEFAULT)
        self.monitor_interval_spinbox.setSuffix(" 秒")
        self.monitor_interval_spinbox.setToolTip(
            f"フォルダ監視のチェック間隔（{MonitorUIConstants.MONITOR_INTERVAL_MIN}〜{MonitorUIConstants.MONITOR_INTERVAL_MAX}秒）"
        )
        self.monitor_interval_spinbox.valueChanged.connect(self.on_monitor_interval_changed)
        interval_layout.addWidget(self.monitor_interval_spinbox)
        interval_layout.addStretch()

        monitor_layout.addLayout(interval_layout)
        monitor_group.setLayout(monitor_layout)
        main_layout.addWidget(monitor_group)

        # === テキスト整形オプション ===
        format_group = QGroupBox("処理オプション")
        format_layout = QVBoxLayout()
        format_layout.setSpacing(6)
        format_layout.setContentsMargins(12, 16, 12, 12)

        self.enable_diarization_check = QCheckBox("話者分離")
        self.enable_diarization_check.setChecked(False)
        self.enable_diarization_check.setToolTip("複数の話者を自動識別（SpeechBrain使用・無料）")
        format_layout.addWidget(self.enable_diarization_check)

        format_group.setLayout(format_layout)
        main_layout.addWidget(format_group)

        # === 統計情報表示 ===
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("background-color: #f5f5f5; border-radius: 3px; padding: 5px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(8, 6, 8, 6)

        self.stats_label = QLabel("処理済み: 0件 | 失敗: 0件 | 処理中: 0件")
        self.stats_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.stats_label)

        main_layout.addWidget(stats_frame)

        # === 自動移動設定グループ ===
        move_group = QGroupBox("自動移動設定")
        move_layout = QVBoxLayout()
        move_layout.setSpacing(6)
        move_layout.setContentsMargins(12, 16, 12, 12)

        # 自動移動チェックボックス
        self.auto_move_check = QCheckBox("処理完了ファイルを自動移動")
        self.auto_move_check.setChecked(False)
        self.auto_move_check.setToolTip("文字起こし完了後、ファイルを指定フォルダに移動します")
        self.auto_move_check.clicked.connect(self.on_auto_move_toggled)
        move_layout.addWidget(self.auto_move_check)

        # 完了フォルダ選択
        completed_folder_layout = QHBoxLayout()
        self.select_completed_folder_button = QPushButton("移動先フォルダ選択")
        self.select_completed_folder_button.setObjectName("flat")
        self.select_completed_folder_button.setMinimumHeight(28)
        self.select_completed_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_completed_folder_button.clicked.connect(self.select_completed_folder)
        self.select_completed_folder_button.setEnabled(False)
        completed_folder_layout.addWidget(self.select_completed_folder_button)

        self.completed_folder_label = QLabel("未設定")
        self.completed_folder_label.setObjectName("subtitle")
        completed_folder_layout.addWidget(self.completed_folder_label)
        completed_folder_layout.addStretch()

        move_layout.addLayout(completed_folder_layout)
        move_group.setLayout(move_layout)
        main_layout.addWidget(move_group)

        # スペーサー
        main_layout.addStretch(1)

        # === プログレスバー ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(8)
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        logger.info("FolderMonitorTab UI initialized")

    def select_monitor_folder(self):
        """監視フォルダ選択"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "監視するフォルダを選択", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder_path:
            self.monitored_folder = folder_path
            folder_name = os.path.basename(folder_path)
            self.monitor_folder_label.setText(f"監視フォルダ: {folder_name}")
            self.status_message.emit(f"監視フォルダ設定: {folder_name}")
            logger.info(f"Monitor folder selected: {folder_path}")

            self.settings.set("monitored_folder", folder_path)
            self.settings.save_debounced()

    def select_completed_folder(self):
        """完了フォルダ選択"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "完了ファイルの移動先フォルダを選択", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder_path:
            self.completed_folder = folder_path
            folder_name = os.path.basename(folder_path)
            self.completed_folder_label.setText(folder_name)
            self.status_message.emit(f"移動先フォルダ設定: {folder_name}")
            logger.info(f"Completed folder selected: {folder_path}")

            self.settings.set("completed_folder", folder_path)
            self.settings.save_debounced()

    def toggle_folder_monitor(self):
        """フォルダ監視開始/停止"""
        # 監視中の場合は停止
        if self.folder_monitor and self.folder_monitor.isRunning():
            if self.batch_worker and self.batch_worker.isRunning():
                logger.info("Stopping monitor batch worker and folder monitor in parallel...")
                self.batch_worker.cancel()
                self.folder_monitor.stop()

                with ThreadPoolExecutor(max_workers=2) as executor:
                    batch_future = executor.submit(lambda: self.batch_worker.wait(10000))
                    monitor_future = executor.submit(lambda: self.folder_monitor.wait(5000))

                    if not batch_future.result():
                        logger.warning("Monitor batch worker did not finish, terminating...")
                        self.batch_worker.terminate()
                        self.batch_worker.wait()

                    if not monitor_future.result():
                        logger.warning("Folder monitor did not finish, terminating...")
                        self.folder_monitor.terminate()
                        self.folder_monitor.wait()

                self.batch_worker = None
            else:
                stop_worker(self.folder_monitor, "folder monitor", timeout=5000, stop=True)

            self.folder_monitor = None

            self.monitor_folder_button.setText("監視開始")
            self.monitor_folder_button.setObjectName("monitor")
            self.status_message.emit("フォルダ監視を停止しました")

            # 停止シグナルを送信（トレイ通知用）
            self.monitoring_stopped.emit()

            logger.info("Folder monitoring stopped")
            return

        # 監視フォルダが未設定の場合
        if not self.monitored_folder:
            reply = QMessageBox.question(
                self,
                "監視フォルダ未設定",
                "監視フォルダが設定されていません。\n今すぐフォルダを選択しますか?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Yes:
                self.select_monitor_folder()
                if not self.monitored_folder:
                    return
            else:
                return

        # 監視開始
        try:
            self.folder_monitor = FolderMonitor(self.monitored_folder, check_interval=self.monitor_interval_spinbox.value())

            self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
            self.folder_monitor.status_update.connect(self.on_monitor_status)
            self.folder_monitor.start()

            self.session_start_time = datetime.now()

            self.monitor_folder_button.setText("監視停止")
            self.monitor_folder_button.setObjectName("danger")
            self.status_message.emit(f"フォルダ監視開始: {os.path.basename(self.monitored_folder)}")

            # 開始シグナルを送信（トレイ通知用）
            self.monitoring_started.emit()

            logger.info(f"Folder monitoring started: {self.monitored_folder}")

        except Exception as e:
            error_msg = f"フォルダ監視の開始に失敗しました: {str(e)}"
            QMessageBox.critical(self, "エラー", error_msg)
            logger.error(error_msg)

    def cleanup_expired_processing_files(self):
        """TTLを超えた処理中ファイルをクリーンアップ"""
        current_time = datetime.now().timestamp()
        with self.processing_files_lock:
            expired_files = [
                file_path
                for file_path, added_time in self.processing_files.items()
                if current_time - added_time > self.processing_files_ttl
            ]
            for file_path in expired_files:
                del self.processing_files[file_path]
                logger.warning(f"Removed expired file from processing list (TTL exceeded): {file_path}")

    def on_monitor_new_files(self, files: list):
        """監視フォルダで新規ファイル検出時の処理"""
        logger.info(f"New files detected: {len(files)} files")

        if self.batch_worker and self.batch_worker.isRunning():
            logger.warning("Previous batch worker is still running, skipping new files")
            self.status_message.emit("前回の処理が完了していません。次回の監視で処理します...")
            return

        self.cleanup_expired_processing_files()

        current_time = datetime.now().timestamp()
        with self.processing_files_lock:
            new_files = [f for f in files if f not in self.processing_files]

            if not new_files:
                logger.info("All detected files are already being processed")
                return

            for f in new_files:
                self.processing_files[f] = current_time

        self.update_stats_display()

        logger.info(f"Processing {len(new_files)} new files (filtered from {len(files)})")

        enable_diarization = self.enable_diarization_check.isChecked()

        self.batch_worker = BatchTranscriptionWorker(
            new_files, enable_diarization=enable_diarization, formatter=self.formatter, use_llm_correction=False
        )

        self.batch_worker.progress.connect(self.on_monitor_progress)
        self.batch_worker.file_finished.connect(self.on_monitor_file_finished)
        self.batch_worker.all_finished.connect(self.on_monitor_all_finished)
        self.batch_worker.error.connect(self.on_monitor_error)
        self.batch_worker.start()

        self.progress_bar.setVisible(True)
        self.status_message.emit(f"監視フォルダから{len(new_files)}ファイルを自動処理中...")

    @Slot(int, int, str)
    def on_monitor_progress(self, completed: int, total: int, filename: str):
        """監視自動処理の進捗更新"""
        progress_percent = int((completed / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        self.status_message.emit(f"自動処理中: {filename} ({completed}/{total})")

    @Slot(str, str, bool)
    def on_monitor_file_finished(self, file_path: str, result: str, success: bool):
        """監視自動処理の個別ファイル完了"""
        filename = os.path.basename(file_path)

        with self.processing_files_lock:
            if file_path in self.processing_files:
                del self.processing_files[file_path]
                logger.debug(f"Removed from processing_files: {filename}")

        self.update_stats_display()

        if success:
            logger.info(f"Monitor auto-processing completed: {filename}")
            self.total_processed += 1
            self.update_stats_display()

            if self.folder_monitor:
                self.folder_monitor.mark_as_processed(file_path)

            # 自動移動が有効な場合
            if self.auto_move_completed and self.completed_folder:
                try:
                    from advanced_features import FileOrganizer

                    if FileOrganizer.move_completed_file(file_path, self.completed_folder):
                        logger.info(f"File moved to completed folder: {filename}")
                        if self.folder_monitor:
                            self.folder_monitor.remove_from_processed(file_path)
                except Exception as e:
                    logger.error(f"Failed to move completed file: {e}")

        else:
            logger.error(f"Monitor auto-processing failed: {filename}")
            self.total_failed += 1
            self.update_stats_display()

    @Slot(int, int)
    def on_monitor_all_finished(self, success_count: int, failed_count: int):
        """監視自動処理の全完了"""
        with self.processing_files_lock:
            if self.processing_files:
                logger.warning(f"Cleaning up {len(self.processing_files)} remaining files from processing list")
                self.processing_files.clear()

        self.progress_bar.setVisible(False)
        self.update_stats_display()

        self.status_message.emit(f"自動処理完了: {success_count}成功, {failed_count}失敗")
        logger.info(f"Monitor auto-processing finished: {success_count} success, {failed_count} failed")

    @Slot(str)
    def on_monitor_status(self, status: str):
        """監視ステータス更新"""
        logger.info(f"Monitor status: {status}")

    @Slot(str)
    def on_monitor_error(self, error_msg: str):
        """監視バッチエラー処理"""
        self.progress_bar.setVisible(False)
        self.status_message.emit("エラー発生")
        logger.error(f"Monitor batch error: {error_msg}")

    def update_stats_display(self):
        """統計情報表示を更新"""
        with self.processing_files_lock:
            processing_count = len(self.processing_files)
        self.stats_label.setText(
            f"処理済み: {self.total_processed}件 | 失敗: {self.total_failed}件 | 処理中: {processing_count}件"
        )

    def on_monitor_interval_changed(self, value: int):
        """監視間隔変更"""
        logger.info(f"Monitor interval changed to: {value}s")

        self.settings.set("monitor_interval", value)
        self.settings.save_debounced()

        # 監視中の場合は再起動
        if self.folder_monitor and self.folder_monitor.isRunning():
            try:
                self.folder_monitor.new_files_detected.disconnect(self.on_monitor_new_files)
                self.folder_monitor.status_update.disconnect(self.on_monitor_status)
            except (RuntimeError, TypeError):
                pass  # 既に切断済み
            self.folder_monitor.stop()
            self.folder_monitor.wait()

            try:
                self.folder_monitor = FolderMonitor(self.monitored_folder, check_interval=value)

                self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
                self.folder_monitor.status_update.connect(self.on_monitor_status)
                self.folder_monitor.start()

                logger.info(f"Folder monitor restarted with new interval: {value}s")
                self.status_message.emit(f"監視間隔を{value}秒に変更しました")
            except Exception as e:
                logger.error(f"Failed to restart folder monitor: {e}")
                self.folder_monitor = None
                self.monitor_folder_button.setText("監視開始")
                self.monitor_folder_button.setObjectName("monitor")
                self.status_message.emit(f"監視の再起動に失敗しました: {e}")

    def on_auto_move_toggled(self, checked: bool):
        """自動移動設定トグル"""
        self.auto_move_completed = checked
        self.select_completed_folder_button.setEnabled(checked)

        self.settings.set("auto_move_completed", checked)
        self.settings.save_debounced()

        if checked:
            logger.info("Auto-move enabled")
            self.status_message.emit("完了ファイルの自動移動を有効にしました")
        else:
            logger.info("Auto-move disabled")
            self.status_message.emit("完了ファイルの自動移動を無効にしました")

    def load_ui_settings(self):
        """UI設定を復元"""
        try:
            # 監視フォルダを復元
            monitored_folder = self.settings.get("monitored_folder")
            if monitored_folder:
                if Path(monitored_folder).exists() and Path(monitored_folder).is_dir():
                    self.monitored_folder = monitored_folder
                    folder_name = os.path.basename(monitored_folder)
                    self.monitor_folder_label.setText(f"監視フォルダ: {folder_name}")
                    logger.info(f"Restored monitored folder: {monitored_folder}")
                else:
                    logger.warning(f"Monitored folder no longer exists: {monitored_folder}")

            # 完了フォルダを復元
            completed_folder = self.settings.get("completed_folder")
            if completed_folder:
                if Path(completed_folder).exists() and Path(completed_folder).is_dir():
                    self.completed_folder = completed_folder
                    folder_name = os.path.basename(completed_folder)
                    self.completed_folder_label.setText(folder_name)
                    logger.info(f"Restored completed folder: {completed_folder}")
                else:
                    logger.warning(f"Completed folder no longer exists: {completed_folder}")

            # 監視間隔を復元
            monitor_interval = self.settings.get("monitor_interval", MonitorUIConstants.MONITOR_INTERVAL_DEFAULT)
            monitor_interval = max(
                MonitorUIConstants.MONITOR_INTERVAL_MIN, min(MonitorUIConstants.MONITOR_INTERVAL_MAX, monitor_interval)
            )
            self.monitor_interval_spinbox.setValue(monitor_interval)

            # 自動移動設定を復元
            auto_move = self.settings.get("auto_move_completed", False)
            if isinstance(auto_move, bool):
                self.auto_move_check.setChecked(auto_move)
                self.auto_move_completed = auto_move
                self.select_completed_folder_button.setEnabled(auto_move)

            # 話者分離設定を復元
            self.enable_diarization_check.setChecked(bool(self.settings.get("enable_diarization", False)))

            logger.info("FolderMonitorTab settings restored successfully")

        except Exception as e:
            logger.error(f"Failed to load UI settings: {e}", exc_info=True)

    def save_ui_settings(self):
        """UI設定を保存"""
        try:
            self.settings.set("monitored_folder", self.monitored_folder)
            self.settings.set("completed_folder", self.completed_folder)
            self.settings.set("monitor_interval", self.monitor_interval_spinbox.value())
            self.settings.set("auto_move_completed", self.auto_move_completed)
            self.settings.set("enable_diarization", self.enable_diarization_check.isChecked())

            self.settings.save_immediate()
            logger.info("FolderMonitorTab settings saved successfully")

        except Exception as e:
            logger.error(f"Failed to save UI settings: {e}")

    def cleanup(self):
        """リソースのクリーンアップ"""
        # 設定を保存
        self.save_ui_settings()

        # Worker を停止
        stop_worker(self.batch_worker, "batch worker", timeout=SharedConstants.BATCH_WAIT_TIMEOUT, cancel=True)
        stop_worker(self.folder_monitor, "folder monitor", timeout=SharedConstants.MONITOR_WAIT_TIMEOUT, stop=True)

        logger.info("FolderMonitorTab cleanup completed")
