"""
KotobaTranscriber - 文字起こしエンジン
kotoba-whisper v2.2を使用した日本語音声文字起こし
"""

import os
import torch
from transformers import pipeline
from typing import Optional, Dict, Any
import logging
from pathlib import Path
from validators import Validator, ValidationError
from config_manager import get_config

# 設定マネージャーを初期化
config = get_config()

# ffmpegのパスを環境変数に追加（設定ファイルから取得）
ffmpeg_path = config.get("audio.ffmpeg.path", default=r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin")
auto_configure = config.get("audio.ffmpeg.auto_configure", default=True)

if auto_configure and os.path.exists(ffmpeg_path) and ffmpeg_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

logger = logging.getLogger(__name__)


class TranscriptionEngine:
    """kotoba-whisper v2.2を使用した文字起こしエンジン"""

    def __init__(self, model_name: Optional[str] = None):
        """
        初期化

        Args:
            model_name: 使用するモデル名（Noneの場合は設定ファイルから取得）

        Raises:
            ValidationError: モデル名が不正な場合
        """
        # モデル名を設定ファイルから取得（引数が指定されていない場合）
        if model_name is None:
            model_name = config.get("model.whisper.name", default="kotoba-tech/kotoba-whisper-v2.2")

        # モデル名を検証
        try:
            self.model_name = Validator.validate_model_name(model_name, model_type="whisper")
        except ValidationError as e:
            logger.error(f"Invalid model name: {model_name} - {e}")
            # デフォルト値にフォールバック
            default_model = config.get("model.whisper.name", default="kotoba-tech/kotoba-whisper-v2.2")
            logger.warning(f"Falling back to default model: {default_model}")
            self.model_name = default_model

        # デバイス設定を取得
        device_config = config.get("model.whisper.device", default="auto")
        if device_config == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device_config

        self.pipe = None
        logger.info(f"TranscriptionEngine initialized with device: {self.device}, model: {self.model_name}")

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
        chunk_length_s: Optional[int] = None,
        add_punctuation: Optional[bool] = None,
        return_timestamps: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        音声ファイルを文字起こし

        Args:
            audio_path: 音声ファイルのパス
            chunk_length_s: チャンク長（秒、Noneの場合は設定ファイルから取得）
            add_punctuation: 句読点を追加するか（現在未使用）
            return_timestamps: タイムスタンプを返すか（Noneの場合は設定ファイルから取得）

        Returns:
            文字起こし結果（text, timestamps等を含む辞書）

        Raises:
            ValidationError: 入力パラメータが不正な場合
            Exception: 文字起こし処理失敗時
        """
        # 設定ファイルからデフォルト値を取得
        if chunk_length_s is None:
            chunk_length_s = config.get("model.whisper.chunk_length_s", default=15)
        if return_timestamps is None:
            return_timestamps = config.get("model.whisper.return_timestamps", default=True)

        # ファイルパスを検証
        try:
            validated_path = Validator.validate_file_path(
                audio_path,
                allowed_extensions=None,  # 全サポート形式を許可
                must_exist=True
            )
            logger.debug(f"File path validated: {validated_path}")
        except ValidationError as e:
            logger.error(f"File validation failed: {e}")
            raise

        # チャンク長を検証
        try:
            chunk_length_s = Validator.validate_chunk_length(chunk_length_s)
        except ValidationError as e:
            logger.error(f"Chunk length validation failed: {e}")
            raise

        if self.pipe is None:
            self.load_model()

        try:
            logger.info(f"Transcribing audio: {validated_path}")
            # 設定ファイルから言語とタスクを取得
            language = config.get("model.whisper.language", default="ja")
            task = config.get("model.whisper.task", default="transcribe")

            result = self.pipe(
                str(validated_path),  # Pathオブジェクトを文字列に変換
                chunk_length_s=chunk_length_s,
                return_timestamps=return_timestamps,
                generate_kwargs={
                    "language": language,
                    "task": task
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
