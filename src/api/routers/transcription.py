"""文字起こしルーター"""

import asyncio
import logging
import os
import threading
import time

from fastapi import APIRouter, HTTPException

from api.schemas import (
    TranscribeRequest, TranscribeResponse,
    BatchTranscribeRequest, BatchTranscribeResponse,
    MessageResponse,
)
from api.dependencies import (
    get_transcription_engine, get_text_formatter, get_worker_state,
)
from api.event_bus import get_event_bus
from api.workers import BatchTranscriptionWorker
from constants import normalize_segments as _normalize_segments
from validators import Validator, ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()

# エンジン排他ロック（同時に1つの文字起こしのみ許可）
_engine_lock = threading.Lock()


class _EngineBusyError(Exception):
    """エンジンがビジー状態（ロック取得失敗）"""
    pass


def _validate_file_path(file_path: str):
    """ファイルパスの存在とセキュリティを検証（音声/動画拡張子チェック付き）"""
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="指定されたファイルが見つかりません")
    try:
        Validator.validate_file_path(
            file_path, must_exist=True,
            allowed_extensions=Validator.ALLOWED_AUDIO_EXTENSIONS
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="ファイルパスが不正です")


def _do_transcribe(engine, file_path: str, bus, req):
    """同期コンテキストで文字起こしを実行（スレッドプール用）"""
    if not _engine_lock.acquire(timeout=1):
        raise _EngineBusyError()
    try:
        if not engine.is_loaded:
            engine.load_model()
        bus.emit("progress", {"value": 20})

        bus.emit("progress", {"value": 40})
        result = engine.transcribe(file_path, return_timestamps=True)
        text = result.get("text", "")
        segments = _normalize_segments(result)
        bus.emit("progress", {"value": 70})
    finally:
        _engine_lock.release()

    # 話者分離（オプション）— エンジンロック外で実行
    if req.enable_diarization:
        try:
            from speaker_diarization_free import FreeSpeakerDiarizer
            diarizer = FreeSpeakerDiarizer()
            bus.emit("progress", {"value": 75})
            diar_segments = diarizer.diarize(file_path)
            bus.emit("progress", {"value": 85})
            text = diarizer.format_with_speakers(segments, diar_segments)
        except Exception as e:
            logger.warning(f"Speaker diarization failed: {e}", exc_info=True)

    # テキストフォーマット
    if req.remove_fillers or req.add_punctuation or req.format_paragraphs:
        formatter = get_text_formatter()
        text = formatter.format_all(
            text,
            remove_fillers=req.remove_fillers,
            add_punctuation=req.add_punctuation,
            format_paragraphs=req.format_paragraphs,
        )

    bus.emit("progress", {"value": 100})
    return text, segments


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_file(req: TranscribeRequest):
    """
    単一ファイル文字起こし。
    重い処理はスレッドプールで実行し、進捗は WebSocket 経由で配信。
    排他制御は _engine_lock で行う（409を返す）。
    """
    _validate_file_path(req.file_path)

    bus = get_event_bus()
    engine = get_transcription_engine()
    start_time = time.time()

    try:
        text, segments = await asyncio.to_thread(
            _do_transcribe, engine, req.file_path, bus, req
        )
        duration = time.time() - start_time
        bus.emit("finished", {"text": text})

        return TranscribeResponse(text=text, segments=segments, duration=duration)

    except _EngineBusyError:
        raise HTTPException(status_code=409, detail="別の文字起こし処理が実行中です")
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        bus.emit("error", {"message": "文字起こし処理中にエラーが発生しました"})
        raise HTTPException(status_code=500, detail="文字起こし処理中にエラーが発生しました")


@router.post("/batch-transcribe", response_model=BatchTranscribeResponse)
async def batch_transcribe(req: BatchTranscribeRequest):
    """
    バッチ文字起こし（非同期開始）。
    進捗は WebSocket 経由で配信。
    """
    for fp in req.file_paths:
        _validate_file_path(fp)

    state = get_worker_state()
    formatter = get_text_formatter() if (req.remove_fillers or req.add_punctuation) else None
    bus = get_event_bus()

    worker = BatchTranscriptionWorker(
        audio_paths=req.file_paths,
        enable_diarization=req.enable_diarization,
        max_workers=req.max_workers,
        formatter=formatter,
        event_bus=bus,
    )
    if not state.try_set_batch_worker(worker):
        raise HTTPException(status_code=409, detail="別のバッチ処理が実行中です")
    worker.start()

    return BatchTranscribeResponse(
        message="バッチ処理を開始しました",
        total_files=len(req.file_paths),
    )


@router.post("/cancel-transcription", response_model=MessageResponse)
async def cancel_transcription():
    """実行中の文字起こしをキャンセル"""
    state = get_worker_state()
    worker = state.get_transcription_worker()
    if worker and worker.is_alive():
        worker.cancel()
        return MessageResponse(message="キャンセルリクエストを送信しました")
    return MessageResponse(message="実行中の処理はありません")


@router.post("/cancel-batch", response_model=MessageResponse)
async def cancel_batch():
    """実行中のバッチ処理をキャンセル"""
    state = get_worker_state()
    worker = state.get_batch_worker()
    if worker and worker.is_alive():
        worker.cancel()
        return MessageResponse(message="バッチキャンセルリクエストを送信しました")
    return MessageResponse(message="実行中のバッチ処理はありません")
