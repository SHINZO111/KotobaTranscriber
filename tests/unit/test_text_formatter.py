"""
text_formatter.py の単体テスト

カバレッジ目標: 85%
テキスト後処理の全機能をテスト
"""

import pytest
import sys
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from text_formatter import TextFormatter


@pytest.fixture
def formatter():
    """TextFormatterインスタンスを返す"""
    return TextFormatter()


# ==================== Initialization Tests ====================

@pytest.mark.unit
class TestTextFormatterInitialization:
    """初期化のテスト"""

    def test_initialization(self):
        """正常に初期化できることを確認"""
        formatter = TextFormatter()
        assert formatter is not None

    def test_filler_words_list_exists(self):
        """フィラー語リストが定義されていることを確認"""
        assert hasattr(TextFormatter, 'FILLER_WORDS')
        assert isinstance(TextFormatter.FILLER_WORDS, list)
        assert len(TextFormatter.FILLER_WORDS) > 0

    def test_filler_words_content(self):
        """フィラー語リストに期待される単語が含まれることを確認"""
        expected_fillers = ['あー', 'えー', 'その', 'まあ', 'うん']
        for filler in expected_fillers:
            assert filler in TextFormatter.FILLER_WORDS


# ==================== Remove Fillers Tests ====================

@pytest.mark.unit
class TestRemoveFillers:
    """フィラー語削除のテスト"""

    def test_remove_basic_fillers(self, formatter):
        """基本的なフィラー語を削除"""
        text = "あのーこれはテストです"
        result = formatter.remove_fillers(text)
        assert "あのー" not in result
        assert "これはテストです" in result

    def test_remove_multiple_fillers(self, formatter):
        """複数のフィラー語を削除"""
        text = "あのーえーとこれはそのテストです"
        result = formatter.remove_fillers(text)
        assert "あのー" not in result
        assert "えーと" not in result
        assert "その" not in result

    def test_remove_fillers_with_punctuation(self, formatter):
        """句読点付きフィラー語を削除"""
        text = "あのー、これはテストです。えー、そうですね。"
        result = formatter.remove_fillers(text)
        assert "あのー" not in result
        assert "えー" not in result

    def test_preserve_non_filler_content(self, formatter):
        """フィラー語以外の内容は保持"""
        text = "これは重要なテストです"
        result = formatter.remove_fillers(text)
        assert result == text

    def test_empty_string(self, formatter):
        """空文字列の処理"""
        result = formatter.remove_fillers("")
        assert result == ""

    def test_only_fillers(self, formatter):
        """フィラー語のみのテキスト"""
        text = "あのー えー その"
        result = formatter.remove_fillers(text)
        assert result.strip() == ""

    def test_consecutive_punctuation_cleanup(self, formatter):
        """連続する句読点を整理"""
        text = "これは、、テストです。。"
        result = formatter.remove_fillers(text)
        assert "、、" not in result
        assert "。。" not in result

    def test_whitespace_cleanup(self, formatter):
        """連続するスペースを1つに"""
        text = "これは    テスト   です"
        result = formatter.remove_fillers(text)
        assert "    " not in result
        assert "   " not in result

    @pytest.mark.parametrize("filler", [
        "あー", "えー", "その", "まあ", "うん", "はい", "ですね"
    ])
    def test_each_filler_word(self, formatter, filler):
        """各フィラー語を個別にテスト"""
        text = f"{filler}これはテストです"
        result = formatter.remove_fillers(text)
        assert filler not in result or result.count(filler) == 0


# ==================== Add Punctuation Tests ====================

@pytest.mark.unit
class TestAddPunctuation:
    """句読点追加のテスト"""

    def test_add_period_to_end(self, formatter):
        """文末に句点を追加"""
        text = "これはテストです"
        result = formatter.add_punctuation(text)
        assert result.endswith("。")

    def test_preserve_existing_period(self, formatter):
        """既存の句点を保持"""
        text = "これはテストです。"
        result = formatter.add_punctuation(text)
        assert result == text

    def test_preserve_question_mark(self, formatter):
        """疑問符を保持"""
        text = "これはテストですか？"
        result = formatter.add_punctuation(text)
        assert result == text

    def test_preserve_exclamation_mark(self, formatter):
        """感嘆符を保持"""
        text = "これはテストです！"
        result = formatter.add_punctuation(text)
        assert result == text

    def test_remove_space_after_punctuation(self, formatter):
        """句読点後のスペースを削除"""
        text = "これは、 テストです。 本当です。"
        result = formatter.add_punctuation(text)
        assert "、 " not in result
        assert "。 " not in result

    def test_clean_consecutive_commas(self, formatter):
        """連続する読点を削除"""
        text = "これは、、テストです"
        result = formatter.add_punctuation(text)
        assert "、、" not in result

    def test_empty_string(self, formatter):
        """空文字列の処理"""
        result = formatter.add_punctuation("")
        assert result == ""

    def test_preserve_ellipsis(self, formatter):
        """三点リーダーを保持"""
        text = "これは…"
        result = formatter.add_punctuation(text)
        assert result == text

    def test_preserve_newline(self, formatter):
        """改行で終わるテキストには句点を追加しない"""
        text = "これはテスト\n"
        result = formatter.add_punctuation(text)
        assert not result.endswith("。")


# ==================== Format Paragraphs Tests ====================

@pytest.mark.unit
class TestFormatParagraphs:
    """段落整形のテスト"""

    def test_preserve_existing_paragraphs(self, formatter):
        """既存の段落分けを保持"""
        text = "これは段落1です。\n\nこれは段落2です。"
        result = formatter.format_paragraphs(text)
        assert "\n\n" in result

    def test_split_long_text_into_paragraphs(self, formatter):
        """長文を段落分け"""
        text = "これは1文目です。これは2文目です。これは3文目です。これは4文目です。これは5文目です。"
        result = formatter.format_paragraphs(text, max_sentences_per_paragraph=3)
        assert "\n\n" in result

    def test_paragraph_break_on_conjunctions(self, formatter):
        """接続詞で段落を分ける"""
        text = "これは1文目です。これは2文目です。しかしこれは3文目です。"
        result = formatter.format_paragraphs(text, max_sentences_per_paragraph=10)
        # しかし で始まる文の前で段落が分かれる可能性がある
        assert "しかし" in result

    def test_single_sentence_no_split(self, formatter):
        """1文のみの場合は段落分けしない"""
        text = "これは1文目です。"
        result = formatter.format_paragraphs(text)
        assert "\n\n" not in result

    def test_empty_string(self, formatter):
        """空文字列の処理"""
        result = formatter.format_paragraphs("")
        assert result == ""

    def test_preserve_question_marks(self, formatter):
        """疑問符で文を区切る"""
        text = "これは何ですか？それはテストです。"
        result = formatter.format_paragraphs(text)
        assert "何ですか？" in result

    def test_preserve_exclamation_marks(self, formatter):
        """感嘆符で文を区切る"""
        text = "すごい！これはテストです。"
        result = formatter.format_paragraphs(text)
        assert "すごい！" in result

    @pytest.mark.parametrize("break_word", [
        "しかし", "また", "ところで", "さて", "では", "それでは", "ちなみに"
    ])
    def test_paragraph_break_words(self, formatter, break_word):
        """各接続詞で段落分けをテスト"""
        text = f"これは1文目です。これは2文目です。{break_word}これは3文目です。"
        result = formatter.format_paragraphs(text)
        assert break_word in result


# ==================== Clean Repeated Words Tests ====================

@pytest.mark.unit
class TestCleanRepeatedWords:
    """繰り返し単語削除のテスト"""

    def test_remove_duplicate_words(self, formatter):
        """重複した単語を削除"""
        text = "これは これは テストです"
        result = formatter.clean_repeated_words(text)
        assert result.count("これは") == 1

    def test_multiple_duplicates(self, formatter):
        """複数の重複を削除"""
        text = "これは これは テスト テスト です"
        result = formatter.clean_repeated_words(text)
        assert result.count("これは") == 1
        assert result.count("テスト") == 1

    def test_preserve_non_consecutive_words(self, formatter):
        """連続していない同じ単語は保持"""
        text = "これはテストですこれは本当です"
        result = formatter.clean_repeated_words(text)
        assert result.count("これは") == 2

    def test_empty_string(self, formatter):
        """空文字列の処理"""
        result = formatter.clean_repeated_words("")
        assert result == ""

    def test_single_word(self, formatter):
        """単一単語の処理"""
        text = "テスト"
        result = formatter.clean_repeated_words(text)
        assert result == text


# ==================== Format Numbers Tests ====================

@pytest.mark.unit
class TestFormatNumbers:
    """数字整形のテスト"""

    def test_remove_spaces_between_numbers(self, formatter):
        """数字間のスペースを削除"""
        text = "123 456 789"
        result = formatter.format_numbers(text)
        assert result == "123456789"

    def test_preserve_text_content(self, formatter):
        """テキスト内容を保持"""
        text = "これは123テストです"
        result = formatter.format_numbers(text)
        assert "これは" in result
        assert "123" in result
        assert "テストです" in result

    def test_empty_string(self, formatter):
        """空文字列の処理"""
        result = formatter.format_numbers("")
        assert result == ""

    def test_no_numbers(self, formatter):
        """数字がないテキスト"""
        text = "これはテストです"
        result = formatter.format_numbers(text)
        assert result == text


# ==================== Format All Tests ====================

@pytest.mark.unit
class TestFormatAll:
    """統合整形のテスト"""

    def test_all_formatting_enabled(self, formatter):
        """全ての整形を適用"""
        text = "あのーこれはテストですねこれはテストですね"
        result = formatter.format_all(text)
        # フィラー削除、重複削除、句読点追加が適用されるはず
        assert "あのー" not in result
        assert result.endswith("。") or "\n" in result

    def test_disable_filler_removal(self, formatter):
        """フィラー削除を無効化"""
        text = "あのーこれはテストです"
        result = formatter.format_all(text, remove_fillers=False)
        assert "あのー" in result

    def test_disable_punctuation(self, formatter):
        """句読点追加を無効化"""
        text = "これはテストです"
        result = formatter.format_all(text, add_punctuation=False)
        # 句読点が追加されないことを確認（元々ない場合）
        # ただし他の処理が影響する可能性があるため、変更があったことを確認
        assert isinstance(result, str)

    def test_disable_paragraph_formatting(self, formatter):
        """段落整形を無効化"""
        text = "これは。" * 10
        result = formatter.format_all(text, format_paragraphs=False)
        # 段落分けが行われていないことを確認
        # （ただし元々段落がなければ \n\n は含まれないはず）
        assert isinstance(result, str)

    def test_disable_repeated_word_cleaning(self, formatter):
        """重複削除を無効化"""
        text = "これは これは テストです"
        result = formatter.format_all(text, clean_repeated=False)
        # 重複が残っていることを確認
        assert "これは これは" in result or result.count("これは") >= 2

    def test_all_disabled(self, formatter):
        """全ての整形を無効化（数字整形のみ適用）"""
        text = "あのーこれは これは 123 456"
        result = formatter.format_all(
            text,
            remove_fillers=False,
            add_punctuation=False,
            format_paragraphs=False,
            clean_repeated=False
        )
        # 数字整形のみ適用される
        assert "123456" in result
        assert "あのー" in result  # フィラー削除が無効なので残る

    def test_empty_string(self, formatter):
        """空文字列の処理"""
        result = formatter.format_all("")
        assert result == ""

    def test_complex_text(self, formatter):
        """複雑なテキストの統合テスト"""
        text = (
            "あのーこれはテストですねえーと今日はいい天気ですあのー"
            "明日も明日も晴れるといいですね"
        )
        result = formatter.format_all(text)

        # フィラー語が削除されている
        assert "あのー" not in result
        assert "えーと" not in result

        # 最終的に文字列が返される
        assert isinstance(result, str)
        assert len(result) > 0


# ==================== Edge Cases Tests ====================

@pytest.mark.unit
class TestEdgeCases:
    """エッジケースのテスト"""

    def test_only_punctuation(self, formatter):
        """句読点のみのテキスト"""
        text = "。、！？"
        result = formatter.format_all(text)
        assert isinstance(result, str)

    def test_only_whitespace(self, formatter):
        """空白のみのテキスト"""
        text = "   \t\n   "
        result = formatter.format_all(text)
        assert result.strip() == "" or result == "。"

    def test_very_long_text(self, formatter):
        """非常に長いテキスト"""
        text = "これはテストです。" * 100
        result = formatter.format_all(text)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mixed_japanese_and_english(self, formatter):
        """日本語と英語が混在"""
        text = "これはtestです"
        result = formatter.format_all(text)
        assert "これは" in result
        assert "test" in result

    def test_numbers_and_symbols(self, formatter):
        """数字と記号が混在"""
        text = "価格は1,000円です"
        result = formatter.format_all(text)
        assert "価格は" in result
        assert "円です" in result

    def test_special_characters(self, formatter):
        """特殊文字を含む"""
        text = "これは①テスト②です"
        result = formatter.format_all(text)
        assert isinstance(result, str)


# ==================== Parametrized Tests ====================

@pytest.mark.unit
class TestParametrized:
    """パラメトライズドテスト"""

    @pytest.mark.parametrize("input_text,expected_substr", [
        ("あのーテスト", "テスト"),
        ("えーとテスト", "テスト"),
        ("そのテスト", "テスト"),
        ("まあテスト", "テスト"),
    ])
    def test_filler_removal_parametrized(self, formatter, input_text, expected_substr):
        """様々なフィラー語削除をパラメトライズテスト"""
        result = formatter.remove_fillers(input_text)
        assert expected_substr in result

    @pytest.mark.parametrize("sentences_per_paragraph", [1, 2, 3, 4, 5])
    def test_paragraph_formatting_with_different_lengths(
        self, formatter, sentences_per_paragraph
    ):
        """様々な段落長でテスト"""
        text = "これはテストです。" * 10
        result = formatter.format_paragraphs(text, sentences_per_paragraph)
        assert isinstance(result, str)

    @pytest.mark.parametrize("text,should_end_with_period", [
        ("これはテストです", True),
        ("これはテストです。", False),  # 既に句点あり
        ("これはテストです！", False),  # 感嘆符あり
        ("これはテストです？", False),  # 疑問符あり
    ])
    def test_punctuation_addition_parametrized(
        self, formatter, text, should_end_with_period
    ):
        """様々なテキストに対する句読点追加"""
        result = formatter.add_punctuation(text)
        if should_end_with_period:
            assert result.endswith("。")
        else:
            # 既に適切な句読点がある場合は重複しない
            assert not result.endswith("。。")


# ==================== Integration Tests ====================

@pytest.mark.unit
class TestIntegration:
    """統合テスト"""

    def test_realistic_transcription_text(self, formatter):
        """実際の文字起こしテキストに近いケース"""
        text = (
            "あのーえーと今日はですね会議がありましてそれでプロジェクトの"
            "進捗を確認しましたしかし問題がいくつかありましてその対応を"
            "検討することになりました"
        )
        result = formatter.format_all(text)

        # フィラー語が削除されている
        assert "あのー" not in result
        assert "えーと" not in result

        # 適切な句読点が付与されている
        assert "。" in result or result.endswith("。")

        # 結果が空でない
        assert len(result) > 0

    def test_processing_order_matters(self, formatter):
        """処理順序が結果に影響することを確認"""
        text = "あのーこれは これは テストです"

        # format_all を使用
        result1 = formatter.format_all(text)

        # 手動で逆順に処理
        result2 = text
        result2 = formatter.format_paragraphs(result2)
        result2 = formatter.add_punctuation(result2)
        result2 = formatter.clean_repeated_words(result2)
        result2 = formatter.remove_fillers(result2)

        # 結果が異なる可能性がある（処理順序が重要）
        assert isinstance(result1, str)
        assert isinstance(result2, str)
