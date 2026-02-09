"""
エクスポート共通定義
"""

import logging
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExportOptions:
    """エクスポートオプション"""
    include_timestamps: bool = True
    include_speaker_labels: bool = True
    merge_short_segments: bool = False
    min_segment_duration: float = 1.0
    format_type: str = "meeting"  # meeting, transcript, subtitle
    template_path: Optional[str] = None
    company_name: str = "AGEC株式会社"
    project_name: str = ""


@contextmanager
def atomic_save(output_path: str):
    """
    アトミック書き込み用コンテキストマネージャ（バイナリ/ライブラリ保存用）

    Usage:
        with atomic_save(output_path) as tmp_path:
            doc.save(tmp_path)  # or wb.save(tmp_path)
    """
    output_dir = os.path.dirname(output_path) or '.'
    tmp_fd, tmp_path = tempfile.mkstemp(dir=output_dir)
    os.close(tmp_fd)
    try:
        yield tmp_path
        os.replace(tmp_path, output_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_text(output_path: str, content: str, encoding: str = 'utf-8') -> None:
    """
    テキストコンテンツをアトミックに書き込む

    Args:
        output_path: 出力ファイルパス
        content: 書き込む文字列
        encoding: エンコーディング
    """
    output_dir = os.path.dirname(output_path) or '.'
    tmp_fd, tmp_path = tempfile.mkstemp(dir=output_dir)
    try:
        with os.fdopen(tmp_fd, 'w', encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, output_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# --- Validation ---

MAX_EXPORT_SEGMENTS = 100_000


def validate_export_path(output_path: str) -> None:
    """
    エクスポート出力パスを検証

    Args:
        output_path: 出力ファイルパス

    Raises:
        ValueError: パスが無効な場合
    """
    if not output_path:
        raise ValueError("Output path cannot be empty")
    # パストラバーサル検出
    parts = str(output_path).replace('/', os.sep).split(os.sep)
    if '..' in parts:
        raise ValueError(f"Path traversal detected: {output_path}")
    parent = os.path.dirname(output_path)
    if parent and not os.path.isdir(parent):
        raise ValueError(f"Parent directory does not exist: {parent}")


def validate_segments(segments: List[Dict], max_count: int = MAX_EXPORT_SEGMENTS) -> None:
    """
    セグメントデータを検証

    Args:
        segments: セグメントリスト
        max_count: 最大セグメント数

    Raises:
        TypeError: セグメントがリストでない場合
        ValueError: セグメント数が上限を超えた場合
    """
    if not isinstance(segments, list):
        raise TypeError("Segments must be a list")
    if len(segments) > max_count:
        raise ValueError(f"Too many segments: {len(segments)} > {max_count}")


# --- Segment manipulation ---


def merge_short_segments(
    segments: List[Dict],
    min_duration: float = 1.0,
    max_chars: int = 40,
) -> List[Dict]:
    """
    短いセグメントをマージして見やすくする（話者情報対応）

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
    current = None

    for segment in segments:
        seg_start = segment.get("start", 0)
        seg_end = segment.get("end", 0)
        seg_text = segment.get("text", "").strip()

        if current is None:
            current = {
                "start": seg_start,
                "end": seg_end,
                "text": seg_text,
                "speaker": segment.get("speaker"),
            }
            continue

        duration = seg_end - current["start"]
        combined_text = current["text"] + " " + seg_text

        same_speaker = segment.get("speaker") == current.get("speaker")
        can_merge = (
            duration < min_duration
            and len(combined_text) <= max_chars
            and same_speaker
        )

        if can_merge:
            current["end"] = seg_end
            current["text"] = combined_text
        else:
            merged.append(current)
            current = {
                "start": seg_start,
                "end": seg_end,
                "text": seg_text,
                "speaker": segment.get("speaker"),
            }

    if current:
        merged.append(current)

    return merged


def split_long_segments(
    segments: List[Dict],
    max_chars: int = 40,
    max_duration: float = 5.0,
) -> List[Dict]:
    """
    長いセグメントを分割（話者情報保持）

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

        if len(text) <= max_chars and duration <= max_duration:
            result.append(segment)
            continue

        # 文で分割
        sentences = re.split(r'([。！？\.!?])', text)
        sentences = [s for s in sentences if s]

        current_text = ""
        current_start = start
        time_per_char = duration / len(text) if text else 0

        for sentence in sentences:
            if not current_text:
                current_text = sentence
            elif len(current_text) + len(sentence) <= max_chars:
                current_text += sentence
            else:
                current_end = current_start + (len(current_text) * time_per_char)
                result.append({
                    "start": current_start,
                    "end": min(current_end, end),
                    "text": current_text,
                    "speaker": segment.get("speaker"),
                })
                current_text = sentence
                current_start = current_end

        if current_text:
            result.append({
                "start": current_start,
                "end": end,
                "text": current_text,
                "speaker": segment.get("speaker"),
            })

    return result
