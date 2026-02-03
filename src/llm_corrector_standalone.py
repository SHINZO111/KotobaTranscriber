"""
単独動作LLM文章補正モジュール
transformersライブラリを使用した完全ローカルLLM
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# 高度な補正用のインポート（オプション）
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import warnings
    warnings.filterwarnings('ignore')
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available, advanced correction disabled")


class StandaloneLLMCorrector:
    """transformersベースの単独動作LLM補正クラス"""

    def __init__(self,
                 model_name: str = "rinna/japanese-gpt2-medium",
                 device: str = "auto"):
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
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
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
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                trust_remote_code=True
            )

            # デバイスに移動
            self.model.to(self.device)
            self.model.eval()

            # パイプライン作成
            self.pipe = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1
            )

            self.is_loaded = True
            logger.info("Model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

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
            result = self.pipe(
                prompt,
                max_new_tokens=max_length,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.2,
                pad_token_id=self.tokenizer.eos_token_id
            )

            # 生成結果から補正文を抽出
            generated = result[0]['generated_text']

            # プロンプトの後の部分を取得
            if "補正後の文章:" in generated:
                corrected = generated.split("補正後の文章:")[1].strip()
                # 最初の句点までを取得（余計な生成を防ぐ）
                sentences = corrected.split('。')
                if sentences:
                    corrected = '。'.join(sentences[:3]) + '。'  # 最大3文まで
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
            except:
                return text[:200] + "..."

        try:
            prompt = f"""以下の文章を要約してください。

文章: {text}

要約:"""

            result = self.pipe(
                prompt,
                max_new_tokens=150,
                do_sample=True,
                temperature=0.7,
                repetition_penalty=1.2
            )

            generated = result[0]['generated_text']

            if "要約:" in generated:
                summary = generated.split("要約:")[1].strip()
                return summary if len(summary) > 10 else text[:200] + "..."

            return text[:200] + "..."

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return text[:200] + "..."

    def unload_model(self):
        """モデルをアンロード（メモリ解放）"""
        if self.model is not None:
            del self.model
            del self.tokenizer
            del self.pipe
            if TRANSFORMERS_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.is_loaded = False
            logger.info("Model unloaded")


class SimpleLLMCorrector:
    """
    より軽量なルールベース+小規模モデルのハイブリッド補正
    モデルなしでも動作可能
    """

    def __init__(self):
        """初期化"""
        self.is_loaded = True  # 常に利用可能

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
        result = text

        # フィラー語（言いよどみ）の削除
        fillers = [
            'えーと', 'えーっと', 'えっと', 'あのー', 'あのう', 'あの',
            'えー', 'あー', 'うー', 'うーん', 'んー', 'まあ',
            'なんか', 'なんていうか', 'ちょっと', 'やっぱり',
            'ですね', 'ですよね', 'ですけど', 'なんですけど',
        ]
        for filler in fillers:
            result = re.sub(re.escape(filler) + r'\s*', '', result)

        # 基本的な補正ルール
        corrections = {
            # よくある音声認識の間違い
            '言ってわ': '言っては',
            '思ってわ': '思っては',

            # 重複表現の削除
            'ですです': 'です',
            'ますます': 'ます',
            'ました。ました': 'ました',

            # スペースの整理
            '　': ' ',  # 全角スペースを半角に
        }

        for wrong, correct in corrections.items():
            result = result.replace(wrong, correct)

        # 連続する句読点の削除
        result = re.sub(r'、{2,}', '、', result)
        result = re.sub(r'。{2,}', '。', result)

        # 連続するスペースを1つに
        result = re.sub(r'\s+', ' ', result)
        result = result.strip()

        # === LLMベースの句読点処理 ===
        result = self._add_intelligent_punctuation(result)

        return result

    def _add_intelligent_punctuation(self, text: str) -> str:
        """
        インテリジェントな句読点追加（LLMライクなルール）

        Args:
            text: 入力テキスト

        Returns:
            句読点が追加されたテキスト
        """
        result = text

        # 既存の句読点の後のスペースを削除
        result = re.sub(r'([、。！？])\s+', r'\1', result)

        # 1. 接続詞の前に読点（文頭以外、既に句読点がない場合のみ）
        conjunctions = [
            'しかし', 'また', 'そして', 'それで', 'つまり', 'ところで',
            'さらに', 'ただし', 'ですが', 'でも', 'けれど', 'けれども',
            'だから', 'なので', 'そのため', 'したがって'
        ]
        for conj in conjunctions:
            # 文頭・改行直後でない接続詞の前に読点
            pattern = r'([^、。！？\n])(' + re.escape(conj) + r')'
            result = re.sub(pattern, r'\1、\2', result)

        # 2. 「～て」「～で」の後に文が続く場合、意味的な区切りで読点
        # 長い文（40文字以上）の場合のみ
        result = re.sub(r'([てで])([^、。！？\n]{40,}?)([^、。！？\n]{20,})', r'\1、\2\3', result)

        # 3. 「～が」の後に対比・逆接が続く場合に読点
        # 「～が」の後に長い文（35文字以上）がある場合
        result = re.sub(r'([が])([^、。！？\n]{35,})', r'\1、\2', result)

        # 4. 理由・原因を表す「～ので」「～から」の後に読点
        result = re.sub(r'(ので|から)([^、。！？\n])', r'\1、\2', result)

        # 5. 条件を表す「～たら」「～れば」「～なら」の後に読点
        result = re.sub(r'(たら|れば|なら)([^、。！？\n])', r'\1、\2', result)

        # 6. 列挙の「～たり」の後に読点
        result = re.sub(r'(たり)([^、。！？\n])', r'\1、\2', result)

        # 7. 引用の「～と」の後に読点（思う、言う、聞く等の前）
        quote_verbs = ['思います', '思った', '言います', '言った', '聞きます', '聞いた', '考えます', '考えた']
        for verb in quote_verbs:
            result = re.sub(r'と(' + re.escape(verb) + ')', r'と、\1', result)

        # 8. 長すぎる文を検出して適切な位置に読点を追加
        # 60文字以上句読点がない場合、中間地点で読点を追加
        sentences = result.split('。')
        processed_sentences = []

        for sentence in sentences:
            if len(sentence) > 60 and '、' not in sentence:
                # 文の中間付近で自然な区切り（助詞の後）を探す
                mid_point = len(sentence) // 2
                # 中間地点から前後10文字の範囲で助詞を探す
                search_range = sentence[max(0, mid_point-10):min(len(sentence), mid_point+10)]
                particles = ['て', 'で', 'が', 'を', 'に', 'は', 'も']

                for particle in particles:
                    if particle in search_range:
                        # 助詞の後に読点を追加
                        insert_pos = sentence.find(particle, max(0, mid_point-10))
                        if insert_pos != -1 and insert_pos + 1 < len(sentence):
                            sentence = sentence[:insert_pos+1] + '、' + sentence[insert_pos+1:]
                            break

            processed_sentences.append(sentence)

        result = '。'.join(processed_sentences)

        # 9. 連続する読点を削除
        result = re.sub(r'、{2,}', '、', result)

        # 10. 句点・疑問符・感嘆符の直前の読点を削除
        result = re.sub(r'、([。！？])', r'\1', result)

        # 11. 文末処理
        # 「です」「ます」等の丁寧語の後に句点がない場合
        polite_endings = ['です', 'ます', 'ました', 'でした', 'ません', 'ませんでした',
                         'でしょう', 'ましょう', 'ください', 'くださいました']
        for ending in polite_endings:
            pattern = r'(' + re.escape(ending) + r')([^。！？\n])'
            result = re.sub(pattern, r'\1。\2', result)

        # 12. 文末に何もない場合は句点を追加
        if result and not result.endswith(('。', '！', '？', '…', '\n')):
            result += '。'

        # 13. 句点の後に文字がある場合は改行（見やすさのため）
        result = re.sub(r'。([^\s\n])', r'。\n\1', result)

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
