"""
Main Window 拡張パッチ
新機能を既存のmain.pyに統合するための拡張モジュール
"""

import os
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QCheckBox, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QThread, Signal

# インポート新機能
try:
    from realtime_tab import RealtimeTab
    REALTIME_AVAILABLE = True
except ImportError:
    REALTIME_AVAILABLE = False

try:
    from subtitle_exporter import SubtitleExporter, TranscriptionResult
    SUBTITLE_AVAILABLE = True
except ImportError:
    SUBTITLE_AVAILABLE = False

try:
    from api_corrector import HybridCorrector, create_corrector
    API_CORRECTOR_AVAILABLE = True
except ImportError:
    API_CORRECTOR_AVAILABLE = False

try:
    from enhanced_batch_processor import EnhancedBatchProcessor, can_resume_batch
    ENHANCED_BATCH_AVAILABLE = True
except ImportError:
    ENHANCED_BATCH_AVAILABLE = False

try:
    from dark_theme import DarkTheme, set_theme
    DARK_THEME_AVAILABLE = True
except ImportError:
    DARK_THEME_AVAILABLE = False

try:
    from llm_corrector_standalone import SimpleLLMCorrector
    LOCAL_CORRECTOR_AVAILABLE = True
except ImportError:
    LOCAL_CORRECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


class ExportOptionsDialog(QWidget):
    """エクスポートオプションダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("エクスポートオプション")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # フォーマット選択
        layout.addWidget(QLabel("出力フォーマット:"))

        self.txt_check = QCheckBox("テキスト (.txt)")
        self.txt_check.setChecked(True)
        layout.addWidget(self.txt_check)

        self.srt_check = QCheckBox("字幕 (.srt)")
        self.srt_check.setChecked(True)
        layout.addWidget(self.srt_check)

        self.vtt_check = QCheckBox("WebVTT (.vtt)")
        self.vtt_check.setChecked(False)
        layout.addWidget(self.vtt_check)

        # 話者情報
        self.speaker_check = QCheckBox("話者情報を含める")
        self.speaker_check.setChecked(False)
        layout.addWidget(self.speaker_check)

        # ボタン
        btn_layout = QHBoxLayout()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_button)

        layout.addLayout(btn_layout)

    def get_selected_formats(self) -> list:
        """選択されたフォーマットを取得"""
        formats = []
        if self.txt_check.isChecked():
            formats.append("txt")
        if self.srt_check.isChecked():
            formats.append("srt")
        if self.vtt_check.isChecked():
            formats.append("vtt")
        return formats

    def include_speakers(self) -> bool:
        """話者情報を含めるか"""
        return self.speaker_check.isChecked()


class EnhancedMainWindowMixin:
    """
    MainWindowの機能拡張ミックスイン
    既存のMainWindowクラスに新機能を追加
    """

    def setup_enhanced_features(self):
        """拡張機能をセットアップ"""
        self._setup_subtitle_export()
        self._setup_realtime_tab()
        self._setup_api_correction()
        self._setup_theme_toggle()
        self._setup_enhanced_batch()

    def _setup_subtitle_export(self):
        """字幕エクスポート機能をセットアップ"""
        if not SUBTITLE_AVAILABLE:
            return

        # 既存のUIに字幕エクスポートボタンを追加
        self.export_subtitle_button = QPushButton("🎬 字幕エクスポート")
        self.export_subtitle_button.setToolTip("SRT/VTT形式の字幕ファイルを出力")
        self.export_subtitle_button.clicked.connect(self.export_subtitles)
        self.export_subtitle_button.setEnabled(False)

        # 最後の文字起こし結果を保持
        self.last_transcription_result = None

        logger.info("Subtitle export feature initialized")

    def _setup_realtime_tab(self):
        """リアルタイムタブをセットアップ"""
        if not REALTIME_AVAILABLE:
            logger.warning("Realtime tab not available")
            return

        # リアルタイムタブを追加
        self.realtime_tab = RealtimeTab(self)
        self.tab_widget.addTab(self.realtime_tab, "🎤 リアルタイム")

        logger.info("Realtime tab initialized")

    def _setup_api_correction(self):
        """API補正機能をセットアップ"""
        if not API_CORRECTOR_AVAILABLE:
            return

        # API設定を読み込み
        self.api_corrector = None
        self._init_api_corrector()

        # ハイブリッド補正器
        if LOCAL_CORRECTOR_AVAILABLE:
            local = SimpleLLMCorrector()
            self.hybrid_corrector = HybridCorrector(
                local_corrector=local,
                api_corrector=self.api_corrector,
                use_api_for_long_text=True,
                long_text_threshold=500
            )
        else:
            self.hybrid_corrector = None

        logger.info("API correction feature initialized")

    def _init_api_corrector(self):
        """API補正器を初期化"""
        try:
            # 環境変数または設定からAPIキーを取得
            import os
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            openai_key = os.getenv("OPENAI_API_KEY")

            if anthropic_key:
                self.api_corrector = create_corrector("claude", anthropic_key)
                logger.info("Claude corrector initialized")
            elif openai_key:
                self.api_corrector = create_corrector("openai", openai_key)
                logger.info("OpenAI corrector initialized")

        except Exception as e:
            logger.error(f"Failed to initialize API corrector: {e}")

    def _setup_theme_toggle(self):
        """テーマ切り替え機能をセットアップ"""
        if not DARK_THEME_AVAILABLE:
            return

        # メニューまたは設定にテーマ切り替えを追加
        self.dark_mode_check = QCheckBox("🌙 ダークモード")
        self.dark_mode_check.stateChanged.connect(self.toggle_dark_mode)

        # 設定から復元
        is_dark = self.settings.get('dark_mode', False)
        self.dark_mode_check.setChecked(is_dark)

        if is_dark:
            self._apply_dark_theme()

        logger.info("Theme toggle initialized")

    def _setup_enhanced_batch(self):
        """強化バッチ処理をセットアップ"""
        if not ENHANCED_BATCH_AVAILABLE:
            return

        self.enhanced_processor = EnhancedBatchProcessor(
            max_workers=4,
            enable_checkpoint=True,
            memory_limit_mb=4096
        )

        # 再開可能なバッチがあるかチェック
        if can_resume_batch():
            self._show_resume_dialog()

        logger.info("Enhanced batch processor initialized")

    def _apply_dark_theme(self):
        """ダークテーマを適用"""
        if DARK_THEME_AVAILABLE:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                DarkTheme.apply(app)
                logger.info("Dark theme applied")

    def _apply_light_theme(self):
        """ライトテーマを適用"""
        if DARK_THEME_AVAILABLE:
            from PySide6.QtWidgets import QApplication
            from dark_theme import LightTheme
            app = QApplication.instance()
            if app:
                LightTheme.apply(app)
                logger.info("Light theme applied")

    def toggle_dark_mode(self, state):
        """ダークモードを切り替え"""
        is_dark = state == Qt.Checked
        self.settings.set('dark_mode', is_dark)
        self.settings.save_debounced()

        if is_dark:
            self._apply_dark_theme()
        else:
            self._apply_light_theme()

    def export_subtitles(self):
        """字幕ファイルをエクスポート"""
        if not SUBTITLE_AVAILABLE or not self.last_transcription_result:
            QMessageBox.warning(self, "警告", "エクスポート可能な結果がありません")
            return

        # ファイル選択ダイアログ
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "字幕ファイルを保存",
            "",
            "Subtitle Files (*.srt *.vtt);;SRT Files (*.srt);;VTT Files (*.vtt);;All Files (*)"
        )

        if not file_path:
            return

        try:
            exporter = SubtitleExporter()

            # 拡張子でフォーマット判定
            if file_path.endswith('.vtt'):
                success = exporter.export_vtt(
                    self.last_transcription_result.segments,
                    file_path,
                    self.last_transcription_result.speaker_segments
                )
            else:
                success = exporter.export_srt(
                    self.last_transcription_result.segments,
                    file_path,
                    self.last_transcription_result.speaker_segments
                )

            if success:
                QMessageBox.information(self, "成功", f"字幕ファイルを保存しました:\n{file_path}")
                self.statusBar().showMessage(f"字幕保存: {os.path.basename(file_path)}")
            else:
                QMessageBox.warning(self, "失敗", "字幕ファイルの保存に失敗しました")

        except Exception as e:
            logger.error(f"Subtitle export failed: {e}")
            QMessageBox.critical(self, "エラー", f"字幕エクスポートエラー:\n{str(e)}")

    def start_enhanced_batch(self):
        """強化バッチ処理を開始"""
        if not ENHANCED_BATCH_AVAILABLE or not self.batch_files:
            return

        # 強化バッチ処理を使用
        def progress_callback(stats):
            self.update_batch_progress(
                stats['processed_count'],
                stats['total_files'],
                f"処理中... (workers: {stats['current_workers']})"
            )

        try:
            result = self.enhanced_processor.process_files(
                self.batch_files,
                self._process_single_file_wrapper,
                progress_callback
            )

            self.batch_all_finished(
                result['stats']['processed_count'],
                result['stats']['failed_count']
            )

        except Exception as e:
            logger.error(f"Enhanced batch processing failed: {e}")
            QMessageBox.critical(self, "エラー", f"バッチ処理エラー:\n{str(e)}")

    def _process_single_file_wrapper(self, file_path: str):
        """単一ファイル処理のラッパー"""
        # 既存の処理関数を呼び出し
        from transcription_engine import TranscriptionEngine
        from text_formatter import TextFormatter

        engine = TranscriptionEngine()
        engine.load_model()

        result = engine.transcribe(file_path, return_timestamps=True)

        return result

    def _show_resume_dialog(self):
        """バッチ再開ダイアログを表示"""
        reply = QMessageBox.question(
            self,
            "バッチ処理の再開",
            "前回中断したバッチ処理があります。再開しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            # バッチ処理を再開
            logger.info("Resuming batch processing from checkpoint")

    def enhanced_correct_text(self, text: str) -> str:
        """拡張テキスト補正（ハイブリッド）"""
        if self.hybrid_corrector:
            return self.hybrid_corrector.correct_text(text)
        return text


# 既存のMainWindowにミックスインを適用するためのパッチ関数
def patch_main_window(main_window_class):
    """
    既存のMainWindowクラスに拡張機能を追加

    Args:
        main_window_class: 既存のMainWindowクラス

    Returns:
        拡張されたクラス
    """
    class EnhancedMainWindow(main_window_class, EnhancedMainWindowMixin):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setup_enhanced_features()

    return EnhancedMainWindow


if __name__ == "__main__":
    # テスト用コード
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)

    # ダークテーマ適用
    if DARK_THEME_AVAILABLE:
        DarkTheme.apply(app)

    # ダイアログテスト
    dialog = ExportOptionsDialog()
    dialog.show()

    sys.exit(app.exec())
