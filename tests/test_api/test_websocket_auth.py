"""WebSocket接続制限・Auth追加テスト・normalize_segments・format-text"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

pytest.importorskip("fastapi")

from api.websocket import ConnectionManager

try:
    from httpx import ASGITransport, AsyncClient

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from api.auth import API_TOKEN, verify_websocket_token, verify_websocket_token_from_header
    from api.main import app

    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False
    API_TOKEN = ""


def _auth_headers():
    return {"Authorization": f"Bearer {API_TOKEN}"}


# ============================================================
# WebSocket 接続数制限テスト
# ============================================================


class TestWebSocketConnectionLimit:
    """WebSocket接続数制限のテスト"""

    @pytest.mark.asyncio
    async def test_max_connections_constant(self):
        """MAX_CONNECTIONS定数が設定されている"""
        mgr = ConnectionManager()
        assert mgr.MAX_CONNECTIONS == 10

    @pytest.mark.asyncio
    async def test_accept_within_limit(self):
        """制限内の接続は受け入れられる"""
        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.headers = {"authorization": f"Bearer {API_TOKEN}"}
        result = await mgr.connect(ws)
        assert result is True
        assert mgr.connection_count() == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_over_limit(self):
        """MAX_CONNECTIONS超過の接続は拒否される"""
        mgr = ConnectionManager()
        # 制限まで接続
        connections = []
        for i in range(mgr.MAX_CONNECTIONS):
            ws = AsyncMock()
            ws.headers = {"authorization": f"Bearer {API_TOKEN}"}
            await mgr.connect(ws)
            connections.append(ws)

        assert mgr.connection_count() == mgr.MAX_CONNECTIONS

        # 制限超過 — 拒否される
        ws_over = AsyncMock()
        ws_over.headers = {"authorization": f"Bearer {API_TOKEN}"}
        result = await mgr.connect(ws_over)
        assert result is False
        ws_over.close.assert_awaited_once_with(code=1008, reason="Maximum connections reached")
        assert mgr.connection_count() == mgr.MAX_CONNECTIONS

    @pytest.mark.asyncio
    async def test_accept_after_disconnect(self):
        """切断後に新しい接続を受け入れ可能"""
        mgr = ConnectionManager()
        # 制限まで接続
        connections = []
        for i in range(mgr.MAX_CONNECTIONS):
            ws = AsyncMock()
            ws.headers = {"authorization": f"Bearer {API_TOKEN}"}
            await mgr.connect(ws)
            connections.append(ws)

        # 1つ切断
        mgr.disconnect(connections[0])
        assert mgr.connection_count() == mgr.MAX_CONNECTIONS - 1

        # 新しい接続が受け入れられる
        ws_new = AsyncMock()
        ws_new.headers = {"authorization": f"Bearer {API_TOKEN}"}
        await mgr.connect(ws_new)
        ws_new.accept.assert_awaited_once()
        assert mgr.connection_count() == mgr.MAX_CONNECTIONS

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self):
        """ブロードキャスト中に失敗した接続は自動削除"""
        mgr = ConnectionManager()

        ws_good = AsyncMock()
        ws_good.headers = {"authorization": f"Bearer {API_TOKEN}"}
        ws_bad = AsyncMock()
        ws_bad.headers = {"authorization": f"Bearer {API_TOKEN}"}
        ws_bad.send_text.side_effect = Exception("connection lost")

        await mgr.connect(ws_good)
        await mgr.connect(ws_bad)
        assert mgr.connection_count() == 2

        await mgr.broadcast("test", {"data": 1})
        assert mgr.connection_count() == 1  # ws_bad が除去された

    @pytest.mark.asyncio
    async def test_disconnect_idempotent(self):
        """同じ接続の複数回disconnectはエラーにならない"""
        mgr = ConnectionManager()
        ws = AsyncMock()
        ws.headers = {"authorization": f"Bearer {API_TOKEN}"}
        await mgr.connect(ws)
        mgr.disconnect(ws)
        mgr.disconnect(ws)  # 2回目もエラーにならない
        assert mgr.connection_count() == 0


# ============================================================
# WebSocket トークン検証テスト（旧クエリパラメータ版 - 非推奨）
# ============================================================


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestWebSocketTokenVerification:
    """WebSocket トークン検証のテスト（旧クエリパラメータ版）"""

    def test_verify_valid_token(self):
        """正しいトークンでTrue"""
        ws = MagicMock()
        ws.query_params = {"token": API_TOKEN}
        assert verify_websocket_token(ws) is True

    def test_verify_invalid_token(self):
        """不正なトークンでFalse"""
        ws = MagicMock()
        ws.query_params = {"token": "invalid_token"}
        assert verify_websocket_token(ws) is False

    def test_verify_empty_token(self):
        """空トークンでFalse"""
        ws = MagicMock()
        ws.query_params = {"token": ""}
        assert verify_websocket_token(ws) is False

    def test_verify_missing_token(self):
        """トークンなしでFalse"""
        ws = MagicMock()
        ws.query_params = {}
        assert verify_websocket_token(ws) is False


# ============================================================
# WebSocket トークン検証テスト（新Authorizationヘッダ版）
# ============================================================


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestWebSocketTokenVerificationFromHeader:
    """WebSocket トークン検証のテスト（Authorizationヘッダ版）"""

    def test_verify_valid_token_from_header(self):
        """正しいBearerトークンでTrue"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {"authorization": f"Bearer {API_TOKEN}"}
        assert verify_websocket_token_from_header(ws) is True

    def test_verify_invalid_token_from_header(self):
        """不正なトークンでFalse"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {"authorization": "Bearer invalid_token_xyz"}
        assert verify_websocket_token_from_header(ws) is False

    def test_verify_missing_authorization_header(self):
        """AuthorizationヘッダなしでFalse"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {}
        assert verify_websocket_token_from_header(ws) is False

    def test_verify_empty_bearer_token(self):
        """空のBearerトークンでFalse"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {"authorization": "Bearer "}
        assert verify_websocket_token_from_header(ws) is False

    def test_verify_no_bearer_prefix(self):
        """BearerプレフィックスなしでFalse"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {"authorization": API_TOKEN}
        assert verify_websocket_token_from_header(ws) is False

    def test_verify_lowercase_bearer_prefix(self):
        """小文字bearerプレフィックスでFalse（大文字小文字区別）"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {"authorization": f"bearer {API_TOKEN}"}
        assert verify_websocket_token_from_header(ws) is False

    def test_verify_short_token(self):
        """トークン長不足でFalse（20文字未満）"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {"authorization": "Bearer short"}
        assert verify_websocket_token_from_header(ws) is False

    def test_verify_token_with_whitespace(self):
        """トークンに前後スペースがあってもstrip処理される"""
        from api.auth import verify_websocket_token_from_header

        ws = MagicMock()
        ws.headers = {"authorization": f"Bearer  {API_TOKEN}  "}
        # strip()されるので正しいトークンとして扱われる
        assert verify_websocket_token_from_header(ws) is True


# ============================================================
# WebSocket接続の統合テスト（Authorizationヘッダ認証）
# ============================================================


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestWebSocketConnectionWithAuth:
    """WebSocket接続時の認証統合テスト"""

    @pytest.mark.asyncio
    async def test_connect_with_valid_authorization_header(self):
        """正しいAuthorizationヘッダで接続成功"""
        from api.websocket import ConnectionManager

        ws = AsyncMock()
        ws.headers = {"authorization": f"Bearer {API_TOKEN}"}

        mgr = ConnectionManager()
        result = await mgr.connect(ws)

        assert result is True
        ws.accept.assert_awaited_once()
        assert mgr.connection_count() == 1

    @pytest.mark.asyncio
    async def test_connect_without_authorization_header(self):
        """Authorizationヘッダなしで接続拒否"""
        from api.websocket import ConnectionManager

        ws = AsyncMock()
        ws.headers = {}

        mgr = ConnectionManager()
        result = await mgr.connect(ws)

        assert result is False
        ws.close.assert_awaited_once_with(code=1008, reason="Authentication required")
        ws.accept.assert_not_awaited()
        assert mgr.connection_count() == 0

    @pytest.mark.asyncio
    async def test_connect_with_invalid_token(self):
        """不正なトークンで接続拒否"""
        from api.websocket import ConnectionManager

        ws = AsyncMock()
        ws.headers = {"authorization": "Bearer invalid_token_xyz"}

        mgr = ConnectionManager()
        result = await mgr.connect(ws)

        assert result is False
        ws.close.assert_awaited_once_with(code=1008, reason="Authentication required")
        ws.accept.assert_not_awaited()
        assert mgr.connection_count() == 0

    @pytest.mark.asyncio
    async def test_connect_with_no_bearer_prefix(self):
        """BearerプレフィックスなしのAuthorizationヘッダで接続拒否"""
        from api.websocket import ConnectionManager

        ws = AsyncMock()
        ws.headers = {"authorization": API_TOKEN}

        mgr = ConnectionManager()
        result = await mgr.connect(ws)

        assert result is False
        ws.close.assert_awaited_once_with(code=1008, reason="Authentication required")
        ws.accept.assert_not_awaited()
        assert mgr.connection_count() == 0

    @pytest.mark.asyncio
    async def test_auth_checked_before_connection_limit(self):
        """認証チェックが接続数制限より先に実行される"""
        from api.websocket import ConnectionManager

        mgr = ConnectionManager()

        # 制限まで有効な接続を追加
        for i in range(mgr.MAX_CONNECTIONS):
            ws_valid = AsyncMock()
            ws_valid.headers = {"authorization": f"Bearer {API_TOKEN}"}
            await mgr.connect(ws_valid)

        # 認証なしで接続試行 — 認証エラーが先に発生
        ws_no_auth = AsyncMock()
        ws_no_auth.headers = {}
        result = await mgr.connect(ws_no_auth)

        assert result is False
        ws_no_auth.close.assert_awaited_once_with(code=1008, reason="Authentication required")
        # "Maximum connections reached" ではなく "Authentication required" が理由


# ============================================================
# Auth 追加テスト（空トークン等）
# ============================================================


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestAuthEdgeCases:
    """認証ミドルウェアの境界値テスト"""

    @pytest.mark.asyncio
    async def test_empty_bearer_token_returns_403(self):
        """空のBearerトークンで403"""
        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer "}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            response = await client.get("/api/settings")
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_bearer_with_spaces_returns_403(self):
        """スペース付きBearerトークンで403"""
        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer  extra_space"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            response = await client.get("/api/settings")
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_case_sensitive_bearer_prefix(self):
        """bearerプレフィックスは大文字小文字区別あり"""
        transport = ASGITransport(app=app)
        headers = {"Authorization": f"bearer {API_TOKEN}"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            response = await client.get("/api/settings")
            assert response.status_code == 401  # "bearer" != "Bearer"


# ============================================================
# normalize_segments 境界値テスト
# ============================================================


class TestNormalizeSegmentsEdgeCases:
    """normalize_segments のエッジケーステスト"""

    def test_empty_result(self):
        """空の結果"""
        from constants import normalize_segments

        assert normalize_segments({}) == []

    def test_empty_chunks(self):
        """空のchunks"""
        from constants import normalize_segments

        assert normalize_segments({"chunks": []}) == []

    def test_timestamp_tuple_single_element(self):
        """timestampが1要素タプル"""
        from constants import normalize_segments

        result = {"chunks": [{"text": "test", "timestamp": (1.0,)}]}
        segments = normalize_segments(result)
        assert len(segments) == 1
        assert segments[0]["start"] == 1.0
        assert segments[0]["end"] == 0  # 2番目がないので0

    def test_timestamp_empty_tuple(self):
        """timestampが空タプル"""
        from constants import normalize_segments

        result = {"chunks": [{"text": "test", "timestamp": ()}]}
        segments = normalize_segments(result)
        assert len(segments) == 1
        assert segments[0]["start"] == 0  # 空なので0
        assert segments[0]["end"] == 0

    def test_segments_key_used(self):
        """segmentsキーが使われる"""
        from constants import normalize_segments

        result = {"segments": [{"text": "hello", "start": 1.0, "end": 2.0}]}
        segments = normalize_segments(result)
        assert segments[0]["start"] == 1.0

    def test_chunks_priority_over_segments(self):
        """chunksがsegmentsより優先される"""
        from constants import normalize_segments

        result = {
            "chunks": [{"text": "from_chunks", "timestamp": (0.0, 1.0)}],
            "segments": [{"text": "from_segments", "start": 0.0, "end": 1.0}],
        }
        segments = normalize_segments(result)
        assert segments[0]["text"] == "from_chunks"

    def test_no_text_key_defaults_empty(self):
        """textキーがないセグメントは空文字"""
        from constants import normalize_segments

        result = {"chunks": [{"timestamp": (0.0, 1.0)}]}
        segments = normalize_segments(result)
        assert segments[0]["text"] == ""

    def test_segment_without_start_or_timestamp(self):
        """startもtimestampもないセグメント"""
        from constants import normalize_segments

        result = {"chunks": [{"text": "orphan"}]}
        segments = normalize_segments(result)
        assert segments[0]["text"] == "orphan"
        assert segments[0]["start"] == 0
        assert segments[0]["end"] == 0

    def test_mixed_segments(self):
        """異なるフォーマットの混合セグメント"""
        from constants import normalize_segments

        result = {
            "chunks": [
                {"text": "a", "timestamp": (0.0, 1.0)},
                {"text": "b", "start": 1.0, "end": 2.0},
                {"text": "c"},
            ]
        }
        segments = normalize_segments(result)
        assert len(segments) == 3
        assert segments[0]["start"] == 0.0
        assert segments[1]["start"] == 1.0
        assert segments[2]["start"] == 0

    def test_timestamp_list_format(self):
        """timestampがリスト形式"""
        from constants import normalize_segments

        result = {"chunks": [{"text": "list", "timestamp": [0.5, 1.5]}]}
        segments = normalize_segments(result)
        assert segments[0]["start"] == 0.5
        assert segments[0]["end"] == 1.5


# ============================================================
# format-text エンドポイント happy-path テスト
# ============================================================


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestFormatTextEndpoint:
    """format-text エンドポイントのテスト"""

    @pytest.mark.asyncio
    async def test_format_text_happy_path(self):
        """テキストフォーマットの正常系"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/format-text",
                json={
                    "text": "えーと、こんにちは。あの、テストです。",
                    "remove_fillers": True,
                    "add_punctuation": True,
                    "format_paragraphs": False,
                    "clean_repeated": False,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "text" in data

    @pytest.mark.asyncio
    async def test_format_text_empty_text(self):
        """空テキストの処理"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/format-text",
                json={
                    "text": "",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "text" in data
