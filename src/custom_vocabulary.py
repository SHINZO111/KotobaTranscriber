"""
カスタム語彙管理モジュール
専門用語やホットワードの管理と適用
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)


class CustomVocabulary:
    """カスタム語彙管理クラス"""

    def __init__(self, vocabulary_file: Optional[str] = None):
        """
        初期化

        Args:
            vocabulary_file: 語彙ファイルのパス（Noneの場合はデフォルト）
        """
        if vocabulary_file is None:
            vocabulary_file = "custom_vocabulary.json"

        self.vocabulary_file = Path(vocabulary_file)
        self.hotwords: List[str] = []
        self.replacements: Dict[str, str] = {}
        self.domain_vocabularies: Dict[str, List[str]] = {}

        self.load_vocabulary()
        logger.info(f"CustomVocabulary initialized with {len(self.hotwords)} hotwords")

    def load_vocabulary(self):
        """語彙ファイルをロード"""
        if not self.vocabulary_file.exists():
            logger.info("Vocabulary file not found, creating default...")
            self.create_default_vocabulary()
            return

        try:
            with open(self.vocabulary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.hotwords = data.get('hotwords', [])
            self.replacements = data.get('replacements', {})
            self.domain_vocabularies = data.get('domains', {})

            logger.info(f"Loaded {len(self.hotwords)} hotwords from {self.vocabulary_file}")

        except Exception as e:
            logger.error(f"Failed to load vocabulary: {e}")
            self.create_default_vocabulary()

    def save_vocabulary(self):
        """語彙ファイルを保存"""
        try:
            data = {
                'hotwords': self.hotwords,
                'replacements': self.replacements,
                'domains': self.domain_vocabularies
            }

            with open(self.vocabulary_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved vocabulary to {self.vocabulary_file}")

        except Exception as e:
            logger.error(f"Failed to save vocabulary: {e}")

    def create_default_vocabulary(self):
        """デフォルト語彙を作成"""
        # 一般的な専門用語の例
        self.hotwords = [
            # IT・技術用語
            "API", "SDK", "OAuth", "REST", "GraphQL",
            "Kubernetes", "Docker", "CI/CD", "DevOps",
            "機械学習", "ディープラーニング", "ニューラルネットワーク",
            "トランスフォーマー", "アテンション機構",

            # ビジネス用語
            "KPI", "ROI", "PDCA", "OKR",
            "ステークホルダー", "アジェンダ", "コンセンサス",

            # 医療用語（例）
            "エビデンス", "プロトコル", "インフォームドコンセント",
        ]

        # よくある誤認識の修正
        self.replacements = {
            # IT用語の誤認識例
            "エーピーアイ": "API",
            "ケーパーアイ": "KPI",
            "機械が嫌": "機械学習",
            "深層が嫌": "ディープラーニング",

            # 一般的な誤認識
            "以上です": "以上です",  # 保持例
        }

        # ドメイン別語彙
        self.domain_vocabularies = {
            "it": [
                "Python", "JavaScript", "TypeScript", "React", "Vue.js",
                "PostgreSQL", "MongoDB", "Redis", "AWS", "Azure", "GCP"
            ],
            "medical": [
                "診断", "治療", "投薬", "手術", "検査", "カルテ"
            ],
            "legal": [
                "契約", "訴訟", "判例", "弁護士", "裁判所"
            ],
            "business": [
                "売上", "利益", "予算", "戦略", "マーケティング"
            ]
        }

        self.save_vocabulary()

    def add_hotword(self, word: str):
        """
        ホットワードを追加

        Args:
            word: 追加する単語
        """
        if word and word not in self.hotwords:
            self.hotwords.append(word)
            self.save_vocabulary()
            logger.info(f"Added hotword: {word}")

    def remove_hotword(self, word: str):
        """
        ホットワードを削除

        Args:
            word: 削除する単語
        """
        if word in self.hotwords:
            self.hotwords.remove(word)
            self.save_vocabulary()
            logger.info(f"Removed hotword: {word}")

    def add_replacement(self, wrong: str, correct: str):
        """
        置換ルールを追加

        Args:
            wrong: 誤認識される単語
            correct: 正しい単語
        """
        self.replacements[wrong] = correct
        self.save_vocabulary()
        logger.info(f"Added replacement: '{wrong}' -> '{correct}'")

    def remove_replacement(self, wrong: str):
        """
        置換ルールを削除

        Args:
            wrong: 削除する誤認識単語
        """
        if wrong in self.replacements:
            del self.replacements[wrong]
            self.save_vocabulary()
            logger.info(f"Removed replacement: {wrong}")

    def get_whisper_prompt(self, domain: Optional[str] = None) -> str:
        """
        Whisperの初期プロンプトを生成

        ホットワードを含むプロンプトを生成し、認識精度を向上させる

        Args:
            domain: 使用するドメイン語彙（Noneの場合は全ホットワード）

        Returns:
            初期プロンプト文字列
        """
        words = self.hotwords.copy()

        # ドメイン指定がある場合は追加
        if domain and domain in self.domain_vocabularies:
            words.extend(self.domain_vocabularies[domain])

        # 重複を削除
        words = list(set(words))

        # プロンプトは最大244トークン程度に制限（Whisperの制限）
        # 1単語あたり約2-3トークンと仮定し、最大80単語程度
        if len(words) > 80:
            words = words[:80]

        # プロンプトを自然な文章形式で生成
        if words:
            prompt = "以下の専門用語に注意してください: " + "、".join(words[:30])
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
        result = text

        for wrong, correct in self.replacements.items():
            # 単語境界を考慮した置換
            # 部分一致を避けるため、前後の文字をチェック
            pattern = r'\b' + re.escape(wrong) + r'\b'
            result = re.sub(pattern, correct, result, flags=re.IGNORECASE)

        return result

    def get_hotwords_list(self) -> List[str]:
        """
        全ホットワードのリストを取得

        Returns:
            ホットワードのリスト
        """
        return self.hotwords.copy()

    def get_replacements_dict(self) -> Dict[str, str]:
        """
        全置換ルールの辞書を取得

        Returns:
            置換ルールの辞書
        """
        return self.replacements.copy()

    def import_words_from_text(self, text: str):
        """
        テキストから単語をインポート（改行区切り）

        Args:
            text: 単語リスト（改行区切り）
        """
        words = [w.strip() for w in text.split('\n') if w.strip()]

        for word in words:
            if word not in self.hotwords:
                self.hotwords.append(word)

        self.save_vocabulary()
        logger.info(f"Imported {len(words)} words")

    def export_words_to_text(self) -> str:
        """
        ホットワードをテキスト形式でエクスポート

        Returns:
            改行区切りの単語リスト
        """
        return '\n'.join(self.hotwords)

    def clear_hotwords(self):
        """全ホットワードをクリア"""
        self.hotwords.clear()
        self.save_vocabulary()
        logger.info("Cleared all hotwords")

    def set_domain_vocabulary(self, domain: str, words: List[str]):
        """
        ドメイン別語彙を設定

        Args:
            domain: ドメイン名
            words: 単語リスト
        """
        self.domain_vocabularies[domain] = words
        self.save_vocabulary()
        logger.info(f"Set {len(words)} words for domain: {domain}")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    vocab = CustomVocabulary()

    print("=== Custom Vocabulary Test ===\n")

    # ホットワード表示
    print(f"Hotwords ({len(vocab.hotwords)}):")
    for word in vocab.hotwords[:10]:
        print(f"  - {word}")
    print(f"  ... and {len(vocab.hotwords) - 10} more\n")

    # Whisperプロンプト生成
    prompt = vocab.get_whisper_prompt()
    print(f"Whisper Prompt:\n{prompt}\n")

    # 置換テスト
    test_text = "エーピーアイを使ってケーパーアイを計測します"
    corrected = vocab.apply_replacements(test_text)
    print(f"Original: {test_text}")
    print(f"Corrected: {corrected}\n")

    # ホットワード追加テスト
    vocab.add_hotword("PyTorch")
    vocab.add_hotword("TensorFlow")
    print(f"Added hotwords, total: {len(vocab.hotwords)}")
