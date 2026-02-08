"""
エクスポート共通定義
"""

from dataclasses import dataclass
from typing import Optional


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
