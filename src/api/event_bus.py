"""
EventBus — Qt Signal の代替
asyncio.Queue ベースのイベント配信システム。
WebSocket ブリッジやワーカースレッドからの通知に使用。
"""

import asyncio
import logging
import threading
import time
from typing import AsyncGenerator, Dict, Optional

logger = logging.getLogger(__name__)


class EventBus:
    """
    スレッドセーフな非同期イベントバス。

    - ワーカースレッド（sync）から emit() でイベントを発行
    - WebSocket ハンドラ（async）から subscribe() でイベントを受信
    - 複数のサブスクライバーに同時配信（ブロードキャスト）
    """

    def __init__(self, maxsize: int = 1000):
        self._subscribers: Dict[int, asyncio.Queue] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._maxsize = maxsize
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutting_down = False
        # CoW スナップショット: subscribe/unsubscribe 時にのみ再構築
        self._snapshot: Optional[list] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """メインの asyncio イベントループを設定"""
        self._loop = loop

    def _invalidate_snapshot(self):
        """スナップショットを無効化（lock保持中に呼ぶこと）"""
        self._snapshot = None

    def _get_snapshot(self) -> list:
        """サブスクライバーのCoWスナップショットを取得"""
        with self._lock:
            if self._snapshot is None:
                self._snapshot = list(self._subscribers.items())
            return self._snapshot

    def shutdown(self):
        """シャットダウンフラグを設定し、全サブスクライバーにセンチネルを送信"""
        self._shutting_down = True
        sentinel = {"type": "__shutdown__", "data": {}, "timestamp": time.time()}
        subscribers = self._get_snapshot()
        for sub_id, queue in subscribers:
            try:
                queue.put_nowait(sentinel)
            except (asyncio.QueueFull, Exception):
                pass

    def emit(self, event_type: str, data: Optional[dict] = None):
        """
        イベントを発行（同期コンテキストから呼び出し可能）。
        全サブスクライバーのキューにイベントを追加。
        """
        if self._shutting_down:
            return

        event = {
            "type": event_type,
            "data": data or {},
            "timestamp": time.time(),
        }

        subscribers = self._get_snapshot()

        for sub_id, queue in subscribers:
            try:
                if self._loop and self._loop.is_running():
                    try:
                        self._loop.call_soon_threadsafe(
                            self._put_nowait, queue, event, sub_id
                        )
                    except RuntimeError:
                        # ループが停止中 — asyncio.Queue はスレッドセーフではないため
                        # 非イベントループスレッドからの直接操作をスキップ
                        logger.debug(f"Event loop closing, event dropped for subscriber {sub_id}")
                else:
                    # ループ未設定時は直接追加（テスト環境等）
                    self._put_nowait(queue, event, sub_id)
            except Exception as e:
                logger.debug(f"Failed to emit to subscriber {sub_id}: {e}")

    def _put_nowait(self, queue: asyncio.Queue, event: dict, sub_id: int):
        """キューにイベントを追加（満杯時は古いイベントを破棄）"""
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # 古いイベントを1つ破棄して再試行
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Event dropped for subscriber {sub_id}")

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        """
        イベントストリームを購読。
        async for で使用:
            async for event in bus.subscribe():
                print(event)
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        with self._lock:
            self._counter += 1
            sub_id = self._counter
            self._subscribers[sub_id] = queue
            self._invalidate_snapshot()

        logger.debug(f"Subscriber {sub_id} registered")
        try:
            while True:
                event = await queue.get()
                if event.get("type") == "__shutdown__":
                    break
                yield event
        finally:
            with self._lock:
                self._subscribers.pop(sub_id, None)
                self._invalidate_snapshot()
            logger.debug(f"Subscriber {sub_id} unregistered")

    def subscriber_count(self) -> int:
        """現在のサブスクライバー数"""
        with self._lock:
            return len(self._subscribers)


# グローバルシングルトン
_event_bus: Optional[EventBus] = None
_event_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """EventBus シングルトンを取得"""
    global _event_bus
    if _event_bus is None:
        with _event_bus_lock:
            if _event_bus is None:
                _event_bus = EventBus()
    return _event_bus
