"""
話者分離モジュール
pyannote.audioを使用した話者識別
"""

import torch
from pyannote.audio import Pipeline
from typing import Dict, List, Optional
import logging
from speaker_diarization_utils import SpeakerFormatterMixin

logger = logging.getLogger(__name__)


class SpeakerDiarizer(SpeakerFormatterMixin):
    """話者分離クラス"""

    def __init__(self, use_auth_token: Optional[str] = None):
        """
        初期化

        Args:
            use_auth_token: Hugging Face認証トークン（pyannote/speaker-diarizationモデル使用時に必要）
        """
        self.use_auth_token = use_auth_token
        self.pipeline = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"SpeakerDiarizer initialized with device: {self.device}")

    def load_model(self):
        """話者分離モデルをロード"""
        try:
            logger.info("Loading speaker diarization model...")
            # pyannoteの事前学習済みモデルを使用
            # 注意: このモデルを使用するにはHugging Faceのアクセストークンが必要
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.use_auth_token
            )

            # GPUがあれば使用
            if self.device == "cuda":
                self.pipeline.to(torch.device("cuda"))

            logger.info("Speaker diarization model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load speaker diarization model: {e}")
            raise

    def diarize(self, audio_path: str, num_speakers: Optional[int] = None) -> List[Dict]:
        """
        話者分離を実行

        Args:
            audio_path: 音声ファイルのパス
            num_speakers: 話者数（None の場合は自動推定）

        Returns:
            話者情報のリスト
            [{"speaker": "SPEAKER_00", "start": 0.5, "end": 2.3}, ...]
        """
        if self.pipeline is None:
            self.load_model()

        try:
            logger.info(f"Running speaker diarization on: {audio_path}")

            # 話者分離実行
            if num_speakers:
                diarization = self.pipeline(audio_path, num_speakers=num_speakers)
            else:
                diarization = self.pipeline(audio_path)

            # 結果を整形
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    "speaker": speaker,
                    "start": turn.start,
                    "end": turn.end
                })

            logger.info(f"Found {len(set([s['speaker'] for s in segments]))} speakers")
            return segments

        except Exception as e:
            logger.error(f"Speaker diarization failed: {e}")
            raise

    # format_with_speakers と get_speaker_statistics は
    # SpeakerFormatterMixin から継承

    def is_available(self) -> bool:
        """話者分離が利用可能かチェック"""
        return self.pipeline is not None


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # 注意: 実際に使用するには Hugging Face のトークンが必要
    # https://huggingface.co/pyannote/speaker-diarization-3.1 でアクセスリクエスト

    print("SpeakerDiarizer module loaded")
    print("To use this module, you need to:")
    print("1. Create a Hugging Face account")
    print("2. Accept the user agreement for pyannote/speaker-diarization-3.1")
    print("3. Get your Hugging Face access token")
    print("4. Pass the token to SpeakerDiarizer(use_auth_token='your_token')")
