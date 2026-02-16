"""
建設業用語辞書のテスト
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from construction_vocabulary import ConstructionVocabulary, get_construction_vocabulary
from custom_dictionary import CustomDictionary, create_dictionary_from_yaml


class TestConstructionVocabulary(unittest.TestCase):
    """ConstructionVocabularyのテスト"""

    def setUp(self):
        """テスト前のセットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.vocab_file = Path(self.temp_dir) / "test_construction_vocab.json"
        self.vocab = ConstructionVocabulary(str(self.vocab_file))

    def tearDown(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """初期化テスト"""
        self.assertIsNotNone(self.vocab)
        self.assertGreater(len(self.vocab.hotwords), 0)
        self.assertIn("標準労務費", self.vocab.hotwords)

    def test_categories(self):
        """カテゴリテスト"""
        categories = self.vocab.get_all_categories()
        self.assertIn("standard_labor", categories)
        self.assertIn("construction_law", categories)
        self.assertIn("cost_management", categories)
        self.assertIn("agec_specific", categories)

    def test_get_terms_by_category(self):
        """カテゴリ別用語取得テスト"""
        terms = self.vocab.get_terms_by_category("standard_labor")
        self.assertGreater(len(terms), 0)
        self.assertIn("標準労務費", terms)

    def test_replacements(self):
        """置換ルールテスト"""
        test_text = "ほおがけを使ってコンクリート工の基準内ちんぎんを計算する"
        corrected = self.vocab.apply_replacements(test_text)
        self.assertIn("歩掛", corrected)

    def test_search_terms(self):
        """検索テスト"""
        results = self.vocab.search_terms("管理")
        self.assertGreater(len(results), 0)
        for term in results:
            self.assertIn("管理", term)

    def test_add_term(self):
        """用語追加テスト"""
        new_term = "テスト用語"
        self.vocab.add_term(new_term, "test_category")
        self.assertIn(new_term, self.vocab.hotwords)
        self.assertIn(new_term, self.vocab.get_terms_by_category("test_category"))

    def test_whisper_prompt(self):
        """Whisperプロンプト生成テスト"""
        prompt = self.vocab.get_whisper_prompt()
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)
        self.assertIn("専門用語", prompt)


class TestCustomDictionary(unittest.TestCase):
    """CustomDictionaryのテスト"""

    def test_create_from_yaml(self):
        """YAMLからの作成テスト"""
        dictionary = create_dictionary_from_yaml()
        self.assertIsInstance(dictionary, CustomDictionary)
        self.assertGreater(len(dictionary.hotwords), 0)

    def test_integration(self):
        """統合テスト"""
        config = {
            "construction_vocabulary": {
                "enabled": True,
                "file": "data/construction_dictionary.json",
                "categories": ["standard_labor", "agec_specific"],
            },
            "vocabulary": {"enabled": False, "file": "custom_vocabulary.json"},
        }

        dictionary = CustomDictionary(config)
        self.assertGreater(len(dictionary.hotwords), 0)

        # 建設業用語が含まれているか
        self.assertIn("標準労務費", dictionary.hotwords)
        self.assertIn("CM", dictionary.hotwords)

        # 置換ルールが機能するか
        test_text = "しーえむ業務について"
        corrected = dictionary.apply_replacements(test_text)
        self.assertIn("CM", corrected)


class TestDictionaryFile(unittest.TestCase):
    """辞書ファイルのテスト"""

    def test_construction_dictionary_json(self):
        """construction_dictionary.jsonの存在と形式テスト"""
        dict_path = Path(__file__).parent.parent / "data" / "construction_dictionary.json"
        self.assertTrue(dict_path.exists(), "辞書ファイルが存在しません")

        with open(dict_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("version", data)
        self.assertIn("categories", data)
        self.assertIn("replacements", data)

        # 各カテゴリの確認
        categories = data["categories"]
        required_categories = ["standard_labor", "construction_law", "cost_management", "agec_specific"]
        for cat in required_categories:
            self.assertIn(cat, categories, f"カテゴリ '{cat}' が存在しません")
            self.assertIn("terms", categories[cat])
            self.assertGreater(len(categories[cat]["terms"]), 0)


if __name__ == "__main__":
    unittest.main()
