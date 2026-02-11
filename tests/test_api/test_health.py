"""Health API テスト"""

import sys
import os
import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# httpx + TestClient のインポートをtry-except
try:
    from httpx import AsyncClient, ASGITransport
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from api.main import app
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestHealthAPI:
    """Health エンドポイントテスト"""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """GET /api/health が正常にレスポンスを返す"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "version" in data
            assert "engines" in data
            assert isinstance(data["engines"], dict)

    @pytest.mark.asyncio
    async def test_health_version(self):
        """ヘルスチェックがバージョン情報を含む"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            data = response.json()
            assert data["version"] == "2.2"
