"""
テキスト整形モジュール
文字起こし結果の後処理を行う
"""

import re
from typing import List, Dict, Pattern
import logging
from validators import Validator, ValidationError

logger = logging.getLogger(__name__)


class PunctuationRules:
    """句読点整形のルールを管理するクラス"""

    # 接続詞リスト
    CONJUNCTIONS = [
        'しかし', 'また', 'そして', 'それで', 'つまり', 'ところで',
        'さらに', 'ただし', 'ですが', 'でも', 'けれど', 'けれども',
        'だから', 'なので', 'そのため', 'したがって'
    ]

    # 段落区切り用接続詞
    PARAGRAPH_BREAK_WORDS = [
        'しかし', 'また', 'ところで', 'さて', 'では', 'それでは', 'ちなみに'
    ]

    # 丁寧語の語尾
    POLITE_ENDINGS = [
        'です', 'ます', 'ました', 'でした', 'ません', 'ませんでした',
        'でしょう', 'ましょう', 'ください', 'くださいました'
    ]

    # 引用動詞
    QUOTE_VERBS = [
        '思います', '思った', '言います', '言った', '聞きます', '聞いた',
        '考えます', '考えた'
    ]

    # 助詞（長文分割用）
    PARTICLES = ['て', 'で', 'が', 'を', 'に', 'は', 'も']

    # 長文の閾値
    LONG_SENTENCE_MIN_LENGTH = 60  # 句読点を追加する最小文字数


class RegexPatterns:
    """
    Precompiled regex patterns for text formatting
    テキスト整形用のプリコンパイル済み正規表現パターン
    """

    # Common patterns used across multiple methods
    CONSECUTIVE_COMMAS = re.compile(r'[、]{2,}')
    CONSECUTIVE_PERIODS = re.compile(r'[。]{2,}')
    CONSECUTIVE_SPACES = re.compile(r'\s+')
    PUNCTUATION_SPACES = re.compile(r'([、。！？])\s+')

    # Punctuation rules
    COMMA_BEFORE_PERIOD = re.compile(r'、([。！？])')
    TE_DE_LONG_SENTENCE = re.compile(r'([てで])([^、。！？\n]{40,}?)([^、。！？\n]{20,})')
    GA_LONG_SENTENCE = re.compile(r'([が])([^、。！？\n]{35,})')
    REASON_PUNCTUATION = re.compile(r'(ので|から)([^、。！？\n])')
    CONDITION_PUNCTUATION = re.compile(r'(たら|れば|なら)([^、。！？\n])')
    TARI_PUNCTUATION = re.compile(r'(たり)([^、。！？\n])')

    # Sentence splitting
    SENTENCE_SPLIT = re.compile(r'([。！？\n])')

    # Repeated words
    REPEATED_WORDS = re.compile(r'\b(\w+)\s+\1\b')

    # Number formatting
    NUMBER_SPACING = re.compile(r'(\d+)\s+(\d+)')

    # Dynamically compiled patterns cache
    _pattern_cache: Dict[str, Pattern] = {}

    @classmethod
    def get_filler_pattern(cls, filler: str) -> Pattern:
        """
        Get or create a cached pattern for filler word removal

        Args:
            filler: Filler word to create pattern for

        Returns:
            Compiled regex pattern
        """
        key = f"filler_{filler}"
        if key not in cls._pattern_cache:
            pattern = r'\b' + re.escape(filler) + r'\b[、。]?\s*'
            cls._pattern_cache[key] = re.compile(pattern, re.IGNORECASE)
        return cls._pattern_cache[key]

    @classmethod
    def get_conjunction_pattern(cls, conjunction: str) -> Pattern:
        """
        Get or create a cached pattern for conjunction punctuation

        Args:
            conjunction: Conjunction word to create pattern for

        Returns:
            Compiled regex pattern
        """
        key = f"conj_{conjunction}"
        if key not in cls._pattern_cache:
            pattern = r'([^、。！？\n])(' + re.escape(conjunction) + r')'
            cls._pattern_cache[key] = re.compile(pattern)
        return cls._pattern_cache[key]

    @classmethod
    def get_quote_verb_pattern(cls, verb: str) -> Pattern:
        """
        Get or create a cached pattern for quote verb punctuation

        Args:
            verb: Quote verb to create pattern for

        Returns:
            Compiled regex pattern
        """
        key = f"quote_{verb}"
        if key not in cls._pattern_cache:
            pattern = r'と(' + re.escape(verb) + ')'
            cls._pattern_cache[key] = re.compile(pattern)
        return cls._pattern_cache[key]

    @classmethod
    def get_polite_ending_pattern(cls, ending: str) -> Pattern:
        """
        Get or create a cached pattern for polite ending punctuation

        Args:
            ending: Polite ending to create pattern for

        Returns:
            Compiled regex pattern
        """
        key = f"polite_{ending}"
        if key not in cls._pattern_cache:
            pattern = r'(' + re.escape(ending) + r')([^。！？\n])'
            cls._pattern_cache[key] = re.compile(pattern)
        return cls._pattern_cache[key]


class TextFormatter:
    """テキスト整形クラス"""

    # フィラー語・言い淀みのリスト（レベル1: 控えめ - 明らかに不要なもののみ）
    FILLER_WORDS = [
        'あー', 'あ', 'ああ', 'あのー', 'あの',
        'えー', 'え', 'ええ', 'えっと', 'えーと',
        'その', 'そのー',
        'まあ', 'まー',
        'うん', 'うーん',
        'んー', 'ん',
        'はい',
        'なんか', 'なんて',
        'ごめん', 'ごめんなさい',  # 不要な謝罪表現
    ]

    # 積極的削除用の追加フィラー語（レベル2: aggressive=True 時のみ使用）
    AGGRESSIVE_FILLER_WORDS = [
        'ちょっと', 'やっぱり', 'やはり', 'やっぱ',
        'まあまあ', 'とりあえず', 'いわゆる',
        'ですです', 'ですね', 'ますね',
        'そうですね', 'そうそう', 'そうそうそう',
        'ほんとに', 'ほんとうに', 'まじで',
        'けっこう', 'けど', 'だけど',
    ]

    def __init__(self):
        """初期化"""
        pass

    def remove_fillers(self, text: str, aggressive: bool = False) -> str:
        """
        フィラー語を削除

        Args:
            text: 入力テキスト
            aggressive: Trueの場合、より積極的に削除

        Returns:
            フィラー語を削除したテキスト

        Raises:
            ValidationError: テキストが不正な場合
        """
        # テキストを検証
        try:
            Validator.validate_text_length(text, min_length=0, max_length=1000000)
        except ValidationError as e:
            logger.error(f"Text validation failed in remove_fillers: {e}")
            raise

        result = text

        # フィラー語を削除（プリコンパイル済みパターンを使用）
        filler_list = self.FILLER_WORDS + self.AGGRESSIVE_FILLER_WORDS if aggressive else self.FILLER_WORDS
        for filler in filler_list:
            pattern = RegexPatterns.get_filler_pattern(filler)
            result = pattern.sub('', result)

        # 連続する句読点を整理（プリコンパイル済みパターンを使用）
        result = RegexPatterns.CONSECUTIVE_COMMAS.sub('、', result)
        result = RegexPatterns.CONSECUTIVE_PERIODS.sub('。', result)

        # 連続するスペースを1つに（プリコンパイル済みパターンを使用）
        result = RegexPatterns.CONSECUTIVE_SPACES.sub(' ', result)

        # 行頭・行末の空白を削除
        result = result.strip()

        return result

    def add_punctuation(self, text: str) -> str:
        """
        句読点を追加・整形（インテリジェントな処理）

        Args:
            text: 入力テキスト

        Returns:
            句読点が整形されたテキスト
        """
        result = text

        # 既存の句読点の後のスペースを削除（プリコンパイル済みパターンを使用）
        result = RegexPatterns.PUNCTUATION_SPACES.sub(r'\1', result)

        # 1. 接続詞の前に読点（文頭以外、既に句読点がない場合のみ）
        for conj in PunctuationRules.CONJUNCTIONS:
            # 文頭・改行直後でない接続詞の前に読点（プリコンパイル済みパターンを使用）
            pattern = RegexPatterns.get_conjunction_pattern(conj)
            result = pattern.sub(r'\1、\2', result)

        # 2. 「～て」「～で」の後に文が続く場合、意味的な区切りで読点
        # 長い文（40文字以上）の場合のみ（プリコンパイル済みパターンを使用）
        result = RegexPatterns.TE_DE_LONG_SENTENCE.sub(r'\1、\2\3', result)

        # 3. 「～が」の後に対比・逆接が続く場合に読点
        # 「～が」の後に長い文（35文字以上）がある場合（プリコンパイル済みパターンを使用）
        result = RegexPatterns.GA_LONG_SENTENCE.sub(r'\1、\2', result)

        # 4. 理由・原因を表す「～ので」「～から」の後に読点（プリコンパイル済みパターンを使用）
        result = RegexPatterns.REASON_PUNCTUATION.sub(r'\1、\2', result)

        # 5. 条件を表す「～たら」「～れば」「～なら」の後に読点（プリコンパイル済みパターンを使用）
        result = RegexPatterns.CONDITION_PUNCTUATION.sub(r'\1、\2', result)

        # 6. 列挙の「～たり」の後に読点（プリコンパイル済みパターンを使用）
        result = RegexPatterns.TARI_PUNCTUATION.sub(r'\1、\2', result)

        # 7. 引用の「～と」の後に読点（思う、言う、聞く等の前）
        for verb in PunctuationRules.QUOTE_VERBS:
            # プリコンパイル済みパターンを使用
            pattern = RegexPatterns.get_quote_verb_pattern(verb)
            result = pattern.sub(r'と、\1', result)

        # 8. 長すぎる文を検出して適切な位置に読点を追加
        result = self._split_long_sentences(result)

        # 10. 句点・疑問符・感嘆符の直前の読点を削除（プリコンパイル済みパターンを使用）
        result = RegexPatterns.COMMA_BEFORE_PERIOD.sub(r'\1', result)

        # 11. 文末処理
        # 「です」「ます」等の丁寧語の後に句点がない場合
        for ending in PunctuationRules.POLITE_ENDINGS:
            # プリコンパイル済みパターンを使用
            pattern = RegexPatterns.get_polite_ending_pattern(ending)
            result = pattern.sub(r'\1。\2', result)

        # 12. 文末に何もない場合は句点を追加
        if result and not result.endswith(('。', '！', '？', '…', '\n')):
            result += '。'

        return result

    def _split_long_sentences(self, text: str) -> str:
        """
        長すぎる文を分割して読点を追加

        Args:
            text: 入力テキスト

        Returns:
            str: 処理済みテキスト
        """
        sentences = text.split('。')
        processed_sentences = []

        for sentence in sentences:
            if len(sentence) > PunctuationRules.LONG_SENTENCE_MIN_LENGTH and '、' not in sentence:
                # 文の中間付近で自然な区切り（助詞の後）を探す
                mid_point = len(sentence) // 2
                # 中間地点から前後10文字の範囲で助詞を探す
                search_range = sentence[max(0, mid_point-10):min(len(sentence), mid_point+10)]

                for particle in PunctuationRules.PARTICLES:
                    if particle in search_range:
                        # 助詞の後に読点を追加
                        insert_pos = sentence.find(particle, max(0, mid_point-10))
                        if insert_pos != -1 and insert_pos + 1 < len(sentence):
                            sentence = sentence[:insert_pos+1] + '、' + sentence[insert_pos+1:]
                            break

            processed_sentences.append(sentence)

        return '。'.join(processed_sentences)

    def format_paragraphs(self, text: str, max_sentences_per_paragraph: int = 4) -> str:
        """
        段落を整形（より自然な改行位置）

        Args:
            text: 入力テキスト
            max_sentences_per_paragraph: 1段落あたりの最大文数

        Returns:
            段落が整形されたテキスト

        Raises:
            ValidationError: テキストまたはパラメータが不正な場合
        """
        # テキストを検証
        try:
            Validator.validate_text_length(text, min_length=0, max_length=1000000)
        except ValidationError as e:
            logger.error(f"Text validation failed in format_paragraphs: {e}")
            raise

        # 段落あたりの文数を検証（1〜10が妥当）
        try:
            max_sentences_per_paragraph = Validator.validate_positive_integer(
                max_sentences_per_paragraph,
                min_val=1,
                max_val=10,
                name="max_sentences_per_paragraph"
            )
        except ValidationError as e:
            logger.warning(f"Invalid max_sentences_per_paragraph: {e}, using default value 4")
            max_sentences_per_paragraph = 4
        # 既に適切な改行がある場合（連続改行が2つ以上）
        if '\n\n' in text:
            return text

        # 文で分割（句点、感嘆符、疑問符で区切る）
        # 改行も保持する（プリコンパイル済みパターンを使用）
        sentences = RegexPatterns.SENTENCE_SPLIT.split(text)

        # 文と句読点をペアにする
        paired_sentences = []
        for i in range(0, len(sentences)-1, 2):
            sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '')
            sentence = sentence.strip()
            if sentence:
                paired_sentences.append(sentence)

        # 最後の要素が句読点で終わらない場合も追加
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            paired_sentences.append(sentences[-1].strip())

        if not paired_sentences:
            return text

        # より自然な段落分け
        paragraphs = self._create_paragraphs(paired_sentences, max_sentences_per_paragraph)

        # 段落が1つしかない場合は改行なし
        if len(paragraphs) <= 1:
            return text

        return '\n\n'.join(paragraphs)

    def _create_paragraphs(self, sentences: List[str], max_per_paragraph: int) -> List[str]:
        """
        文のリストから段落を作成

        Args:
            sentences: 文のリスト
            max_per_paragraph: 段落あたりの最大文数

        Returns:
            List[str]: 段落のリスト
        """
        paragraphs = []
        current_paragraph = []
        current_length = 0

        for i, sentence in enumerate(sentences):
            current_paragraph.append(sentence)
            current_length += 1

            # 段落を分ける条件判定
            should_break = self._should_break_paragraph(
                current_length,
                max_per_paragraph,
                i,
                sentences
            )

            if should_break or i == len(sentences) - 1:
                paragraphs.append(''.join(current_paragraph))
                current_paragraph = []
                current_length = 0

        return paragraphs

    def _should_break_paragraph(
        self,
        current_length: int,
        max_length: int,
        current_index: int,
        sentences: List[str]
    ) -> bool:
        """
        段落を分けるべきか判定

        Args:
            current_length: 現在の段落の文数
            max_length: 最大文数
            current_index: 現在の文のインデックス
            sentences: 全文のリスト

        Returns:
            bool: 段落を分けるべきならTrue
        """
        # 最大文数に達した
        if current_length >= max_length:
            return True

        # 次の文が接続詞で始まり、現在2文以上ある
        if current_index < len(sentences) - 1:
            next_sentence = sentences[current_index + 1]
            for break_word in PunctuationRules.PARAGRAPH_BREAK_WORDS:
                if next_sentence.startswith(break_word) and current_length >= 2:
                    return True

        return False

    def clean_repeated_words(self, text: str) -> str:
        """
        繰り返された単語を削除

        Args:
            text: 入力テキスト

        Returns:
            重複が削除されたテキスト
        """
        # 同じ単語が2回以上連続している場合は1回に（プリコンパイル済みパターンを使用）
        result = RegexPatterns.REPEATED_WORDS.sub(r'\1', text)
        return result

    def format_numbers(self, text: str) -> str:
        """
        数字の表記を統一

        Args:
            text: 入力テキスト

        Returns:
            数字が整形されたテキスト
        """
        # 漢数字をアラビア数字に変換（オプション）
        # ここでは基本的な整形のみ
        result = text

        # 数字の前後のスペースを調整（プリコンパイル済みパターンを使用）
        result = RegexPatterns.NUMBER_SPACING.sub(r'\1\2', result)

        return result

    def format_all(self, text: str,
                   remove_fillers: bool = True,
                   add_punctuation: bool = True,
                   format_paragraphs: bool = True,
                   clean_repeated: bool = True) -> str:
        """
        すべての整形を適用

        Args:
            text: 入力テキスト
            remove_fillers: フィラー語削除を適用
            add_punctuation: 句読点整形を適用
            format_paragraphs: 段落整形を適用
            clean_repeated: 重複削除を適用

        Returns:
            整形されたテキスト
        """
        result = text

        if remove_fillers:
            result = self.remove_fillers(result)

        if clean_repeated:
            result = self.clean_repeated_words(result)

        if add_punctuation:
            result = self.add_punctuation(result)

        result = self.format_numbers(result)

        if format_paragraphs:
            result = self.format_paragraphs(result)

        return result


if __name__ == "__main__":
    # テスト
    formatter = TextFormatter()

    test_texts = [
        "あのーこれはテストですねえーと今日はいい天気ですあのー明日も晴れるといいですね",
        "えーとですね今日は会議がありましてそれでプロジェクトの進捗を確認しましたしかし問題がいくつかありましてその対応を検討することになりました",
        "これはテストですこれはテストですこれはテストです"
    ]

    for i, test_text in enumerate(test_texts, 1):
        print(f"\n{'='*60}")
        print(f"テスト {i}")
        print(f"{'='*60}")
        print("元のテキスト:")
        print(test_text)
        print("\n整形後:")
        print(formatter.format_all(test_text))
        print()
