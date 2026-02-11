"""ヘルスチェックルーター"""

import logging
import os
import signal
import threading

from fastapi import APIRouter, HTTPException
from api.schemas import HealthResponse, MessageResponse

logger = logging.getLogger(__name__)
router = APIRouter()
_shutdown_lock = threading.Lock()
_shutdown_requested = False


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """ヘルスチェック"""
    engines = {}

    try:
        from transcription_engine import TranscriptionEngine
        engines["kotoba_whisper"] = True
    except ImportError:
        engines["kotoba_whisper"] = False

    try:
        from faster_whisper_engine import FasterWhisperEngine
        engines["faster_whisper"] = True
    except ImportError:
        engines["faster_whisper"] = False

    return HealthResponse(
        status="ok",
        version="2.2",
        engines=engines,
    )


@router.post("/shutdown", response_model=MessageResponse)
async def shutdown():
    """グレースフルシャットダウン — Tauri sidecar から呼び出される"""
    global _shutdown_requested
    with _shutdown_lock:
        if _shutdown_requested:
            raise HTTPException(status_code=409, detail="シャットダウンは既に開始されています")
        _shutdown_requested = True
    logger.info("Shutdown requested via API")
    # SIGINT を自プロセスに送信 → uvicorn が graceful shutdown を実行
    os.kill(os.getpid(), signal.SIGINT)
    return MessageResponse(message="シャットダウンを開始しました")
