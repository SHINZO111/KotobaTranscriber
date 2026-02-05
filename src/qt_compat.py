"""
PySide6 → PyQt5 移行アダプター
互換性レイヤーと移行ガイド

DEPRECATED: このモジュールは非推奨です。新しいコードでは PySide6 を直接インポートしてください。
テストがまだ参照しているため削除はしませんが、プロダクションコードでの使用は避けてください。
"""

# ============================================================================
# 移行概要
# ============================================================================
"""
【主要な変更点】

1. インポート変更:
   PySide6.QtWidgets → PyQt5.QtWidgets
   PySide6.QtCore → PyQt5.QtCore
   PySide6.QtGui → PyQt5.QtGui

2. Signal/Slot の変更:
   PySide6: Signal, Slot
   PyQt5: pyqtSignal, pyqtSlot

3. その他の違い:
   - PyQt5ではexec_()を使用（Pythonの予約語回避）
   - 一部のメソッド名が異なる場合あり

【ライセンス注意】
PyQt5はGPL v3または商用ライセンスが必要
PySide6はLGPL v3（より緩やか）

本プロジェクトではPyQt5を採用（GPL v3準拠）
"""

# ============================================================================
# 統一インポートモジュール
# ============================================================================

try:
    # PyQt5を優先して試行
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QPushButton, QTextEdit, QFileDialog, QLabel, QProgressBar, QMessageBox,
        QCheckBox, QGroupBox, QListWidget, QListWidgetItem, QSystemTrayIcon, QMenu,
        QSpinBox, QFrame, QTabWidget, QComboBox, QSlider, QDialog, QLineEdit,
        QPlainTextEdit, QSplitter, QStatusBar, QToolBar, QAction, QMenuBar,
        QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView,
        QAbstractItemView, QScrollArea, QStackedWidget, QProgressDialog, QInputDialog,
        QColorDialog, QFontDialog, QWizard, QWizardPage, QSizePolicy
    )
    from PyQt5.QtCore import (
        Qt, QThread, Signal as PyQtSignal, pyqtSignal, pyqtSlot, QRunnable, 
        QThreadPool, Slot, QObject, QTimer, QSettings, QCoreApplication,
        QMimeData, QUrl, QPoint, QSize, QEvent, QMetaObject, Q_ARG
    )
    from PyQt5.QtGui import (
        QIcon, QPixmap, QPainter, QColor, QFont, QFontMetrics, QKeySequence,
        QClipboard, QCursor, QMouseEvent, QCloseEvent, QDragEnterEvent, QDropEvent,
        QTextCursor, QTextCharFormat, QSyntaxHighlighter, QPalette
    )
    
    # 互換性のためのエイリアス
    Signal = pyqtSignal
    Slot = pyqtSlot
    
    QT_VERSION = "PyQt5"
    
except ImportError:
    # PyQt5がない場合はPySide6をフォールバック
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QPushButton, QTextEdit, QFileDialog, QLabel, QProgressBar, QMessageBox,
        QCheckBox, QGroupBox, QListWidget, QListWidgetItem, QSystemTrayIcon, QMenu,
        QSpinBox, QFrame, QTabWidget, QComboBox, QSlider, QDialog, QLineEdit,
        QPlainTextEdit, QSplitter, QStatusBar, QToolBar, QAction, QMenuBar,
        QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView,
        QAbstractItemView, QScrollArea, QStackedWidget, QProgressDialog, QInputDialog,
        QColorDialog, QFontDialog, QWizard, QWizardPage, QSizePolicy
    )
    from PySide6.QtCore import (
        Qt, QThread, Signal, Slot, QRunnable, QThreadPool, QObject, QTimer,
        QSettings, QCoreApplication, QMimeData, QUrl, QPoint, QSize, QEvent,
        QMetaObject, Q_ARG
    )
    from PySide6.QtGui import (
        QIcon, QPixmap, QPainter, QColor, QFont, QFontMetrics, QKeySequence,
        QClipboard, QCursor, QMouseEvent, QCloseEvent, QDragEnterEvent, QDropEvent,
        QTextCursor, QTextCharFormat, QSyntaxHighlighter, QPalette
    )
    
    QT_VERSION = "PySide6"

import sys
import logging

logger = logging.getLogger(__name__)
logger.info(f"Using Qt binding: {QT_VERSION}")


# ============================================================================
# 互換性関数
# ============================================================================

def exec_dialog(dialog):
    """
    ダイアログを実行（PyQt5/PySide6互換）
    
    Args:
        dialog: 実行するダイアログ
        
    Returns:
        ダイアログの結果
    """
    if QT_VERSION == "PyQt5":
        return dialog.exec_()
    else:
        return dialog.exec()


def exec_menu(menu):
    """
    メニューを実行（PyQt5/PySide6互対）
    
    Args:
        menu: 実行するメニュー
        
    Returns:
        メニューの結果
    """
    if QT_VERSION == "PyQt5":
        return menu.exec_(QCursor.pos())
    else:
        return menu.exec(QCursor.pos())


def exec_app(app):
    """
    アプリケーションを実行（PyQt5/PySide6互対）
    
    Args:
        app: QApplicationインスタンス
        
    Returns:
        アプリケーションの終了コード
    """
    if QT_VERSION == "PyQt5":
        return app.exec_()
    else:
        return app.exec()


# ============================================================================
# 移行チェッカー
# ============================================================================

def check_migration_issues(file_path: str) -> list:
    """
    ファイル内の移行が必要な箇所をチェック
    
    Args:
        file_path: チェックするファイルパス
        
    Returns:
        問題リスト
    """
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        # PySide6のインポートをチェック
        if 'from PySide6' in line or 'import PySide6' in line:
            issues.append(f"Line {i}: PySide6 import found - {line.strip()}")
        
        # Signalの使用をチェック（PySide6スタイル）
        if 'progress = Signal(' in line or 'finished = Signal(' in line:
            if 'pyqtSignal' not in lines[max(0, i-10):i]:
                issues.append(f"Line {i}: PySide6-style Signal - {line.strip()}")
        
        # exec()の使用をチェック
        if '.exec()' in line and '.exec_()' not in line:
            issues.append(f"Line {i}: exec() should be exec_() for PyQt5 - {line.strip()}")
    
    return issues


def migrate_file(file_path: str, output_path: str = None) -> bool:
    """
    ファイルをPyQt5用に移行
    
    Args:
        file_path: 入力ファイルパス
        output_path: 出力ファイルパス（Noneの場合は上書き）
        
    Returns:
        成功時True
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 置換ルール
        replacements = [
            # インポート
            ('from PySide6.', 'from PyQt5.'),
            ('import PySide6', 'import PyQt5'),
            
            # Signal/Slot
            ('from PyQt5.QtCore import Signal', 'from PyQt5.QtCore import pyqtSignal as Signal'),
            ('from PyQt5.QtCore import Slot', 'from PyQt5.QtCore import pyqtSlot as Slot'),
            
            # exec() → exec_()
            ('.exec()', '.exec_()'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        # 出力
        if output_path is None:
            output_path = file_path
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Migrated: {file_path} -> {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


# ============================================================================
# テスト
# ============================================================================

if __name__ == "__main__":
    print(f"Qt Binding: {QT_VERSION}")
    print("\nAvailable imports:")
    print("- QApplication, QMainWindow, QWidget")
    print("- QVBoxLayout, QHBoxLayout, QGridLayout")
    print("- QPushButton, QLabel, QProgressBar")
    print("- QThread, Signal, Slot")
    print("- QIcon, QPixmap, QColor")
    print("\nMigration utilities:")
    print("- check_migration_issues(file_path)")
    print("- migrate_file(file_path, output_path)")
