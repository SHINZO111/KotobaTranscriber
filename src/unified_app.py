"""
KotobaTranscriber - 統合アプリケーション
ファイル処理、フォルダ監視、設定を統合した単一アプリケーション
"""

import ctypes
import ctypes.wintypes
import logging
import os
import sys

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QTabWidget,
)

from app_settings import AppSettings
from dark_theme import set_theme
from tabs.file_tab import FileTranscriptionTab
from tabs.monitor_tab import FolderMonitorTab
from tabs.settings_tab import SettingsTab

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UnifiedWindow(QMainWindow):
    """統合アプリケーションメインウィンドウ"""

    def __init__(self):
        super().__init__()

        # AppSettings初期化（unified_settings.jsonを使用）
        self.settings = AppSettings("unified_settings.json")
        self.settings.load()

        # タブウィジェット（後で参照するため先に初期化）
        self.tab_widget = None

        # システムトレイアイコン
        self.tray_icon = None

        self.init_ui()
        self.init_tray_icon()
        self.restore_window_state()

        logger.info("UnifiedWindow initialized")

    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("KotobaTranscriber v2.2")

        # アイコン設定
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            logger.info(f"Window icon set: {icon_path}")
        else:
            logger.warning(f"Icon file not found: {icon_path}")

        # デフォルトウィンドウサイズ
        self.resize(800, 600)
        self.setMinimumSize(600, 400)

        # メニューバー作成
        self.create_menu_bar()

        # タブウィジェット作成
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 3つの空タブを作成（実際のコンテンツは後のタスクで実装）
        self.create_file_tab()
        self.create_monitor_tab()
        self.create_settings_tab()

        # ステータスバーの初期メッセージ
        self.statusBar().showMessage("準備完了")

        logger.info("UI initialized with 3 tabs")

    def create_menu_bar(self):
        """メニューバー作成"""
        menubar = self.menuBar()

        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル(&F)")

        quit_action = QAction("終了(&Q)", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.quit_application)
        file_menu.addAction(quit_action)

        # ヘルプメニュー
        help_menu = menubar.addMenu("ヘルプ(&H)")

        about_action = QAction("バージョン情報(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        logger.info("Menu bar created")

    def create_file_tab(self):
        """ファイル処理タブ作成"""
        self.file_tab = FileTranscriptionTab()
        # ステータスメッセージシグナルを接続
        self.file_tab.status_message.connect(lambda msg: self.statusBar().showMessage(msg))
        self.tab_widget.addTab(self.file_tab, "ファイル")
        logger.info("File tab created")

        # トレイ通知シグナルの接続（後でinit_tray_icon後に再接続）
        # 文字起こし完了時にトレイ通知を表示

    def create_monitor_tab(self):
        """フォルダ監視タブ作成"""
        self.monitor_tab = FolderMonitorTab()
        # ステータスメッセージシグナルを接続
        self.monitor_tab.status_message.connect(lambda msg: self.statusBar().showMessage(msg))
        self.tab_widget.addTab(self.monitor_tab, "フォルダ監視")
        logger.info("Monitor tab created")

        # トレイ通知シグナルの接続（後でinit_tray_icon後に再接続）
        # 監視開始/停止時にトレイメニューの更新が必要

    def create_settings_tab(self):
        """設定タブ作成"""
        self.settings_tab = SettingsTab()
        # ステータスメッセージシグナルを接続
        self.settings_tab.status_message.connect(lambda msg: self.statusBar().showMessage(msg))
        # 設定適用シグナルを接続（ダークモード切り替えなど）
        self.settings_tab.settings_applied.connect(self.on_settings_applied)
        self.tab_widget.addTab(self.settings_tab, "設定")
        logger.info("Settings tab created")

    def init_tray_icon(self):
        """システムトレイアイコン初期化"""
        self.tray_icon = QSystemTrayIcon(self)

        # アイコン設定
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
            logger.info(f"Tray icon set: {icon_path}")
        else:
            logger.warning(f"Icon file not found for tray: {icon_path}")

        # トレイメニュー作成
        self.tray_menu = QMenu()

        show_action = QAction("表示", self)
        show_action.triggered.connect(self.show_window)
        self.tray_menu.addAction(show_action)

        hide_action = QAction("非表示", self)
        hide_action.triggered.connect(self.hide_window)
        self.tray_menu.addAction(hide_action)

        self.tray_menu.addSeparator()

        # フォルダ監視トグルアクション（動的に変更）
        self.monitor_toggle_action = QAction("フォルダ監視開始", self)
        self.monitor_toggle_action.triggered.connect(self.toggle_folder_monitor_from_tray)
        self.tray_menu.addAction(self.monitor_toggle_action)

        self.tray_menu.addSeparator()

        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self.quit_application)
        self.tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(self.tray_menu)

        # トレイアイコンクリックで表示/非表示切り替え
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        self.tray_icon.show()
        self.tray_icon.setToolTip("KotobaTranscriber v2.2")
        logger.info("System tray icon initialized")

        # タブシグナルを接続（トレイアイコン初期化後）
        self.connect_tab_signals()

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
        logger.info("Window hidden")

    def connect_tab_signals(self):
        """タブのシグナルをトレイ通知に接続"""
        # file_tab: 文字起こし完了通知
        if hasattr(self, "file_tab"):
            self.file_tab.transcription_completed.connect(self.on_file_transcription_completed)
            logger.debug("file_tab.transcription_completed signal connected")

        # monitor_tab: 監視開始/停止通知
        if hasattr(self, "monitor_tab"):
            self.monitor_tab.monitoring_started.connect(self.on_monitor_started)
            self.monitor_tab.monitoring_stopped.connect(self.on_monitor_stopped)
            logger.debug("monitor_tab monitoring signals connected")

        logger.info("Tab signals connected to tray notifications")

    def toggle_folder_monitor_from_tray(self):
        """トレイメニューからフォルダ監視をトグル"""
        if hasattr(self, "monitor_tab"):
            self.monitor_tab.toggle_folder_monitor()
            # メニュー項目を更新
            self.update_monitor_tray_menu()
        logger.info("Folder monitor toggled from tray menu")

    def update_monitor_tray_menu(self):
        """フォルダ監視メニュー項目を更新"""
        if hasattr(self, "monitor_tab"):
            is_monitoring = self.monitor_tab.folder_monitor and self.monitor_tab.folder_monitor.isRunning()
            if is_monitoring:
                self.monitor_toggle_action.setText("フォルダ監視停止")
            else:
                self.monitor_toggle_action.setText("フォルダ監視開始")
        logger.debug("Monitor tray menu updated")

    def show_tray_notification(self, title: str, message: str, icon_type=QSystemTrayIcon.Information):
        """トレイ通知を表示

        Args:
            title: 通知タイトル
            message: 通知メッセージ
            icon_type: アイコンタイプ (Information, Warning, Critical)
        """
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon_type, 3000)
            logger.info(f"Tray notification shown: {title}")

    def on_file_transcription_completed(self):
        """ファイル文字起こし完了時の処理"""
        self.show_tray_notification("文字起こし完了", "ファイルの文字起こしが完了しました", QSystemTrayIcon.Information)

    def on_monitor_started(self):
        """フォルダ監視開始時の処理"""
        self.update_monitor_tray_menu()
        if hasattr(self, "monitor_tab") and self.monitor_tab.monitored_folder:
            folder_name = os.path.basename(self.monitor_tab.monitored_folder)
            self.show_tray_notification("フォルダ監視開始", f"フォルダ監視を開始しました: {folder_name}", QSystemTrayIcon.Information)

    def on_monitor_stopped(self):
        """フォルダ監視停止時の処理"""
        self.update_monitor_tray_menu()
        self.show_tray_notification("フォルダ監視停止", "フォルダ監視を停止しました", QSystemTrayIcon.Information)

    def on_settings_applied(self, settings_dict):
        """設定適用時の処理（ダークモード切り替えなど）"""
        try:
            # ダークモードの切り替え
            if "dark_mode" in settings_dict:
                dark_mode = settings_dict["dark_mode"]
                app = QApplication.instance()
                if app:
                    set_theme(app, dark_mode)
                    logger.info(f"Theme changed to: {'dark' if dark_mode else 'light'}")
                    self.statusBar().showMessage(f"テーマを {'ダーク' if dark_mode else 'ライト'} モードに変更しました")

        except Exception as e:
            logger.error(f"Failed to apply settings: {e}", exc_info=True)

    def show_about(self):
        """バージョン情報ダイアログ"""
        QMessageBox.about(
            self,
            "KotobaTranscriber について",
            "<h3>KotobaTranscriber v2.2</h3>"
            "<p>日本語音声文字起こしアプリケーション</p>"
            "<p>Kotoba-Whisper v2.2 & Faster-Whisper を使用</p>"
            "<p>© 2024-2026 KotobaTranscriber Project</p>",
        )
        logger.info("About dialog shown")

    def restore_window_state(self):
        """ウィンドウ状態を復元"""
        try:
            # ウィンドウサイズと位置を復元
            width = self.settings.get("window.width", 800)
            height = self.settings.get("window.height", 600)
            x = self.settings.get("window.x", 100)
            y = self.settings.get("window.y", 100)

            # 範囲検証
            width = max(600, min(10000, width))
            height = max(400, min(10000, height))
            x = max(-5000, min(10000, x))
            y = max(-5000, min(10000, y))

            self.setGeometry(x, y, width, height)
            logger.info(f"Window geometry restored: {width}x{height} at ({x}, {y})")

            # 最後に選択していたタブを復元
            tab_index = self.settings.get("window.tab_index", 0)
            if isinstance(tab_index, int) and 0 <= tab_index < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(tab_index)
                logger.info(f"Tab index restored: {tab_index}")

        except Exception as e:
            logger.error(f"Failed to restore window state: {e}")

    def save_window_state(self):
        """ウィンドウ状態を保存"""
        try:
            # ウィンドウサイズと位置を保存
            self.settings.set("window.width", self.width())
            self.settings.set("window.height", self.height())
            self.settings.set("window.x", self.x())
            self.settings.set("window.y", self.y())

            # 現在のタブインデックスを保存
            if self.tab_widget:
                self.settings.set("window.tab_index", self.tab_widget.currentIndex())

            # 即座に保存（アプリ終了時は確実に保存する）
            self.settings.save_immediate()

            logger.info("Window state saved")

        except Exception as e:
            logger.error(f"Failed to save window state: {e}")

    def closeEvent(self, event):
        """ウィンドウを閉じる時の処理"""
        # ウィンドウ状態を保存
        self.save_window_state()

        # トレイに最小化（完全終了しない）
        event.ignore()
        self.hide()

        # トレイ通知
        self.tray_icon.showMessage(
            "KotobaTranscriber",
            "アプリはトレイで実行中です。完全に終了するには右クリックメニューから「終了」を選択してください。",
            QSystemTrayIcon.Information,
            3000,  # 3秒表示
        )

        logger.info("Window closed to tray")

    def quit_application(self):
        """アプリケーション完全終了"""
        logger.info("Application quitting")

        # ファイルタブのクリーンアップ
        if hasattr(self, "file_tab"):
            self.file_tab.cleanup()

        # フォルダ監視タブのクリーンアップ
        if hasattr(self, "monitor_tab"):
            self.monitor_tab.cleanup()

        # ウィンドウ状態を保存
        self.save_window_state()

        # トレイアイコンを非表示
        if self.tray_icon:
            self.tray_icon.hide()

        # アプリケーション終了
        QApplication.quit()


def main():
    """メイン関数"""
    # 多重起動防止
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mutex_name = "Local\\KotobaTranscriber_Unified_Mutex"
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.get_last_error()

    if last_error == ERROR_ALREADY_EXISTS:
        logger.warning("Unified application is already running")
        app = QApplication(sys.argv)
        QMessageBox.warning(
            None,
            "多重起動エラー",
            "KotobaTranscriberは既に起動しています。\n\nシステムトレイにアイコンがある場合は、そちらをクリックしてウィンドウを表示してください。",
        )
        kernel32.CloseHandle(mutex)
        sys.exit(1)

    # アプリケーション作成
    app = QApplication(sys.argv)
    app.setApplicationName("KotobaTranscriber")
    app.setOrganizationName("KotobaTranscriber")
    app.setStyle("Fusion")

    # ダークモード設定を読み込み適用
    _settings = AppSettings("unified_settings.json")
    _settings.load()
    dark_mode = bool(_settings.get("dark_mode", False))
    set_theme(app, dark_mode=dark_mode)

    # メインウィンドウ作成と表示
    window = UnifiedWindow()
    window.show()

    logger.info("Unified application started")

    # イベントループ開始
    try:
        exit_code = app.exec()
    finally:
        # mutexクリーンアップを確実に実行
        kernel32.CloseHandle(mutex)
        logger.info("Application exited")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
