"""
アイコン表示テストスクリプト
新しいアイコンがすべての箇所で正しく表示されるかテスト
"""
import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

class IconTestWindow(QMainWindow):
    """アイコンテスト用ウィンドウ"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("KotobaTranscriber - アイコンテスト")
        self.setGeometry(100, 100, 500, 400)

        # メインウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # タイトル
        title = QLabel("🎨 アイコン表示テスト")
        title.setStyleSheet("font-size: 20px; font-weight: bold; padding: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # アイコンプレビュー
        icon_label = QLabel("アイコンプレビュー（256x256）:")
        icon_label.setStyleSheet("font-size: 14px; padding-top: 10px;")
        layout.addWidget(icon_label)

        # アイコン画像を表示
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_display = QLabel()
            icon_display.setPixmap(pixmap)
            icon_display.setAlignment(Qt.AlignCenter)
            icon_display.setStyleSheet("padding: 20px;")
            layout.addWidget(icon_display)

            # ウィンドウアイコンとして設定
            self.setWindowIcon(QIcon(icon_path))

        # 確認項目リスト
        checks = QLabel(
            "確認項目:\n"
            "✓ ウィンドウタイトルバーのアイコン\n"
            "✓ タスクバーのアイコン\n"
            "✓ Alt+Tabでのアイコン\n"
            "✓ アイコンの配色（青→紫グラデーション）\n"
            "✓ 音声波形バー（3本）\n"
            "✓ 日本語文字「文」"
        )
        checks.setStyleSheet("font-size: 12px; padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(checks)

        # 閉じるボタン
        close_btn = QPushButton("テスト完了 - 閉じる")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("padding: 10px; font-size: 14px; margin-top: 10px;")
        layout.addWidget(close_btn)

        # ストレッチを追加して配置を整える
        layout.addStretch()

def main():
    """メイン関数"""
    app = QApplication(sys.argv)

    # アプリケーション全体のアイコンも設定
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = IconTestWindow()
    window.show()

    print("\n" + "="*60)
    print("アイコンテストウィンドウを表示しています")
    print("="*60)
    print("\n以下を確認してください:")
    print("  1. ウィンドウタイトルバーにアイコンが表示される")
    print("  2. タスクバーにアイコンが表示される")
    print("  3. アイコンの色: 青から紫へのグラデーション")
    print("  4. 音声波形: 3本の白いバー")
    print("  5. 日本語文字: 「文」")
    print("\nすべて確認できたら「テスト完了」ボタンを押してください。")
    print("="*60 + "\n")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
