"""
話者分離モジュール
pyannote.audioを使用した話者識別
"""

import torch
from pyannote.audio import Pipeline
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SpeakerDiarizer:
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

    def format_with_speakers(self, transcription_text: str,
                           diarization_segments: List[Dict],
                           transcription_segments: Optional[List[Dict]] = None) -> str:
        """
        文字起こしテキストに話者情報を追加

        Args:
            transcription_text: 文字起こしテキスト
            diarization_segments: 話者分離結果
            transcription_segments: 文字起こしセグメント（タイムスタンプ付き）

        Returns:
            話者情報が付加されたテキスト
        """
        if not transcription_segments:
            # タイムスタンプ情報がない場合はシンプルな形式
            result = []
            current_speaker = None

            for seg in diarization_segments:
                speaker = seg["speaker"]
                if speaker != current_speaker:
                    result.append(f"\n[{speaker}]")
                    current_speaker = speaker

            # 文字起こしテキストを追加
            if result:
                result.append(transcription_text)
                return "\n".join(result)
            else:
                return transcription_text

        # タイムスタンプ情報がある場合は詳細な形式
        result = []
        current_speaker = None

        for trans_seg in transcription_segments:
            trans_start = trans_seg.get("start", 0)
            trans_end = trans_seg.get("end", 0)
            trans_text = trans_seg.get("text", "")

            # この文字起こしセグメントに対応する話者を探す
            for diar_seg in diarization_segments:
                diar_start = diar_seg["start"]
                diar_end = diar_seg["end"]
                speaker = diar_seg["speaker"]

                # タイムスタンプが重複している場合
                if (trans_start >= diar_start and trans_start < diar_end) or \
                   (trans_end > diar_start and trans_end <= diar_end) or \
                   (trans_start <= diar_start and trans_end >= diar_end):

                    if speaker != current_speaker:
                        result.append(f"\n[{speaker}] ({trans_start:.1f}秒 - {trans_end:.1f}秒)")
                        current_speaker = speaker

                    result.append(trans_text)
                    break

        return "\n".join(result)

    def get_speaker_statistics(self, diarization_segments: List[Dict]) -> Dict[str, float]:
        """
        話者ごとの統計情報を取得

        Args:
            diarization_segments: 話者分離結果

        Returns:
            話者ごとの発話時間（秒）
        """
        stats = {}
        for seg in diarization_segments:
            speaker = seg["speaker"]
            duration = seg["end"] - seg["start"]

            if speaker in stats:
                stats[speaker] += duration
            else:
                stats[speaker] = duration

        return stats

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
