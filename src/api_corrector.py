"""
APIベース文章補正モジュール
Claude 3.5 Sonnet / OpenAI GPT-4 API統合
"""

import os
import re
import time
import logging
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from exceptions import (
    APIError as KotobaAPIError,
    APIConnectionError as KotobaAPIConnectionError,
    APIAuthenticationError as KotobaAPIAuthenticationError,
    APIRateLimitError as KotobaAPIRateLimitError,
)

logger = logging.getLogger(__name__)


class APIProvider(Enum):
    """APIプロバイダー"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"


@dataclass
class CorrectionConfig:
    """補正設定"""
    provider: APIProvider
    api_key: str = field(repr=False)
    model: str
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60
    retry_count: int = 3
    retry_base_delay: float = 1.0  # リトライ基本遅延（秒）


class BaseAPICorrector(ABC):
    """API補正の基底クラス"""

    SYSTEM_PROMPT = """あなたは日本語の文章補正の専門家です。
与えられた音声文字起こしテキストを、以下の観点で補正してください：

1. 句読点の適切な挿入
2. 段落の適切な分割
3. 誤字・脱字の修正
4. 自然な日本語表現への改善
5. フィラー語（あー、えー、など）の削除
6. 重複表現の削除

元の意味を保持しながら、読みやすく自然な文章に仕上げてください。
説明や注釈は不要です。補正後の文章のみを出力してください。"""

    def __init__(self, config: CorrectionConfig):
        self.config = config
        self.is_available = False

    @abstractmethod
    def correct_text(self, text: str, context: Optional[str] = None) -> str:
        """文章を補正"""
        pass

    def correct_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        セグメントを補正

        Args:
            segments: 文字起こしセグメントリスト

        Returns:
            補正済みセグメントリスト
        """
        if not self.is_available:
            return segments

        try:
            result = []
            for seg in segments:
                corrected_seg = seg.copy()
                original_text = seg.get("text", "")
                if original_text.strip():
                    try:
                        corrected_text = self.correct_text(original_text)
                        corrected_seg["text"] = corrected_text
                        corrected_seg["corrected"] = True
                    except Exception as e:
                        logger.warning(f"Segment correction failed, keeping original: {e}")
                result.append(corrected_seg)
            return result
        except Exception as e:
            logger.error(f"correct_segments failed, returning original segments: {e}")
            return segments

    @abstractmethod
    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """要約を生成"""
        pass

    def _handle_api_error(self, e: Exception, provider_name: str) -> None:
        """API呼び出しエラーの共通ハンドリング（常に例外を再raiseする）"""
        error_msg = str(e).lower()
        if "authentication" in error_msg or "api key" in error_msg or "unauthorized" in error_msg:
            logger.error(f"{provider_name} API authentication failed: {type(e).__name__}")
            raise KotobaAPIAuthenticationError(f"{provider_name} API authentication failed") from e
        elif "rate limit" in error_msg or "rate_limit" in error_msg:
            logger.error(f"{provider_name} API rate limit exceeded: {type(e).__name__}")
            raise KotobaAPIRateLimitError(f"{provider_name} API rate limit exceeded") from e
        else:
            logger.error(f"{provider_name} API call failed: {type(e).__name__}")
            raise KotobaAPIError(f"{provider_name} API call failed: {type(e).__name__}") from e

    def _call_with_retry(self, func, *args, **kwargs):
        """
        リトライ付きAPI呼び出し（指数バックオフ）

        認証エラーはリトライ不可のため即座に再raise。
        レート制限・接続エラーはリトライ可能。
        """
        last_error = None
        for attempt in range(max(1, self.config.retry_count)):
            try:
                return func(*args, **kwargs)
            except KotobaAPIAuthenticationError:
                raise  # 認証エラーはリトライ不可
            except (KotobaAPIRateLimitError, KotobaAPIConnectionError) as e:
                last_error = e
                if attempt < self.config.retry_count - 1:
                    delay = self.config.retry_base_delay * (2 ** attempt)
                    logger.warning(
                        f"API call failed (attempt {attempt + 1}/{self.config.retry_count}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
            except KotobaAPIError:
                raise  # その他のAPIエラーはリトライ不可
        raise last_error

    def _split_text(self, text: str, max_chars: int = 2000) -> List[str]:
        """
        長い文章を分割

        Args:
            text: 元の文章
            max_chars: 最大文字数

        Returns:
            分割された文章リスト
        """
        if len(text) <= max_chars:
            return [text]

        # 文で分割（区切り文字を前の文に結合）
        parts = re.split(r'([。！？])', text)
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sentences.append(parts[i] + parts[i + 1])
        if len(parts) % 2 == 1 and parts[-1]:
            sentences.append(parts[-1])

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chars:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


class ClaudeCorrector(BaseAPICorrector):
    """Claude 3.5 Sonnet API補正クラス"""

    DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

    def __init__(self, config: CorrectionConfig):
        super().__init__(config)
        self.client = None
        self._init_client()

    def _init_client(self):
        """Anthropicクライアントを初期化"""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.config.api_key)
            self.is_available = True
            logger.info("Claude client initialized")
        except ImportError:
            logger.error("anthropic package not installed. Run: pip install anthropic")
        except Exception as e:
            logger.error(f"Failed to initialize Claude client: {e}")

    def _call_claude_api(self, user_content: str) -> str:
        """単一チャンクのClaude API呼び出し"""
        try:
            response = self.client.messages.create(
                model=self.config.model or self.DEFAULT_MODEL,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=self.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": user_content
                }]
            )
            return response.content[0].text if response.content else ""
        except KotobaAPIError:
            raise
        except ConnectionError as e:
            raise KotobaAPIConnectionError(f"Claude API connection failed: {e}") from e
        except Exception as e:
            self._handle_api_error(e, "Claude")

    def correct_text(self, text: str, context: Optional[str] = None) -> str:
        """
        Claude APIで文章を補正（リトライ付き）

        Args:
            text: 入力テキスト
            context: 前後の文脈（オプション）

        Returns:
            補正後のテキスト
        """
        if not self.is_available or not self.client:
            return text
        if not text or not text.strip():
            return text

        chunks = self._split_text(text, max_chars=3000)
        corrected_chunks = []

        for chunk in chunks:
            user_content = f"以下のテキストを補正してください：\n\n{chunk}"
            if context:
                user_content = f"文脈: {context}\n\n{user_content}"

            corrected = self._call_with_retry(self._call_claude_api, user_content)
            corrected_chunks.append(corrected or chunk)

        return "\n\n".join(corrected_chunks)

    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        要約を生成

        Args:
            text: 入力テキスト
            max_length: 最大文字数

        Returns:
            要約テキスト
        """
        if not self.is_available:
            return text[:max_length] + "..."

        try:
            response = self.client.messages.create(
                model=self.config.model or self.DEFAULT_MODEL,
                max_tokens=min(max_length, 1024),
                temperature=0.5,
                system="以下の文章を簡潔に要約してください。",
                messages=[{
                    "role": "user",
                    "content": text
                }]
            )

            return response.content[0].text if response.content else text[:max_length]

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return text[:max_length] + "..."


class OpenAICorrector(BaseAPICorrector):
    """OpenAI GPT-4 API補正クラス"""

    DEFAULT_MODEL = "gpt-4"

    def __init__(self, config: CorrectionConfig):
        super().__init__(config)
        self.client = None
        self._init_client()

    def _init_client(self):
        """OpenAIクライアントを初期化"""
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.config.api_key)
            self.is_available = True
            logger.info("OpenAI client initialized")
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")

    def _call_openai_api(self, user_content: str) -> str:
        """単一チャンクのOpenAI API呼び出し"""
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ]
            response = self.client.chat.completions.create(
                model=self.config.model or self.DEFAULT_MODEL,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            return response.choices[0].message.content if response.choices else ""
        except KotobaAPIError:
            raise
        except ConnectionError as e:
            raise KotobaAPIConnectionError(f"OpenAI API connection failed: {e}") from e
        except Exception as e:
            self._handle_api_error(e, "OpenAI")

    def correct_text(self, text: str, context: Optional[str] = None) -> str:
        """
        GPT-4で文章を補正（リトライ付き）

        Args:
            text: 入力テキスト
            context: 前後の文脈（オプション）

        Returns:
            補正後のテキスト
        """
        if not self.is_available or not self.client:
            return text
        if not text or not text.strip():
            return text

        chunks = self._split_text(text, max_chars=3000)
        corrected_chunks = []

        for chunk in chunks:
            user_content = f"以下のテキストを補正してください：\n\n{chunk}"
            if context:
                user_content = f"文脈: {context}\n\n{user_content}"

            corrected = self._call_with_retry(self._call_openai_api, user_content)
            corrected_chunks.append(corrected or chunk)

        return "\n\n".join(corrected_chunks)

    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        要約を生成

        Args:
            text: 入力テキスト
            max_length: 最大文字数

        Returns:
            要約テキスト
        """
        if not self.is_available:
            return text[:max_length] + "..."

        try:
            response = self.client.chat.completions.create(
                model=self.config.model or self.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": "以下の文章を簡潔に要約してください。"},
                    {"role": "user", "content": text}
                ],
                max_tokens=min(max_length, 1024),
                temperature=0.5
            )

            return response.choices[0].message.content if response.choices else text[:max_length]

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return text[:max_length] + "..."


class HybridCorrector:
    """
    ハイブリッド補正クラス
    ローカルLLM + APIの組み合わせ
    """

    def __init__(self,
                 local_corrector=None,
                 api_corrector: Optional[BaseAPICorrector] = None,
                 use_api_for_long_text: bool = True,
                 long_text_threshold: int = 500):
        """
        初期化

        Args:
            local_corrector: ローカル補正器（SimpleLLMCorrector等）
            api_corrector: API補正器
            use_api_for_long_text: 長い文章でAPIを使用
            long_text_threshold: 長文と判断する閾値
        """
        self.local = local_corrector
        self.api = api_corrector
        self.use_api_for_long_text = use_api_for_long_text
        self.long_text_threshold = long_text_threshold

    def correct_text(self, text: str) -> str:
        """
        最適な方法で文章を補正

        Args:
            text: 入力テキスト

        Returns:
            補正後のテキスト
        """
        # 短い文章はローカルで処理
        if len(text) < self.long_text_threshold and self.local:
            return self.local.correct_text(text)

        # 長い文章はAPIを使用
        if self.use_api_for_long_text and self.api and self.api.is_available:
            return self.api.correct_text(text)

        # フォールバック
        if self.local:
            return self.local.correct_text(text)

        return text

    def correct_with_fallback(self, text: str) -> str:
        """
        API失敗時にローカルにフォールバック

        Args:
            text: 入力テキスト

        Returns:
            補正後のテキスト
        """
        if self.api and self.api.is_available:
            try:
                return self.api.correct_text(text)
            except Exception as e:
                logger.warning(f"API correction failed, falling back to local: {e}")

        if self.local:
            return self.local.correct_text(text)

        return text


def create_corrector(provider: str,
                    api_key: Optional[str] = None,
                    model: Optional[str] = None) -> Optional[BaseAPICorrector]:
    """
    プロバイダーに応じた補正器を作成

    Args:
        provider: プロバイダー名 ("claude", "openai")
        api_key: APIキー
        model: モデル名

    Returns:
        補正器インスタンス
    """
    config = CorrectionConfig(
        provider=APIProvider(provider),
        api_key=api_key or "",
        model=model or ""
    )

    if provider == "claude":
        return ClaudeCorrector(config)
    elif provider == "openai":
        return OpenAICorrector(config)

    return None


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== API Corrector Test ===\n")

    # ローカル補正テスト
    try:
        from llm_corrector_standalone import SimpleLLMCorrector
        local = SimpleLLMCorrector()

        test_text = "えーとですね今日は会議がありましてですです"
        print(f"元: {test_text}")
        print(f"ローカル補正: {local.correct_text(test_text)}")
    except Exception as e:
        print(f"ローカル補正エラー: {e}")

    # API補正テスト（APIキーが設定されている場合）
    claude_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if claude_key:
        print("\nClaude APIテスト:")
        claude = create_corrector("claude", claude_key)
        if claude and claude.is_available:
            result = claude.correct_text(test_text)
            print(f"Claude補正: {result}")

    if openai_key:
        print("\nOpenAI APIテスト:")
        openai_corr = create_corrector("openai", openai_key)
        if openai_corr and openai_corr.is_available:
            result = openai_corr.correct_text(test_text)
            print(f"OpenAI補正: {result}")

    print("\nテスト完了!")
