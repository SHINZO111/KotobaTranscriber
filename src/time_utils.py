"""
時間フォーマットユーティリティ
KotobaTranscriber — 共通の時間変換関数
"""


def format_time_hms(seconds: float) -> str:
    """秒数をH:MM:SS or MM:SS形式に変換（エクスポート表示用）"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_time_srt(seconds: float) -> str:
    """秒数をSRT時間形式に変換 (HH:MM:SS,mmm)"""
    seconds = max(0.0, seconds)
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def format_time_vtt(seconds: float) -> str:
    """秒数をVTT時間形式に変換 (HH:MM:SS.mmm)"""
    seconds = max(0.0, seconds)
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
