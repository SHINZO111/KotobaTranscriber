"""
KotobaTranscriber FastAPI バックエンド
メインアプリケーションエントリポイント。
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.auth import TokenAuthMiddleware, get_token_manager
from api.event_bus import get_event_bus
from api.routers import (
    export,
    health,
    models,
    monitor,
    postprocess,
    realtime,
    settings,
    transcription,
)
from api.websocket import manager

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理（startup / shutdown）"""
    # --- Startup ---
    try:
        loop = asyncio.get_running_loop()
        bus = get_event_bus()
        bus.set_loop(loop)

        # TokenManager 初期化
        token_manager = get_token_manager()
        logger.info(f"TokenManager initialized (TTL: {token_manager._ttl_seconds}s)")

        logger.info("KotobaTranscriber API started")
    except Exception as e:
        logger.error(f"EventBus initialization failed: {e}")

    yield

    # --- Shutdown ---
    bus = get_event_bus()
    bus.shutdown()

    from api.dependencies import get_worker_state

    state = get_worker_state()

    worker = state.get_transcription_worker()
    if worker and worker.is_alive():
        worker.cancel()
        worker.join(timeout=5)

    batch = state.get_batch_worker()
    if batch and batch.is_alive():
        batch.cancel()
        batch.join(timeout=10)

    rt = state.get_realtime_worker()
    if rt and rt.is_alive():
        rt.stop()

    mon = state.get_folder_monitor()
    if mon and mon.is_alive():
        mon.stop()
        mon.join(timeout=5)

    logger.info("KotobaTranscriber API shut down")


# ドキュメント公開制御（開発時のみ: KOTOBA_DEV=1）
_dev_mode = os.environ.get("KOTOBA_DEV", "") == "1"

# FastAPI アプリ
app = FastAPI(
    title="KotobaTranscriber API",
    description="日本語音声文字起こしバックエンド",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/docs" if _dev_mode else None,
    redoc_url="/redoc" if _dev_mode else None,
    openapi_url="/openapi.json" if _dev_mode else None,
)

# 認証ミドルウェア（CORSより先に登録 = CORSの後に実行される）
app.add_middleware(TokenAuthMiddleware)

# CORS設定（Tauri + 開発サーバー）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "https://tauri.localhost",
        "http://localhost:1420",  # Vite dev server
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ルーター登録
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(transcription.router, prefix="/api", tags=["transcription"])
app.include_router(realtime.router, prefix="/api", tags=["realtime"])
app.include_router(models.router, prefix="/api", tags=["models"])
app.include_router(postprocess.router, prefix="/api", tags=["postprocess"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(monitor.router, prefix="/api", tags=["monitor"])
app.include_router(export.router, prefix="/api", tags=["export"])


# WebSocket エンドポイント
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket接続 — EventBus からのイベントをリアルタイム配信

    認証チェックは ConnectionManager.connect() 内で実施されます。
    """
    accepted = await manager.connect(websocket)
    if not accepted:
        return
    bus = get_event_bus()
    try:
        async for event in bus.subscribe():
            try:
                await websocket.send_json(event)
            except WebSocketDisconnect:
                break
            except Exception:
                logger.debug("WebSocket send failed, closing connection")
                break
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        logger.debug("WebSocket task cancelled (shutdown)")
    finally:
        manager.disconnect(websocket)


def main():
    """CLIエントリポイント"""
    import uvicorn

    # src/ を sys.path に追加
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # ポート0 = OS自動割り当て
    port = int(os.environ.get("KOTOBA_PORT", "0"))

    config = uvicorn.Config(
        app="api.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    # ポート番号をstdoutにJSON出力（Tauri sidecarが読み取る）
    original_startup = server.startup

    async def startup_with_port_notify(*args, **kwargs):
        await original_startup(*args, **kwargs)
        token_manager = get_token_manager()
        current_token = token_manager.get_current_token()
        for s in server.servers:
            for sock in s.sockets:
                addr = sock.getsockname()
                port_info = {"port": addr[1], "host": addr[0], "token": current_token}
                print(json.dumps(port_info), flush=True)
                return

    server.startup = startup_with_port_notify
    server.run()


if __name__ == "__main__":
    main()
