"""
議事録生成のテスト
"""

import unittest
import tempfile
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from minutes_generator import MinutesGenerator, get_minutes_generator, quick_generate
from meeting_minutes_generator import (
    MeetingMinutesGenerator,
    MeetingMinutes,
    StatementType,
    get_minutes_generator as get_base_generator
)


class TestMinutesGenerator(unittest.TestCase):
    """MinutesGeneratorのテスト"""

    def setUp(self):
        """テスト前のセットアップ"""
        self.generator = MinutesGenerator()
        self.test_segments = [
            {"speaker": "田中", "text": "本日の会議を始めます。", "start": 0},
            {"speaker": "佐藤", "text": "進捗状況を報告します。", "start": 10},
            {"speaker": "山田", "text": "外壁材はタイルに決定しました。", "start": 30},
            {"speaker": "田中", "text": "佐藤さんに調整をお願いします。", "start": 45},
            {"speaker": "佐藤", "text": "確認させていただきます。", "start": 55},
        ]

    def test_initialization(self):
        """初期化テスト"""
        self.assertIsNotNone(self.generator)
        self.assertIsNotNone(self.generator._generator)

    def test_generate(self):
        """議事録生成テスト"""
        minutes = self.generator.generate(
            segments=self.test_segments,
            title="テスト会議",
            date="2026年2月3日",
            location="会議室A",
            attendees=["田中", "佐藤", "山田"]
        )

        self.assertIsNotNone(minutes)
        self.assertEqual(minutes["title"], "テスト会議")
        self.assertEqual(minutes["location"], "会議室A")
        self.assertEqual(len(minutes["attendees"]), 3)
        self.assertIn("text_format", minutes)
        self.assertIn("markdown_format", minutes)

    def test_generate_decisions(self):
        """決定事項抽出テスト"""
        minutes = self.generator.generate(
            segments=self.test_segments,
            title="テスト会議"
        )

        # 決定事項が抽出されているか
        self.assertIn("decisions", minutes)
        # 「決定」キーワードを含む発言が決定事項として抽出される

    def test_generate_action_items(self):
        """アクションアイテム抽出テスト"""
        minutes = self.generator.generate(
            segments=self.test_segments,
            title="テスト会議"
        )

        # アクションアイテムが抽出されているか
        self.assertIn("action_items", minutes)

    def test_extract_action_items(self):
        """アクションアイテム抽出メソッドテスト"""
        test_text = "佐藤さんに資料を準備してもらいます。来週までに。"
        items = self.generator.extract_action_items(test_text)

        self.assertGreater(len(items), 0)
        # 担当者が抽出されているか

    def test_classify_statements(self):
        """発言分類テスト"""
        statements = [
            "外壁材はタイルに決定しました。",
            "予算について確認です。",
            "調整をお願いします。"
        ]

        classified = self.generator.classify_statements(statements)
        self.assertIn("decisions", classified)
        self.assertIn("confirmations", classified)
        self.assertIn("action_items", classified)

    def test_save_minutes(self):
        """議事録保存テスト"""
        minutes = self.generator.generate(
            segments=self.test_segments,
            title="テスト会議"
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            temp_path = f.name

        try:
            success = self.generator.save_minutes(minutes, temp_path, "text")
            self.assertTrue(success)
            self.assertTrue(Path(temp_path).exists())

            # 内容を確認
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn("テスト会議", content)
        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_generate_from_file(self):
        """ファイルからの生成テスト"""
        # テスト用JSONファイルを作成
        test_data = {
            "segments": self.test_segments,
            "title": "ファイルテスト"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(test_data, f)
            temp_path = f.name

        try:
            minutes = self.generator.generate_from_file(temp_path, title="テスト")
            self.assertEqual(minutes["title"], "テスト")
            self.assertEqual(len(minutes["statements"]), 5)
        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()


class TestQuickGenerate(unittest.TestCase):
    """quick_generate関数のテスト"""

    def test_quick_generate(self):
        """簡易生成テスト"""
        segments = [
            {"speaker": "田中", "text": "会議を始めます。", "start": 0},
        ]

        minutes = quick_generate(segments, title="クイックテスト")
        self.assertEqual(minutes["title"], "クイックテスト")


class TestBaseGenerator(unittest.TestCase):
    """MeetingMinutesGenerator（ベースクラス）のテスト"""

    def setUp(self):
        """テスト前のセットアップ"""
        self.generator = MeetingMinutesGenerator()

    def test_classify_statement(self):
        """発言分類テスト"""
        # 決定事項
        decision_text = "外壁材はタイルに決定しました。"
        stmt_type = self.generator.classify_statement(decision_text)
        self.assertEqual(stmt_type, StatementType.DECISION)

        # アクションアイテム
        action_text = "調整をお願いします。"
        stmt_type = self.generator.classify_statement(action_text)
        self.assertEqual(stmt_type, StatementType.ACTION_ITEM)

        # 確認事項
        confirm_text = "予算について確認です。"
        stmt_type = self.generator.classify_statement(confirm_text)
        self.assertEqual(stmt_type, StatementType.CONFIRMATION)

    def test_extract_decision_text(self):
        """決定事項テキスト抽出テスト"""
        text = "外壁材はタイルに決定しました。"
        result = self.generator.extract_decision_text(text)
        self.assertIsNotNone(result)

    def test_extract_action_item(self):
        """アクションアイテム抽出テスト"""
        text = "佐藤さんに資料を準備してもらいます。"
        item = self.generator.extract_action_item(text, "田中")
        self.assertEqual(item.description, text)

    def test_extract_attendees(self):
        """出席者抽出テスト"""
        segments = [
            {"speaker": "田中", "text": "会議を始めます。"},
            {"speaker": "佐藤", "text": "了解です。"},
            {"speaker": "田中", "text": "進捗は？"},
        ]

        attendees = self.generator.extract_attendees_from_segments(segments)
        self.assertEqual(len(attendees), 2)
        self.assertIn("田中", attendees)
        self.assertIn("佐藤", attendees)


class TestMeetingMinutes(unittest.TestCase):
    """MeetingMinutes（データクラス）のテスト"""

    def test_to_text(self):
        """テキスト形式出力テスト"""
        minutes = MeetingMinutes(
            title="テスト会議",
            date="2026年2月3日",
            location="会議室A",
            attendees=["田中", "佐藤"],
            decisions=["決定事項1"],
            action_items=[]
        )

        text = minutes.to_text()
        self.assertIn("テスト会議", text)
        self.assertIn("会議室A", text)
        self.assertIn("田中", text)
        self.assertIn("決定事項1", text)

    def test_to_markdown(self):
        """Markdown形式出力テスト"""
        minutes = MeetingMinutes(
            title="テスト会議",
            date="2026年2月3日",
        )

        md = minutes.to_markdown()
        self.assertIn("# 議事録: テスト会議", md)
        self.assertIn("2026年2月3日", md)


class TestSingleton(unittest.TestCase):
    """シングルトンテスト"""

    def test_get_minutes_generator(self):
        """シングルトンテスト"""
        gen1 = get_minutes_generator()
        gen2 = get_minutes_generator()
        self.assertIs(gen1, gen2)


if __name__ == "__main__":
    unittest.main()
