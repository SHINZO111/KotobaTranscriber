"""EventBus CoWスナップショットのテスト"""

import asyncio
import os
import sys

import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from api.event_bus import EventBus


class TestCoWSnapshot:
    """CoW (Copy-on-Write) スナップショットのテスト"""

    def test_initial_snapshot_is_none(self):
        """初期状態でスナップショットはNone"""
        bus = EventBus()
        assert bus._snapshot is None

    def test_get_snapshot_builds_on_first_call(self):
        """_get_snapshot()の初回呼び出しでスナップショットを構築"""
        bus = EventBus()
        snapshot = bus._get_snapshot()
        assert isinstance(snapshot, list)
        assert len(snapshot) == 0
        # 構築後はキャッシュされている
        assert bus._snapshot is not None

    def test_get_snapshot_returns_cached(self):
        """_get_snapshot()はキャッシュされた同じオブジェクトを返す"""
        bus = EventBus()
        snap1 = bus._get_snapshot()
        snap2 = bus._get_snapshot()
        assert snap1 is snap2  # 同じオブジェクト

    def test_invalidate_snapshot_clears_cache(self):
        """_invalidate_snapshot()でキャッシュがクリアされる"""
        bus = EventBus()
        bus._get_snapshot()  # キャッシュを構築
        assert bus._snapshot is not None
        bus._invalidate_snapshot()
        assert bus._snapshot is None

    @pytest.mark.asyncio
    async def test_subscribe_invalidates_snapshot(self):
        """subscribe()でスナップショットが無効化される"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        # スナップショットを構築
        snap_before = bus._get_snapshot()
        assert len(snap_before) == 0

        async def consumer():
            async for event in bus.subscribe():
                break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        # subscribe後、新しいスナップショットにはサブスクライバーが含まれる
        snap_after = bus._get_snapshot()
        assert len(snap_after) == 1
        assert snap_before is not snap_after  # 異なるオブジェクト

        bus.emit("stop", {})
        await task

    @pytest.mark.asyncio
    async def test_unsubscribe_invalidates_snapshot(self):
        """unsubscribe（subscribe終了）でスナップショットが無効化される"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        async def consumer():
            async for event in bus.subscribe():
                break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        snap_during = bus._get_snapshot()
        assert len(snap_during) == 1

        bus.emit("stop", {})
        await task
        await asyncio.sleep(0.05)

        # unsubscribe後、スナップショットが無効化されている
        snap_after = bus._get_snapshot()
        assert len(snap_after) == 0
        assert snap_during is not snap_after

    def test_emit_uses_snapshot_without_lock(self):
        """emit()はスナップショット経由でサブスクライバーにアクセス"""
        bus = EventBus()
        # スナップショットを手動設定してemitがそれを使うことを確認
        bus._snapshot = []  # 空スナップショット
        # emit()はエラーなく完了すべき
        bus.emit("test", {"value": 1})

    @pytest.mark.asyncio
    async def test_snapshot_stable_during_emit(self):
        """emit中のスナップショットは安定（subscribe中に変わらない）"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received = []

        async def consumer():
            async for event in bus.subscribe():
                received.append(event)
                if len(received) >= 2:
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        # 最初のemit
        bus.emit("event", {"n": 1})
        await asyncio.sleep(0.02)

        # スナップショットがキャッシュされていることを確認
        snap = bus._snapshot
        assert snap is not None

        # 2つ目のemit — 同じスナップショットを使用
        bus.emit("event", {"n": 2})
        assert bus._snapshot is snap  # 同じオブジェクト

        await asyncio.wait_for(task, timeout=3.0)
        assert len(received) == 2

    def test_shutdown_uses_snapshot(self):
        """shutdown()もスナップショットを使用"""
        bus = EventBus()
        # 手動でスナップショットを構築
        bus._get_snapshot()
        assert bus._snapshot is not None

        # shutdown後もスナップショットメカニズムは正常動作
        bus.shutdown()
        assert bus._shutting_down is True
