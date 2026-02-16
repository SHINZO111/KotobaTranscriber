"""API edge cases テスト — Round 3 追加分

スキーマバリデーション境界値、ルーター応答一貫性、
WebSocket管理、依存性注入のエッジケースをカバー。
"""

import asyncio
import os
import sys

import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from pydantic import ValidationError as PydanticValidationError

    from api.schemas import (
        BatchTranscribeRequest,
        BatchTranscribeResponse,
        ConfigModel,
        CorrectTextRequest,
        DiarizeRequest,
        ExportRequest,
        ExportResponse,
        FormatTextRequest,
        HealthResponse,
        MessageResponse,
        ModelInfoResponse,
        MonitorRequest,
        MonitorStatusResponse,
        RealtimeControlRequest,
        RealtimeStatusResponse,
        SettingsModel,
        TranscribeRequest,
        TranscribeResponse,
    )

    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False

try:
    from httpx import ASGITransport, AsyncClient

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from api.auth import get_token_manager
    from api.main import app

    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False

try:
    from api.event_bus import EventBus

    EVENTBUS_AVAILABLE = True
except ImportError:
    EVENTBUS_AVAILABLE = False

try:
    from api.websocket import ConnectionManager

    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

try:
    from api.dependencies import WorkerState

    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False


# ===================================================================
# Schema edge cases
# ===================================================================


@pytest.mark.skipif(not SCHEMAS_AVAILABLE, reason="schemas not importable")
class TestSchemaEdgeCases:
    """スキーマバリデーション境界値テスト"""

    def test_batch_max_workers_upper_bound(self):
        """max_workers=2 は le=1 に違反して拒否される（エンジン排他のため常に1）"""
        with pytest.raises(PydanticValidationError):
            BatchTranscribeRequest(
                file_paths=["/a.mp3"],
                max_workers=2,
            )

    def test_batch_max_workers_exact_bounds(self):
        """max_workers=1 のみ許容される（エンジン排他のため常に1）"""
        req1 = BatchTranscribeRequest(file_paths=["/a.mp3"], max_workers=1)
        assert req1.max_workers == 1

    def test_realtime_vad_threshold_boundary(self):
        """vad_threshold 0.0 と 1.0 は境界値として許容される"""
        req0 = RealtimeControlRequest(vad_threshold=0.0)
        assert req0.vad_threshold == 0.0
        req1 = RealtimeControlRequest(vad_threshold=1.0)
        assert req1.vad_threshold == 1.0

    def test_realtime_vad_threshold_out_of_range(self):
        """vad_threshold 1.1 は範囲外で拒否される"""
        with pytest.raises(PydanticValidationError):
            RealtimeControlRequest(vad_threshold=1.1)

    def test_realtime_buffer_duration_boundary(self):
        """buffer_duration 1.0 と 10.0 は境界値として許容される"""
        req_min = RealtimeControlRequest(buffer_duration=1.0)
        assert req_min.buffer_duration == 1.0
        req_max = RealtimeControlRequest(buffer_duration=10.0)
        assert req_max.buffer_duration == 10.0

    def test_realtime_buffer_duration_out_of_range(self):
        """buffer_duration 0.5 は範囲外で拒否される"""
        with pytest.raises(PydanticValidationError):
            RealtimeControlRequest(buffer_duration=0.5)

    def test_monitor_check_interval_boundary(self):
        """check_interval 5 と 60 は境界値として許容される"""
        req_min = MonitorRequest(folder_path="/test", check_interval=5)
        assert req_min.check_interval == 5
        req_max = MonitorRequest(folder_path="/test", check_interval=60)
        assert req_max.check_interval == 60

    def test_monitor_check_interval_out_of_range(self):
        """check_interval 4 は ge=5 に違反して拒否される"""
        with pytest.raises(PydanticValidationError):
            MonitorRequest(folder_path="/test", check_interval=4)

    def test_message_response(self):
        """MessageResponse の基本動作"""
        resp = MessageResponse(message="テスト")
        assert resp.message == "テスト"

    def test_message_response_default(self):
        """MessageResponse デフォルト値"""
        resp = MessageResponse()
        assert resp.message == ""

    def test_batch_transcribe_response(self):
        """BatchTranscribeResponse"""
        resp = BatchTranscribeResponse(total_files=5)
        assert resp.total_files == 5
        assert resp.message == "バッチ処理を開始しました"

    def test_config_model_all_none(self):
        """ConfigModel で全フィールド None"""
        cfg = ConfigModel()
        assert cfg.model is None
        assert cfg.audio is None
        assert cfg.output is None

    def test_config_model_with_data(self):
        """ConfigModel にデータを設定"""
        cfg = ConfigModel(model={"whisper": {"language": "ja"}})
        assert cfg.model["whisper"]["language"] == "ja"

    def test_transcribe_response_defaults(self):
        """TranscribeResponse のデフォルト値"""
        resp = TranscribeResponse()
        assert resp.text == ""
        assert resp.segments == []
        assert resp.duration is None

    def test_export_response_defaults(self):
        """ExportResponse のデフォルト値"""
        resp = ExportResponse()
        assert resp.success is True
        assert resp.output_path == ""
        assert resp.message == ""

    def test_export_request_all_formats(self):
        """ExportRequest で全フォーマットを指定可能"""
        for fmt in ("txt", "docx", "xlsx", "srt", "vtt", "json"):
            req = ExportRequest(text="t", output_path="/out", format=fmt)
            assert req.format == fmt

    def test_diarize_request_empty_segments(self):
        """DiarizeRequest セグメントなし"""
        req = DiarizeRequest(file_path="/test.mp3")
        assert req.segments == []

    def test_settings_model_partial_update(self):
        """SettingsModel 部分更新"""
        settings = SettingsModel(theme="dark", device="cuda")
        dump = settings.model_dump()
        non_none = {k: v for k, v in dump.items() if v is not None}
        assert non_none == {"theme": "dark", "device": "cuda"}


# ===================================================================
# Router response consistency
# ===================================================================


def _auth_headers():
    """テスト用認証ヘッダーを返す"""
    if APP_AVAILABLE:
        token_manager = get_token_manager()
        token = token_manager.get_current_token()
        return {"Authorization": f"Bearer {token}"}
    return {"Authorization": "Bearer invalid_token"}


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not importable")
class TestRouterResponseConsistency:
    """ルーター応答の一貫性テスト"""

    @pytest.mark.asyncio
    async def test_cancel_transcription_returns_message(self):
        """POST /api/cancel-transcription は message フィールドを含む"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/cancel-transcription")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert isinstance(data["message"], str)

    @pytest.mark.asyncio
    async def test_cancel_batch_returns_message(self):
        """POST /api/cancel-batch は message フィールドを含む"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/cancel-batch")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_realtime_stop_returns_message(self):
        """POST /api/realtime/stop は message フィールドを含む"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/realtime/stop")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_monitor_stop_returns_message(self):
        """POST /api/monitor/stop は message フィールドを含む"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/monitor/stop")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_settings_patch_empty_body(self):
        """PATCH /api/settings で空ボディ"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.patch("/api/settings", json={})
            assert response.status_code == 200
            data = response.json()
            assert "updated" in data
            assert data["updated"] == {}

    @pytest.mark.asyncio
    async def test_model_unload_unknown_engine(self):
        """POST /api/models/unknown/unload で 400"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/models/unknown/unload")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_transcribe_missing_file_path(self):
        """POST /api/transcribe でfile_path未指定は422"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/transcribe", json={})
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_transcribe_empty_list(self):
        """POST /api/batch-transcribe で空リストは正常に処理"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/batch-transcribe", json={"file_paths": []})
            # 空リストは200を返す（ワーカーが即完了するため）
            # または422 (空リストのバリデーションによる)
            assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_export_missing_text(self):
        """POST /api/export/txt でtext未指定は422"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=_auth_headers()) as client:
            response = await client.post("/api/export/txt", json={"output_path": "/tmp/test.txt"})
            assert response.status_code == 422


# ===================================================================
# WebSocket ConnectionManager
# ===================================================================


@pytest.mark.skipif(not WS_AVAILABLE, reason="websocket module not importable")
class TestConnectionManager:
    """ConnectionManager テスト"""

    def test_initial_state(self):
        """初期状態 — 接続なし"""
        mgr = ConnectionManager()
        assert mgr.connection_count() == 0
        assert len(mgr.active_connections) == 0

    def test_disconnect_nonexistent(self):
        """存在しない接続の disconnect はエラーにならない"""
        mgr = ConnectionManager()

        class FakeWS:
            pass

        mgr.disconnect(FakeWS())
        assert mgr.connection_count() == 0

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        """接続なしでの broadcast はエラーにならない"""
        mgr = ConnectionManager()
        # 接続がないときは何もしないはず
        await mgr.broadcast("test", {"data": 1})


# ===================================================================
# EventBus additional edge cases
# ===================================================================


@pytest.mark.skipif(not EVENTBUS_AVAILABLE, reason="EventBus not importable")
class TestEventBusEdgeCases:
    """EventBus 追加エッジケーステスト"""

    def test_emit_with_none_data(self):
        """data=None での emit"""
        bus = EventBus()
        # エラーにならないこと
        bus.emit("test", None)

    def test_emit_without_loop(self):
        """ループ未設定での emit"""
        bus = EventBus()
        # ループが設定されていなくてもエラーにならないこと
        bus.emit("test", {"value": 1})

    @pytest.mark.asyncio
    async def test_subscribe_cleanup_on_break(self):
        """subscribe から break で抜けた後にサブスクライバーが解除される"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        assert bus.subscriber_count() == 0

        async def consumer():
            async for event in bus.subscribe():
                break

        async def producer():
            await asyncio.sleep(0.05)
            bus.emit("stop", {})

        await asyncio.wait_for(asyncio.gather(consumer(), producer()), timeout=3.0)
        assert bus.subscriber_count() == 0

    def test_emit_after_shutdown_is_noop(self):
        """shutdown 後の emit はサイレントに無視される"""
        bus = EventBus()
        bus.shutdown()
        # 何度呼んでもエラーにならない
        for _ in range(100):
            bus.emit("test", {"n": 1})


# ===================================================================
# WorkerState tests
# ===================================================================


@pytest.mark.skipif(not DEPS_AVAILABLE, reason="dependencies not importable")
class TestWorkerState:
    """WorkerState テスト"""

    def test_initial_state(self):
        """初期状態 — 全 worker が None"""
        state = WorkerState()
        assert state.get_transcription_worker() is None
        assert state.get_batch_worker() is None
        assert state.get_realtime_worker() is None
        assert state.get_folder_monitor() is None

    def test_set_and_get(self):
        """set/get の往復"""
        state = WorkerState()
        sentinel = object()
        state.set_transcription_worker(sentinel)
        assert state.get_transcription_worker() is sentinel

    def test_overwrite(self):
        """ワーカーの上書き"""
        state = WorkerState()
        old = object()
        new = object()
        state.set_batch_worker(old)
        state.set_batch_worker(new)
        assert state.get_batch_worker() is new

    def test_set_none(self):
        """None の設定（ワーカークリア）"""
        state = WorkerState()
        state.set_realtime_worker(object())
        state.set_realtime_worker(None)
        assert state.get_realtime_worker() is None
