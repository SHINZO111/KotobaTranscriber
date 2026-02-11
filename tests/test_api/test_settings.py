"""Settings API テスト"""

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
    from api.auth import get_token_manager
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False


def _auth_headers():
    if APP_AVAILABLE:
        token_manager = get_token_manager()
        token = token_manager.get_current_token()
        return {"Authorization": f"Bearer {token}"}
    return {"Authorization": "Bearer invalid_token"}


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestSettingsAPI:
    """Settings エンドポイントテスト"""

    @pytest.mark.asyncio
    async def test_get_settings(self):
        """GET /api/settings"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.get("/api/settings")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_patch_settings(self):
        """PATCH /api/settings"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.patch(
                "/api/settings",
                json={"theme": "dark"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "updated" in data
            assert data["updated"].get("theme") == "dark"

    @pytest.mark.asyncio
    async def test_get_config(self):
        """GET /api/config — 設定データが空でないことを検証"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.get("/api/config")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            # ConfigManager のデフォルト設定が返されること（空 {} ではない）
            assert len(data) > 0
            assert "app" in data or "model" in data

    @pytest.mark.asyncio
    async def test_patch_config(self):
        """PATCH /api/config — 設定更新"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.patch(
                "/api/config",
                json={"output": {"default_format": "srt"}}
            )
            assert response.status_code == 200
            data = response.json()
            assert "updated" in data

    @pytest.mark.asyncio
    async def test_patch_config_empty(self):
        """PATCH /api/config — 空更新"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.patch("/api/config", json={})
            assert response.status_code == 200
            data = response.json()
            assert "更新する項目がありません" in data["message"]

    @pytest.mark.asyncio
    async def test_patch_settings_empty(self):
        """PATCH /api/settings — 空更新"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.patch("/api/settings", json={})
            assert response.status_code == 200
            data = response.json()
            assert "更新する項目がありません" in data["message"]
