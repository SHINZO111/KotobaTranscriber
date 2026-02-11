"""
KotobaTranscriber - 共有定数・ユーティリティモジュール
Qt非依存。全アプリ（PySide6、FastAPI）から使用される。
"""


class SharedConstants:
    """main.py / monitor_app.py / API で共有する定数"""
    # 進捗値
    PROGRESS_MODEL_LOAD = 20
    PROGRESS_BEFORE_TRANSCRIBE = 40
    PROGRESS_AFTER_TRANSCRIBE = 70
    PROGRESS_DIARIZATION_START = 75
    PROGRESS_DIARIZATION_END = 85
    PROGRESS_COMPLETE = 100

    # 並列処理数（TranscriptionEngineの排他制御により常に1）
    # CRITICAL: TranscriptionEngineはスレッドセーフではないため、
    # この値を超えて並列化してはならない（データ競合が発生する）
    BATCH_WORKERS_MAX = 1  # 最大ワーカー数（この値を超えてはならない）
    MONITOR_BATCH_WORKERS = 1  # モニターアプリのバッチワーカー数（常に1）

    # タイムアウト設定（ミリ秒）
    THREAD_WAIT_TIMEOUT = 10000  # 10秒
    MONITOR_WAIT_TIMEOUT = 5000   # 5秒
    BATCH_WAIT_TIMEOUT = 30000    # 30秒

    # 処理中ファイルTTL（秒）
    PROCESSING_FILES_TTL = 3600  # 1時間

    # ボタンスタイル（Qt UI用）
    BUTTON_STYLE_NORMAL = "font-size: 12px; padding: 5px; background-color: #4CAF50; color: white; font-weight: bold;"
    BUTTON_STYLE_MONITOR = "font-size: 12px; padding: 5px; background-color: #FF9800; color: white; font-weight: bold;"
    BUTTON_STYLE_STOP = "font-size: 12px; padding: 5px; background-color: #F44336; color: white; font-weight: bold;"

    # ウィンドウサイズ制限（共通）
    WINDOW_MAX_WIDTH = 3840
    WINDOW_MAX_HEIGHT = 2160

    # ステータスメッセージ表示時間（ミリ秒）
    STATUS_MESSAGE_TIMEOUT = 3000  # 3秒
    TRAY_NOTIFICATION_TIMEOUT = 2000  # 2秒（トレイ通知用）
    ERROR_NOTIFICATION_TIMEOUT = 5000  # 5秒（エラー通知用）

    # サポートする音声/動画ファイル拡張子
    SUPPORTED_EXTENSIONS = (
        '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma', '.opus', '.amr',
        '.mp4', '.avi', '.mov', '.mkv', '.3gp', '.webm',
    )

    # 拡張子セット（folder_monitor / enhanced_folder_monitor 共通）
    AUDIO_EXTENSIONS = set(SUPPORTED_EXTENSIONS)

    # QFileDialog 用フィルタ文字列（Qt UI専用 — API側では不使用）
    AUDIO_FILE_FILTER = (
        "Audio Files ("
        + " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
        + ");;All Files (*)"
    )


def normalize_segments(result: dict) -> list:
    """エンジン出力のセグメントを正規化（chunks/segments/timestampタプル対応）

    全ワーカー（Qt版・API版）および transcription ルーターで共有。
    """
    segments = result.get("chunks", result.get("segments", []))
    normalized = []
    for seg in segments:
        if "timestamp" in seg and isinstance(seg["timestamp"], (list, tuple)):
            ts = seg["timestamp"]
            normalized.append({
                "text": seg.get("text", ""),
                "start": ts[0] if len(ts) > 0 else 0,
                "end": ts[1] if len(ts) > 1 else 0,
            })
        elif "start" in seg:
            normalized.append(seg)
        else:
            normalized.append({"text": seg.get("text", ""), "start": 0, "end": 0})
    return normalized
