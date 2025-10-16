"""
LLM補正ユーティリティ
LLMCorrector と StandaloneLLMCorrector の共通機能
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMAvailabilityMixin:
    """
    LLM利用可能性チェック機能を提供するミックスイン

    is_available メソッドを提供し、各LLMクラスで共通利用
    """

    def _check_server_availability(self, url: str, timeout: int = 2) -> bool:
        """
        サーバーの利用可能性をチェック

        Args:
            url: サーバーURL
            timeout: タイムアウト（秒）

        Returns:
            利用可能ならTrue
        """
        try:
            import requests
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Server not available at {url}: {e}")
            return False


class TextCorrectionMixin:
    """
    テキスト補正機能を提供するミックスイン

    基本的な補正ロジックを共通化
    """

    def _build_correction_prompt(self, text: str, preserve_meaning: bool = True) -> str:
        """
        補正用プロンプトを構築

        Args:
            text: 入力テキスト
            preserve_meaning: 意味を保持するか

        Returns:
            プロンプト文字列
        """
        if preserve_meaning:
            return f"""以下の文字起こしテキストを、意味を変えずに自然な日本語に補正してください。
- 誤字脱字を修正
- 不自然な表現を自然に
- 元の意味は絶対に変えない
- 余計な説明は追加しない
- 補正後のテキストのみを出力

【元のテキスト】
{text}

【補正後】
"""
        else:
            return f"""以下の文字起こしテキストを、より読みやすく自然な日本語に補正してください。
- 誤字脱字を修正
- 不自然な表現を改善
- 冗長な部分を簡潔に
- わかりやすい表現に
- 補正後のテキストのみを出力

【元のテキスト】
{text}

【補正後】
"""

    def _build_summary_prompt(self, text: str, max_length: int = 200) -> str:
        """
        要約用プロンプトを構築

        Args:
            text: 入力テキスト
            max_length: 最大文字数

        Returns:
            プロンプト文字列
        """
        return f"""以下のテキストを{max_length}文字程度に要約してください。
重要なポイントを簡潔にまとめてください。

【テキスト】
{text}

【要約】
"""

    def _validate_corrected_text(self, corrected: str, original: str) -> str:
        """
        補正結果を検証

        Args:
            corrected: 補正後のテキスト
            original: 元のテキスト

        Returns:
            検証済みテキスト（問題があれば元のテキスト）
        """
        # 空文字チェック
        if not corrected or len(corrected.strip()) == 0:
            logger.warning("LLM returned empty response, using original")
            return original

        # 長さチェック（元の3倍以上になっていたら怪しい）
        if len(corrected) > len(original) * 3:
            logger.warning("LLM response too long, using original")
            return original

        return corrected


class ErrorHandlingMixin:
    """
    エラーハンドリング機能を提供するミックスイン

    LLM処理の共通エラーハンドリング
    """

    def _handle_llm_error(self, error: Exception, original_text: str,
                         operation: str = "correction") -> str:
        """
        LLMエラーを処理

        Args:
            error: 発生した例外
            original_text: 元のテキスト
            operation: 実行していた操作名

        Returns:
            元のテキスト（フォールバック）
        """
        logger.error(f"LLM {operation} failed: {error}")
        return original_text


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("LLM Utilities loaded successfully")
    print("\nAvailable Mixins:")
    print("  - LLMAvailabilityMixin: サーバー利用可能性チェック")
    print("  - TextCorrectionMixin: テキスト補正プロンプト構築")
    print("  - ErrorHandlingMixin: エラーハンドリング")
    print("\nUsage example:")
    print("  class MyLLMCorrector(TextCorrectionMixin, ErrorHandlingMixin):")
    print("      def correct_text(self, text):")
    print("          prompt = self._build_correction_prompt(text)")
    print("          # ... LLM処理 ...")
    print("          return corrected")
