"""
完全無料の話者分離モジュール
speechbrainを使用したトークン不要の話者分離
"""

import logging
from typing import List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)

# オプショナルインポート
try:
    import torch
    import torchaudio
    from speechbrain.pretrained import SpeakerRecognition
    SPEECHBRAIN_AVAILABLE = True
except ImportError:
    SPEECHBRAIN_AVAILABLE = False
    logger.warning("speechbrain not available")

try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    from pathlib import Path
    RESEMBLYZER_AVAILABLE = True
except ImportError:
    RESEMBLYZER_AVAILABLE = False
    logger.warning("resemblyzer not available")


class FreeSpeakerDiarizer:
    """完全無料の話者分離クラス（speechbrain使用）"""

    def __init__(self, method: str = "auto"):
        """
        初期化

        Args:
            method: 使用する方法
                   - "auto": 利用可能な方法を自動選択
                   - "speechbrain": speechbrainを使用
                   - "resemblyzer": resemblyzerを使用
        """
        self.method = method
        self.encoder = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu" if SPEECHBRAIN_AVAILABLE else "cpu"

        logger.info(f"FreeSpeakerDiarizer initialized with method: {method}, device: {self.device}")

    def load_model(self):
        """モデルをロード"""
        if self.encoder is not None:
            return

        try:
            # 自動選択
            if self.method == "auto":
                if SPEECHBRAIN_AVAILABLE:
                    self.method = "speechbrain"
                elif RESEMBLYZER_AVAILABLE:
                    self.method = "resemblyzer"
                else:
                    raise ImportError("No diarization library available")

            # speechbrainを使用
            if self.method == "speechbrain":
                if not SPEECHBRAIN_AVAILABLE:
                    raise ImportError("speechbrain not installed")

                logger.info("Loading speechbrain model...")
                self.encoder = SpeakerRecognition.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceleb",
                    savedir="models/speechbrain_speaker",
                    run_opts={"device": self.device},
                    use_symlinks=False  # シンボリックリンクを使用しない
                )
                logger.info("speechbrain model loaded")

            # resemblyzerを使用
            elif self.method == "resemblyzer":
                if not RESEMBLYZER_AVAILABLE:
                    raise ImportError("resemblyzer not installed")

                logger.info("Loading resemblyzer model...")
                self.encoder = VoiceEncoder()
                logger.info("resemblyzer model loaded")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def is_available(self) -> bool:
        """話者分離が利用可能かチェック"""
        return self.encoder is not None or SPEECHBRAIN_AVAILABLE or RESEMBLYZER_AVAILABLE

    def diarize(self, audio_path: str, num_speakers: Optional[int] = None) -> List[Dict]:
        """
        話者分離を実行

        Args:
            audio_path: 音声ファイルのパス
            num_speakers: 話者数（Noneの場合は自動推定）

        Returns:
            話者情報のリスト
            [{"speaker": "SPEAKER_00", "start": 0.5, "end": 2.3}, ...]
        """
        if self.encoder is None:
            self.load_model()

        try:
            logger.info(f"Running speaker diarization on: {audio_path}")

            if self.method == "speechbrain":
                return self._diarize_speechbrain(audio_path, num_speakers)
            elif self.method == "resemblyzer":
                return self._diarize_resemblyzer(audio_path, num_speakers)

        except Exception as e:
            logger.error(f"Speaker diarization failed: {e}")
            raise

    def _diarize_speechbrain(self, audio_path: str, num_speakers: Optional[int]) -> List[Dict]:
        """speechbrainを使用した話者分離"""
        # 音声を読み込み
        waveform, sample_rate = torchaudio.load(audio_path)

        # モノラルに変換
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # セグメント長（秒）
        segment_length = 3.0
        segment_samples = int(segment_length * sample_rate)

        # オーバーラップ
        hop_length = segment_samples // 2

        # セグメントごとに埋め込みを取得
        embeddings = []
        timestamps = []

        for start_sample in range(0, waveform.shape[1] - segment_samples, hop_length):
            end_sample = start_sample + segment_samples
            segment = waveform[:, start_sample:end_sample]

            # 埋め込みを取得
            with torch.no_grad():
                embedding = self.encoder.encode_batch(segment.to(self.device))
                embeddings.append(embedding.cpu().numpy().flatten())

            start_time = start_sample / sample_rate
            end_time = end_sample / sample_rate
            timestamps.append((start_time, end_time))

        embeddings = np.array(embeddings)

        # クラスタリング（K-means）
        from sklearn.cluster import KMeans

        if num_speakers is None:
            # 話者数を自動推定（エルボー法の簡易版）
            num_speakers = min(max(2, len(embeddings) // 20), 5)

        kmeans = KMeans(n_clusters=num_speakers, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        # 結果を整形
        segments = []
        current_speaker = None
        current_start = None

        for i, (label, (start, end)) in enumerate(zip(labels, timestamps)):
            speaker = f"SPEAKER_{label:02d}"

            # 同じ話者が連続している場合は結合
            if speaker == current_speaker:
                continue
            else:
                # 前のセグメントを保存
                if current_speaker is not None:
                    segments.append({
                        "speaker": current_speaker,
                        "start": current_start,
                        "end": start
                    })

                current_speaker = speaker
                current_start = start

        # 最後のセグメント
        if current_speaker is not None:
            segments.append({
                "speaker": current_speaker,
                "start": current_start,
                "end": timestamps[-1][1]
            })

        logger.info(f"Found {num_speakers} speakers")
        return segments

    def _diarize_resemblyzer(self, audio_path: str, num_speakers: Optional[int]) -> List[Dict]:
        """resemblyzerを使用した話者分離"""
        from scipy.io import wavfile

        # 音声を読み込み
        wav = preprocess_wav(Path(audio_path))

        # セグメント長
        segment_length = int(16000 * 3.0)  # 3秒
        hop_length = segment_length // 2

        # セグメントごとに埋め込みを取得
        embeddings = []
        timestamps = []

        for start_sample in range(0, len(wav) - segment_length, hop_length):
            end_sample = start_sample + segment_length
            segment = wav[start_sample:end_sample]

            embedding = self.encoder.embed_utterance(segment)
            embeddings.append(embedding)

            start_time = start_sample / 16000
            end_time = end_sample / 16000
            timestamps.append((start_time, end_time))

        embeddings = np.array(embeddings)

        # クラスタリング
        from sklearn.cluster import KMeans

        if num_speakers is None:
            num_speakers = min(max(2, len(embeddings) // 20), 5)

        kmeans = KMeans(n_clusters=num_speakers, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        # 結果を整形
        segments = []
        current_speaker = None
        current_start = None

        for i, (label, (start, end)) in enumerate(zip(labels, timestamps)):
            speaker = f"SPEAKER_{label:02d}"

            if speaker == current_speaker:
                continue
            else:
                if current_speaker is not None:
                    segments.append({
                        "speaker": current_speaker,
                        "start": current_start,
                        "end": start
                    })

                current_speaker = speaker
                current_start = start

        if current_speaker is not None:
            segments.append({
                "speaker": current_speaker,
                "start": current_start,
                "end": timestamps[-1][1]
            })

        return segments

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
            # シンプルな形式
            result = []
            for seg in diarization_segments:
                speaker = seg["speaker"]
                result.append(f"\n[{speaker}] ({seg['start']:.1f}秒 - {seg['end']:.1f}秒)")

            result.append("\n" + transcription_text)
            return "\n".join(result)

        # 詳細な形式
        result = []
        current_speaker = None

        for trans_seg in transcription_segments:
            trans_start = trans_seg.get("start", 0)
            trans_end = trans_seg.get("end", 0)
            trans_text = trans_seg.get("text", "")

            for diar_seg in diarization_segments:
                diar_start = diar_seg["start"]
                diar_end = diar_seg["end"]
                speaker = diar_seg["speaker"]

                if (trans_start >= diar_start and trans_start < diar_end) or \
                   (trans_end > diar_start and trans_end <= diar_end):

                    if speaker != current_speaker:
                        result.append(f"\n[{speaker}] ({trans_start:.1f}秒 - {trans_end:.1f}秒)")
                        current_speaker = speaker

                    result.append(trans_text)
                    break

        return "\n".join(result)

    def get_speaker_statistics(self, diarization_segments: List[Dict]) -> Dict[str, float]:
        """話者ごとの統計情報を取得"""
        stats = {}
        for seg in diarization_segments:
            speaker = seg["speaker"]
            duration = seg["end"] - seg["start"]

            if speaker in stats:
                stats[speaker] += duration
            else:
                stats[speaker] = duration

        return stats


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== FreeSpeakerDiarizer Test ===\n")

    diarizer = FreeSpeakerDiarizer()

    if SPEECHBRAIN_AVAILABLE:
        print("✓ speechbrain is available (完全無料)")
    else:
        print("✗ speechbrain not installed")
        print("  インストール: pip install speechbrain")

    if RESEMBLYZER_AVAILABLE:
        print("✓ resemblyzer is available (完全無料)")
    else:
        print("✗ resemblyzer not installed")
        print("  インストール: pip install resemblyzer")

    print("\n推奨: speechbrain (より高精度)")
    print("  pip install speechbrain")
    print("\n軽量版: resemblyzer (軽量・高速)")
    print("  pip install resemblyzer")
