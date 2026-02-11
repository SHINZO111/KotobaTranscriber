"""フォルダ監視ルーター"""

import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Body

from api.schemas import MonitorRequest, MonitorStatusResponse, MessageResponse
from api.dependencies import get_worker_state
from api.event_bus import get_event_bus
from api.folder_monitor_service import FolderMonitorService
from validators import Validator, ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/monitor/start", response_model=MessageResponse)
async def start_monitor(req: MonitorRequest):
    """フォルダ監視を開始"""
    if not os.path.isdir(req.folder_path):
        raise HTTPException(status_code=404, detail="指定されたフォルダが見つかりません")

    # フォルダパスバリデーション
    try:
        Validator.validate_file_path(req.folder_path, must_exist=True)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="フォルダパスが不正です")

    state = get_worker_state()
    bus = get_event_bus()
    monitor = FolderMonitorService(
        folder_path=req.folder_path,
        check_interval=req.check_interval,
        event_bus=bus,
    )
    if not state.try_set_folder_monitor(monitor):
        raise HTTPException(status_code=409, detail="フォルダ監視が既に実行中です")
    monitor.start()

    return MessageResponse(message="フォルダ監視を開始しました")


@router.post("/monitor/stop", response_model=MessageResponse)
async def stop_monitor():
    """フォルダ監視を停止"""
    state = get_worker_state()
    monitor = state.get_folder_monitor()
    if not monitor or not monitor.is_alive():
        return MessageResponse(message="実行中のフォルダ監視はありません")

    def _stop_monitor():
        monitor.stop()
        monitor.join(timeout=5)

    await asyncio.to_thread(_stop_monitor)
    state.set_folder_monitor(None)
    return MessageResponse(message="フォルダ監視を停止しました")


@router.get("/monitor/status", response_model=MonitorStatusResponse)
async def get_monitor_status():
    """フォルダ監視の状態を取得"""
    state = get_worker_state()
    monitor = state.get_folder_monitor()

    if not monitor or not monitor.is_alive():
        return MonitorStatusResponse(is_running=False)

    return MonitorStatusResponse(
        is_running=True,
        folder_path=monitor.folder_path,
        check_interval=monitor.check_interval,
    )


@router.post("/monitor/mark-processed", response_model=MessageResponse)
async def mark_processed(file_path: str = Body(..., embed=True)):
    """ファイルを処理済みとしてマーク"""
    # パスバリデーション（パストラバーサル防止）
    try:
        Validator.validate_file_path(file_path, must_exist=False)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="ファイルパスが不正です")

    state = get_worker_state()
    monitor = state.get_folder_monitor()
    if not monitor:
        raise HTTPException(status_code=409, detail="フォルダ監視が実行されていません")

    monitor.mark_as_processed(file_path)
    return MessageResponse(message="処理済みとしてマークしました")
