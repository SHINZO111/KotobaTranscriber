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
    """
    WebSocket接続時のトークン検証（クエリパラメータ ?token=xxx）

    ⚠️ DEPRECATED: クエリパラメータはURL履歴に記録されるため非推奨。
    代わりに verify_websocket_token_from_header() を使用してください。
    """
    token = websocket.query_params.get("token", "")
    return secrets.compare_digest(token, API_TOKEN)


def verify_websocket_token_from_header(websocket: WebSocket) -> bool:
    """
    WebSocket接続時のトークン検証（Authorizationヘッダ）

    ハンドシェイク時の初期HTTPリクエストから Authorization: Bearer <token> ヘッダを検証します。
    クエリパラメータ方式と異なり、トークンがURL履歴やプロキシログに記録されません。

    Args:
        websocket: WebSocket接続オブジェクト

    Returns:
        bool: トークンが有効な場合True、無効な場合False

    Examples:
        >>> # 正しい使用例
        >>> if not verify_websocket_token_from_header(websocket):
        >>>     await websocket.close(code=1008, reason="Authentication required")
        >>>     return False
    """
    auth_header = websocket.headers.get("authorization", "")

    # Bearer プレフィックスチェック（大文字小文字区別あり）
    if not auth_header.startswith("Bearer "):
        return False

    # トークン抽出とstrip
    token = auth_header[7:].strip()

    # トークン長チェック（最小20文字）
    if not token or len(token) < 20:
        return False

    # 定数時間比較
    return secrets.compare_digest(token, API_TOKEN)
