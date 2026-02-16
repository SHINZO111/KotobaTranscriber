"""モデル管理ルーター"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from api.dependencies import get_faster_whisper_engine, get_transcription_engine
from api.schemas import MessageResponse, ModelInfoResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_engine(engine: str):
    """エンジン名からエンジンインスタンスを取得"""
    if engine == "kotoba":
        eng = get_transcription_engine()
        if eng is None:
            raise HTTPException(status_code=404, detail="Kotoba-Whisperエンジンが利用できません")
        return eng, "Kotoba-Whisper"
    elif engine == "faster-whisper":
        eng = get_faster_whisper_engine()
        if eng is None:
            raise HTTPException(status_code=404, detail="Faster-Whisperエンジンが利用できません")
        return eng, "Faster-Whisper"
    else:
        raise HTTPException(status_code=400, detail="不明なエンジンです")


@router.post("/models/{engine}/load", response_model=MessageResponse)
async def load_model(engine: str):
    """モデルをロード（スレッドプールで非同期実行）"""
    eng, name = _get_engine(engine)
    try:
        await asyncio.to_thread(eng.load_model)
        return MessageResponse(message=f"{name}モデルをロードしました")
    except Exception as e:
        logger.error(f"モデルロード失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="モデルロードに失敗しました")


@router.post("/models/{engine}/unload", response_model=MessageResponse)
async def unload_model(engine: str):
    """モデルをアンロード（スレッドプールで非同期実行）"""
    eng, name = _get_engine(engine)
    try:
        await asyncio.to_thread(eng.unload_model)
    except Exception as e:
        logger.warning(f"Model unload warning: {e}")
    return MessageResponse(message=f"{name}モデルをアンロードしました")


@router.get("/models/{engine}/info", response_model=ModelInfoResponse)
async def get_model_info(engine: str):
    """モデル情報を取得"""
    if engine == "kotoba":
        eng = get_transcription_engine()
        is_loaded = eng is not None and hasattr(eng, "model") and eng.model is not None
        return ModelInfoResponse(
            engine="kotoba_whisper",
            is_loaded=is_loaded,
            model_name=getattr(eng, "model_name", None) if eng else None,
            device=getattr(eng, "device", None) if eng else None,
        )

    elif engine == "faster-whisper":
        eng = get_faster_whisper_engine()
        is_loaded = eng is not None and hasattr(eng, "model") and eng.model is not None
        return ModelInfoResponse(
            engine="faster_whisper",
            is_loaded=is_loaded,
            model_name=getattr(eng, "model_size", None) if eng else None,
            device=getattr(eng, "device", None) if eng else None,
        )

    else:
        raise HTTPException(status_code=400, detail="不明なエンジンです")
