"""
話者分離ユーティリティ
SpeakerDiarizer と FreeSpeakerDiarizer の共通機能
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SpeakerFormatterMixin:
    """
    話者情報フォーマット機能を提供するミックスイン

    format_with_speakers と get_speaker_statistics は
    両方の話者分離クラスで完全に同一なのでミックスインとして抽出
    """

    def format_with_speakers(self,
                            transcription_text: str,
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
            return self._format_simple(transcription_text, diarization_segments)

        # タイムスタンプ情報がある場合は詳細な形式
        return self._format_detailed(diarization_segments, transcription_segments)

    def _format_simple(self, transcription_text: str, diarization_segments: List[Dict]) -> str:
        """シンプルなフォーマット（タイムスタンプなし）"""
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

    def _format_detailed(self, diarization_segments: List[Dict],
                        transcription_segments: List[Dict]) -> str:
        """詳細なフォーマット（タイムスタンプあり）"""
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
                if self._is_overlapping(trans_start, trans_end, diar_start, diar_end):
                    if speaker != current_speaker:
                        result.append(f"\n[{speaker}] ({trans_start:.1f}秒 - {trans_end:.1f}秒)")
                        current_speaker = speaker

                    result.append(trans_text)
                    break

        return "\n".join(result)

    def _is_overlapping(self, trans_start: float, trans_end: float,
                       diar_start: float, diar_end: float) -> bool:
        """
        タイムスタンプの重複判定

        Args:
            trans_start: 文字起こしセグメント開始時刻
            trans_end: 文字起こしセグメント終了時刻
            diar_start: 話者分離セグメント開始時刻
            diar_end: 話者分離セグメント終了時刻

        Returns:
            重複していればTrue
        """
        return ((trans_start >= diar_start and trans_start < diar_end) or
                (trans_end > diar_start and trans_end <= diar_end) or
                (trans_start <= diar_start and trans_end >= diar_end))

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


class ClusteringMixin:
    """
    話者クラスタリング機能を提供するミックスイン

    speechbrain と resemblyzer で共通する部分を抽出
    """

    def _perform_clustering(self, embeddings, num_speakers: Optional[int]) -> list:
        """
        K-meansクラスタリングを実行

        Args:
            embeddings: 話者埋め込みベクトル
            num_speakers: 話者数（Noneの場合は自動推定）

        Returns:
            クラスタラベルのリスト
        """
        from sklearn.cluster import KMeans

        if num_speakers is None:
            # 話者数を自動推定（エルボー法の簡易版）
            num_speakers = min(max(2, len(embeddings) // 20), 5)

        kmeans = KMeans(n_clusters=num_speakers, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        return labels

    def _merge_consecutive_segments(self, labels: list, timestamps: list) -> List[Dict]:
        """
        連続する同一話者のセグメントを結合

        Args:
            labels: クラスタラベル
            timestamps: タイムスタンプのリスト [(start, end), ...]

        Returns:
            話者セグメントのリスト
        """
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

        return segments


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("SpeakerFormatterMixin and ClusteringMixin loaded successfully")
    print("\nUsage example:")
    print("  class MySpeakerDiarizer(SpeakerFormatterMixin):")
    print("      def diarize(self, audio_path):")
    print("          # 話者分離処理")
    print("          segments = [...]")
    print("          return segments")
    print("")
    print("  diarizer = MySpeakerDiarizer()")
    print("  formatted = diarizer.format_with_speakers(text, segments)")
    print("  stats = diarizer.get_speaker_statistics(segments)")
