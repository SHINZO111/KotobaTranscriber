"""
WebSocket 接続管理
EventBus → WebSocket ブリッジ。
"""

import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 接続管理（接続トラッキングのみ）"""

    MAX_CONNECTIONS = 10  # 最大同時接続数

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> bool:
        """新しいWebSocket接続を受け入れ。成功時True、拒否時False。"""
        if len(self.active_connections) >= self.MAX_CONNECTIONS:
            await websocket.close(code=1008, reason="Maximum connections reached")
            logger.warning(f"WebSocket rejected: max connections ({self.MAX_CONNECTIONS}) reached")
            return False
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Active: {len(self.active_connections)}")
        return True

    def disconnect(self, websocket: WebSocket):
        """WebSocket接続を削除"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: dict):
        """全接続にイベントをブロードキャスト"""
        if not self.active_connections:
            return

        message = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        disconnected = set()

        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)

        for conn in disconnected:
            self.active_connections.discard(conn)

    def connection_count(self) -> int:
        """アクティブ接続数"""
        return len(self.active_connections)


# グローバルシングルトン
manager = ConnectionManager()
