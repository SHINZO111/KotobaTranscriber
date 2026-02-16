"""
EventBus — Qt Signal の代替
asyncio.Queue ベースのイベント配信システム。
WebSocket ブリッジやワーカースレッドからの通知に使用。
"""

import asyncio
import logging
import queue
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
        # フォールバック: イベントループ未設定時の threading.Queue
        self._fallback_queues: Dict[int, queue.Queue] = {}

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
        for sub_id, sub_queue in subscribers:
            try:
                sub_queue.put_nowait(sentinel)
            except (asyncio.QueueFull, Exception):
                pass

    def emit(self, event_type: str, data: Optional[dict] = None):
        """
        イベントを発行（同期コンテキストから呼び出し可能）。
        全サブスクライバーのキューにイベントを追加。

        スレッドセーフ実装:
        - イベントループが稼働中 → call_soon_threadsafe() 経由で asyncio.Queue に追加
        - イベントループ未設定 → threading.Queue にフォールバック
        """
        if self._shutting_down:
            return

        event = {
            "type": event_type,
            "data": data or {},
            "timestamp": time.time(),
        }

        subscribers = self._get_snapshot()

        for sub_id, async_queue in subscribers:
            try:
                if self._loop and self._loop.is_running():
                    # asyncio.Queue への追加（スレッドセーフ）
                    try:
                        self._loop.call_soon_threadsafe(self._put_nowait, async_queue, event, sub_id)
                    except RuntimeError:
                        # イベントループが停止中 — フォールバックに移行
                        logger.debug("Event loop closing, falling back to threading.Queue")
                        self._put_to_fallback(sub_id, event)
                else:
                    # イベントループ未設定 — フォールバックキューを使用
                    self._put_to_fallback(sub_id, event)
            except Exception:
                # 汎用的なエラーログ（情報漏洩防止）
                logger.debug(f"Failed to emit event to subscriber {sub_id}")

    def _put_nowait(self, async_queue: asyncio.Queue, event: dict, sub_id: int):
        """
        asyncio.Queue にイベントを追加（満杯時は古いイベントを破棄）
        注: この関数はイベントループスレッド内で実行される（call_soon_threadsafe 経由）
        """
        try:
            async_queue.put_nowait(event)
        except asyncio.QueueFull:
            # 古いイベントを1つ破棄して再試行
            try:
                async_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                async_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Event dropped for subscriber {sub_id}")

    def _put_to_fallback(self, sub_id: int, event: dict):
        """
        フォールバック用の threading.Queue にイベントを追加
        注: イベントループ未設定時や停止中に使用
        """
        with self._lock:
            fallback_q = self._fallback_queues.get(sub_id)
            if fallback_q is None:
                fallback_q = queue.Queue(maxsize=self._maxsize)
                self._fallback_queues[sub_id] = fallback_q

        try:
            fallback_q.put_nowait(event)
        except queue.Full:
            # 古いイベントを破棄して再試行
            try:
                fallback_q.get_nowait()
            except queue.Empty:
                pass
            try:
                fallback_q.put_nowait(event)
            except queue.Full:
                logger.warning(f"Fallback event dropped for subscriber {sub_id}")

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        """
        イベントストリームを購読。
        async for で使用:
            async for event in bus.subscribe():
                print(event)

        注: 購読開始時にフォールバックキューからイベントを移行しない。
        フォールバックキューは購読解除時にクリーンアップされる。
        """
        async_queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        with self._lock:
            self._counter += 1
            sub_id = self._counter
            self._subscribers[sub_id] = async_queue
            self._invalidate_snapshot()

        logger.debug(f"Subscriber {sub_id} registered")
        try:
            while True:
                event = await async_queue.get()
                if event.get("type") == "__shutdown__":
                    break
                yield event
        finally:
            with self._lock:
                self._subscribers.pop(sub_id, None)
                # フォールバックキューもクリーンアップ
                if sub_id in self._fallback_queues:
                    del self._fallback_queues[sub_id]
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
