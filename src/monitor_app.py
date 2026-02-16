"""
KotobaTranscriber - フォルダ監視アプリケーション
フォルダ監視・システムトレイ・自動起動・自動移動の専用アプリ
ファイル文字起こし機能は main.py を参照
"""

import sys
import os
from datetime import datetime
from pathlib import Path
import ctypes
import ctypes.wintypes
import threading
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QProgressBar, QMessageBox,
    QCheckBox, QGroupBox, QSystemTrayIcon, QMenu, QSpinBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
import logging

from text_formatter import TextFormatter
from folder_monitor import FolderMonitor
from app_settings import AppSettings
from workers import (
    BatchTranscriptionWorker,
    SharedConstants,
    stop_worker,
)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MonitorUIConstants(SharedConstants):
    """モニターアプリ固有のUI定数"""
    # 監視間隔範囲
    MONITOR_INTERVAL_MIN = 5
    MONITOR_INTERVAL_MAX = 9999  # 上限なし（実質無制限）
    MONITOR_INTERVAL_DEFAULT = 10

    # ウィンドウサイズ制限
    WINDOW_MIN_WIDTH = 300
    WINDOW_MIN_HEIGHT = 400


class MonitorWindow(QMainWindow):
    """フォルダ監視メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.batch_worker = None
        self.formatter = TextFormatter()

        # フォルダ監視関連
        self.folder_monitor = None
        self.monitored_folder = None
        self.monitor_check_interval = MonitorUIConstants.MONITOR_INTERVAL_DEFAULT
        self.processing_files = {}
        self.processing_files_lock = threading.Lock()
        self.processing_files_ttl = SharedConstants.PROCESSING_FILES_TTL

        # 統計情報
        self.total_processed = 0
        self.total_failed = 0
        self.session_start_time = None

        # 自動移動設定
        self.auto_move_completed = False
        self.completed_folder = None

        # 設定管理（モニター専用設定ファイル）
        self.settings = AppSettings("monitor_settings.json")
        self.settings.load()

        self.init_ui()
        self.init_tray_icon()
        self.check_startup_status()
        self.load_ui_settings()

    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("KotobaTranscriber - フォルダ監視")

        # アイコン設定
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setGeometry(100, 100, 350, 500)

        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(3)

        # フォルダ監視グループ
        monitor_group = QGroupBox("フォルダ監視")
        monitor_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; }")
        monitor_layout = QVBoxLayout()
        monitor_layout.setSpacing(3)
        monitor_layout.setContentsMargins(5, 5, 5, 5)

        # 監視ボタン行
        monitor_button_layout = QHBoxLayout()

        self.monitor_folder_button = QPushButton("監視開始")
        self.monitor_folder_button.setStyleSheet(SharedConstants.BUTTON_STYLE_MONITOR)
        self.monitor_folder_button.setToolTip("フォルダ監視を開始/停止します。監視中は新しいファイルを自動的に文字起こしします")
        self.monitor_folder_button.clicked.connect(self.toggle_folder_monitor)
        monitor_button_layout.addWidget(self.monitor_folder_button)

        self.select_monitor_folder_button = QPushButton("フォルダ選択")
        self.select_monitor_folder_button.setStyleSheet("font-size: 12px; padding: 5px; font-weight: bold;")
        self.select_monitor_folder_button.setToolTip("監視するフォルダを選択します")
        self.select_monitor_folder_button.clicked.connect(self.select_monitor_folder)
        monitor_button_layout.addWidget(self.select_monitor_folder_button)

        monitor_layout.addLayout(monitor_button_layout)

        # 監視フォルダ表示
        self.monitor_folder_label = QLabel("監視フォルダ: 未設定")
        self.monitor_folder_label.setStyleSheet("margin: 2px; font-size: 10px; color: #666;")
        monitor_layout.addWidget(self.monitor_folder_label)

        # 監視間隔設定
        interval_layout = QHBoxLayout()
        interval_label = QLabel("監視間隔:")
        interval_label.setStyleSheet("font-size: 10px;")
        interval_layout.addWidget(interval_label)

        self.monitor_interval_spinbox = QSpinBox()
        self.monitor_interval_spinbox.setRange(
            MonitorUIConstants.MONITOR_INTERVAL_MIN,
            MonitorUIConstants.MONITOR_INTERVAL_MAX
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

        # テキスト整形オプション
        format_group = QGroupBox("テキスト整形オプション")
        format_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; }")
        format_layout = QVBoxLayout()
        format_layout.setSpacing(2)
        format_layout.setContentsMargins(5, 5, 5, 5)

        self.enable_diarization_check = QCheckBox("話者分離")
        self.enable_diarization_check.setStyleSheet("font-size: 12px;")
        self.enable_diarization_check.setChecked(False)
        self.enable_diarization_check.setToolTip("複数の話者を識別します。speechbrainまたはresemblyzerを使用。完全無料、トークン不要。")
        format_layout.addWidget(self.enable_diarization_check)

        format_group.setLayout(format_layout)
        main_layout.addWidget(format_group)

        # 統計情報表示
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("background-color: #f5f5f5; border-radius: 3px; padding: 5px; margin: 2px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(5, 3, 5, 3)

        self.stats_label = QLabel("処理済み: 0件 | 失敗: 0件 | 処理中: 0件")
        self.stats_label.setStyleSheet("font-size: 10px; font-weight: bold; color: #333;")
        stats_layout.addWidget(self.stats_label)

        main_layout.addWidget(stats_frame)

        # 詳細設定グループ
        advanced_group = QGroupBox("詳細設定")
        advanced_group.setStyleSheet("QGroupBox { font-size: 11px; font-weight: bold; }")
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(2)
        advanced_layout.setContentsMargins(5, 5, 5, 5)

        # Windows起動時に自動起動
        self.startup_check = QCheckBox("Windows起動時に自動起動")
        self.startup_check.setStyleSheet("font-size: 10px;")
        self.startup_check.setChecked(False)
        self.startup_check.setToolTip("Windowsスタートアップに登録します")
        self.startup_check.clicked.connect(self.on_startup_toggled)
        advanced_layout.addWidget(self.startup_check)

        # 完了ファイル自動移動
        self.auto_move_check = QCheckBox("完了ファイルを自動移動")
        self.auto_move_check.setStyleSheet("font-size: 10px;")
        self.auto_move_check.setChecked(False)
        self.auto_move_check.setToolTip("文字起こし完了後、ファイルを指定フォルダに移動します")
        self.auto_move_check.clicked.connect(self.on_auto_move_toggled)
        advanced_layout.addWidget(self.auto_move_check)

        # 移動先フォルダ選択
        move_folder_layout = QHBoxLayout()
        self.select_completed_folder_button = QPushButton("移動先フォルダ選択")
        self.select_completed_folder_button.setStyleSheet("font-size: 10px; padding: 3px;")
        self.select_completed_folder_button.clicked.connect(self.select_completed_folder)
        self.select_completed_folder_button.setEnabled(False)
        move_folder_layout.addWidget(self.select_completed_folder_button)

        self.completed_folder_label = QLabel("未設定")
        self.completed_folder_label.setStyleSheet("font-size: 9px; color: #666;")
        move_folder_layout.addWidget(self.completed_folder_label)
        move_folder_layout.addStretch()

        advanced_layout.addLayout(move_folder_layout)

        advanced_group.setLayout(advanced_layout)
        main_layout.addWidget(advanced_group)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ステータスバー
        self.statusBar().showMessage("準備完了")

        logger.info("Monitor UI initialized")

    # ---------------------------------------------------------------
    # システムトレイ
    # ---------------------------------------------------------------

    def init_tray_icon(self):
        """システムトレイアイコン初期化"""
        self.tray_icon = QSystemTrayIcon(self)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self._create_tray_icon())

        self.tray_icon.setToolTip("KotobaTranscriber Monitor")

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
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        logger.info("System tray icon initialized")

    def _create_tray_icon(self):
        """トレイアイコン画像作成"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景円（オレンジ — 監視アプリ区別用）
        painter.setBrush(QColor(255, 152, 0))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)

        # 白い「M」マーク（Monitor の頭文字）
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPointSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "M")

        painter.end()
        return QIcon(pixmap)

    def update_tray_tooltip(self):
        """システムトレイアイコンのツールチップを更新"""
        tooltip = "KotobaTranscriber Monitor\n"

        if self.folder_monitor and self.folder_monitor.isRunning():
            tooltip += "フォルダ監視: 実行中\n"
        else:
            tooltip += "フォルダ監視: 停止中\n"

        with self.processing_files_lock:
            processing_count = len(self.processing_files)
        if processing_count > 0:
            tooltip += f"処理中: {processing_count}ファイル\n"

        if self.total_processed > 0 or self.total_failed > 0:
            tooltip += f"完了: {self.total_processed}件"
            if self.total_failed > 0:
                tooltip += f" | 失敗: {self.total_failed}件"

        self.tray_icon.setToolTip(tooltip.strip())

    def on_tray_icon_activated(self, reason):
        """トレイアイコンクリック時の処理"""
        if reason == QSystemTrayIcon.Trigger:
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

    def closeEvent(self, event):
        """ウィンドウを閉じる時の処理（トレイに最小化）"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "KotobaTranscriber Monitor",
            "アプリはトレイで実行中です。完全に終了するには右クリックメニューから「終了」を選択してください。",
            QSystemTrayIcon.Information,
            SharedConstants.TRAY_NOTIFICATION_TIMEOUT
        )
        logger.info("Window closed to tray")

    # ---------------------------------------------------------------
    # フォルダ監視
    # ---------------------------------------------------------------

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

            self.settings.set('monitored_folder', folder_path)
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
            self.monitor_folder_button.setStyleSheet(SharedConstants.BUTTON_STYLE_MONITOR)
            self.statusBar().showMessage("フォルダ監視を停止しました")
            self.update_tray_tooltip()
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
                if not self.monitored_folder:
                    return
            else:
                return

        # 監視開始
        try:
            self.folder_monitor = FolderMonitor(
                self.monitored_folder,
                check_interval=self.monitor_interval_spinbox.value()
            )

            self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
            self.folder_monitor.status_update.connect(self.on_monitor_status)
            self.folder_monitor.start()

            self.session_start_time = datetime.now()

            self.monitor_folder_button.setText("監視停止")
            self.monitor_folder_button.setStyleSheet(SharedConstants.BUTTON_STYLE_STOP)
            self.statusBar().showMessage(f"フォルダ監視開始: {os.path.basename(self.monitored_folder)}")
            self.update_tray_tooltip()
            logger.info(f"Folder monitoring started: {self.monitored_folder}")

            self.tray_icon.showMessage(
                "フォルダ監視開始",
                f"{os.path.basename(self.monitored_folder)} を監視中...",
                QSystemTrayIcon.Information,
                SharedConstants.TRAY_NOTIFICATION_TIMEOUT
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

        if self.batch_worker and self.batch_worker.isRunning():
            logger.warning("Previous batch worker is still running, skipping new files")
            self.statusBar().showMessage("前回の処理が完了していません。次回の監視で処理します...")
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

        self.tray_icon.showMessage(
            "新規ファイル検出",
            f"{len(new_files)}個のファイルを自動文字起こし中...",
            QSystemTrayIcon.Information,
            SharedConstants.TRAY_NOTIFICATION_TIMEOUT
        )

        enable_diarization = self.enable_diarization_check.isChecked()

        self.batch_worker = BatchTranscriptionWorker(
            new_files,
            enable_diarization=enable_diarization,
            formatter=self.formatter,
            use_llm_correction=False
        )

        self.batch_worker.progress.connect(self.on_monitor_progress)
        self.batch_worker.file_finished.connect(self.on_monitor_file_finished)
        self.batch_worker.all_finished.connect(self.on_monitor_all_finished)
        self.batch_worker.error.connect(self.on_monitor_error)
        self.batch_worker.start()

        self.progress_bar.setVisible(True)
        self.statusBar().showMessage(f"監視フォルダから{len(new_files)}ファイルを自動処理中...")

    def on_monitor_progress(self, completed: int, total: int, filename: str):
        """監視自動処理の進捗更新"""
        progress_percent = int((completed / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        self.statusBar().showMessage(f"自動処理中: {filename} ({completed}/{total})")

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

            self.tray_icon.showMessage(
                "文字起こし失敗",
                f"{filename}\nエラー: {result[:100]}",
                QSystemTrayIcon.Critical,
                SharedConstants.ERROR_NOTIFICATION_TIMEOUT
            )

    def on_monitor_all_finished(self, success_count: int, failed_count: int):
        """監視自動処理の全完了"""
        with self.processing_files_lock:
            if self.processing_files:
                logger.warning(f"Cleaning up {len(self.processing_files)} remaining files from processing list")
                self.processing_files.clear()

        self.progress_bar.setVisible(False)
        self.update_stats_display()

        self.tray_icon.showMessage(
            "自動文字起こし完了",
            f"成功: {success_count}件, 失敗: {failed_count}件",
            QSystemTrayIcon.Information,
            SharedConstants.TRAY_NOTIFICATION_TIMEOUT
        )

        self.statusBar().showMessage(f"自動処理完了: {success_count}成功, {failed_count}失敗")
        logger.info(f"Monitor auto-processing finished: {success_count} success, {failed_count} failed")

    def on_monitor_status(self, status: str):
        """監視ステータス更新"""
        logger.info(f"Monitor status: {status}")

    def on_monitor_error(self, error_msg: str):
        """監視バッチエラー処理"""
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("エラー発生")
        logger.error(f"Monitor batch error: {error_msg}")

        self.tray_icon.showMessage(
            "バッチ処理エラー",
            error_msg[:200],
            QSystemTrayIcon.Critical,
            SharedConstants.ERROR_NOTIFICATION_TIMEOUT
        )

    def update_stats_display(self):
        """統計情報表示を更新"""
        with self.processing_files_lock:
            processing_count = len(self.processing_files)
        self.stats_label.setText(
            f"処理済み: {self.total_processed}件 | 失敗: {self.total_failed}件 | 処理中: {processing_count}件"
        )

    def on_monitor_interval_changed(self, value: int):
        """監視間隔変更"""
        self.monitor_check_interval = value
        logger.info(f"Monitor interval changed to: {value}s")

        self.settings.set('monitor_interval', value)
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
                self.folder_monitor = FolderMonitor(
                    self.monitored_folder,
                    check_interval=value
                )

                self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
                self.folder_monitor.status_update.connect(self.on_monitor_status)
                self.folder_monitor.start()

                logger.info(f"Folder monitor restarted with new interval: {value}s")
                self.statusBar().showMessage(f"監視間隔を{value}秒に変更しました")
            except Exception as e:
                logger.error(f"Failed to restart folder monitor: {e}")
                self.folder_monitor = None
                self.monitor_folder_button.setText("監視開始")
                self.monitor_folder_button.setStyleSheet(SharedConstants.BUTTON_STYLE_MONITOR)
                self.statusBar().showMessage(f"監視の再起動に失敗しました: {e}")

    # ---------------------------------------------------------------
    # 起動設定
    # ---------------------------------------------------------------

    def check_startup_status(self):
        """Windows起動設定の状態をチェック"""
        try:
            from advanced_features import StartupManager

            if StartupManager.is_startup_enabled(app_name='KotobaTranscriberMonitor'):
                self.startup_check.setChecked(True)
                logger.info("Startup is enabled")
            else:
                self.startup_check.setChecked(False)
                logger.info("Startup is disabled")

        except Exception as e:
            logger.warning(f"Failed to check startup status: {e}")

    def on_startup_toggled(self, checked: bool):
        """Windows起動時の自動起動設定"""
        try:
            from advanced_features import StartupManager

            if checked:
                if StartupManager.enable_startup(
                    app_name='KotobaTranscriberMonitor',
                    entry_script='monitor_app.py'
                ):
                    logger.info("Startup enabled")
                    self.statusBar().showMessage("Windows起動時に自動起動するように設定しました")
                else:
                    self.startup_check.setChecked(False)
                    QMessageBox.warning(self, "警告", "スタートアップの設定に失敗しました")
            else:
                if StartupManager.disable_startup(app_name='KotobaTranscriberMonitor'):
                    logger.info("Startup disabled")
                    self.statusBar().showMessage("自動起動を無効にしました")
                else:
                    self.startup_check.setChecked(True)
                    QMessageBox.warning(self, "警告", "スタートアップの解除に失敗しました")

        except Exception as e:
            logger.error(f"Failed to toggle startup: {e}")
            QMessageBox.critical(self, "エラー", f"スタートアップ設定に失敗しました: {str(e)}")
            self.startup_check.setChecked(not checked)

    # ---------------------------------------------------------------
    # 自動移動
    # ---------------------------------------------------------------

    def on_auto_move_toggled(self, checked: bool):
        """自動移動設定トグル"""
        self.auto_move_completed = checked
        self.select_completed_folder_button.setEnabled(checked)

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

            self.settings.set('completed_folder', folder_path)
            self.settings.save_debounced()

    # ---------------------------------------------------------------
    # 設定 保存/復元
    # ---------------------------------------------------------------

    def load_ui_settings(self):
        """UI設定を復元（検証付き）"""
        try:
            # ウィンドウジオメトリ
            width = self.settings.get('window.width', 350)
            height = self.settings.get('window.height', 500)
            x = self.settings.get('window.x', 100)
            y = self.settings.get('window.y', 100)

            width = max(MonitorUIConstants.WINDOW_MIN_WIDTH, min(MonitorUIConstants.WINDOW_MAX_WIDTH, width))
            height = max(MonitorUIConstants.WINDOW_MIN_HEIGHT, min(MonitorUIConstants.WINDOW_MAX_HEIGHT, height))
            x = max(0, min(MonitorUIConstants.WINDOW_MAX_WIDTH, x))
            y = max(0, min(MonitorUIConstants.WINDOW_MAX_HEIGHT, y))

            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                if x + width > screen_geometry.width():
                    x = max(0, screen_geometry.width() - width)
                if y + height > screen_geometry.height():
                    y = max(0, screen_geometry.height() - height)

            self.setGeometry(x, y, width, height)
            logger.info(f"Window geometry restored: {width}x{height} at ({x}, {y})")

            # フォルダ設定を復元
            monitored_folder = self.settings.get('monitored_folder')
            if monitored_folder:
                if Path(monitored_folder).exists() and Path(monitored_folder).is_dir():
                    self.monitored_folder = monitored_folder
                    folder_name = os.path.basename(monitored_folder)
                    self.monitor_folder_label.setText(f"監視フォルダ: {folder_name}")
                    logger.info(f"Restored monitored folder: {monitored_folder}")
                else:
                    logger.warning(f"Monitored folder no longer exists: {monitored_folder}")

            completed_folder = self.settings.get('completed_folder')
            if completed_folder:
                if Path(completed_folder).exists() and Path(completed_folder).is_dir():
                    self.completed_folder = completed_folder
                    folder_name = os.path.basename(completed_folder)
                    self.completed_folder_label.setText(folder_name)
                    logger.info(f"Restored completed folder: {completed_folder}")
                else:
                    logger.warning(f"Completed folder no longer exists: {completed_folder}")

            # 監視間隔を復元
            monitor_interval = self.settings.get('monitor_interval', MonitorUIConstants.MONITOR_INTERVAL_DEFAULT)
            monitor_interval = max(MonitorUIConstants.MONITOR_INTERVAL_MIN,
                                   min(MonitorUIConstants.MONITOR_INTERVAL_MAX, monitor_interval))
            self.monitor_interval_spinbox.setValue(monitor_interval)

            # 自動移動設定を復元
            auto_move = self.settings.get('auto_move_completed', False)
            if isinstance(auto_move, bool):
                self.auto_move_check.setChecked(auto_move)
                self.auto_move_completed = auto_move
                self.select_completed_folder_button.setEnabled(auto_move)

            # 話者分離設定を復元
            self.enable_diarization_check.setChecked(
                bool(self.settings.get('enable_diarization', False))
            )

            logger.info("UI settings restored successfully")

            # 自動監視開始
            self._auto_start_monitoring_if_needed()

        except Exception as e:
            logger.error(f"Failed to load UI settings: {e}", exc_info=True)
            self.setGeometry(100, 100, 350, 500)

    def _auto_start_monitoring_if_needed(self):
        """自動監視開始: 監視フォルダが設定されており、未処理ファイルが存在する場合"""
        try:
            if not self.monitored_folder:
                logger.debug("Auto-start skipped: No monitored folder configured")
                return

            folder_path = Path(self.monitored_folder)
            if not folder_path.exists() or not folder_path.is_dir():
                logger.warning(f"Auto-start skipped: Monitored folder does not exist: {self.monitored_folder}")
                return

            # 未処理ファイルの確認
            all_files = []
            for ext in SharedConstants.SUPPORTED_EXTENSIONS:
                all_files.extend(list(folder_path.glob(f'*{ext}')))
                all_files.extend(list(folder_path.glob(f'*{ext.upper()}')))

            processed_files_path = folder_path / ".processed_files.txt"
            processed_files = set()
            if processed_files_path.exists():
                try:
                    MAX_PROCESSED_SIZE = 50 * 1024 * 1024  # 50MB
                    file_size = processed_files_path.stat().st_size
                    if file_size > MAX_PROCESSED_SIZE:
                        logger.error(f"Processed files list too large: {file_size} bytes, skipping")
                    else:
                        with open(processed_files_path, 'r', encoding='utf-8') as f:
                            processed_files = set(line.strip() for line in f if line.strip())
                except Exception as e:
                    logger.warning(f"Failed to load processed files list: {e}")

            unprocessed_files = [str(f) for f in all_files if str(f) not in processed_files]

            if not unprocessed_files:
                logger.info("Auto-start skipped: No unprocessed files found in monitored folder")
                return

            logger.info(f"Auto-starting monitoring: {len(unprocessed_files)} unprocessed files found")

            self.folder_monitor = FolderMonitor(
                self.monitored_folder,
                check_interval=self.monitor_interval_spinbox.value()
            )

            self.folder_monitor.new_files_detected.connect(self.on_monitor_new_files)
            self.folder_monitor.status_update.connect(self.on_monitor_status)
            self.folder_monitor.start()

            self.session_start_time = datetime.now()

            self.monitor_folder_button.setText("監視停止")
            self.monitor_folder_button.setStyleSheet(SharedConstants.BUTTON_STYLE_STOP)
            self.statusBar().showMessage(
                f"自動監視開始: {os.path.basename(self.monitored_folder)} ({len(unprocessed_files)}個の未処理ファイル)"
            )
            logger.info(f"Folder monitoring auto-started: {self.monitored_folder}")

            self.tray_icon.showMessage(
                "自動監視開始",
                f"{os.path.basename(self.monitored_folder)}\n{len(unprocessed_files)}個の未処理ファイルを検出",
                QSystemTrayIcon.Information,
                SharedConstants.TRAY_NOTIFICATION_TIMEOUT
            )

        except Exception as e:
            logger.error(f"Failed to auto-start monitoring: {e}", exc_info=True)

    def save_ui_settings(self):
        """UI設定を保存"""
        try:
            self.settings.set('monitored_folder', self.monitored_folder)
            self.settings.set('completed_folder', self.completed_folder)
            self.settings.set('monitor_interval', self.monitor_interval_spinbox.value())
            self.settings.set('auto_move_completed', self.auto_move_completed)
            self.settings.set('enable_diarization', self.enable_diarization_check.isChecked())

            self.settings.set('window.width', self.width())
            self.settings.set('window.height', self.height())
            self.settings.set('window.x', self.x())
            self.settings.set('window.y', self.y())

            self.settings.save_immediate()
            logger.info("UI settings saved successfully")

        except Exception as e:
            logger.error(f"Failed to save UI settings: {e}")

    # ---------------------------------------------------------------
    # アプリケーション終了
    # ---------------------------------------------------------------

    def quit_application(self):
        """アプリケーション終了"""
        self.save_ui_settings()

        stop_worker(self.batch_worker, "batch worker",
                    timeout=SharedConstants.BATCH_WAIT_TIMEOUT, cancel=True)
        stop_worker(self.folder_monitor, "folder monitor",
                    timeout=SharedConstants.MONITOR_WAIT_TIMEOUT, stop=True)

        self.tray_icon.hide()

        logger.info("Monitor application quitting - all worker threads cleaned up")
        QApplication.quit()


def main():
    """メイン関数"""
    # 多重起動防止
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    mutex_name = "Local\\KotobaTranscriber_Monitor_Mutex"
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.get_last_error()

    if last_error == ERROR_ALREADY_EXISTS:
        logger.warning("Monitor application is already running")
        QApplication(sys.argv)
        QMessageBox.warning(
            None,
            "多重起動エラー",
            "KotobaTranscriber Monitorは既に起動しています。\n\nシステムトレイにアイコンがある場合は、そちらをクリックしてウィンドウを表示してください。"
        )
        kernel32.CloseHandle(mutex)
        return

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # トレイに最小化できるよう、最後のウィンドウが閉じてもアプリを終了しない
    app.setQuitOnLastWindowClosed(False)

    window = MonitorWindow()
    window.show()

    logger.info("Monitor application started")

    try:
        sys.exit(app.exec())
    finally:
        kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
