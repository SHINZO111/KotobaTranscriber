"""
APIベース文章補正モジュール
Claude 3.5 Sonnet / OpenAI GPT-4 API統合
"""

import os
import re
import logging
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

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
    api_key: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60
    retry_count: int = 3


class BaseAPICorrector(ABC):
    """API補正の基底クラス"""

    def __init__(self, config: CorrectionConfig):
        self.config = config
        self.is_available = False

    @abstractmethod
    def correct_text(self, text: str, context: Optional[str] = None) -> str:
        """文章を補正"""
        pass

    @abstractmethod
    def correct_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """セグメントを補正"""
        pass

    @abstractmethod
    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """要約を生成"""
        pass

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

        # 文で分割
        sentences = re.split(r'([。！？])', text)
        sentences = [s for s in sentences if s]

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

    def correct_text(self, text: str, context: Optional[str] = None) -> str:
        """
        Claude APIで文章を補正

        Args:
            text: 入力テキスト
            context: 前後の文脈（オプション）

        Returns:
            補正後のテキスト
        """
        if not self.is_available or not self.client:
            return text

        try:
            # 長い文章は分割して処理
            chunks = self._split_text(text, max_chars=3000)
            corrected_chunks = []

            for chunk in chunks:
                response = self.client.messages.create(
                    model=self.config.model or "claude-3-5-sonnet-20241022",
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=self.SYSTEM_PROMPT,
                    messages=[{
                        "role": "user",
                        "content": f"以下のテキストを補正してください：\n\n{chunk}"
                    }]
                )

                corrected = response.content[0].text if response.content else chunk
                corrected_chunks.append(corrected)

            return "\n\n".join(corrected_chunks)

        except Exception as e:
            logger.error(f"Claude correction failed: {e}")
            return text

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

        # セグメントを結合して一括補正
        combined_text = "\n".join([seg.get("text", "") for seg in segments])
        corrected_text = self.correct_text(combined_text)

        # 補正後のテキストを分割して各セグメントに割り当て
        corrected_lines = corrected_text.split("\n")

        result = []
        for i, seg in enumerate(segments):
            corrected_seg = seg.copy()
            if i < len(corrected_lines):
                corrected_seg["text"] = corrected_lines[i]
                corrected_seg["corrected"] = True
            result.append(corrected_seg)

        return result

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
                model=self.config.model or "claude-3-5-sonnet-20241022",
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

    SYSTEM_PROMPT = """あなたは日本語の文章補正の専門家です。
与えられた音声文字起こしテキストを、以下の観点で補正してください：

1. 句読点の適切な挿入
2. 段落の適切な分割
3. 誤字・脱字の修正
4. 自然な日本語表現への改善
5. フィラー語（あー、えー、など）の削除
6. 重複表現の削除

元の意味を保持しながら、読みやすく自然な文章に仕上げてください。"""

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

    def correct_text(self, text: str, context: Optional[str] = None) -> str:
        """
        GPT-4で文章を補正

        Args:
            text: 入力テキスト
            context: 前後の文脈（オプション）

        Returns:
            補正後のテキスト
        """
        if not self.is_available or not self.client:
            return text

        try:
            chunks = self._split_text(text, max_chars=3000)
            corrected_chunks = []

            for chunk in chunks:
                messages = [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"以下のテキストを補正してください：\n\n{chunk}"}
                ]

                if context:
                    messages.insert(1, {"role": "user", "content": f"文脈: {context}"})

                response = self.client.chat.completions.create(
                    model=self.config.model or "gpt-4",
                    messages=messages,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature
                )

                corrected = response.choices[0].message.content if response.choices else chunk
                corrected_chunks.append(corrected)

            return "\n\n".join(corrected_chunks)

        except Exception as e:
            logger.error(f"OpenAI correction failed: {e}")
            return text

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

        combined_text = "\n".join([seg.get("text", "") for seg in segments])
        corrected_text = self.correct_text(combined_text)
        corrected_lines = corrected_text.split("\n")

        result = []
        for i, seg in enumerate(segments):
            corrected_seg = seg.copy()
            if i < len(corrected_lines):
                corrected_seg["text"] = corrected_lines[i]
                corrected_seg["corrected"] = True
            result.append(corrected_seg)

        return result

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
                model=self.config.model or "gpt-4",
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
