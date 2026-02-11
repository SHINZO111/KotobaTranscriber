"""API認証ミドルウェアのテスト"""

import sys
import os
import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from httpx import AsyncClient, ASGITransport
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from api.main import app
    from api.auth import API_TOKEN
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False
    API_TOKEN = ""


def _auth_headers():
    return {"Authorization": f"Bearer {API_TOKEN}"}


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestAuthMiddleware:
    """認証ミドルウェアの動作テスト"""

    @pytest.mark.asyncio
    async def test_public_path_no_auth_required(self):
        """公開パス（/api/health）は認証不要"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_path_without_token_returns_401(self):
        """保護パスにトークンなしで401"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/settings")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_path_with_invalid_token_returns_403(self):
        """保護パスに無効トークンで403"""
        transport = ASGITransport(app=app)
        headers = {"Authorization": "Bearer invalid_token_12345"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            response = await client.get("/api/settings")
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_protected_path_with_valid_token_succeeds(self):
        """保護パスに正しいトークンで成功"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.get("/api/settings")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_malformed_auth_header_returns_401(self):
        """Bearer プレフィックスなしのAuthorizationヘッダーで401"""
        transport = ASGITransport(app=app)
        headers = {"Authorization": f"Token {API_TOKEN}"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            response = await client.get("/api/settings")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_docs_path_disabled_in_production(self):
        """/docs はプロダクションモードで無効（KOTOBA_DEV未設定時）"""
        import os
        if os.environ.get("KOTOBA_DEV") == "1":
            pytest.skip("KOTOBA_DEV=1 で実行中のためスキップ")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/docs")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_openapi_path_disabled_in_production(self):
        """/openapi.json はプロダクションモードで無効"""
        import os
        if os.environ.get("KOTOBA_DEV") == "1":
            pytest.skip("KOTOBA_DEV=1 で実行中のためスキップ")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 404
