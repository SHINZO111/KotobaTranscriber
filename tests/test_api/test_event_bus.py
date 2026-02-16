"""EventBus 単体テスト"""

import asyncio
import os
import sys
import threading
import time

import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from api.event_bus import EventBus


class TestEventBus:
    """EventBus テスト"""

    def test_init(self):
        """初期化"""
        bus = EventBus()
        assert bus.subscriber_count() == 0

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        """購読とイベント発行"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received = []

        async def consumer():
            async for event in bus.subscribe():
                received.append(event)
                if len(received) >= 2:
                    break

        # 少し待ってからイベントを発行
        async def producer():
            await asyncio.sleep(0.05)
            bus.emit("test", {"value": 1})
            await asyncio.sleep(0.05)
            bus.emit("test", {"value": 2})

        await asyncio.wait_for(asyncio.gather(consumer(), producer()), timeout=3.0)

        assert len(received) == 2
        assert received[0]["type"] == "test"
        assert received[0]["data"]["value"] == 1
        assert received[1]["data"]["value"] == 2

    @pytest.mark.asyncio
    async def test_subscriber_count(self):
        """サブスクライバーカウント"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        assert bus.subscriber_count() == 0

        async def short_consumer():
            async for event in bus.subscribe():
                break

        task = asyncio.create_task(short_consumer())
        await asyncio.sleep(0.05)
        assert bus.subscriber_count() == 1

        bus.emit("stop", {})
        await asyncio.sleep(0.05)
        await task
        assert bus.subscriber_count() == 0

    @pytest.mark.asyncio
    async def test_emit_from_thread(self):
        """別スレッドからの emit"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received = []

        async def consumer():
            async for event in bus.subscribe():
                received.append(event)
                if len(received) >= 1:
                    break

        def thread_emitter():
            time.sleep(0.1)
            bus.emit("from_thread", {"thread": True})

        t = threading.Thread(target=thread_emitter)
        t.start()

        await asyncio.wait_for(consumer(), timeout=3.0)
        t.join()

        assert len(received) == 1
        assert received[0]["type"] == "from_thread"
        assert received[0]["data"]["thread"] is True

    def test_emit_no_subscribers(self):
        """サブスクライバーなしでの emit（エラーにならないこと）"""
        bus = EventBus()
        bus.emit("no_one_listening", {"data": True})
        # エラーが出ないことを確認

    @pytest.mark.asyncio
    async def test_event_has_timestamp(self):
        """イベントにタイムスタンプが含まれること"""
        bus = EventBus()
        loop = asyncio.get_running_loop()
        bus.set_loop(loop)

        received = []

        async def consumer():
            async for event in bus.subscribe():
                received.append(event)
                break

        async def producer():
            await asyncio.sleep(0.05)
            bus.emit("ts_test", {})

        await asyncio.wait_for(asyncio.gather(consumer(), producer()), timeout=3.0)

        assert "timestamp" in received[0]
        assert isinstance(received[0]["timestamp"], float)
