"""APIルーターセキュリティテスト — パス検証・入力バリデーション"""

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
class TestTranscribeRouterSecurity:
    """文字起こしルーターのセキュリティテスト"""

    @pytest.mark.asyncio
    async def test_transcribe_file_not_found(self):
        """存在しないファイルで404を返す"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/transcribe",
                json={"file_path": "/nonexistent/audio.mp3"}
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_batch_nonexistent_file(self):
        """存在しないファイルを含むバッチで404"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/batch-transcribe",
                json={"file_paths": ["/nonexistent/audio.mp3"]}
            )
            assert response.status_code == 404


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestExportRouterSecurity:
    """エクスポートルーターのセキュリティテスト"""

    @pytest.mark.asyncio
    async def test_unsupported_format(self):
        """サポートされていないフォーマットで400を返す"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/export/exe",
                json={"text": "test", "output_path": "/tmp/test.exe"}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_srt_without_segments(self):
        """SRTエクスポートでセグメントなしは400"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/export/srt",
                json={"text": "test", "output_path": "/tmp/test.srt"}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_vtt_without_segments(self):
        """VTTエクスポートでセグメントなしは400"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/export/vtt",
                json={"text": "test", "output_path": "/tmp/test.vtt"}
            )
            assert response.status_code == 400


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestRealtimeRouterSecurity:
    """リアルタイムルーターのセキュリティテスト"""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """停止時に実行中でなければ正常レスポンス"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/realtime/stop")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_pause_when_not_running(self):
        """一時停止時に実行中でなければ409"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/realtime/pause")
            assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_resume_when_not_running(self):
        """再開時に実行中でなければ409"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/realtime/resume")
            assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_status_when_not_running(self):
        """ステータス取得 — 未実行時"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.get("/api/realtime/status")
            assert response.status_code == 200
            data = response.json()
            assert data["is_running"] is False


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestMonitorRouterSecurity:
    """フォルダ監視ルーターのセキュリティテスト"""

    @pytest.mark.asyncio
    async def test_start_nonexistent_folder(self):
        """存在しないフォルダで404"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/monitor/start",
                json={"folder_path": "/nonexistent/folder"}
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """停止時に未実行なら正常"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/monitor/stop")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_when_not_running(self):
        """ステータス取得 — 未実行時"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.get("/api/monitor/status")
            assert response.status_code == 200
            data = response.json()
            assert data["is_running"] is False


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestModelRouterSecurity:
    """モデルルーターのセキュリティテスト"""

    @pytest.mark.asyncio
    async def test_unknown_engine(self):
        """不明なエンジンで400"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/models/unknown-engine/load")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_model_info_unknown_engine(self):
        """不明なエンジンのinfo取得で400"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.get("/api/models/invalid/info")
            assert response.status_code == 400


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestPostprocessRouterSecurity:
    """後処理ルーターのセキュリティテスト"""

    @pytest.mark.asyncio
    async def test_format_text(self):
        """テキストフォーマット正常系"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/format-text",
                json={"text": "テスト テスト"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "text" in data

    @pytest.mark.asyncio
    async def test_correct_text_invalid_provider(self):
        """不明なプロバイダーで422（スキーマバリデーション）"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/correct-text",
                json={"text": "テスト", "provider": "invalid"}
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_diarize_file_not_found(self):
        """存在しないファイルで話者分離すると404"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post(
                "/api/diarize",
                json={"file_path": "/nonexistent/audio.mp3"}
            )
            assert response.status_code == 404
