"""
ダークテーマモジュール
PySide6用ダークモードスタイルシート
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class DarkTheme:
    """ダークテーマ設定クラス"""

    # カラーパレット
    COLORS = {
        # 背景色
        "background": "#1e1e1e",
        "surface": "#252526",
        "elevated": "#2d2d30",

        # 前景色
        "text_primary": "#d4d4d4",
        "text_secondary": "#9cdcfe",
        "text_disabled": "#6e6e6e",

        # アクセント色
        "accent": "#007acc",
        "accent_hover": "#1177bb",
        "accent_pressed": "#005a9e",

        # 状態色
        "success": "#4ec9b0",
        "warning": "#ce9178",
        "error": "#f44747",
        "info": "#569cd6",

        # ボーダー
        "border": "#3e3e42",
        "border_focus": "#007acc",

        # ボタン
        "button_bg": "#0e639c",
        "button_hover": "#1177bb",
        "button_pressed": "#005a9e",
        "button_disabled": "#3e3e42",
    }

    @classmethod
    def get_stylesheet(cls) -> str:
        """
        ダークテーム用スタイルシートを取得

        Returns:
            QSSスタイルシート文字列
        """
        c = cls.COLORS

        return f"""
        /* メインウィンドウ */
        QMainWindow {{
            background-color: {c['background']};
            color: {c['text_primary']};
        }}

        QWidget {{
            background-color: {c['background']};
            color: {c['text_primary']};
            font-family: "Segoe UI", "Meiryo UI", sans-serif;
            font-size: 10pt;
        }}

        /* グループボックス */
        QGroupBox {{
            background-color: {c['surface']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
            font-weight: bold;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {c['text_secondary']};
        }}

        /* ボタン */
        QPushButton {{
            background-color: {c['button_bg']};
            color: white;
            border: none;
            border-radius: 3px;
            padding: 6px 16px;
            font-weight: bold;
        }}

        QPushButton:hover {{
            background-color: {c['button_hover']};
        }}

        QPushButton:pressed {{
            background-color: {c['button_pressed']};
        }}

        QPushButton:disabled {{
            background-color: {c['button_disabled']};
            color: {c['text_disabled']};
        }}

        /* プライマリーボタン（緑） */
        QPushButton#primary {{
            background-color: {c['success']};
            color: {c['background']};
        }}

        QPushButton#primary:hover {{
            background-color: #5fd9c0;
        }}

        /* 警告ボタン（オレンジ） */
        QPushButton#warning {{
            background-color: {c['warning']};
            color: {c['background']};
        }}

        /* 危険ボタン（赤） */
        QPushButton#danger {{
            background-color: {c['error']};
            color: white;
        }}

        QPushButton#danger:hover {{
            background-color: #ff5a5a;
        }}

        /* ラインエディット */
        QLineEdit {{
            background-color: {c['elevated']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 3px;
            padding: 4px 8px;
        }}

        QLineEdit:focus {{
            border: 1px solid {c['border_focus']};
        }}

        QLineEdit:disabled {{
            background-color: {c['surface']};
            color: {c['text_disabled']};
        }}

        /* テキストエディット */
        QTextEdit {{
            background-color: {c['elevated']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 3px;
            padding: 4px;
        }}

        QTextEdit:focus {{
            border: 1px solid {c['border_focus']};
        }}

        /* コンボボックス */
        QComboBox {{
            background-color: {c['elevated']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 3px;
            padding: 4px 8px;
            min-width: 6em;
        }}

        QComboBox:hover {{
            border: 1px solid {c['border_focus']};
        }}

        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid {c['border']};
        }}

        QComboBox QAbstractItemView {{
            background-color: {c['elevated']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            selection-background-color: {c['accent']};
        }}

        /* チェックボックス */
        QCheckBox {{
            color: {c['text_primary']};
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {c['border']};
            border-radius: 3px;
            background-color: {c['elevated']};
        }}

        QCheckBox::indicator:checked {{
            background-color: {c['accent']};
            border: 1px solid {c['accent']};
        }}

        QCheckBox::indicator:hover {{
            border: 1px solid {c['border_focus']};
        }}

        /* ラジオボタン */
        QRadioButton {{
            color: {c['text_primary']};
            spacing: 8px;
        }}

        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {c['border']};
            border-radius: 8px;
            background-color: {c['elevated']};
        }}

        QRadioButton::indicator:checked {{
            background-color: {c['accent']};
            border: 1px solid {c['accent']};
        }}

        /* スピンボックス */
        QSpinBox, QDoubleSpinBox {{
            background-color: {c['elevated']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 3px;
            padding: 4px;
        }}

        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {c['surface']};
            border: 1px solid {c['border']};
            width: 16px;
        }}

        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {c['accent']};
        }}

        /* スライダー */
        QSlider::groove:horizontal {{
            height: 4px;
            background-color: {c['border']};
            border-radius: 2px;
        }}

        QSlider::handle:horizontal {{
            background-color: {c['accent']};
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}

        QSlider::handle:horizontal:hover {{
            background-color: {c['accent_hover']};
        }}

        QSlider::sub-page:horizontal {{
            background-color: {c['accent']};
            border-radius: 2px;
        }}

        /* プログレスバー */
        QProgressBar {{
            border: 1px solid {c['border']};
            border-radius: 3px;
            background-color: {c['elevated']};
            text-align: center;
            color: {c['text_primary']};
        }}

        QProgressBar::chunk {{
            background-color: {c['accent']};
            border-radius: 2px;
        }}

        /* リストウィジェット */
        QListWidget {{
            background-color: {c['elevated']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            border-radius: 3px;
            outline: none;
        }}

        QListWidget::item {{
            padding: 4px 8px;
            border-bottom: 1px solid {c['border']};
        }}

        QListWidget::item:selected {{
            background-color: {c['accent']};
        }}

        QListWidget::item:hover {{
            background-color: {c['surface']};
        }}

        /* タブウィジェット */
        QTabWidget::pane {{
            border: 1px solid {c['border']};
            background-color: {c['surface']};
        }}

        QTabBar::tab {{
            background-color: {c['surface']};
            color: {c['text_secondary']};
            padding: 8px 16px;
            border: 1px solid {c['border']};
            border-bottom: none;
            border-top-left-radius: 3px;
            border-top-right-radius: 3px;
        }}

        QTabBar::tab:selected {{
            background-color: {c['accent']};
            color: white;
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {c['elevated']};
        }}

        /* スクロールバー */
        QScrollBar:vertical {{
            background-color: {c['surface']};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {c['border']};
            min-height: 20px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {c['text_disabled']};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: {c['surface']};
            height: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {c['border']};
            min-width: 20px;
            border-radius: 6px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {c['text_disabled']};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* メニュー */
        QMenu {{
            background-color: {c['surface']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            padding: 4px;
        }}

        QMenu::item {{
            padding: 4px 20px;
        }}

        QMenu::item:selected {{
            background-color: {c['accent']};
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {c['border']};
            margin: 4px 8px;
        }}

        /* メニューバー */
        QMenuBar {{
            background-color: {c['surface']};
            color: {c['text_primary']};
            border-bottom: 1px solid {c['border']};
        }}

        QMenuBar::item {{
            padding: 4px 12px;
            background-color: transparent;
        }}

        QMenuBar::item:selected {{
            background-color: {c['accent']};
        }}

        /* ステータスバー */
        QStatusBar {{
            background-color: {c['accent']};
            color: white;
        }}

        QStatusBar::item {{
            border: none;
        }}

        /* ラベル */
        QLabel {{
            color: {c['text_primary']};
        }}

        QLabel#title {{
            font-size: 14pt;
            font-weight: bold;
            color: {c['text_secondary']};
        }}

        QLabel#subtitle {{
            font-size: 10pt;
            color: {c['text_disabled']};
        }}

        /* ツールチップ */
        QToolTip {{
            background-color: {c['elevated']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            padding: 4px 8px;
        }}
        """

    @classmethod
    def apply(cls, app: QApplication):
        """
        アプリケーションにダークテーマを適用

        Args:
            app: QApplicationインスタンス
        """
        app.setStyleSheet(cls.get_stylesheet())

        # パレットも設定
        palette = QPalette()
        c = cls.COLORS

        palette.setColor(QPalette.Window, QColor(c['background']))
        palette.setColor(QPalette.WindowText, QColor(c['text_primary']))
        palette.setColor(QPalette.Base, QColor(c['elevated']))
        palette.setColor(QPalette.AlternateBase, QColor(c['surface']))
        palette.setColor(QPalette.ToolTipBase, QColor(c['elevated']))
        palette.setColor(QPalette.ToolTipText, QColor(c['text_primary']))
        palette.setColor(QPalette.Text, QColor(c['text_primary']))
        palette.setColor(QPalette.Button, QColor(c['button_bg']))
        palette.setColor(QPalette.ButtonText, QColor("white"))
        palette.setColor(QPalette.BrightText, QColor(c['error']))
        palette.setColor(QPalette.Highlight, QColor(c['accent']))
        palette.setColor(QPalette.HighlightedText, QColor("white"))

        # Disabled group for accessibility
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.WindowText, QColor(c['text_disabled']))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.Text, QColor(c['text_disabled']))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ButtonText, QColor(c['text_disabled']))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.Button, QColor(c['button_disabled']))

        app.setPalette(palette)


class LightTheme:
    """ライトテーマ（デフォルト）"""

    @classmethod
    def get_stylesheet(cls) -> str:
        """ライトテーマ用スタイルシート"""
        return """"""  # デフォルトを使用

    @classmethod
    def apply(cls, app: QApplication):
        """ライトテーマを適用"""
        app.setStyleSheet("")
        style = app.style()
        if style is not None:
            app.setPalette(style.standardPalette())
        else:
            app.setPalette(QPalette())


def set_theme(app: QApplication, dark_mode: bool = True):
    """
    テーマを設定

    Args:
        app: QApplicationインスタンス
        dark_mode: Trueの場合ダークモード
    """
    if dark_mode:
        DarkTheme.apply(app)
    else:
        LightTheme.apply(app)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
        QCheckBox, QGroupBox, QSlider, QProgressBar
    )

    app = QApplication(sys.argv)

    # ダークテーマ適用
    DarkTheme.apply(app)

    # テストウィンドウ
    window = QMainWindow()
    window.setWindowTitle("Dark Theme Test")
    window.resize(600, 500)

    central = QWidget()
    layout = QVBoxLayout(central)

    # タイトル
    title = QLabel("ダークテーマテスト")
    title.setObjectName("title")
    layout.addWidget(title)

    # グループボックス
    group = QGroupBox("設定")
    group_layout = QVBoxLayout()

    # 入力フィールド
    group_layout.addWidget(QLabel("テキスト入力:"))
    group_layout.addWidget(QLineEdit("サンプルテキスト"))

    # コンボボックス
    combo = QComboBox()
    combo.addItems(["オプション1", "オプション2", "オプション3"])
    group_layout.addWidget(combo)

    # チェックボックス
    checkbox = QCheckBox("有効化")
    checkbox.setChecked(True)
    group_layout.addWidget(checkbox)

    group.setLayout(group_layout)
    layout.addWidget(group)

    # テキストエディット
    text_edit = QTextEdit()
    text_edit.setPlainText("ここにテキストを入力...\n複数行対応")
    layout.addWidget(text_edit)

    # ボタン
    btn_layout = QHBoxLayout()

    btn_normal = QPushButton("通常ボタン")
    btn_layout.addWidget(btn_normal)

    btn_primary = QPushButton("プライマリー")
    btn_primary.setObjectName("primary")
    btn_layout.addWidget(btn_primary)

    btn_danger = QPushButton("危険")
    btn_danger.setObjectName("danger")
    btn_layout.addWidget(btn_danger)

    layout.addLayout(btn_layout)

    # プログレスバー
    progress = QProgressBar()
    progress.setValue(65)
    layout.addWidget(progress)

    # スライダー
    slider = QSlider(Qt.Horizontal)
    slider.setValue(50)
    layout.addWidget(slider)

    window.setCentralWidget(central)
    window.show()

    sys.exit(app.exec())
