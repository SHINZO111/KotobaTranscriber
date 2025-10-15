"""
faster-whisperエンジン
高速なリアルタイム文字起こしエンジン
"""

import logging
import numpy as np
from typing import Optional, Dict, List, Any
import time

logger = logging.getLogger(__name__)

# faster-whisper のインポート（オプショナル）
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available, install with: pip install faster-whisper")


class FasterWhisperEngine:
    """faster-whisperベースのリアルタイム文字起こしエンジン"""

    def __init__(self,
                 model_size: str = "base",
                 device: str = "auto",
                 compute_type: str = "auto",
                 language: str = "ja"):
        """
        初期化

        Args:
            model_size: モデルサイズ ("tiny", "base", "small", "medium", "large-v2", "large-v3")
            device: 実行デバイス ("cpu", "cuda", "auto")
            compute_type: 計算精度 ("int8", "float16", "float32", "auto")
            language: 言語コード
        """
        self.model_size = model_size
        self.language = language
        self.model: Optional[WhisperModel] = None
        self.is_loaded = False

        # デバイス自動選択
        if device == "auto":
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
        else:
            self.device = device

        # 計算精度の自動選択
        if compute_type == "auto":
            if self.device == "cuda":
                self.compute_type = "float16"  # GPUの場合はfloat16
            else:
                self.compute_type = "int8"  # CPUの場合はint8で高速化
        else:
            self.compute_type = compute_type

        logger.info(f"FasterWhisperEngine initialized: model={model_size}, "
                   f"device={self.device}, compute_type={self.compute_type}")

    def load_model(self) -> bool:
        """モデルをロード"""
        if self.is_loaded:
            logger.info("Model already loaded")
            return True

        if not FASTER_WHISPER_AVAILABLE:
            logger.error("faster-whisper is not installed")
            return False

        try:
            logger.info(f"Loading faster-whisper model: {self.model_size}...")
            start_time = time.time()

            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )

            load_time = time.time() - start_time
            self.is_loaded = True

            logger.info(f"Model loaded successfully in {load_time:.2f}s")
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def transcribe(self,
                   audio: np.ndarray,
                   sample_rate: int = 16000,
                   beam_size: int = 5,
                   best_of: int = 5,
                   temperature: float = 0.0,
                   vad_filter: bool = True,
                   vad_parameters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        音声を文字起こし

        Args:
            audio: 音声データ（NumPy配列、float32、-1.0〜1.0）
            sample_rate: サンプリングレート
            beam_size: ビームサーチのサイズ
            best_of: 候補数
            temperature: サンプリング温度
            vad_filter: VADフィルタ有効化
            vad_parameters: VADパラメータ

        Returns:
            {
                "text": str,
                "segments": List[Dict],
                "language": str,
                "duration": float
            }
        """
        if not self.is_loaded:
            logger.warning("Model not loaded, loading now...")
            if not self.load_model():
                return {
                    "text": "",
                    "segments": [],
                    "language": self.language,
                    "duration": 0.0,
                    "error": "Model loading failed"
                }

        try:
            start_time = time.time()

            # faster-whisperは直接NumPy配列を受け取る
            segments, info = self.model.transcribe(
                audio,
                language=self.language,
                beam_size=beam_size,
                best_of=best_of,
                temperature=temperature,
                vad_filter=vad_filter,
                vad_parameters=vad_parameters or {
                    "threshold": 0.5,
                    "min_speech_duration_ms": 250,
                    "min_silence_duration_ms": 1000
                }
            )

            # セグメントを収集
            result_segments = []
            full_text = []

            for segment in segments:
                result_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "avg_logprob": segment.avg_logprob,
                    "no_speech_prob": segment.no_speech_prob
                })
                full_text.append(segment.text.strip())

            processing_time = time.time() - start_time
            audio_duration = len(audio) / sample_rate

            result = {
                "text": " ".join(full_text),
                "segments": result_segments,
                "language": info.language,
                "duration": audio_duration,
                "processing_time": processing_time,
                "realtime_factor": processing_time / audio_duration if audio_duration > 0 else 0
            }

            logger.info(f"Transcription completed: {audio_duration:.2f}s audio in {processing_time:.2f}s "
                       f"(RTF: {result['realtime_factor']:.2f}x)")

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "text": "",
                "segments": [],
                "language": self.language,
                "duration": 0.0,
                "error": str(e)
            }

    def transcribe_stream(self,
                         audio_chunk: np.ndarray,
                         sample_rate: int = 16000) -> Optional[str]:
        """
        音声チャンクを文字起こし（ストリーミング用・簡易版）

        Args:
            audio_chunk: 音声データ
            sample_rate: サンプリングレート

        Returns:
            文字起こし結果のテキスト（Noneの場合はエラー）
        """
        result = self.transcribe(
            audio_chunk,
            sample_rate=sample_rate,
            beam_size=1,  # 高速化のためビームサイズを小さく
            vad_filter=False  # 外部VADを使用するため無効化
        )

        if "error" in result:
            return None

        return result["text"]

    def is_available(self) -> bool:
        """エンジンが利用可能かチェック"""
        return FASTER_WHISPER_AVAILABLE and self.is_loaded

    def get_model_info(self) -> Dict[str, Any]:
        """モデル情報を取得"""
        return {
            "available": FASTER_WHISPER_AVAILABLE,
            "loaded": self.is_loaded,
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "language": self.language
        }

    def unload_model(self):
        """モデルをアンロード（メモリ解放）"""
        if self.model is not None:
            del self.model
            self.model = None
            self.is_loaded = False
            logger.info("Model unloaded")


# フォールバック用：transformers版
class TransformersWhisperEngine:
    """transformersベースのWhisperエンジン（フォールバック用）"""

    def __init__(self,
                 model_name: str = "kotoba-tech/kotoba-whisper-v2.2",
                 device: str = "auto"):
        """
        初期化

        Args:
            model_name: モデル名
            device: デバイス
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.processor = None
        self.is_loaded = False

        logger.info(f"TransformersWhisperEngine initialized: model={model_name}")

    def load_model(self) -> bool:
        """モデルをロード"""
        if self.is_loaded:
            return True

        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
            import torch

            logger.info(f"Loading transformers model: {self.model_name}...")

            # デバイス選択
            if self.device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device

            # モデルロード
            self.processor = AutoProcessor.from_pretrained(self.model_name)
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32
            )
            self.model.to(device)

            self.is_loaded = True
            logger.info("Transformers model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load transformers model: {e}")
            return False

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """音声を文字起こし"""
        if not self.is_loaded:
            if not self.load_model():
                return {"text": "", "error": "Model loading failed"}

        try:
            import torch

            # 前処理
            inputs = self.processor(
                audio,
                sampling_rate=sample_rate,
                return_tensors="pt"
            )

            # 推論
            with torch.no_grad():
                generated_ids = self.model.generate(**inputs)

            # デコード
            transcription = self.processor.batch_decode(
                generated_ids,
                skip_special_tokens=True
            )[0]

            return {
                "text": transcription,
                "segments": [],
                "language": "ja"
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {"text": "", "error": str(e)}

    def is_available(self) -> bool:
        """エンジンが利用可能かチェック"""
        return self.is_loaded


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # faster-whisperの利用可能性チェック
    print(f"\nfaster-whisper available: {FASTER_WHISPER_AVAILABLE}")

    if FASTER_WHISPER_AVAILABLE:
        # faster-whisperテスト
        print("\n=== FasterWhisperEngine Test ===")
        engine = FasterWhisperEngine(model_size="base", device="auto")

        print(f"Model info: {engine.get_model_info()}")

        # テスト用音声データ（5秒の無音）
        test_audio = np.zeros(16000 * 5, dtype=np.float32)

        print("\nLoading model...")
        if engine.load_model():
            print("Model loaded successfully")

            print("\nTranscribing test audio...")
            result = engine.transcribe(test_audio)

            print(f"Result: {result}")
            print(f"Text: {result['text']}")
            print(f"RTF: {result.get('realtime_factor', 0):.2f}x")

            engine.unload_model()
        else:
            print("Failed to load model")

    else:
        print("\nfaster-whisper not available")
        print("Install with: pip install faster-whisper")

    print("\nテスト完了")
