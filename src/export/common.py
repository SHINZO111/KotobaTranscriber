"""
エクスポート共通定義
"""

import logging
import os
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
