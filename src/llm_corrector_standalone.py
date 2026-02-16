"""
単独動作LLM文章補正モジュール
transformersライブラリを使用した完全ローカルLLM
"""

import logging
import re
from typing import Optional

from exceptions import ModelLoadError
from text_formatter import TextFormatter

logger = logging.getLogger(__name__)

# 高度な補正用のインポート（オプション）
try:
    import warnings

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

    warnings.filterwarnings("ignore")
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available, advanced correction disabled")


class StandaloneLLMCorrector:
    """transformersベースの単独動作LLM補正クラス"""

    def __init__(self, model_name: str = "rinna/japanese-gpt2-medium", device: str = "auto"):
        """
        初期化

        Args:
            model_name: 使用するモデル名
                       推奨オプション:
                       - "rinna/japanese-gpt2-medium" (軽量、310MB)
                       - "rinna/japanese-gpt-1b" (高性能、4GB)
                       - "cyberagent/open-calm-small" (軽量、400MB)
                       - "stabilityai/japanese-stablelm-base-alpha-7b" (高性能、重い)
            device: 実行デバイス ("auto", "cuda", "cpu")
        """
        self.model_name = model_name

        # デバイス自動選択
        if device == "auto":
            self.device = "cuda" if TRANSFORMERS_AVAILABLE and torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.tokenizer = None
        self.model = None
        self.pipe = None
        self.is_loaded = False

        logger.info(f"StandaloneLLMCorrector initialized with model: {model_name}, device: {self.device}")

    def load_model(self):
        """モデルをロード"""
        if self.is_loaded:
            return

        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers library is not installed. Install with: pip install transformers torch")

        try:
            logger.info(f"Loading model: {self.model_name}...")

            # トークナイザーとモデルをロード
            # セキュリティ: trust_remote_code=Falseで安全にモデルをロード
            # Model name is configured by user; trust_remote_code=False ensures safety
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=False)  # nosec B615

            self.model = AutoModelForCausalLM.from_pretrained(  # nosec B615
                self.model_name, torch_dtype=torch.float16 if self.device == "cuda" else torch.float32, trust_remote_code=False
            )

            # デバイスに移動
            self.model.to(self.device)
            self.model.eval()

            # パイプライン作成
            self.pipe = pipeline(
                "text-generation", model=self.model, tokenizer=self.tokenizer, device=0 if self.device == "cuda" else -1
            )

            self.is_loaded = True
            logger.info("Model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ModelLoadError(f"Failed to load LLM model '{self.model_name}': {e}") from e

    def is_available(self) -> bool:
        """モデルが利用可能かチェック"""
        return self.is_loaded

    def correct_text(self, text: str, max_length: int = 512) -> str:
        """
        文章を補正

        Args:
            text: 入力テキスト
            max_length: 生成する最大トークン数

        Returns:
            補正された文章
        """
        if not self.is_loaded:
            try:
                self.load_model()
            except Exception as e:
                logger.error(f"Cannot load model: {e}")
                return text

        try:
            # プロンプト作成
            prompt = f"""以下の文章を自然な日本語に補正してください。

元の文章: {text}

補正後の文章:"""

            # テキスト生成
            if self.pipe is None or self.tokenizer is None:
                return text

            result = self.pipe(
                prompt,
                max_new_tokens=max_length,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.2,
                pad_token_id=self.tokenizer.eos_token_id,
            )

            # 生成結果から補正文を抽出
            generated = result[0]["generated_text"]

            # プロンプトの後の部分を取得
            if "補正後の文章:" in generated:
                corrected = generated.split("補正後の文章:")[1].strip()
                # 最初の句点までを取得（余計な生成を防ぐ）
                sentences = corrected.split("。")
                if sentences:
                    corrected = "。".join(sentences[:3]) + "。"  # 最大3文まで
                    return corrected if len(corrected) > 10 else text

            return text

        except Exception as e:
            logger.error(f"Text correction failed: {e}")
            return text

    def generate_summary(self, text: str) -> str:
        """
        文章を要約

        Args:
            text: 入力テキスト

        Returns:
            要約された文章
        """
        if not self.is_loaded:
            try:
                self.load_model()
            except Exception:
                return text[:200] + "..."

        try:
            prompt = f"""以下の文章を要約してください。

文章: {text}

要約:"""

            if self.pipe is None:
                return text[:200] + "..."

            result = self.pipe(prompt, max_new_tokens=150, do_sample=True, temperature=0.7, repetition_penalty=1.2)

            generated = result[0]["generated_text"]

            if "要約:" in generated:
                summary = generated.split("要約:")[1].strip()
                return summary if len(summary) > 10 else text[:200] + "..."

            return text[:200] + "..."

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return text[:200] + "..."

    def unload_model(self):
        """モデルをアンロード（メモリ解放）"""
        if self.model is not None or self.tokenizer is not None or self.pipe is not None:
            self.model = None
            self.tokenizer = None
            self.pipe = None
            if TRANSFORMERS_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.is_loaded = False
            logger.info("Model unloaded")


class SimpleLLMCorrector:
    """
    より軽量なルールベース補正
    TextFormatterに委譲しつつ、追加の補正ルールを適用する。
    モデルなしでも動作可能。
    """

    def __init__(self):
        """初期化"""
        self.is_loaded = True  # 常に利用可能
        self._formatter = TextFormatter()

    def is_available(self) -> bool:
        """常に利用可能"""
        return True

    def correct_text(self, text: str) -> str:
        """
        ルールベース補正（句読点処理を含む）

        Args:
            text: 入力テキスト

        Returns:
            補正された文章
        """
        # フィラー語削除（TextFormatterのリストを再利用、スペースなしテキスト対応）
        filler_list = TextFormatter.FILLER_WORDS + TextFormatter.AGGRESSIVE_FILLER_WORDS
        result = text
        for filler in filler_list:
            result = re.sub(re.escape(filler) + r"\s*", "", result)

        # 基本的な補正ルール
        corrections = {
            # よくある音声認識の間違い
            "言ってわ": "言っては",
            "思ってわ": "思っては",
            # 重複表現の削除
            "ですです": "です",
            "ますます": "ます",
            "ました。ました": "ました",
            # スペースの整理
            "　": " ",  # 全角スペースを半角に
        }

        for wrong, correct in corrections.items():
            result = result.replace(wrong, correct)

        # 連続する句読点の削除
        result = re.sub(r"、{2,}", "、", result)
        result = re.sub(r"。{2,}", "。", result)

        # 連続するスペースを1つに
        result = re.sub(r"\s+", " ", result)
        result = result.strip()

        # 句読点処理はTextFormatterに委譲
        result = str(self._formatter.add_punctuation(result))

        return result


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== StandaloneLLMCorrector Test ===\n")

    # 軽量版を使用
    print("1. SimpleLLMCorrector（ルールベース、モデル不要）:")
    simple_corrector = SimpleLLMCorrector()
    test_text = "えーとですね今日わ会議がありましてですです"
    print(f"元: {test_text}")
    print(f"補正後: {simple_corrector.correct_text(test_text)}")

    print("\n2. StandaloneLLMCorrector（要: モデルダウンロード）:")
    print("初回実行時は rinna/japanese-gpt2-medium (310MB) をダウンロードします。")
    print("使用するには以下のようにインスタンス化してください：")
    print("  corrector = StandaloneLLMCorrector()")
    print("  corrector.load_model()  # 初回のみ数分かかります")
    print("  corrected = corrector.correct_text(text)")
