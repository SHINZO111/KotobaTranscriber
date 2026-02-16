"""リアルタイム文字起こしルーター"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from api.dependencies import get_worker_state
from api.event_bus import get_event_bus
from api.realtime_worker import RealtimeWorker
from api.schemas import MessageResponse, RealtimeControlRequest, RealtimeStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/realtime/start", response_model=MessageResponse)
async def start_realtime(req: RealtimeControlRequest):
    """リアルタイム文字起こしを開始"""
    state = get_worker_state()
    bus = get_event_bus()
    worker = RealtimeWorker(
        model_size=req.model_size,
        device=req.device,
        buffer_duration=req.buffer_duration,
        vad_threshold=req.vad_threshold,
        event_bus=bus,
    )
    if not state.try_set_realtime_worker(worker):
        raise HTTPException(status_code=409, detail="リアルタイム文字起こしが既に実行中です")
    worker.start()

    return MessageResponse(message="リアルタイム文字起こしを開始しました")


@router.post("/realtime/stop", response_model=MessageResponse)
async def stop_realtime():
    """リアルタイム文字起こしを停止"""
    state = get_worker_state()
    worker = state.get_realtime_worker()
    if not worker or not worker.is_alive():
        return MessageResponse(message="実行中のリアルタイム処理はありません")

    await asyncio.to_thread(worker.stop)
    state.set_realtime_worker(None)
    return MessageResponse(message="リアルタイム文字起こしを停止しました")


@router.post("/realtime/pause", response_model=MessageResponse)
async def pause_realtime():
    """リアルタイム文字起こしを一時停止"""
    state = get_worker_state()
    worker = state.get_realtime_worker()
    if not worker or not worker.is_alive():
        raise HTTPException(status_code=409, detail="リアルタイム処理が実行されていません")

    worker.pause()
    return MessageResponse(message="一時停止しました")


@router.post("/realtime/resume", response_model=MessageResponse)
async def resume_realtime():
    """リアルタイム文字起こしを再開"""
    state = get_worker_state()
    worker = state.get_realtime_worker()
    if not worker or not worker.is_alive():
        raise HTTPException(status_code=409, detail="リアルタイム処理が実行されていません")

    worker.resume()
    return MessageResponse(message="再開しました")


@router.get("/realtime/status", response_model=RealtimeStatusResponse)
async def get_realtime_status():
    """リアルタイム文字起こしの状態を取得"""
    state = get_worker_state()
    worker = state.get_realtime_worker()

    if not worker or not worker.is_alive():
        return RealtimeStatusResponse(is_running=False)

    return RealtimeStatusResponse(
        is_running=True,
        is_paused=worker.is_paused(),
        model_size=worker.model_size,
    )
