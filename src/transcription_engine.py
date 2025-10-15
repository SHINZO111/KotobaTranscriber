"""
KotobaTranscriber - 文字起こしエンジン
kotoba-whisper v2.2を使用した日本語音声文字起こし
"""

import os
import torch
from transformers import pipeline
from typing import Optional, Dict, Any
import logging

# ffmpegのパスを環境変数に追加
ffmpeg_path = r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
if os.path.exists(ffmpeg_path) and ffmpeg_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger(__name__)


class TranscriptionEngine:
    """kotoba-whisper v2.2を使用した文字起こしエンジン"""

    def __init__(self, model_name: str = "kotoba-tech/kotoba-whisper-v2.2"):
        """
        初期化

        Args:
            model_name: 使用するモデル名（デフォルト: kotoba-whisper v2.2）
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipe = None
        logger.info(f"TranscriptionEngine initialized with device: {self.device}")

    def load_model(self):
        """モデルをロード"""
        try:
            logger.info(f"Loading model: {self.model_name}")
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=0 if self.device == "cuda" else -1,
                trust_remote_code=True
            )
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def transcribe(
        self,
        audio_path: str,
        chunk_length_s: int = 15,
        add_punctuation: bool = True,
        return_timestamps: bool = True
    ) -> Dict[str, Any]:
        """
        音声ファイルを文字起こし

        Args:
            audio_path: 音声ファイルのパス
            chunk_length_s: チャンク長（秒）
            add_punctuation: 句読点を追加するか
            return_timestamps: タイムスタンプを返すか

        Returns:
            文字起こし結果（text, timestamps等を含む辞書）
        """
        if self.pipe is None:
            self.load_model()

        try:
            logger.info(f"Transcribing audio: {audio_path}")
            result = self.pipe(
                audio_path,
                chunk_length_s=chunk_length_s,
                return_timestamps=return_timestamps,
                generate_kwargs={
                    "language": "ja",
                    "task": "transcribe"
                }
            )
            logger.info("Transcription completed successfully")
            return result
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise

    def is_available(self) -> bool:
        """エンジンが利用可能かチェック"""
        return self.pipe is not None or torch.cuda.is_available()


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    engine = TranscriptionEngine()
    print(f"Device: {engine.device}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    # モデルロードテスト
    try:
        engine.load_model()
        print("Model loaded successfully!")
    except Exception as e:
        print(f"Failed to load model: {e}")
