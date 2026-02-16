"""
カスタム語彙管理ダイアログ
専門用語やホットワードをGUIで管理
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from custom_vocabulary import CustomVocabulary

logger = logging.getLogger(__name__)


class VocabularyDialog(QDialog):
    """カスタム語彙管理ダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("カスタム語彙管理")
        self.setMinimumSize(700, 500)

        # カスタム語彙マネージャーを初期化
        try:
            self.vocabulary = CustomVocabulary()
        except Exception as e:
            logger.error(f"Failed to initialize vocabulary: {e}")
            self.vocabulary = None
            QMessageBox.warning(self, "エラー", f"語彙ファイルの読み込みに失敗しました:\n{e}")
            self.reject()
            return

        self.init_ui()
        self.load_data()

    def init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout()

        # タブウィジェット
        tabs = QTabWidget()

        # タブ1: ホットワード管理
        hotwords_tab = self.create_hotwords_tab()
        tabs.addTab(hotwords_tab, "ホットワード")

        # タブ2: 置換ルール管理
        replacements_tab = self.create_replacements_tab()
        tabs.addTab(replacements_tab, "置換ルール")

        # タブ3: インポート/エクスポート
        import_export_tab = self.create_import_export_tab()
        tabs.addTab(import_export_tab, "インポート/エクスポート")

        layout.addWidget(tabs)

        # 閉じるボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton("閉じる")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_hotwords_tab(self) -> QWidget:
        """ホットワードタブを作成"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 説明
        info_label = QLabel(
            "ホットワードは文字起こし時にWhisperに提示され、認識精度が向上します。\n" "専門用語や固有名詞を登録してください。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # ホットワードリスト
        list_group = QGroupBox("登録済みホットワード")
        list_layout = QVBoxLayout()

        self.hotword_list = QListWidget()
        self.hotword_list.setSelectionMode(QListWidget.SingleSelection)
        list_layout.addWidget(self.hotword_list)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # 追加/削除コントロール
        control_layout = QHBoxLayout()

        self.hotword_input = QLineEdit()
        self.hotword_input.setPlaceholderText("追加するホットワードを入力...")
        self.hotword_input.returnPressed.connect(self.add_hotword)
        control_layout.addWidget(self.hotword_input)

        add_button = QPushButton("追加")
        add_button.clicked.connect(self.add_hotword)
        control_layout.addWidget(add_button)

        remove_button = QPushButton("削除")
        remove_button.clicked.connect(self.remove_hotword)
        control_layout.addWidget(remove_button)

        clear_button = QPushButton("全クリア")
        clear_button.clicked.connect(self.clear_hotwords)
        control_layout.addWidget(clear_button)

        layout.addLayout(control_layout)

        widget.setLayout(layout)
        return widget

    def create_replacements_tab(self) -> QWidget:
        """置換ルールタブを作成"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 説明
        info_label = QLabel("よくある誤認識を自動的に修正します。\n" "例: 「エーピーアイ」→「API」")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 置換ルールリスト
        list_group = QGroupBox("登録済み置換ルール")
        list_layout = QVBoxLayout()

        self.replacement_list = QListWidget()
        self.replacement_list.setSelectionMode(QListWidget.SingleSelection)
        list_layout.addWidget(self.replacement_list)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # 追加/削除コントロール
        control_layout = QHBoxLayout()

        wrong_label = QLabel("誤認識:")
        control_layout.addWidget(wrong_label)

        self.wrong_input = QLineEdit()
        self.wrong_input.setPlaceholderText("例: エーピーアイ")
        control_layout.addWidget(self.wrong_input)

        arrow_label = QLabel("→")
        control_layout.addWidget(arrow_label)

        correct_label = QLabel("正しい表記:")
        control_layout.addWidget(correct_label)

        self.correct_input = QLineEdit()
        self.correct_input.setPlaceholderText("例: API")
        self.correct_input.returnPressed.connect(self.add_replacement)
        control_layout.addWidget(self.correct_input)

        layout.addLayout(control_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        add_button = QPushButton("追加")
        add_button.clicked.connect(self.add_replacement)
        button_layout.addWidget(add_button)

        remove_button = QPushButton("削除")
        remove_button.clicked.connect(self.remove_replacement)
        button_layout.addWidget(remove_button)

        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def create_import_export_tab(self) -> QWidget:
        """インポート/エクスポートタブを作成"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 説明
        info_label = QLabel("ホットワードをテキスト形式でインポート/エクスポートできます。\n" "1行に1単語を記入してください。")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # テキストエリア
        self.import_export_text = QTextEdit()
        self.import_export_text.setPlaceholderText("例:\nPython\nJavaScript\nKubernetes\nDocker")
        layout.addWidget(self.import_export_text)

        # ボタン
        button_layout = QHBoxLayout()

        export_button = QPushButton("エクスポート")
        export_button.clicked.connect(self.export_words)
        button_layout.addWidget(export_button)

        import_button = QPushButton("インポート")
        import_button.clicked.connect(self.import_words)
        button_layout.addWidget(import_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def load_data(self):
        """データをロード"""
        if self.vocabulary is None:
            return

        # ホットワードをロード
        self.hotword_list.clear()
        for word in self.vocabulary.get_hotwords_list():
            self.hotword_list.addItem(word)

        # 置換ルールをロード
        self.replacement_list.clear()
        for wrong, correct in self.vocabulary.get_replacements_dict().items():
            item = QListWidgetItem(f"{wrong} → {correct}")
            item.setData(Qt.UserRole, wrong)
            self.replacement_list.addItem(item)

    def add_hotword(self):
        """ホットワードを追加"""
        word = self.hotword_input.text().strip()

        if not word:
            return

        if self.vocabulary is None:
            return

        try:
            self.vocabulary.add_hotword(word)
            self.hotword_list.addItem(word)
            self.hotword_input.clear()
            logger.info(f"Added hotword: {word}")
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"ホットワードの追加に失敗しました:\n{e}")

    def remove_hotword(self):
        """ホットワードを削除"""
        current_item = self.hotword_list.currentItem()

        if current_item is None:
            QMessageBox.information(self, "情報", "削除するホットワードを選択してください")
            return

        word = current_item.text()

        if self.vocabulary is None:
            return

        try:
            self.vocabulary.remove_hotword(word)
            self.hotword_list.takeItem(self.hotword_list.currentRow())
            logger.info(f"Removed hotword: {word}")
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"ホットワードの削除に失敗しました:\n{e}")

    def clear_hotwords(self):
        """全ホットワードをクリア"""
        reply = QMessageBox.question(
            self,
            "確認",
            "全てのホットワードを削除しますか？\nこの操作は取り消せません。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            if self.vocabulary is None:
                return

            try:
                self.vocabulary.clear_hotwords()
                self.hotword_list.clear()
                logger.info("Cleared all hotwords")
            except Exception as e:
                QMessageBox.warning(self, "エラー", f"クリアに失敗しました:\n{e}")

    def add_replacement(self):
        """置換ルールを追加"""
        wrong = self.wrong_input.text().strip()
        correct = self.correct_input.text().strip()

        if not wrong or not correct:
            QMessageBox.information(self, "情報", "誤認識と正しい表記の両方を入力してください")
            return

        if self.vocabulary is None:
            return

        try:
            self.vocabulary.add_replacement(wrong, correct)
            item = QListWidgetItem(f"{wrong} → {correct}")
            item.setData(Qt.UserRole, wrong)
            self.replacement_list.addItem(item)
            self.wrong_input.clear()
            self.correct_input.clear()
            logger.info(f"Added replacement: {wrong} → {correct}")
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"置換ルールの追加に失敗しました:\n{e}")

    def remove_replacement(self):
        """置換ルールを削除"""
        current_item = self.replacement_list.currentItem()

        if current_item is None:
            QMessageBox.information(self, "情報", "削除する置換ルールを選択してください")
            return

        # QListWidgetItemのデータロールから誤認識キーを取得
        wrong = current_item.data(Qt.UserRole)

        if self.vocabulary is None:
            return

        try:
            self.vocabulary.remove_replacement(wrong)
            self.replacement_list.takeItem(self.replacement_list.currentRow())
            logger.info(f"Removed replacement: {wrong}")
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"置換ルールの削除に失敗しました:\n{e}")

    def export_words(self):
        """ホットワードをエクスポート"""
        if self.vocabulary is None:
            return

        try:
            text = self.vocabulary.export_words_to_text()
            self.import_export_text.setPlainText(text)
            logger.info("Exported hotwords")
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"エクスポートに失敗しました:\n{e}")

    def import_words(self):
        """ホットワードをインポート"""
        text = self.import_export_text.toPlainText().strip()

        if not text:
            QMessageBox.information(self, "情報", "インポートするテキストを入力してください")
            return

        if self.vocabulary is None:
            return

        try:
            self.vocabulary.import_words_from_text(text)
            self.load_data()  # リストを再読み込み
            QMessageBox.information(self, "完了", "ホットワードをインポートしました")
            logger.info("Imported hotwords")
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"インポートに失敗しました:\n{e}")


if __name__ == "__main__":
    # テスト用コード
    import sys

    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    dialog = VocabularyDialog()
    dialog.exec()
