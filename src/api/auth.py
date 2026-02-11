"""
API認証モジュール
起動時にランダムトークンを生成し、全エンドポイント（/api/health除く）で検証する。
Tauri sidecarはstdout JSONからトークンを受け取り、Authorization: Bearer <token> で送信する。
"""

import secrets
import logging
import os
import time
import threading
from typing import Optional
from fastapi import Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class TokenManager:
    """トークンのライフサイクル管理（TTLベースローテーション）"""

    def __init__(self, ttl_minutes: int = 60, grace_period_minutes: int = 5):
        """
        Args:
            ttl_minutes: トークンの有効期限（分）。デフォルト: 60分
            grace_period_minutes: 旧トークンの猶予期間（分）。デフォルト: 5分
        """
        self._current_token: str = secrets.token_urlsafe(32)
        self._previous_token: Optional[str] = None
        self._token_created_at: float = time.time()
        self._ttl_seconds = ttl_minutes * 60
        self._grace_period_seconds = grace_period_minutes * 60
        self._lock = threading.RLock()

    def get_current_token(self) -> str:
        """現在有効なトークンを取得（必要に応じてローテーション）"""
        with self._lock:
            self._rotate_if_needed()
            return self._current_token

    def verify_token(self, token: str) -> bool:
        """
        トークンの有効性を検証

        Args:
            token: 検証するトークン

        Returns:
            bool: トークンが有効な場合True（現在 or 猶予期間内の旧トークン）
        """
        with self._lock:
            self._rotate_if_needed()

            # 現在のトークンと比較
            if secrets.compare_digest(token, self._current_token):
                return True

            # 猶予期間内の旧トークンと比較
            if self._previous_token and secrets.compare_digest(token, self._previous_token):
                elapsed = time.time() - self._token_created_at
                if elapsed <= self._grace_period_seconds:
                    return True

            return False

    def _rotate_if_needed(self):
        """TTL経過時にトークンをローテーション（内部メソッド、lockが必要）"""
        elapsed = time.time() - self._token_created_at
        if elapsed >= self._ttl_seconds:
            self._previous_token = self._current_token
            self._current_token = secrets.token_urlsafe(32)
            self._token_created_at = time.time()
            logger.info("Token rotated (TTL expired)")


# グローバルシングルトンインスタンス
_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """TokenManager シングルトンを取得"""
    global _token_manager
    if _token_manager is None:
        ttl = int(os.environ.get("KOTOBA_TOKEN_TTL_MINUTES", "60"))
        _token_manager = TokenManager(ttl_minutes=ttl)
    return _token_manager


def _reset_token_manager_for_test():
    """テスト用: シングルトンをリセット（プロダクションでは使用禁止）"""
    global _token_manager
    _token_manager = None


# 起動時に1回だけ生成されるトークン（DEPRECATED: 後方互換性のため残す）
# 新規コードでは get_token_manager().get_current_token() を使用すること
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

        token_manager = get_token_manager()
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "認証トークンが必要です"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:].strip()  # "Bearer " の後
        if not token_manager.verify_token(token):
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
    token_manager = get_token_manager()
    token = websocket.query_params.get("token", "")
    return token_manager.verify_token(token)


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
    token_manager = get_token_manager()
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
    return token_manager.verify_token(token)
