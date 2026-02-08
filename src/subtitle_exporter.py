"""
字幕エクスポートモジュール
SRT/VTT形式の字幕ファイル生成
"""

import html
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from time_utils import format_time_srt, format_time_vtt

logger = logging.getLogger(__name__)


class SubtitleExporter:
    """字幕ファイルエクスポートクラス"""

    def __init__(self):
        """初期化"""
        pass

    @staticmethod
    def format_srt_time(seconds: float) -> str:
        """秒数をSRT時間形式に変換 (HH:MM:SS,mmm)"""
        return format_time_srt(seconds)

    @staticmethod
    def format_vtt_time(seconds: float) -> str:
        """秒数をVTT時間形式に変換 (HH:MM:SS.mmm)"""
        return format_time_vtt(seconds)

    def export_srt(self,
                   segments: List[Dict[str, Any]],
                   output_path: str,
                   speaker_segments: Optional[List[Dict]] = None) -> bool:
        """
        SRT字幕ファイルをエクスポート

        Args:
            segments: 文字起こしセグメントリスト
                     [{"start": float, "end": float, "text": str}, ...]
            output_path: 出力ファイルパス
            speaker_segments: 話者分離結果（オプション）

        Returns:
            成功時True
        """
        try:
            srt_content = self.generate_srt_content(segments, speaker_segments)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)

            logger.info(f"SRT exported: {output_path}")
            return True

        except (IOError, OSError) as e:
            logger.error(f"SRT export I/O error: {e}")
            return False
        except Exception as e:
            logger.error(f"SRT export failed: {e}")
            return False

    def export_vtt(self,
                   segments: List[Dict[str, Any]],
                   output_path: str,
                   speaker_segments: Optional[List[Dict]] = None) -> bool:
        """
        VTT字幕ファイルをエクスポート

        Args:
            segments: 文字起こしセグメントリスト
            output_path: 出力ファイルパス
            speaker_segments: 話者分離結果（オプション）

        Returns:
            成功時True
        """
        try:
            vtt_content = self.generate_vtt_content(segments, speaker_segments)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(vtt_content)

            logger.info(f"VTT exported: {output_path}")
            return True

        except (IOError, OSError) as e:
            logger.error(f"VTT export I/O error: {e}")
            return False
        except Exception as e:
            logger.error(f"VTT export failed: {e}")
            return False

    def generate_srt_content(self,
                            segments: List[Dict[str, Any]],
                            speaker_segments: Optional[List[Dict]] = None) -> str:
        """
        SRT形式のコンテンツを生成

        Args:
            segments: 文字起こしセグメントリスト
            speaker_segments: 話者分離結果（オプション）

        Returns:
            SRT形式の文字列
        """
        lines = []
        subtitle_index = 1

        for segment in segments:
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip()

            if not text:
                continue

            # 話者情報を追加
            speaker = self._get_speaker_for_time(start, speaker_segments)
            if speaker:
                text = f"[{speaker}] {text}"

            lines.append(str(subtitle_index))
            lines.append(f"{self.format_srt_time(start)} --> {self.format_srt_time(end)}")
            lines.append(text)
            lines.append("")  # 空行

            subtitle_index += 1

        return "\n".join(lines)

    def generate_vtt_content(self,
                            segments: List[Dict[str, Any]],
                            speaker_segments: Optional[List[Dict]] = None) -> str:
        """
        VTT形式のコンテンツを生成

        Args:
            segments: 文字起こしセグメントリスト
            speaker_segments: 話者分離結果（オプション）

        Returns:
            VTT形式の文字列
        """
        lines = ["WEBVTT", ""]

        for segment in segments:
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip()

            if not text:
                continue

            # 話者情報を追加
            speaker = self._get_speaker_for_time(start, speaker_segments)
            if speaker:
                text = f"<v {html.escape(speaker)}>{html.escape(text)}</v>"

            lines.append(f"{self.format_vtt_time(start)} --> {self.format_vtt_time(end)}")
            lines.append(text)
            lines.append("")  # 空行

        return "\n".join(lines)

    def _get_speaker_for_time(self,
                             time: float,
                             speaker_segments: Optional[List[Dict]]) -> Optional[str]:
        """
        指定時刻の話者を取得

        Args:
            time: 時刻（秒）
            speaker_segments: 話者分離セグメントリスト

        Returns:
            話者名（該当なしの場合None）
        """
        if not speaker_segments:
            return None

        for seg in speaker_segments:
            if seg.get("start", 0) <= time <= seg.get("end", 0):
                return seg.get("speaker")

        return None

    def merge_short_segments(self,
                            segments: List[Dict[str, Any]],
                            min_duration: float = 1.0,
                            max_chars: int = 40) -> List[Dict[str, Any]]:
        """
        短いセグメントをマージして見やすくする

        Args:
            segments: 元のセグメントリスト
            min_duration: 最小表示時間（秒）
            max_chars: 最大文字数

        Returns:
            マージ済みセグメントリスト
        """
        if not segments:
            return []

        merged = []
        current_segment = None

        for segment in segments:
            seg_start = segment.get("start", 0)
            seg_end = segment.get("end", 0)
            seg_text = segment.get("text", "").strip()

            if current_segment is None:
                current_segment = {
                    "start": seg_start,
                    "end": seg_end,
                    "text": seg_text
                }
                continue

            duration = seg_end - current_segment["start"]
            combined_text = current_segment["text"] + " " + seg_text

            # マージ条件:
            # 1. 現在のセグメントがmin_duration未満
            # 2. 結合後の文字数がmax_chars未満
            if duration < min_duration and len(combined_text) <= max_chars:
                current_segment["end"] = seg_end
                current_segment["text"] = combined_text
            else:
                merged.append(current_segment)
                current_segment = {
                    "start": seg_start,
                    "end": seg_end,
                    "text": seg_text
                }

        # 最後のセグメントを追加
        if current_segment:
            merged.append(current_segment)

        return merged

    def split_long_segments(self,
                           segments: List[Dict[str, Any]],
                           max_chars: int = 40,
                           max_duration: float = 5.0) -> List[Dict[str, Any]]:
        """
        長いセグメントを分割

        Args:
            segments: 元のセグメントリスト
            max_chars: 最大文字数
            max_duration: 最大表示時間（秒）

        Returns:
            分割済みセグメントリスト
        """
        result = []

        for segment in segments:
            text = segment.get("text", "").strip()
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            duration = end - start

            # 分割が必要かチェック
            if len(text) <= max_chars and duration <= max_duration:
                result.append(segment)
                continue

            # 文で分割
            sentences = re.split(r'([。！？])', text)
            sentences = [s for s in sentences if s]

            # 文を結合して適切な長さに
            current_text = ""
            current_start = start
            time_per_char = duration / len(text) if text else 0

            for i, sentence in enumerate(sentences):
                if not current_text:
                    current_text = sentence
                elif len(current_text) + len(sentence) <= max_chars:
                    current_text += sentence
                else:
                    # セグメントを確定
                    current_end = current_start + (len(current_text) * time_per_char)
                    result.append({
                        "start": current_start,
                        "end": min(current_end, end),
                        "text": current_text
                    })
                    current_text = sentence
                    current_start = current_end

            # 最後のセグメント
            if current_text:
                result.append({
                    "start": current_start,
                    "end": end,
                    "text": current_text
                })

        return result

    def export_auto(self,
                   segments: List[Dict[str, Any]],
                   base_path: str,
                   formats: List[str] = None,
                   speaker_segments: Optional[List[Dict]] = None) -> Dict[str, bool]:
        """
        複数フォーマットで自動エクスポート

        Args:
            segments: 文字起こしセグメントリスト
            base_path: 基本ファイルパス（拡張子なし）
            formats: 出力フォーマットリスト ["srt", "vtt", "txt"]
            speaker_segments: 話者分離結果（オプション）

        Returns:
            {フォーマット: 成功/失敗}の辞書
        """
        if formats is None:
            formats = ["srt", "vtt"]

        results = {}
        base_path = Path(base_path)

        for fmt in formats:
            try:
                if fmt == "srt":
                    output_path = base_path.with_suffix(".srt")
                    results[fmt] = self.export_srt(segments, str(output_path), speaker_segments)

                elif fmt == "vtt":
                    output_path = base_path.with_suffix(".vtt")
                    results[fmt] = self.export_vtt(segments, str(output_path), speaker_segments)

                elif fmt == "txt":
                    output_path = base_path.with_suffix("_字幕.txt")
                    results[fmt] = self._export_txt(segments, str(output_path))

            except Exception as e:
                logger.error(f"Export failed for {fmt}: {e}")
                results[fmt] = False

        return results

    def _export_txt(self, segments: List[Dict[str, Any]], output_path: str) -> bool:
        """プレーンテキストでエクスポート"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for segment in segments:
                    f.write(f"[{segment.get('start', 0):.2f}s] {segment.get('text', '')}\n")

            return True
        except (IOError, OSError) as e:
            logger.error(f"TXT export I/O error: {e}")
            return False
        except Exception as e:
            logger.error(f"TXT export failed: {e}")
            return False


class TranscriptionResult:
    """文字起こし結果の統合管理クラス"""

    def __init__(self):
        self.segments: List[Dict[str, Any]] = []
        self.full_text: str = ""
        self.speaker_segments: Optional[List[Dict]] = None
        self.language: str = "ja"

    def add_segment(self, start: float, end: float, text: str, speaker: Optional[str] = None):
        """セグメントを追加"""
        segment = {
            "start": start,
            "end": end,
            "text": text,
            "speaker": speaker
        }
        self.segments.append(segment)

    def set_speaker_segments(self, speaker_segments: List[Dict]):
        """話者分離結果を設定"""
        self.speaker_segments = speaker_segments

    def export(self,
              base_path: str,
              formats: List[str] = None) -> Dict[str, bool]:
        """
        複数フォーマットでエクスポート

        Args:
            base_path: 基本ファイルパス
            formats: 出力フォーマットリスト

        Returns:
            エクスポート結果
        """
        exporter = SubtitleExporter()
        return exporter.export_auto(
            self.segments,
            base_path,
            formats,
            self.speaker_segments
        )


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== SubtitleExporter Test ===\n")

    # テストデータ
    test_segments = [
        {"start": 0.5, "end": 3.2, "text": "こんにちは、今日は会議です。"},
        {"start": 3.5, "end": 6.8, "text": "プロジェクトの進捗を確認します。"},
        {"start": 7.0, "end": 10.5, "text": "昨日の作業は順調でした。"},
    ]

    speaker_segments = [
        {"start": 0.0, "end": 5.0, "speaker": "話者A"},
        {"start": 5.0, "end": 11.0, "speaker": "話者B"},
    ]

    exporter = SubtitleExporter()

    # SRT出力テスト
    print("1. SRT Export:")
    srt_content = exporter.generate_srt_content(test_segments, speaker_segments)
    print(srt_content)

    # VTT出力テスト
    print("\n2. VTT Export:")
    vtt_content = exporter.generate_vtt_content(test_segments, speaker_segments)
    print(vtt_content)

    # セグメントマージテスト
    print("\n3. Merge Segments Test:")
    short_segments = [
        {"start": 0.0, "end": 0.3, "text": "あ"},
        {"start": 0.4, "end": 0.7, "text": "い"},
        {"start": 0.8, "end": 3.0, "text": "うえお"},
    ]
    merged = exporter.merge_short_segments(short_segments)
    for seg in merged:
        print(f"  {seg['start']:.1f}s - {seg['end']:.1f}s: {seg['text']}")

    print("\nTest completed!")
