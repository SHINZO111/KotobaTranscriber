"""
カスタム辞書読み込み・適用モジュール
建設業用語辞書とカスタム語彙の統合管理
"""

import logging
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any

from construction_vocabulary import ConstructionVocabulary, get_construction_vocabulary
from custom_vocabulary import CustomVocabulary

logger = logging.getLogger(__name__)


class CustomDictionary:
    """
    カスタム辞書統合管理クラス
    建設業用語辞書とカスタム語彙を統合して管理
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初期化

        Args:
            config: 設定辞書（config.yamlから読み込んだ内容）
        """
        self.config = config or {}
        self.hotwords: List[str] = []
        self.replacements: Dict[str, str] = {}
        self.categories: Dict[str, List[str]] = {}

        # 各種辞書インスタンス
        self._construction_vocab: Optional[ConstructionVocabulary] = None
        self._custom_vocab: Optional[CustomVocabulary] = None

        # 設定から読み込み
        self._load_from_config()

        logger.info(f"CustomDictionary initialized with {len(self.hotwords)} hotwords")

    def _load_from_config(self):
        """設定ファイルから辞書を読み込み"""
        # 建設業用語辞書
        construction_config = self.config.get('construction_vocabulary', {})
        if construction_config.get('enabled', True):
            vocab_file = construction_config.get('file', 'data/construction_dictionary.json')
            try:
                self._construction_vocab = get_construction_vocabulary(vocab_file)
                self._merge_construction_vocabulary(construction_config)
                logger.info(f"Loaded construction vocabulary from {vocab_file}")
            except Exception as e:
                logger.error(f"Failed to load construction vocabulary: {e}")

        # カスタム語彙
        vocab_config = self.config.get('vocabulary', {})
        if vocab_config.get('enabled', False):
            vocab_file = vocab_config.get('file', 'custom_vocabulary.json')
            try:
                self._custom_vocab = CustomVocabulary(vocab_file)
                self._merge_custom_vocabulary()
                logger.info(f"Loaded custom vocabulary from {vocab_file}")
            except Exception as e:
                logger.error(f"Failed to load custom vocabulary: {e}")

    def _merge_construction_vocabulary(self, config: Dict):
        """
        建設業用語辞書をマージ

        Args:
            config: 建設業用語辞書設定
        """
        if not self._construction_vocab:
            return

        # 指定されたカテゴリの用語をマージ
        enabled_categories = config.get('categories', [])

        if enabled_categories:
            # 特定カテゴリのみ
            for category in enabled_categories:
                terms = self._construction_vocab.get_terms_by_category(category)
                self.hotwords.extend(terms)
                self.categories[category] = terms
        else:
            # 全カテゴリ
            self.hotwords.extend(self._construction_vocab.hotwords)
            self.categories.update(self._construction_vocab.category_vocabularies)

        # 置換ルールをマージ
        self.replacements.update(self._construction_vocab.replacements)

    def _merge_custom_vocabulary(self):
        """カスタム語彙をマージ"""
        if not self._custom_vocab:
            return

        self.hotwords.extend(self._custom_vocab.hotwords)
        self.replacements.update(self._custom_vocab.replacements)

        # ドメイン別語彙をカテゴリとして追加
        for domain, words in self._custom_vocab.domain_vocabularies.items():
            if domain not in self.categories:
                self.categories[domain] = []
            self.categories[domain].extend(words)

    def get_whisper_prompt(self, category: Optional[str] = None) -> str:
        """
        Whisperの初期プロンプトを生成

        Args:
            category: カテゴリ指定（Noneの場合は全用語）

        Returns:
            初期プロンプト文字列
        """
        if category and category in self.categories:
            words = self.categories[category]
        else:
            words = self.hotwords

        # 重複を削除（挿入順を維持）
        words = list(dict.fromkeys(words))

        # プロンプトは最大244トークン程度に制限
        # 1単語あたり約2-3トークンと仮定し、最大30単語
        if words:
            prompt = "以下の専門用語に注意: " + "、".join(words[:30])
            return prompt

        return ""

    def apply_replacements(self, text: str) -> str:
        """
        テキストに置換ルールを適用

        Args:
            text: 入力テキスト

        Returns:
            置換後のテキスト
        """
        return ConstructionVocabulary.apply_replacements_to_text(text, self.replacements)

    def add_term(self, term: str, category: str = "custom"):
        """
        用語を追加

        Args:
            term: 追加する用語
            category: カテゴリ名
        """
        if term and term not in self.hotwords:
            self.hotwords.append(term)

            if category not in self.categories:
                self.categories[category] = []
            if term not in self.categories[category]:
                self.categories[category].append(term)

            # カスタム語彙にも追加
            if self._custom_vocab:
                self._custom_vocab.add_hotword(term)

            logger.info(f"Added term: {term} ({category})")

    def add_replacement(self, wrong: str, correct: str):
        """
        置換ルールを追加

        Args:
            wrong: 誤認識される単語
            correct: 正しい単語
        """
        self.replacements[wrong] = correct

        # カスタム語彙にも追加
        if self._custom_vocab:
            self._custom_vocab.add_replacement(wrong, correct)

        logger.info(f"Added replacement: '{wrong}' -> '{correct}'")

    def get_terms_by_category(self, category: str) -> List[str]:
        """
        カテゴリ別の用語リストを取得

        Args:
            category: カテゴリ名

        Returns:
            用語リスト
        """
        return self.categories.get(category, [])

    def get_all_categories(self) -> List[str]:
        """
        全カテゴリリストを取得

        Returns:
            カテゴリ名のリスト
        """
        return list(self.categories.keys())

    def search_terms(self, keyword: str) -> List[str]:
        """
        キーワードで用語を検索

        Args:
            keyword: 検索キーワード

        Returns:
            一致した用語リスト
        """
        keyword_lower = keyword.lower()
        return [term for term in self.hotwords if keyword_lower in term.lower()]

    def get_construction_vocabulary(self) -> Optional[ConstructionVocabulary]:
        """
        建設業用語辞書インスタンスを取得

        Returns:
            ConstructionVocabularyインスタンス（未読み込みの場合はNone）
        """
        return self._construction_vocab

    def get_custom_vocabulary(self) -> Optional[CustomVocabulary]:
        """
        カスタム語彙インスタンスを取得

        Returns:
            CustomVocabularyインスタンス（未読み込みの場合はNone）
        """
        return self._custom_vocab

    def reload(self):
        """辞書を再読み込み"""
        self.hotwords.clear()
        self.replacements.clear()
        self.categories.clear()
        self._load_from_config()
        logger.info("Dictionary reloaded")


# グローバルインスタンス（スレッドセーフ）
_custom_dictionary = None
_custom_dictionary_lock = threading.Lock()


def get_custom_dictionary(config: Optional[Dict[str, Any]] = None) -> CustomDictionary:
    """
    カスタム辞書のシングルトンインスタンスを取得（スレッドセーフ）

    Args:
        config: 設定辞書（初回呼び出し時のみ使用）

    Returns:
        CustomDictionaryインスタンス
    """
    global _custom_dictionary
    if _custom_dictionary is None:
        with _custom_dictionary_lock:
            if _custom_dictionary is None:
                _custom_dictionary = CustomDictionary(config)
    return _custom_dictionary


def load_config_from_yaml(yaml_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    YAML設定ファイルから辞書関連設定を読み込み

    Args:
        yaml_path: YAMLファイルのパス

    Returns:
        設定辞書
    """
    try:
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load config from {yaml_path}: {e}")
        return {}


def create_dictionary_from_yaml(yaml_path: str = "config/config.yaml") -> CustomDictionary:
    """
    YAML設定ファイルからCustomDictionaryを作成

    Args:
        yaml_path: YAMLファイルのパス

    Returns:
        CustomDictionaryインスタンス
    """
    config = load_config_from_yaml(yaml_path)
    return CustomDictionary(config)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # YAMLから読み込みテスト
    dictionary = create_dictionary_from_yaml()

    print("=== Custom Dictionary Test ===\n")

    # 用語数表示
    print(f"Total terms: {len(dictionary.hotwords)}")
    print(f"Categories: {dictionary.get_all_categories()}")
    print()

    # カテゴリ別表示
    for category in dictionary.get_all_categories()[:3]:
        terms = dictionary.get_terms_by_category(category)
        print(f"{category}: {len(terms)} terms")
        for term in terms[:5]:
            print(f"  - {term}")
        if len(terms) > 5:
            print(f"  ... and {len(terms) - 5} more")
        print()

    # Whisperプロンプト生成
    prompt = dictionary.get_whisper_prompt()
    print(f"Whisper Prompt (first 200 chars):\n{prompt[:200]}...\n")

    # 置換テスト
    test_text = "ほおがけを使ってコンクリート工の基準内ちんぎんを計算する"
    corrected = dictionary.apply_replacements(test_text)
    print(f"Original: {test_text}")
    print(f"Corrected: {corrected}\n")

    # 検索テスト
    search_results = dictionary.search_terms("管理")
    print(f"Search '管理': {len(search_results)} results")
    for term in search_results[:10]:
        print(f"  - {term}")
