"""
テキスト整形モジュール
文字起こし結果の後処理を行う
"""

import re
from typing import List, Dict


class TextFormatter:
    """テキスト整形クラス"""

    # フィラー語・言い淀みのリスト
    FILLER_WORDS = [
        'あー', 'あ', 'ああ', 'あのー', 'あの',
        'えー', 'え', 'ええ', 'えっと', 'えーと',
        'その', 'そのー',
        'まあ', 'まー',
        'うん', 'うーん',
        'んー', 'ん',
        'はい',
        'ですね', 'ですねえ',
        'なんか', 'なんて',
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
        """
        result = text

        # フィラー語のパターンを作成
        for filler in self.FILLER_WORDS:
            # 単語の境界を考慮したパターン
            pattern = r'\b' + re.escape(filler) + r'\b[、。]?\s*'
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        # 連続する句読点を整理
        result = re.sub(r'[、]{2,}', '、', result)
        result = re.sub(r'[。]{2,}', '。', result)

        # 連続するスペースを1つに
        result = re.sub(r'\s+', ' ', result)

        # 行頭・行末の空白を削除
        result = result.strip()

        return result

    def add_punctuation(self, text: str) -> str:
        """
        句読点を追加・整形（簡易版 - LLM補正使用を推奨）

        注意: この関数は最小限の処理のみ行います。
        より高度な句読点処理は SimpleLLMCorrector を使用してください。

        Args:
            text: 入力テキスト

        Returns:
            句読点が整形されたテキスト
        """
        result = text

        # 既存の句読点の後のスペースを削除（日本語では不要）
        result = re.sub(r'([、。！？])\s+', r'\1', result)

        # 連続する読点を削除
        result = re.sub(r'、{2,}', '、', result)

        # 文末に何もない場合は句点を追加
        if result and not result.endswith(('。', '！', '？', '…', '\n')):
            result += '。'

        return result

    def format_paragraphs(self, text: str, max_sentences_per_paragraph: int = 4) -> str:
        """
        段落を整形（より自然な改行位置）

        Args:
            text: 入力テキスト
            max_sentences_per_paragraph: 1段落あたりの最大文数

        Returns:
            段落が整形されたテキスト
        """
        # 既に適切な改行がある場合（連続改行が2つ以上）
        if '\n\n' in text:
            return text

        # 文で分割（句点、感嘆符、疑問符で区切る）
        # 改行も保持する
        sentences = re.split(r'([。！？\n])', text)

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
        paragraphs = []
        current_paragraph = []
        current_length = 0

        # 接続詞で段落を分けるかの判定用
        paragraph_break_words = ['しかし', 'また', 'ところで', 'さて', 'では', 'それでは', 'ちなみに']

        for i, sentence in enumerate(paired_sentences):
            current_paragraph.append(sentence)
            current_length += 1

            # 段落を分ける条件：
            # 1. 最大文数に達した
            # 2. 次の文が接続詞で始まり、現在2文以上ある
            # 3. 最後の文
            should_break = False

            if current_length >= max_sentences_per_paragraph:
                should_break = True
            elif i < len(paired_sentences) - 1:
                next_sentence = paired_sentences[i + 1]
                for break_word in paragraph_break_words:
                    if next_sentence.startswith(break_word) and current_length >= 2:
                        should_break = True
                        break

            if should_break or i == len(paired_sentences) - 1:
                paragraphs.append(''.join(current_paragraph))
                current_paragraph = []
                current_length = 0

        # 段落が1つしかない場合は改行なし
        if len(paragraphs) <= 1:
            return text

        return '\n\n'.join(paragraphs)

    def clean_repeated_words(self, text: str) -> str:
        """
        繰り返された単語を削除

        Args:
            text: 入力テキスト

        Returns:
            重複が削除されたテキスト
        """
        # 同じ単語が2回以上連続している場合は1回に
        result = re.sub(r'\b(\w+)\s+\1\b', r'\1', text)
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

        # 数字の前後のスペースを調整
        result = re.sub(r'(\d+)\s+(\d+)', r'\1\2', result)

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
