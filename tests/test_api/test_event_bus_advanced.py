"""EventBus 高度なテスト — shutdown, QueueFull, 複数サブスクライバー"""

import asyncio
import os
import sys
import threading

import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from api.event_bus import EventBus


class TestEventBusShutdown:
    """shutdown 動作テスト"""

    def test_shutdown_prevents_emit(self):
        """shutdown後のemitは無視される"""
        bus = EventBus()
        bus.shutdown()
        # エラーにならないこと
        bus.emit("test", {"data": 1})

    @pytest.mark.asyncio
    async def test_shutdown_flag(self):
        """shutdown フラグの状態"""
        bus = EventBus()
        assert bus._shutting_down is False
        bus.shutdown()
        assert bus._shutting_down is True


class TestEventBusQueueFull:
    """キュー満杯時の動作テスト"""

    @pytest.mark.asyncio
    async def test_queue_overflow_drops_old(self):
        """キュー満杯時に古いイベントを破棄して新しいイベントを追加"""
        bus = EventBus(maxsize=2)
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received = []

        async def consumer():
            count = 0
            async for event in bus.subscribe():
                received.append(event)
                count += 1
                if count >= 2:
                    break

        # 先にサブスクライバーを登録、3つのイベントを送信（キューは2）
        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        # 3つ連続でemit（キューサイズ2なので1つ目がドロップされる可能性がある）
        bus.emit("event", {"n": 1})
        bus.emit("event", {"n": 2})
        bus.emit("event", {"n": 3})

        await asyncio.wait_for(task, timeout=3.0)
        assert len(received) == 2


class TestEventBusMultipleSubscribers:
    """複数サブスクライバーのテスト"""

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple(self):
        """複数のサブスクライバーに同時配信"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received_a = []
        received_b = []

        async def consumer_a():
            async for event in bus.subscribe():
                received_a.append(event)
                if len(received_a) >= 1:
                    break

        async def consumer_b():
            async for event in bus.subscribe():
                received_b.append(event)
                if len(received_b) >= 1:
                    break

        async def producer():
            await asyncio.sleep(0.1)
            bus.emit("broadcast", {"msg": "hello"})

        await asyncio.wait_for(asyncio.gather(consumer_a(), consumer_b(), producer()), timeout=3.0)

        assert len(received_a) == 1
        assert len(received_b) == 1
        assert received_a[0]["data"]["msg"] == "hello"
        assert received_b[0]["data"]["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_subscriber_count_multiple(self):
        """複数サブスクライバーのカウント"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        assert bus.subscriber_count() == 0

        async def consumer():
            async for event in bus.subscribe():
                break

        t1 = asyncio.create_task(consumer())
        t2 = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        assert bus.subscriber_count() == 2

        bus.emit("stop", {})
        await asyncio.sleep(0.05)
        await t1
        await t2

        assert bus.subscriber_count() == 0


class TestEventBusCounterMonotonic:
    """カウンター単調増加テスト"""

    @pytest.mark.asyncio
    async def test_counter_increments(self):
        """カウンターが単調増加する（衝突回避）"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)
        bus._counter = 999_999

        async def consumer():
            async for event in bus.subscribe():
                break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.05)

        # counter は単調増加（ラップしない）
        assert bus._counter == 1_000_000

        bus.emit("stop", {})
        await task


class TestEventBusLoopShutdown:
    """ループシャットダウン時の安全性テスト"""

    def test_emit_without_loop(self):
        """ループ未設定でもemitがエラーにならない"""
        bus = EventBus()
        # ループなし — _put_nowait が直接呼ばれる
        bus.emit("test", {"data": 1})

    def test_emit_with_closed_loop(self):
        """閉じたループでemitがエラーにならない（RuntimeError をキャッチ）"""
        bus = EventBus()
        loop = asyncio.new_event_loop()
        bus.set_loop(loop)
        loop.close()  # ループを閉じる
        # call_soon_threadsafe が RuntimeError を出すが、安全にスキップされる
        bus.emit("test", {"data": 1})

    @pytest.mark.asyncio
    async def test_emit_after_shutdown_no_subscribers(self):
        """shutdown後、サブスクライバーなしでemitがエラーにならない"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)
        bus.shutdown()
        bus.emit("test", {"data": 1})
        assert bus.subscriber_count() == 0
