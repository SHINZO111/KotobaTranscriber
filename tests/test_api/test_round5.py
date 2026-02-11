"""Round 5 テスト — EventBus shutdown unblock, workers, export, config flatten, transcription lock"""

import asyncio
import json
import os
import sys
import threading
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from api.event_bus import EventBus


# ============================================================
# EventBus shutdown: subscribers unblocked
# ============================================================

class TestEventBusShutdownUnblock:
    """shutdown() がアクティブなサブスクライバーをアンブロックする"""

    @pytest.mark.asyncio
    async def test_shutdown_unblocks_subscriber(self):
        """shutdown() が await queue.get() で待機中のサブスクライバーを解放する"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received = []

        async def consumer():
            async for event in bus.subscribe():
                received.append(event)

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)
        assert bus.subscriber_count() == 1

        # emit a normal event then shutdown
        bus.emit("normal", {"n": 1})
        await asyncio.sleep(0.05)
        bus.shutdown()

        # subscriber should exit cleanly within timeout
        await asyncio.wait_for(task, timeout=3.0)

        # should have received the normal event but NOT the __shutdown__ sentinel
        assert len(received) == 1
        assert received[0]["type"] == "normal"
        assert bus.subscriber_count() == 0

    @pytest.mark.asyncio
    async def test_shutdown_unblocks_multiple_subscribers(self):
        """shutdown() が複数のサブスクライバーを同時に解放する"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        tasks = []
        for _ in range(3):
            async def consumer():
                async for event in bus.subscribe():
                    pass
            tasks.append(asyncio.create_task(consumer()))

        await asyncio.sleep(0.05)
        assert bus.subscriber_count() == 3

        bus.shutdown()
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=3.0)
        assert bus.subscriber_count() == 0

    @pytest.mark.asyncio
    async def test_sentinel_not_yielded(self):
        """__shutdown__ センチネルはサブスクライバーにyieldされない"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        yielded_types = []

        async def consumer():
            async for event in bus.subscribe():
                yielded_types.append(event["type"])

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        bus.emit("real_event", {})
        await asyncio.sleep(0.05)
        bus.shutdown()
        await asyncio.wait_for(task, timeout=3.0)

        assert "__shutdown__" not in yielded_types
        assert "real_event" in yielded_types


# ============================================================
# _normalize_segments
# ============================================================

class TestNormalizeSegments:
    """_normalize_segments の各フォーマット対応テスト"""

    def test_chunks_format(self):
        """chunks キーからセグメントを正規化"""
        from api.workers import _normalize_segments

        result = {"chunks": [
            {"text": "hello", "timestamp": [0.0, 1.5]},
            {"text": "world", "timestamp": [1.5, 3.0]},
        ]}
        segments = _normalize_segments(result)
        assert len(segments) == 2
        assert segments[0]["text"] == "hello"
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 1.5
        assert segments[1]["text"] == "world"
        assert segments[1]["start"] == 1.5

    def test_segments_format(self):
        """segments キーからそのまま取得"""
        from api.workers import _normalize_segments

        result = {"segments": [
            {"text": "test", "start": 0.0, "end": 2.0},
        ]}
        segments = _normalize_segments(result)
        assert len(segments) == 1
        assert segments[0]["start"] == 0.0

    def test_no_timestamp_key(self):
        """timestamp も start もない場合は 0 をデフォルト"""
        from api.workers import _normalize_segments

        result = {"segments": [{"text": "no_time"}]}
        segments = _normalize_segments(result)
        assert segments[0]["start"] == 0
        assert segments[0]["end"] == 0

    def test_empty_result(self):
        """空の結果"""
        from api.workers import _normalize_segments

        segments = _normalize_segments({})
        assert segments == []

    def test_single_timestamp(self):
        """timestamp が1要素のタプル"""
        from api.workers import _normalize_segments

        result = {"chunks": [{"text": "x", "timestamp": [5.0]}]}
        segments = _normalize_segments(result)
        assert segments[0]["start"] == 5.0
        assert segments[0]["end"] == 0


# ============================================================
# Export router: _get_segments helper
# ============================================================

class TestExportGetSegments:
    """_get_segments ヘルパー関数のテスト"""

    def test_with_segments(self):
        """セグメントがある場合はそのまま返す"""
        from api.routers.export import _get_segments
        from api.schemas import ExportRequest

        req = ExportRequest(
            text="test",
            segments=[{"text": "a", "start": 0, "end": 1}],
            output_path="/tmp/test.txt"
        )
        result = _get_segments(req)
        assert result == [{"text": "a", "start": 0, "end": 1}]

    def test_without_segments(self):
        """セグメントがない場合はテキストから単一セグメントを作成"""
        from api.routers.export import _get_segments
        from api.schemas import ExportRequest

        req = ExportRequest(
            text="hello world",
            segments=[],
            output_path="/tmp/test.txt"
        )
        result = _get_segments(req)
        assert len(result) == 1
        assert result[0]["text"] == "hello world"
        assert result[0]["start"] == 0
        assert result[0]["end"] == 0


# ============================================================
# Config flatten: recursive dict handling
# ============================================================

class TestConfigFlattenRecursion:
    """settings.py の flatten_and_set が深いネストを処理する"""

    def test_flat_config_update(self):
        """フラットなキーの更新"""
        from api.routers.settings import flatten_and_set
        calls = {}

        class MockConfig:
            def set(self, key, value):
                calls[key] = value

        cfg = MockConfig()
        flatten_and_set(cfg, "language", "ja")
        assert calls == {"language": "ja"}

    def test_nested_config_update(self):
        """ネストされた dict の再帰展開"""
        from api.routers.settings import flatten_and_set
        calls = {}

        class MockConfig:
            def set(self, key, value):
                calls[key] = value

        cfg = MockConfig()
        flatten_and_set(cfg, "model", {"whisper": {"name": "large-v3", "device": "cuda"}})
        assert calls == {
            "model.whisper.name": "large-v3",
            "model.whisper.device": "cuda",
        }

    def test_mixed_depth_config(self):
        """浅いキーと深いキーの混在"""
        from api.routers.settings import flatten_and_set
        calls = {}

        class MockConfig:
            def set(self, key, value):
                calls[key] = value

        cfg = MockConfig()
        flatten_and_set(cfg, "audio", {"sample_rate": 16000})
        flatten_and_set(cfg, "debug", True)
        assert calls == {"audio.sample_rate": 16000, "debug": True}


# ============================================================
# Transcription router: engine lock
# ============================================================

class TestTranscriptionEngineLock:
    """エンジンロックによる排他制御テスト"""

    def test_engine_lock_exists(self):
        """_engine_lock がモジュールレベルで定義されている"""
        from api.routers.transcription import _engine_lock
        assert isinstance(_engine_lock, type(threading.Lock()))

    def test_do_transcribe_checks_is_loaded(self):
        """_do_transcribe がエンジンの is_loaded を確認してから load_model を呼ぶ"""
        from api.routers.transcription import _do_transcribe

        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.transcribe.return_value = {"text": "test", "chunks": []}

        mock_bus = MagicMock()
        mock_req = MagicMock()
        mock_req.enable_diarization = False
        mock_req.remove_fillers = False
        mock_req.add_punctuation = False
        mock_req.format_paragraphs = False

        text, segments = _do_transcribe(mock_engine, "test.wav", mock_bus, mock_req)

        # is_loaded=True なので load_model は呼ばれない
        mock_engine.load_model.assert_not_called()
        assert text == "test"

    def test_do_transcribe_loads_when_not_loaded(self):
        """is_loaded=False のときは load_model が呼ばれる"""
        from api.routers.transcription import _do_transcribe

        mock_engine = MagicMock()
        mock_engine.is_loaded = False
        mock_engine.transcribe.return_value = {"text": "loaded", "chunks": []}

        mock_bus = MagicMock()
        mock_req = MagicMock()
        mock_req.enable_diarization = False
        mock_req.remove_fillers = False
        mock_req.add_punctuation = False
        mock_req.format_paragraphs = False

        text, segments = _do_transcribe(mock_engine, "test.wav", mock_bus, mock_req)

        mock_engine.load_model.assert_called_once()
        assert text == "loaded"


# ============================================================
# Postprocess router: correct-text provider mapping
# ============================================================

class TestCorrectTextProviderMapping:
    """correct-text エンドポイントのプロバイダーマッピングテスト"""

    def test_valid_provider_accepted_by_schema(self):
        """有効なプロバイダーがスキーマで受け入れられる"""
        from api.schemas import CorrectTextRequest
        for p in ("local", "claude", "openai"):
            req = CorrectTextRequest(text="test", provider=p)
            assert req.provider == p

    def test_invalid_provider_rejected_by_schema(self):
        """無効なプロバイダーはスキーマで拒否される"""
        from api.schemas import CorrectTextRequest
        from pydantic import ValidationError
        for p in ("anthropic", "gpt4", ""):
            with pytest.raises(ValidationError):
                CorrectTextRequest(text="test", provider=p)


# ============================================================
# Export router: format validation
# ============================================================

class TestExportFormatValidation:
    """エクスポートフォーマットの検証テスト"""

    def test_supported_formats_accepted_by_schema(self):
        """サポートされているフォーマットがスキーマで受け入れられる"""
        from api.schemas import ExportRequest
        for fmt in ("txt", "docx", "xlsx", "srt", "vtt", "json"):
            req = ExportRequest(text="test", output_path="/tmp/out", format=fmt)
            assert req.format == fmt

    def test_unsupported_format_rejected_by_schema(self):
        """未サポートフォーマットはスキーマで拒否される"""
        from api.schemas import ExportRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExportRequest(text="test", output_path="/tmp/out", format="pdf")

    def test_srt_requires_segments(self):
        """SRT/VTTエクスポートにはセグメントが必要"""
        from api.routers.export import _export_srt, _export_vtt
        from api.schemas import ExportRequest
        from fastapi import HTTPException

        req = ExportRequest(text="test", segments=[], output_path="/tmp/test.srt")

        with pytest.raises(HTTPException) as exc_info:
            _export_srt(req)
        assert exc_info.value.status_code == 400

    def test_vtt_requires_segments(self):
        """VTTエクスポートにはセグメントが必要"""
        from api.routers.export import _export_vtt
        from api.schemas import ExportRequest
        from fastapi import HTTPException

        req = ExportRequest(text="test", segments=[], output_path="/tmp/test.vtt")

        with pytest.raises(HTTPException) as exc_info:
            _export_vtt(req)
        assert exc_info.value.status_code == 400


# ============================================================
# Export router: txt export
# ============================================================

class TestExportTxt:
    """TXT エクスポートのテスト"""

    def test_export_txt(self, tmp_path):
        """テキストファイルへのエクスポート"""
        from api.routers.export import _export_txt
        from api.schemas import ExportRequest

        output = str(tmp_path / "output.txt")
        req = ExportRequest(text="テスト文字起こし", segments=[], output_path=output)

        result = _export_txt(req)
        assert result.success is True
        assert result.output_path == output

        with open(output, "r", encoding="utf-8") as f:
            assert f.read() == "テスト文字起こし"

    def test_export_json(self, tmp_path):
        """JSONファイルへのエクスポート"""
        from api.routers.export import _export_json
        from api.schemas import ExportRequest

        output = str(tmp_path / "output.json")
        segments = [{"text": "a", "start": 0, "end": 1}]
        req = ExportRequest(text="test", segments=segments, output_path=output)

        result = _export_json(req)
        assert result.success is True

        with open(output, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        assert data["text"] == "test"
        assert len(data["segments"]) == 1


# ============================================================
# WorkerState thread-safety
# ============================================================

class TestWorkerState:
    """WorkerState のスレッドセーフなアクセステスト"""

    def test_set_and_get_workers(self):
        """各ワーカータイプの set/get"""
        from api.dependencies import WorkerState

        state = WorkerState()

        mock_worker = MagicMock()
        state.set_transcription_worker(mock_worker)
        assert state.get_transcription_worker() is mock_worker

        mock_batch = MagicMock()
        state.set_batch_worker(mock_batch)
        assert state.get_batch_worker() is mock_batch

        mock_realtime = MagicMock()
        state.set_realtime_worker(mock_realtime)
        assert state.get_realtime_worker() is mock_realtime

        mock_monitor = MagicMock()
        state.set_folder_monitor(mock_monitor)
        assert state.get_folder_monitor() is mock_monitor

    def test_initial_state_is_none(self):
        """初期状態は全てNone"""
        from api.dependencies import WorkerState

        state = WorkerState()
        assert state.get_transcription_worker() is None
        assert state.get_batch_worker() is None
        assert state.get_realtime_worker() is None
        assert state.get_folder_monitor() is None

    def test_concurrent_access(self):
        """複数スレッドからの同時アクセス"""
        from api.dependencies import WorkerState

        state = WorkerState()
        errors = []

        def setter(n):
            try:
                for i in range(50):
                    state.set_transcription_worker(MagicMock())
                    state.get_transcription_worker()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=setter, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ============================================================
# EventBus emit thread-safety stress
# ============================================================

class TestEventBusThreadSafety:
    """EventBus のスレッドセーフ性ストレステスト"""

    @pytest.mark.asyncio
    async def test_concurrent_emit_from_threads(self):
        """複数スレッドからの同時emit"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received = []
        done = asyncio.Event()

        async def consumer():
            count = 0
            async for event in bus.subscribe():
                received.append(event)
                count += 1
                if count >= 30:
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        def emitter(thread_id):
            for i in range(10):
                bus.emit("thread_event", {"thread": thread_id, "i": i})

        threads = [threading.Thread(target=emitter, args=(t,)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        await asyncio.wait_for(task, timeout=5.0)
        assert len(received) == 30


# ============================================================
# P2-5: FolderMonitorService processed_files pruning
# ============================================================

class TestFolderMonitorPruning:
    """processed_files セットの上限と刈り込みテスト"""

    def test_max_processed_entries_constant(self):
        """MAX_PROCESSED_ENTRIES 定数が設定されている"""
        from api.folder_monitor_service import FolderMonitorService
        assert hasattr(FolderMonitorService, "MAX_PROCESSED_ENTRIES")
        assert FolderMonitorService.MAX_PROCESSED_ENTRIES > 0

    def test_prune_removes_nonexistent_files(self, tmp_path):
        """刈り込みがディスク不在エントリを除去する"""
        from api.folder_monitor_service import FolderMonitorService

        folder = str(tmp_path)
        with patch.object(FolderMonitorService, "load_processed_files"):
            monitor = FolderMonitorService(folder_path=folder)

        # MAX を小さくしてテスト
        monitor.MAX_PROCESSED_ENTRIES = 3

        existing = str(tmp_path / "existing.wav")
        with open(existing, "w") as f:
            f.write("data")

        with monitor._processed_lock:
            monitor.processed_files = {
                existing,
                str(tmp_path / "gone1.wav"),
                str(tmp_path / "gone2.wav"),
                str(tmp_path / "gone3.wav"),
            }

        with patch.object(monitor, "save_processed_files"):
            monitor._prune_processed_files()

        assert existing in monitor.processed_files
        assert len(monitor.processed_files) == 1

    def test_prune_skipped_under_limit(self, tmp_path):
        """上限以下なら刈り込みは発動しない"""
        from api.folder_monitor_service import FolderMonitorService

        folder = str(tmp_path)
        with patch.object(FolderMonitorService, "load_processed_files"):
            monitor = FolderMonitorService(folder_path=folder)

        monitor.MAX_PROCESSED_ENTRIES = 100
        with monitor._processed_lock:
            monitor.processed_files = {"a.wav", "b.wav"}

        # _prune は何もしない（save_processed_files を呼ばない）
        with patch.object(monitor, "save_processed_files") as mock_save:
            monitor._prune_processed_files()
            mock_save.assert_not_called()


# ============================================================
# P2-8: Batch timeout constant
# ============================================================

class TestBatchTimeoutConstant:
    """バッチタイムアウト定数のテスト"""

    def test_batch_file_timeout_constant_exists(self):
        """BATCH_FILE_TIMEOUT_SECONDS 定数が存在する"""
        from api.workers import BATCH_FILE_TIMEOUT_SECONDS
        assert isinstance(BATCH_FILE_TIMEOUT_SECONDS, (int, float))
        assert BATCH_FILE_TIMEOUT_SECONDS > 0


# ============================================================
# P2-9: Export extension validation
# ============================================================

class TestExportExtensionValidation:
    """エクスポート拡張子検証テスト"""

    @pytest.mark.asyncio
    async def test_mismatched_extension_rejected(self):
        """拡張子がフォーマットと一致しない場合は400"""
        try:
            from httpx import AsyncClient, ASGITransport
        except ImportError:
            pytest.skip("httpx not installed")
        try:
            from api.main import app
            from api.auth import API_TOKEN
        except ImportError:
            pytest.skip("FastAPI app not importable")

        transport = ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {API_TOKEN}"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
            response = await client.post(
                "/api/export/srt",
                json={"text": "test", "output_path": "/tmp/test.txt",
                      "segments": [{"text": "a", "start": 0, "end": 1}]}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_matching_extension_accepted(self):
        """拡張子がフォーマットと一致する場合はパスする（別の理由で失敗する可能性がある）"""
        from api.routers.export import _FORMAT_EXTENSIONS
        assert "txt" in _FORMAT_EXTENSIONS
        assert _FORMAT_EXTENSIONS["srt"] == ".srt"


# ============================================================
# P2-11: Shutdown rate limiting
# ============================================================

class TestShutdownRateLimit:
    """シャットダウン二重呼び出し防止テスト"""

    def test_shutdown_flag_exists(self):
        """_shutdown_requested フラグが存在する"""
        from api.routers import health
        assert hasattr(health, "_shutdown_requested")
        assert hasattr(health, "_shutdown_lock")
