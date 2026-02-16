"""
改善機能テストスクリプト
KotobaTranscriber v2.1.0+ の新機能をテスト
"""

import logging
import os
import sys
import unittest
from pathlib import Path

# テスト対象のパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TestSubtitleExporter(unittest.TestCase):
    """字幕エクスポート機能のテスト"""

    @classmethod
    def setUpClass(cls):
        try:
            from subtitle_exporter import SubtitleExporter

            cls.SubtitleExporter = SubtitleExporter
            cls.available = True
        except ImportError as e:
            logger.warning(f"SubtitleExporter not available: {e}")
            cls.available = False

    def test_srt_time_formatting(self):
        """SRT時間形式のフォーマットテスト"""
        if not self.available:
            self.skipTest("SubtitleExporter not available")

        exporter = self.SubtitleExporter()

        # テストケース: 秒数 -> SRT形式
        test_cases = [
            (0.0, "00:00:00,000"),
            (61.5, "00:01:01,500"),
            (3661.123, "01:01:01,123"),
        ]

        for seconds, expected in test_cases:
            result = exporter.format_srt_time(seconds)
            self.assertEqual(result, expected, f"Failed for {seconds}s")

        logger.info("✓ SRT time formatting test passed")

    def test_vtt_time_formatting(self):
        """VTT時間形式のフォーマットテスト"""
        if not self.available:
            self.skipTest("SubtitleExporter not available")

        exporter = self.SubtitleExporter()

        # VTT形式ではカンマの代わりにドットを使用
        result = exporter.format_vtt_time(61.5)
        self.assertEqual(result, "00:01:01.500")

        logger.info("✓ VTT time formatting test passed")

    def test_srt_generation(self):
        """SRTコンテンツ生成テスト"""
        if not self.available:
            self.skipTest("SubtitleExporter not available")

        exporter = self.SubtitleExporter()

        segments = [
            {"start": 0.5, "end": 3.2, "text": "こんにちは"},
            {"start": 3.5, "end": 6.8, "text": "テストです"},
        ]

        content = exporter.generate_srt_content(segments)

        # 検証
        self.assertIn("1", content)
        self.assertIn("00:00:00,500 --> 00:00:03,200", content)
        self.assertIn("こんにちは", content)

        logger.info("✓ SRT generation test passed")


class TestAPICorrector(unittest.TestCase):
    """API補正機能のテスト"""

    @classmethod
    def setUpClass(cls):
        try:
            from api_corrector import HybridCorrector, create_corrector

            cls.HybridCorrector = HybridCorrector
            cls.create_corrector = create_corrector
            cls.available = True
        except ImportError as e:
            logger.warning(f"APICorrector not available: {e}")
            cls.available = False

    def test_local_correction(self):
        """ローカル補正のテスト"""
        if not self.available:
            self.skipTest("APICorrector not available")

        try:
            from llm_corrector_standalone import SimpleLLMCorrector

            local = SimpleLLMCorrector()

            test_text = "えーとですね今日は会議です"
            result = local.correct_text(test_text)

            # フィラー語が削除されているか確認
            self.assertNotIn("えーと", result)
            self.assertNotIn("ですね", result)

            logger.info(f"  Input: {test_text}")
            logger.info(f"  Output: {result}")
            logger.info("✓ Local correction test passed")

        except ImportError:
            self.skipTest("SimpleLLMCorrector not available")


class TestEnhancedBatchProcessor(unittest.TestCase):
    """強化バッチプロセッサーのテスト"""

    @classmethod
    def setUpClass(cls):
        try:
            from enhanced_batch_processor import CheckpointManager, EnhancedBatchProcessor

            cls.EnhancedBatchProcessor = EnhancedBatchProcessor
            cls.CheckpointManager = CheckpointManager
            cls.available = True
        except ImportError as e:
            logger.warning(f"EnhancedBatchProcessor not available: {e}")
            cls.available = False

    def test_checkpoint_save_load(self):
        """チェックポイントの保存と読み込みテスト"""
        if not self.available:
            self.skipTest("EnhancedBatchProcessor not available")

        manager = self.CheckpointManager(checkpoint_dir="/tmp/test_checkpoint")

        # 保存
        checkpoint_data = {
            "batch_id": "test_batch",
            "processed_files": ["file1.wav", "file2.wav"],
            "failed_files": [],
            "remaining_files": ["file3.wav"],
            "stats": {"total_files": 3},
        }

        saved = manager.save(**checkpoint_data)
        self.assertTrue(saved, "Checkpoint save failed")

        # 読み込み
        loaded = manager.load("test_batch")
        self.assertIsNotNone(loaded, "Checkpoint load failed")
        self.assertEqual(len(loaded["processed_files"]), 2)

        # クリーンアップ
        manager.clear()

        logger.info("✓ Checkpoint save/load test passed")

    def test_worker_adjustment(self):
        """ワーカー数調整のテスト"""
        if not self.available:
            self.skipTest("EnhancedBatchProcessor not available")

        processor = self.EnhancedBatchProcessor(max_workers=4, memory_limit_mb=4096)

        # EnhancedBatchProcessor forces max_workers=1 because TranscriptionEngine
        # is not thread-safe (see enhanced_batch_processor.py __init__).
        # Verify the safety constraint: workers are capped at 1 regardless of request.
        self.assertEqual(processor.max_workers, 1)
        self.assertEqual(processor.current_workers, 1)

        logger.info("✓ Worker adjustment test passed")


class TestDarkTheme(unittest.TestCase):
    """ダークテーマのテスト"""

    @classmethod
    def setUpClass(cls):
        try:
            from dark_theme import DarkTheme, LightTheme

            cls.DarkTheme = DarkTheme
            cls.LightTheme = LightTheme
            cls.available = True
        except ImportError as e:
            logger.warning(f"DarkTheme not available: {e}")
            cls.available = False

    def test_stylesheet_generation(self):
        """スタイルシート生成テスト"""
        if not self.available:
            self.skipTest("DarkTheme not available")

        stylesheet = self.DarkTheme.get_stylesheet()

        # 基本的なスタイルが含まれているか確認
        self.assertIn("background-color", stylesheet)
        self.assertIn("color", stylesheet)
        self.assertIn("QPushButton", stylesheet)
        self.assertIn("QGroupBox", stylesheet)

        logger.info("✓ Stylesheet generation test passed")

    def test_color_palette(self):
        """カラーパレットのテスト"""
        if not self.available:
            self.skipTest("DarkTheme not available")

        colors = self.DarkTheme.COLORS

        # 必須カラーの存在確認
        required_colors = ["background", "text_primary", "accent", "button_bg"]
        for color in required_colors:
            self.assertIn(color, colors, f"Missing color: {color}")

        logger.info("✓ Color palette test passed")


class TestRealtimeTab(unittest.TestCase):
    """リアルタイムタブのテスト"""

    @classmethod
    def setUpClass(cls):
        try:
            from realtime_tab import RealtimeTab, RealtimeTranscriptionWorker

            cls.RealtimeTab = RealtimeTab
            cls.RealtimeTranscriptionWorker = RealtimeTranscriptionWorker
            cls.available = True
        except ImportError as e:
            logger.warning(f"RealtimeTab not available: {e}")
            cls.available = False

    def test_worker_initialization(self):
        """ワーカー初期化テスト"""
        if not self.available:
            self.skipTest("RealtimeTab not available")

        # ワーカー作成（実際の録音は開始しない）
        worker = self.RealtimeTranscriptionWorker(model_size="base", device="cpu")

        self.assertEqual(worker.model_size, "base")
        self.assertEqual(worker.device, "cpu")
        self.assertFalse(worker.isRunning())

        logger.info("✓ Worker initialization test passed")


def run_all_tests():
    """全テストを実行"""
    logger.info("=" * 60)
    logger.info("KotobaTranscriber Enhancement Tests")
    logger.info("=" * 60)

    # テストスイート作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # テスト追加
    suite.addTests(loader.loadTestsFromTestCase(TestSubtitleExporter))
    suite.addTests(loader.loadTestsFromTestCase(TestAPICorrector))
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedBatchProcessor))
    suite.addTests(loader.loadTestsFromTestCase(TestDarkTheme))
    suite.addTests(loader.loadTestsFromTestCase(TestRealtimeTab))

    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 結果サマリー
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    logger.info(f"Tests Run: {result.testsRun}")
    logger.info(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"Failures: {len(result.failures)}")
    logger.info(f"Errors: {len(result.errors)}")
    logger.info("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
