"""
LLM文章補正モジュール
ローカルLLM（Ollama）を使用した文章補正
"""

import logging
import requests
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


class LLMCorrector:
    """LLMを使用した文章補正クラス"""

    def __init__(self,
                 model_name: str = "gemma2:2b-jpn",
                 ollama_url: str = "http://localhost:11434"):
        """
        初期化

        Args:
            model_name: 使用するOllamaモデル名
                       推奨: gemma2:2b-jpn (日本語対応、軽量)
                       その他: llama3:8b, gemma:7b, etc.
            ollama_url: OllamaサーバーのURL
        """
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.api_url = f"{ollama_url}/api/generate"
        logger.info(f"LLMCorrector initialized with model: {model_name}")

    def is_available(self) -> bool:
        """Ollamaサーバーが利用可能かチェック"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama server not available: {e}")
            return False

    def correct_text(self, text: str, preserve_meaning: bool = True) -> str:
        """
        文章を補正

        Args:
            text: 入力テキスト
            preserve_meaning: 意味を保持するか（Trueの場合は控えめな補正）

        Returns:
            補正された文章
        """
        if not self.is_available():
            logger.warning("Ollama not available, returning original text")
            return text

        try:
            # プロンプトの作成
            if preserve_meaning:
                prompt = f"""以下の文字起こしテキストを、意味を変えずに自然な日本語に補正してください。
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
                prompt = f"""以下の文字起こしテキストを、より読みやすく自然な日本語に補正してください。
- 誤字脱字を修正
- 不自然な表現を改善
- 冗長な部分を簡潔に
- わかりやすい表現に
- 補正後のテキストのみを出力

【元のテキスト】
{text}

【補正後】
"""

            # Ollama APIにリクエスト
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # 創造性低め = 正確性重視
                        "top_p": 0.9,
                        "top_k": 40
                    }
                },
                timeout=60  # 最大60秒
            )

            if response.status_code == 200:
                result = response.json()
                corrected = result.get("response", "").strip()

                # 補正が成功した場合のみ返す
                if corrected and len(corrected) > 0:
                    logger.info("Text correction completed")
                    return corrected
                else:
                    logger.warning("LLM returned empty response")
                    return text
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return text

        except Exception as e:
            logger.error(f"Text correction failed: {e}")
            return text

    def correct_with_context(self, text: str, context: str = "") -> str:
        """
        コンテキストを考慮して文章を補正

        Args:
            text: 入力テキスト
            context: コンテキスト情報（会議、講演、インタビューなど）

        Returns:
            補正された文章
        """
        if not self.is_available():
            return text

        try:
            prompt = f"""以下は{context}の文字起こしテキストです。
自然で読みやすい日本語に補正してください。

【元のテキスト】
{text}

【補正後】
"""

            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                corrected = result.get("response", "").strip()
                if corrected:
                    return corrected

            return text

        except Exception as e:
            logger.error(f"Context-based correction failed: {e}")
            return text

    def summarize(self, text: str, max_length: int = 200) -> str:
        """
        文章を要約

        Args:
            text: 入力テキスト
            max_length: 要約の最大文字数

        Returns:
            要約された文章
        """
        if not self.is_available():
            return text[:max_length] + "..." if len(text) > max_length else text

        try:
            prompt = f"""以下のテキストを{max_length}文字程度に要約してください。
重要なポイントを簡潔にまとめてください。

【テキスト】
{text}

【要約】
"""

            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.5
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                summary = result.get("response", "").strip()
                if summary:
                    return summary

            return text[:max_length] + "..."

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return text[:max_length] + "..."


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    corrector = LLMCorrector()

    # Ollamaが利用可能かチェック
    if corrector.is_available():
        print("✓ Ollama is available")

        # テストテキスト
        test_text = "えーとですね今日は会議がありましてそれでプロジェクトの進捗を確認しましたしかし問題がいくつかありましてその対応を検討することになりました"

        print("\n【元のテキスト】")
        print(test_text)

        print("\n【補正後】")
        corrected = corrector.correct_text(test_text)
        print(corrected)

    else:
        print("✗ Ollama is not available")
        print("\nOllamaをインストールして起動してください：")
        print("1. https://ollama.com/ からOllamaをダウンロード")
        print("2. インストール後、以下のコマンドでモデルをダウンロード：")
        print("   ollama pull gemma2:2b")
        print("3. Ollamaサーバーが自動起動します")
