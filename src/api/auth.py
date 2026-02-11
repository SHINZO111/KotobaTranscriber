"""
API認証モジュール
起動時にランダムトークンを生成し、全エンドポイント（/api/health除く）で検証する。
Tauri sidecarはstdout JSONからトークンを受け取り、Authorization: Bearer <token> で送信する。
"""

import secrets
import logging
from fastapi import Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 起動時に1回だけ生成されるトークン
API_TOKEN: str = secrets.token_urlsafe(32)

# 認証不要のパス（プレフィックス一致）
_PUBLIC_PATHS = frozenset({"/api/health", "/docs", "/openapi.json", "/redoc"})


def _is_public_path(path: str) -> bool:
    """認証不要パスかどうか判定"""
    return path in _PUBLIC_PATHS


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Bearer トークン認証ミドルウェア"""

    async def dispatch(self, request: Request, call_next):
        if _is_public_path(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "認証トークンが必要です"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]  # "Bearer " の後
        if not secrets.compare_digest(token, API_TOKEN):
            return JSONResponse(
                status_code=403,
                content={"detail": "無効な認証トークンです"},
            )

        return await call_next(request)


def verify_websocket_token(websocket: WebSocket) -> bool:
    """WebSocket接続時のトークン検証（クエリパラメータ ?token=xxx）"""
    token = websocket.query_params.get("token", "")
    return secrets.compare_digest(token, API_TOKEN)
