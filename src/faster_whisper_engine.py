"""
faster-whisperエンジン
高速なリアルタイム文字起こしエンジン
"""

import logging
import time
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import numpy.typing as npt

from base_engine import BaseTranscriptionEngine
from exceptions import ModelLoadError, TranscriptionFailedError

logger = logging.getLogger(__name__)

# Type aliases for better type safety
ModelSize = Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"]
ComputeType = Literal["auto", "int8", "int8_float16", "int16", "float16", "float32"]
DeviceType = Literal["auto", "cpu", "cuda"]

# faster-whisper のインポート（オプショナル）
# FileNotFoundError: ctranslate2がDLLディレクトリを参照する際に発生する場合がある
# OSError: 共有ライブラリの読み込みに失敗する場合がある
try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
except (ImportError, OSError, Exception) as e:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning(f"faster-whisper not available: {e}")


class FasterWhisperEngine(BaseTranscriptionEngine):
    """
    faster-whisperベースのリアルタイム文字起こしエンジン

    コンテキストマネージャとして使用可能:
        with FasterWhisperEngine(model_size="base") as engine:
            result = engine.transcribe(audio_data)
            # ... 処理 ...
        # 自動的にモデルがアンロードされる
    """

    def __init__(
        self,
        model_size: ModelSize = "base",
        device: DeviceType = "auto",
        compute_type: ComputeType = "auto",
        language: str = "ja",
    ):
        """
        初期化

        Args:
            model_size: モデルサイズ ("tiny", "base", "small", "medium", "large-v2", "large-v3")
            device: 実行デバイス ("cpu", "cuda", "auto")
            compute_type: 計算精度 ("int8", "float16", "float32", "auto")
            language: 言語コード
        """
        # Note: parent class stores model_size in self.model_name
        # We also keep it as self.model_size for semantic clarity
        super().__init__(model_size, device, language)
        # Re-declare types for mypy (set by super().__init__)
        self.device: str = self.device
        self.is_loaded: bool = self.is_loaded
        self.model_size = model_size  # Explicitly preserved for clarity (parent sets as model_name)
        self.compute_type = self._resolve_compute_type(compute_type)

        logger.info(
            f"FasterWhisperEngine initialized: model={model_size}, " f"device={self.device}, compute_type={self.compute_type}"
        )

    def _resolve_compute_type(self, compute_type: ComputeType) -> str:
        """計算精度を自動選択"""
        if compute_type == "auto":
            if self.device == "cuda":
                return "float16"  # GPUの場合はfloat16
            else:
                return "int8"  # CPUの場合はint8で高速化
        return compute_type

    def load_model(self) -> bool:
        """モデルをロード"""
        if self.is_loaded:
            logger.info("Model already loaded")
            return True

        if not FASTER_WHISPER_AVAILABLE:
            raise ModelLoadError("faster-whisper is not installed")

        try:
            logger.info(f"Loading faster-whisper model: {self.model_size}...")
            start_time = time.time()

            self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)

            load_time = time.time() - start_time
            self.is_loaded = True

            logger.info(f"Model loaded successfully in {load_time:.2f}s")
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ModelLoadError(f"Failed to load model {self.model_size}: {e}") from e

    def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        sample_rate: int = 16000,
        beam_size: int = 5,
        best_of: int = 5,
        temperature: float = 0.0,
        vad_filter: bool = True,
        vad_parameters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
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
            self.load_model()

        # 入力検証
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        if audio.size == 0:
            return {
                "text": "",
                "segments": [],
                "language": self.language,
                "duration": 0.0,
                "processing_time": 0.0,
                "realtime_factor": 0.0,
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
                vad_parameters=vad_parameters
                or {"threshold": 0.5, "min_speech_duration_ms": 250, "min_silence_duration_ms": 1000},
            )

            # セグメントを収集
            result_segments = []
            full_text = []

            for segment in segments:
                result_segments.append(
                    {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip(),
                        "avg_logprob": segment.avg_logprob,
                        "no_speech_prob": segment.no_speech_prob,
                    }
                )
                full_text.append(segment.text.strip())

            processing_time = time.time() - start_time
            audio_duration = len(audio) / sample_rate

            result = {
                "text": " ".join(full_text),
                "segments": result_segments,
                "language": info.language,
                "duration": audio_duration,
                "processing_time": processing_time,
                "realtime_factor": processing_time / audio_duration if audio_duration > 0 else 0,
            }

            logger.info(
                f"Transcription completed: {audio_duration:.2f}s audio in {processing_time:.2f}s "
                f"(RTF: {result['realtime_factor']:.2f}x)"
            )

            return result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            audio_duration = len(audio) / sample_rate if sample_rate > 0 else 0.0
            raise TranscriptionFailedError(str(e), audio_duration)

    def transcribe_stream(self, audio_chunk: npt.NDArray[np.float32], sample_rate: int = 16000) -> Optional[str]:
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
            vad_filter=False,  # 外部VADを使用するため無効化
        )

        if "error" in result:
            return None

        return str(result["text"])

    def is_available(self) -> bool:
        """エンジンが利用可能かチェック"""
        return FASTER_WHISPER_AVAILABLE and self.is_loaded

    def get_model_info(self) -> Dict[str, Any]:
        """モデル情報を取得（compute_type を追加）"""
        info = dict(super().get_model_info())
        info["available"] = FASTER_WHISPER_AVAILABLE
        info["compute_type"] = self.compute_type
        return info

    # unload_model は BaseEngine から継承


# フォールバック用：transformers版
class TransformersWhisperEngine(BaseTranscriptionEngine):
    """
    transformersベースのWhisperエンジン（フォールバック用）

    コンテキストマネージャとして使用可能:
        with TransformersWhisperEngine() as engine:
            result = engine.transcribe(audio_data)
            # ... 処理 ...
        # 自動的にモデルがアンロードされる
    """

    def __init__(self, model_name: str = "kotoba-tech/kotoba-whisper-v2.2", device: str = "auto"):
        """
        初期化

        Args:
            model_name: モデル名
            device: デバイス
        """
        super().__init__(model_name, device, language="ja")
        # Re-declare types for mypy (set by super().__init__)
        self.device: str = self.device
        self.is_loaded: bool = self.is_loaded
        self.processor = None

        logger.info(f"TransformersWhisperEngine initialized: model={model_name}")

    def load_model(self) -> bool:
        """モデルをロード"""
        if self.is_loaded:
            return True

        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

            logger.info(f"Loading transformers model: {self.model_name}...")

            # デバイス選択
            if self.device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device

            # モデルロード
            # Model name is configured in config.yaml; revision pinning not needed
            self.processor = AutoProcessor.from_pretrained(self.model_name)  # nosec B615
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(  # nosec B615
                self.model_name, torch_dtype=torch.float16 if device == "cuda" else torch.float32
            )
            self.model.to(device)

            self.is_loaded = True
            logger.info("Transformers model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load transformers model: {e}", exc_info=True)
            raise ModelLoadError(f"Failed to load transformers model: {e}") from e

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """音声を文字起こし"""
        if not self.is_loaded:
            self.load_model()

        try:
            import torch

            # 前処理
            if self.processor is None:
                raise RuntimeError("processor is not initialized")
            inputs = self.processor(audio, sampling_rate=sample_rate, return_tensors="pt")

            # 推論
            with torch.no_grad():
                if self.model is None:
                    raise RuntimeError("model is not initialized")
                generated_ids = self.model.generate(**inputs)

            # デコード
            transcription = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            return {"text": transcription, "segments": [], "language": "ja"}

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            audio_duration = len(audio) / sample_rate if sample_rate > 0 else 0.0
            raise TranscriptionFailedError(str(e), audio_duration)

    def is_available(self) -> bool:
        """エンジンが利用可能かチェック"""
        return self.is_loaded

    def unload_model(self) -> None:
        """
        モデルをアンロード（メモリ解放）

        プロセッサも含めてクリーンアップ
        """
        # プロセッサを削除
        if self.processor is not None:
            del self.processor
            self.processor = None

        # 基底クラスのunload_modelを呼び出し
        super().unload_model()


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # faster-whisperの利用可能性チェック
    print(f"\nfaster-whisper available: {FASTER_WHISPER_AVAILABLE}")

    if FASTER_WHISPER_AVAILABLE:
        # faster-whisperテスト（コンテキストマネージャを使用）
        print("\n=== FasterWhisperEngine Context Manager Test ===")

        # コンテキストマネージャとして使用
        with FasterWhisperEngine(model_size="base", device="auto") as engine:
            print(f"Model info: {engine.get_model_info()}")

            # テスト用音声データ（5秒の無音）
            test_audio = np.zeros(16000 * 5, dtype=np.float32)

            print("\nTranscribing test audio...")
            result = engine.transcribe(test_audio)

            print(f"Result: {result}")
            print(f"Text: {result['text']}")
            print(f"RTF: {result.get('realtime_factor', 0):.2f}x")

        # with ブロックを抜けると自動的にモデルがアンロードされる
        print("\nモデルは自動的にアンロードされました")

    else:
        print("\nfaster-whisper not available")
        print("Install with: pip install faster-whisper")

    print("\nテスト完了")
