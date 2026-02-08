"""
話者分離ユーティリティ - Speaker Diarization Utilities

話者分離モジュールで共通使用されるMixinクラス。
クラスタリングと結果フォーマットの機能を提供。
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

__all__ = ['SpeakerFormatterMixin', 'ClusteringMixin']


class ClusteringMixin:
    """クラスタリング機能を提供するMixin"""

    def _perform_clustering(
        self,
        embeddings: np.ndarray,
        num_speakers: Optional[int] = None
    ) -> np.ndarray:
        """
        埋め込みベクトルをクラスタリングして話者ラベルを割り当て

        Args:
            embeddings: 話者埋め込みの配列 (N, D)
            num_speakers: 話者数（Noneの場合は自動推定）

        Returns:
            各セグメントの話者ラベル配列
        """
        try:
            from sklearn.cluster import AgglomerativeClustering, KMeans

            if len(embeddings) == 0:
                return np.array([])

            if num_speakers is not None and num_speakers > 0:
                n_clusters = min(num_speakers, len(embeddings))
            else:
                # 自動推定: シルエットスコアで最適なクラスタ数を決定
                n_clusters = self._estimate_num_speakers(embeddings)

            clustering = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric='cosine',
                linkage='average'
            )
            labels = clustering.fit_predict(embeddings)

            logger.info(f"Clustering complete: {n_clusters} speakers detected")
            return labels

        except ImportError:
            logger.warning("scikit-learn not available, falling back to simple clustering")
            return self._simple_clustering(embeddings, num_speakers or 2)

    def _estimate_num_speakers(self, embeddings: np.ndarray, max_speakers: int = 10) -> int:
        """
        シルエットスコアで最適な話者数を推定

        Args:
            embeddings: 話者埋め込み
            max_speakers: 最大話者数

        Returns:
            推定話者数
        """
        try:
            from sklearn.cluster import AgglomerativeClustering
            from sklearn.metrics import silhouette_score

            max_k = min(max_speakers, len(embeddings) - 1)
            if max_k < 2:
                return 1

            best_score = -1
            best_k = 2

            for k in range(2, max_k + 1):
                clustering = AgglomerativeClustering(
                    n_clusters=k,
                    metric='cosine',
                    linkage='average'
                )
                labels = clustering.fit_predict(embeddings)
                score = silhouette_score(embeddings, labels, metric='cosine')

                if score > best_score:
                    best_score = score
                    best_k = k

            logger.info(f"Estimated {best_k} speakers (silhouette score: {best_score:.3f})")
            return best_k

        except (ImportError, ValueError, np.linalg.LinAlgError) as e:
            logger.warning(f"Speaker estimation failed: {e}, defaulting to 2")
            return 2

    def _simple_clustering(self, embeddings: np.ndarray, num_speakers: int) -> np.ndarray:
        """
        シンプルなk-meansクラスタリング（フォールバック用）

        Args:
            embeddings: 話者埋め込み
            num_speakers: 話者数

        Returns:
            話者ラベル配列
        """
        n_clusters = min(num_speakers, len(embeddings))

        # 正規化
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized = embeddings / norms

        # シンプルなk-means
        centroids = normalized[:n_clusters].copy()
        labels = np.zeros(len(normalized), dtype=int)

        for _ in range(20):
            # 割り当て
            for i, emb in enumerate(normalized):
                distances = [np.linalg.norm(emb - c) for c in centroids]
                labels[i] = np.argmin(distances)

            # 更新（セントロイドを正規化して単位球面上に保つ）
            for k in range(n_clusters):
                mask = labels == k
                if mask.any():
                    centroid = normalized[mask].mean(axis=0)
                    norm = np.linalg.norm(centroid)
                    if norm > 0:
                        centroid = centroid / norm
                    centroids[k] = centroid

        return labels

    def _merge_consecutive_segments(
        self,
        labels: np.ndarray,
        timestamps: List[Tuple[float, float]]
    ) -> List[Dict]:
        """
        連続する同一話者のセグメントをマージ

        Args:
            labels: 話者ラベル配列
            timestamps: (start, end) のタイムスタンプリスト

        Returns:
            マージ済み話者セグメントリスト
        """
        if len(labels) == 0:
            return []

        if len(labels) != len(timestamps):
            raise ValueError(
                f"labels and timestamps length mismatch: {len(labels)} != {len(timestamps)}"
            )

        segments = []
        current_speaker = labels[0]
        current_start = timestamps[0][0]
        current_end = timestamps[0][1]

        for i in range(1, len(labels)):
            if labels[i] == current_speaker:
                current_end = timestamps[i][1]
            else:
                segments.append({
                    "speaker": f"SPEAKER_{current_speaker:02d}",
                    "start": round(current_start, 2),
                    "end": round(current_end, 2)
                })
                current_speaker = labels[i]
                current_start = timestamps[i][0]
                current_end = timestamps[i][1]

        # 最後のセグメント
        segments.append({
            "speaker": f"SPEAKER_{current_speaker:02d}",
            "start": round(current_start, 2),
            "end": round(current_end, 2)
        })

        return segments


class SpeakerFormatterMixin:
    """話者情報のフォーマット機能を提供するMixin"""

    def format_with_speakers(
        self,
        text_segments: List[Dict],
        speaker_segments: List[Dict]
    ) -> str:
        """
        文字起こしセグメントに話者情報を付与してフォーマット

        Args:
            text_segments: 文字起こしセグメント [{"start", "end", "text"}, ...]
            speaker_segments: 話者セグメント [{"speaker", "start", "end"}, ...]

        Returns:
            話者情報付きフォーマット済みテキスト
        """
        if not speaker_segments:
            return "\n".join(seg.get("text", "") for seg in text_segments)

        lines = []
        current_speaker = None

        for seg in text_segments:
            start = seg.get("start", 0)
            text = seg.get("text", "").strip()
            if not text:
                continue

            # この時刻の話者を特定
            speaker = self._find_speaker_at_time(start, speaker_segments)

            if speaker != current_speaker:
                if lines:
                    lines.append("")  # 話者変更時に空行
                lines.append(f"[{speaker}]")
                current_speaker = speaker

            lines.append(text)

        return "\n".join(lines)

    def get_speaker_statistics(
        self,
        speaker_segments: List[Dict]
    ) -> Dict[str, Dict]:
        """
        話者ごとの統計情報を取得

        Args:
            speaker_segments: 話者セグメント

        Returns:
            話者ごとの統計 {"SPEAKER_00": {"total_time": float, "segment_count": int}, ...}
        """
        stats = {}

        for seg in speaker_segments:
            speaker = seg.get("speaker", "UNKNOWN")
            duration = seg.get("end", 0) - seg.get("start", 0)

            if speaker not in stats:
                stats[speaker] = {"total_time": 0.0, "segment_count": 0}

            stats[speaker]["total_time"] += duration
            stats[speaker]["segment_count"] += 1

        # パーセンテージ計算
        total_time = sum(s["total_time"] for s in stats.values())
        if total_time > 0:
            for speaker in stats:
                stats[speaker]["percentage"] = round(
                    stats[speaker]["total_time"] / total_time * 100, 1
                )

        return stats

    def _find_speaker_at_time(
        self,
        timestamp: float,
        speaker_segments: List[Dict]
    ) -> str:
        """指定時刻の話者を特定"""
        for seg in speaker_segments:
            if seg.get("start", 0) <= timestamp <= seg.get("end", 0):
                return seg.get("speaker", "UNKNOWN")
        return "UNKNOWN"
