"""
UI/UX改善モジュール
KotobaTranscriber v2.2 - ユーザー体験向上
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UITheme:
    """UIテーマ定義"""
    name: str
    background_color: str
    text_color: str
    accent_color: str
    button_bg: str
    button_text: str
    border_color: str
    hover_color: str
    disabled_color: str
    error_color: str
    success_color: str
    warning_color: str
    info_color: str


# 定義済みテーマ
DARK_THEME = UITheme(
    name="Dark",
    background_color="#1e1e1e",
    text_color="#ffffff",
    accent_color="#4CAF50",
    button_bg="#3d3d3d",
    button_text="#ffffff",
    border_color="#555555",
    hover_color="#4a4a4a",
    disabled_color="#666666",
    error_color="#f44336",
    success_color="#4CAF50",
    warning_color="#ff9800",
    info_color="#2196f3"
)

LIGHT_THEME = UITheme(
    name="Light",
    background_color="#f5f5f5",
    text_color="#212121",
    accent_color="#4CAF50",
    button_bg="#ffffff",
    button_text="#212121",
    border_color="#cccccc",
    hover_color="#e0e0e0",
    disabled_color="#9e9e9e",
    error_color="#d32f2f",
    success_color="#388e3c",
    warning_color="#f57c00",
    info_color="#1976d2"
)


class ThemeManager:
    """テーマ管理クラス"""
    
    def __init__(self):
        self._current_theme = DARK_THEME
        self._listeners: List[Callable[[UITheme], None]] = []
    
    def set_theme(self, theme: UITheme):
        """テーマを設定"""
        self._current_theme = theme
        self._notify_listeners()
        logger.info(f"Theme changed to: {theme.name}")
    
    def get_theme(self) -> UITheme:
        """現在のテーマを取得"""
        return self._current_theme
    
    def get_stylesheet(self) -> str:
        """テーマ用スタイルシートを生成"""
        t = self._current_theme
        
        return f"""
        QMainWindow {{
            background-color: {t.background_color};
            color: {t.text_color};
        }}
        
        QWidget {{
            background-color: {t.background_color};
            color: {t.text_color};
        }}
        
        QPushButton {{
            background-color: {t.button_bg};
            color: {t.button_text};
            border: 1px solid {t.border_color};
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        QPushButton:hover {{
            background-color: {t.hover_color};
        }}
        
        QPushButton:disabled {{
            background-color: {t.disabled_color};
            color: {t.disabled_color};
        }}
        
        QPushButton#primary {{
            background-color: {t.accent_color};
            color: white;
        }}
        
        QPushButton#primary:hover {{
            background-color: {self._lighten_color(t.accent_color, 20)};
        }}
        
        QTextEdit, QPlainTextEdit {{
            background-color: {self._darken_color(t.background_color, 10)};
            color: {t.text_color};
            border: 1px solid {t.border_color};
            border-radius: 4px;
            padding: 8px;
        }}
        
        QProgressBar {{
            border: 1px solid {t.border_color};
            border-radius: 4px;
            text-align: center;
            background-color: {self._darken_color(t.background_color, 20)};
        }}
        
        QProgressBar::chunk {{
            background-color: {t.accent_color};
            border-radius: 3px;
        }}
        
        QGroupBox {{
            border: 1px solid {t.border_color};
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: bold;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
        
        QLabel {{
            color: {t.text_color};
        }}
        
        QLabel#status {{
            color: {t.info_color};
        }}
        
        QLabel#error {{
            color: {t.error_color};
        }}
        
        QLabel#success {{
            color: {t.success_color};
        }}
        
        QComboBox {{
            background-color: {t.button_bg};
            color: {t.button_text};
            border: 1px solid {t.border_color};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        
        QComboBox:hover {{
            background-color: {t.hover_color};
        }}
        
        QCheckBox {{
            color: {t.text_color};
        }}
        
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
        }}
        
        QSlider::groove:horizontal {{
            border: 1px solid {t.border_color};
            height: 8px;
            background: {self._darken_color(t.background_color, 20)};
            margin: 2px 0;
            border-radius: 4px;
        }}
        
        QSlider::handle:horizontal {{
            background: {t.accent_color};
            border: 1px solid {t.accent_color};
            width: 18px;
            margin: -2px 0;
            border-radius: 9px;
        }}
        
        QTabWidget::pane {{
            border: 1px solid {t.border_color};
            border-radius: 4px;
            background-color: {t.background_color};
        }}
        
        QTabBar::tab {{
            background-color: {t.button_bg};
            color: {t.button_text};
            padding: 8px 16px;
            border: 1px solid {t.border_color};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {t.accent_color};
            color: white;
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: {t.hover_color};
        }}
        
        QScrollBar:vertical {{
            background-color: {self._darken_color(t.background_color, 20)};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {t.border_color};
            border-radius: 6px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {t.hover_color};
        }}
        
        QMenu {{
            background-color: {t.button_bg};
            color: {t.button_text};
            border: 1px solid {t.border_color};
        }}
        
        QMenu::item:selected {{
            background-color: {t.accent_color};
            color: white;
        }}
        
        QListWidget {{
            background-color: {self._darken_color(t.background_color, 10)};
            color: {t.text_color};
            border: 1px solid {t.border_color};
            border-radius: 4px;
        }}
        
        QListWidget::item:selected {{
            background-color: {t.accent_color};
            color: white;
        }}
        
        QSpinBox, QDoubleSpinBox {{
            background-color: {t.button_bg};
            color: {t.button_text};
            border: 1px solid {t.border_color};
            border-radius: 4px;
            padding: 4px;
        }}
        
        QStatusBar {{
            background-color: {self._darken_color(t.background_color, 20)};
            color: {t.text_color};
        }}
        
        QToolBar {{
            background-color: {self._darken_color(t.background_color, 10)};
            border: none;
            padding: 4px;
        }}
        """
    
    def _lighten_color(self, color: str, percent: int) -> str:
        """色を明るくする"""
        # 簡易実装: 16進数カラーを解析して明るくする
        color = color.lstrip('#')
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        
        r = min(255, r + int((255 - r) * percent / 100))
        g = min(255, g + int((255 - g) * percent / 100))
        b = min(255, b + int((255 - b) * percent / 100))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _darken_color(self, color: str, percent: int) -> str:
        """色を暗くする"""
        color = color.lstrip('#')
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        
        r = max(0, r - int(r * percent / 100))
        g = max(0, g - int(g * percent / 100))
        b = max(0, b - int(b * percent / 100))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def register_listener(self, callback: Callable[[UITheme], None]):
        """テーマ変更リスナーを登録"""
        self._listeners.append(callback)
    
    def _notify_listeners(self):
        """リスナーに通知"""
        for listener in self._listeners:
            try:
                listener(self._current_theme)
            except Exception as e:
                logger.error(f"Theme listener error: {e}")


class ProgressIndicator:
    """詳細な進捗表示クラス"""
    
    def __init__(self, 
                 progress_bar: Any = None,
                 status_label: Any = None,
                 detail_label: Any = None):
        self.progress_bar = progress_bar
        self.status_label = status_label
        self.detail_label = detail_label
        
        self._current_phase = ""
        self._phases: List[str] = []
        self._phase_weights: Dict[str, float] = {}
    
    def set_phases(self, phases: List[str], weights: List[float] = None):
        """処理フェーズを設定"""
        self._phases = phases
        if weights and len(weights) == len(phases):
            total = sum(weights)
            self._phase_weights = {p: w/total for p, w in zip(phases, weights)}
        else:
            # 均等配分
            weight = 1.0 / len(phases) if phases else 1.0
            self._phase_weights = {p: weight for p in phases}
    
    def set_phase(self, phase: str, message: str = ""):
        """現在のフェーズを設定"""
        self._current_phase = phase
        if self.status_label:
            self.status_label.setText(f"{phase}: {message}" if message else phase)
    
    def set_progress(self, phase: str, percent: float):
        """進捗を設定"""
        if phase not in self._phase_weights:
            # フェーズが設定されていない場合は直接設定
            if self.progress_bar:
                self.progress_bar.setValue(int(percent))
            return
        
        # 全体進捗を計算
        phase_index = self._phases.index(phase)
        base_progress = sum(
            self._phase_weights[p] * 100 
            for p in self._phases[:phase_index]
        )
        current_phase_progress = self._phase_weights[phase] * percent
        total_progress = base_progress + current_phase_progress
        
        if self.progress_bar:
            self.progress_bar.setValue(int(total_progress))
    
    def set_detail(self, detail: str):
        """詳細メッセージを設定"""
        if self.detail_label:
            self.detail_label.setText(detail)


class NotificationManager:
    """通知管理クラス"""
    
    def __init__(self, parent: Any = None):
        self.parent = parent
        self._notifications: List[Dict[str, Any]] = []
    
    def show_notification(self, 
                         message: str, 
                         notification_type: str = "info",
                         duration: int = 3000):
        """通知を表示"""
        notification = {
            "message": message,
            "type": notification_type,
            "duration": duration,
            "timestamp": time.time()
        }
        
        self._notifications.append(notification)
        
        # 実際の表示処理
        if self.parent:
            self._display_notification(notification)
    
    def _display_notification(self, notification: Dict[str, Any]):
        """通知を実際に表示"""
        try:
            from PySide6.QtWidgets import QMessageBox
            
            msg_type = notification["type"]
            message = notification["message"]
            
            if msg_type == "error":
                QMessageBox.critical(self.parent, "エラー", message)
            elif msg_type == "warning":
                QMessageBox.warning(self.parent, "警告", message)
            elif msg_type == "success":
                QMessageBox.information(self.parent, "成功", message)
            else:
                QMessageBox.information(self.parent, "情報", message)
        
        except Exception as e:
            logger.error(f"Notification display failed: {e}")


class DragDropHandler:
    """ドラッグ＆ドロップ処理ハンドラー"""
    
    def __init__(self, 
                 supported_extensions: List[str] = None,
                 callback: Callable[[List[str]], None] = None):
        self.supported_extensions = set(
            ext.lower() for ext in (supported_extensions or [".wav", ".mp3", ".m4a", ".flac"])
        )
        self.callback = callback
        self._drag_active = False
    
    def validate_drag(self, mime_data: Any) -> bool:
        """ドラッグデータを検証"""
        if not mime_data.hasUrls():
            return False
        
        urls = mime_data.urls()
        if not urls:
            return False
        
        # サポートされるファイルが含まれているかチェック
        for url in urls:
            file_path = url.toLocalFile()
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self.supported_extensions:
                return True
        
        return False
    
    def handle_drop(self, mime_data: Any) -> List[str]:
        """ドロップを処理"""
        if not mime_data.hasUrls():
            return []
        
        valid_files = []
        for url in mime_data.urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1].lower()
                if ext in self.supported_extensions:
                    valid_files.append(file_path)
        
        if self.callback and valid_files:
            self.callback(valid_files)
        
        return valid_files


class KeyboardShortcuts:
    """キーボードショートカット定義"""
    
    SHORTCUTS = {
        "open_file": ("Ctrl+O", "ファイルを開く"),
        "save_file": ("Ctrl+S", "ファイルを保存"),
        "start_transcription": ("Ctrl+T", "文字起こし開始"),
        "stop_transcription": ("Ctrl+Shift+T", "文字起こし停止"),
        "batch_process": ("Ctrl+B", "バッチ処理"),
        "settings": ("Ctrl+,", "設定"),
        "quit": ("Ctrl+Q", "終了"),
        "copy": ("Ctrl+C", "コピー"),
        "paste": ("Ctrl+V", "貼り付け"),
        "select_all": ("Ctrl+A", "すべて選択"),
        "find": ("Ctrl+F", "検索"),
        "zoom_in": ("Ctrl++", "拡大"),
        "zoom_out": ("Ctrl+-", "縮小"),
        "toggle_theme": ("Ctrl+Shift+L", "テーマ切り替え"),
        "help": ("F1", "ヘルプ"),
    }
    
    @classmethod
    def get_shortcut(cls, action: str) -> str:
        """ショートカットを取得"""
        return cls.SHORTCUTS.get(action, ("", ""))[0]
    
    @classmethod
    def get_description(cls, action: str) -> str:
        """説明を取得"""
        return cls.SHORTCUTS.get(action, ("", ""))[1]
    
    @classmethod
    def register_shortcuts(cls, parent: Any, actions: Dict[str, Callable]):
        """ショートカットを登録"""
        try:
            from PySide6.QtGui import QKeySequence, QShortcut
            
            for action_name, callback in actions.items():
                shortcut_str = cls.get_shortcut(action_name)
                if shortcut_str:
                    shortcut = QShortcut(QKeySequence(shortcut_str), parent)
                    shortcut.activated.connect(callback)
        
        except Exception as e:
            logger.error(f"Shortcut registration failed: {e}")


# グローバルテーママネージャー
_theme_manager = ThemeManager()

def get_theme_manager() -> ThemeManager:
    """グローバルテーママネージャーを取得"""
    return _theme_manager


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== UI/UX Improvements Test ===\n")
    
    # テーマテスト
    manager = get_theme_manager()
    print(f"Default theme: {manager.get_theme().name}")
    
    stylesheet = manager.get_stylesheet()
    print(f"Stylesheet length: {len(stylesheet)} chars")
    
    # ショートカットテスト
    print("\nKeyboard shortcuts:")
    for action, (shortcut, desc) in list(KeyboardShortcuts.SHORTCUTS.items())[:5]:
        print(f"  {action}: {shortcut} - {desc}")
    
    print("\nTest completed!")
