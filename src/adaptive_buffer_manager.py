"""
適応型バッファマネージャ
システムメモリ使用量に基づいてバッファサイズを動的に調整する
"""

import psutil
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import time

logger = logging.getLogger(__name__)


class MemoryPressureLevel(Enum):
    """メモリ圧迫レベル"""
    LOW = "low"           # < 50% 使用
    MODERATE = "moderate" # 50-70% 使用
    HIGH = "high"         # 70-85% 使用
    CRITICAL = "critical" # > 85% 使用


@dataclass
class BufferStats:
    """バッファ統計情報"""
    current_size: int
    min_size: int
    max_size: int
    memory_percent: float
    pressure_level: MemoryPressureLevel
    adjustment_count: int
    last_adjustment_time: float


class AdaptiveBufferManager:
    """
    適応型バッファマネージャ

    システムメモリ使用量に応じてバッファサイズを動的に調整し、
    メモリ効率を最適化する。

    使用例:
        buffer_manager = AdaptiveBufferManager(min_size=1000, max_size=100000)
        optimal_size = buffer_manager.adjust_buffer_size()
        buffer_manager.update_statistics()
    """

    # 調整係数
    SHRINK_FACTOR = 0.7      # メモリ圧迫時の縮小率
    GROW_FACTOR = 1.3        # メモリ余裕時の拡大率
    AGGRESSIVE_SHRINK = 0.5  # 重大な圧迫時の縮小率

    # メモリ閾値
    THRESHOLD_LOW = 50.0       # 低圧力閾値
    THRESHOLD_MODERATE = 70.0  # 中圧力閾値
    THRESHOLD_HIGH = 85.0      # 高圧力閾値

    def __init__(
        self,
        min_size: int = 1000,
        max_size: int = 100000,
        enable_adaptive: bool = True,
        check_interval: float = 5.0
    ):
        """
        初期化

        Args:
            min_size: 最小バッファサイズ（要素数）
            max_size: 最大バッファサイズ（要素数）
            enable_adaptive: 適応的調整を有効化
            check_interval: メモリチェック間隔（秒）
        """
        if min_size <= 0 or max_size <= 0:
            raise ValueError("Buffer sizes must be positive")
        if min_size > max_size:
            raise ValueError("min_size must be <= max_size")

        self.min_size = min_size
        self.max_size = max_size
        self.current_size = min_size
        self.enable_adaptive = enable_adaptive
        self.check_interval = check_interval

        # 統計情報
        self._adjustment_count = 0
        self._last_adjustment_time = time.time()
        self._last_check_time = 0.0
        self._memory_history = []  # 最近のメモリ使用率履歴
        self._history_size = 10

        logger.info(
            f"AdaptiveBufferManager initialized: min={min_size}, max={max_size}, "
            f"adaptive={enable_adaptive}"
        )

    def adjust_buffer_size(self, force: bool = False) -> int:
        """
        メモリ使用量に基づいてバッファサイズを調整

        Args:
            force: 強制的に調整（check_intervalを無視）

        Returns:
            調整後のバッファサイズ
        """
        if not self.enable_adaptive:
            return self.current_size

        # チェック間隔の確認
        current_time = time.time()
        if not force and (current_time - self._last_check_time) < self.check_interval:
            return self.current_size

        self._last_check_time = current_time

        try:
            # メモリ情報取得
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # メモリ履歴に追加
            self._memory_history.append(memory_percent)
            if len(self._memory_history) > self._history_size:
                self._memory_history.pop(0)

            # 圧力レベル判定
            pressure_level = self._get_pressure_level(memory_percent)
            old_size = self.current_size

            # 圧力レベルに応じた調整
            if pressure_level == MemoryPressureLevel.CRITICAL:
                # 重大: 大幅に縮小
                self.current_size = max(
                    self.min_size,
                    int(self.current_size * self.AGGRESSIVE_SHRINK)
                )
                logger.warning(
                    f"CRITICAL memory pressure ({memory_percent:.1f}%): "
                    f"Buffer shrunk {old_size} -> {self.current_size}"
                )

            elif pressure_level == MemoryPressureLevel.HIGH:
                # 高圧力: 縮小
                self.current_size = max(
                    self.min_size,
                    int(self.current_size * self.SHRINK_FACTOR)
                )
                logger.warning(
                    f"HIGH memory pressure ({memory_percent:.1f}%): "
                    f"Buffer shrunk {old_size} -> {self.current_size}"
                )

            elif pressure_level == MemoryPressureLevel.MODERATE:
                # 中圧力: 現状維持またはわずかに縮小
                if self.current_size > self.min_size * 1.5:
                    self.current_size = max(
                        self.min_size,
                        int(self.current_size * 0.9)
                    )
                    logger.info(
                        f"MODERATE memory pressure ({memory_percent:.1f}%): "
                        f"Buffer slightly reduced {old_size} -> {self.current_size}"
                    )

            elif pressure_level == MemoryPressureLevel.LOW:
                # 低圧力: 拡大可能
                avg_memory = sum(self._memory_history) / len(self._memory_history)
                if avg_memory < self.THRESHOLD_LOW and self.current_size < self.max_size:
                    self.current_size = min(
                        self.max_size,
                        int(self.current_size * self.GROW_FACTOR)
                    )
                    logger.info(
                        f"LOW memory pressure ({memory_percent:.1f}%): "
                        f"Buffer expanded {old_size} -> {self.current_size}"
                    )

            # 調整が発生した場合の記録
            if old_size != self.current_size:
                self._adjustment_count += 1
                self._last_adjustment_time = current_time

            return self.current_size

        except Exception as e:
            logger.error(f"Failed to adjust buffer size: {e}")
            # エラー時は安全側に倒してmin_sizeを返す
            self.current_size = self.min_size
            return self.current_size

    def _get_pressure_level(self, memory_percent: float) -> MemoryPressureLevel:
        """
        メモリ使用率から圧力レベルを判定

        Args:
            memory_percent: メモリ使用率（%）

        Returns:
            圧力レベル
        """
        if memory_percent >= self.THRESHOLD_HIGH:
            return MemoryPressureLevel.CRITICAL
        elif memory_percent >= self.THRESHOLD_MODERATE:
            return MemoryPressureLevel.HIGH
        elif memory_percent >= self.THRESHOLD_LOW:
            return MemoryPressureLevel.MODERATE
        else:
            return MemoryPressureLevel.LOW

    def get_current_size(self) -> int:
        """現在のバッファサイズを取得"""
        return self.current_size

    def get_statistics(self) -> BufferStats:
        """
        統計情報を取得

        Returns:
            バッファ統計情報
        """
        try:
            memory = psutil.virtual_memory()
            pressure_level = self._get_pressure_level(memory.percent)

            return BufferStats(
                current_size=self.current_size,
                min_size=self.min_size,
                max_size=self.max_size,
                memory_percent=memory.percent,
                pressure_level=pressure_level,
                adjustment_count=self._adjustment_count,
                last_adjustment_time=self._last_adjustment_time
            )
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return BufferStats(
                current_size=self.current_size,
                min_size=self.min_size,
                max_size=self.max_size,
                memory_percent=0.0,
                pressure_level=MemoryPressureLevel.LOW,
                adjustment_count=self._adjustment_count,
                last_adjustment_time=self._last_adjustment_time
            )

    def get_memory_info(self) -> Dict[str, Any]:
        """
        現在のメモリ情報を取得

        Returns:
            メモリ情報の辞書
        """
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "total_mb": memory.total / (1024 ** 2),
                "available_mb": memory.available / (1024 ** 2),
                "used_mb": memory.used / (1024 ** 2),
                "percent": memory.percent,
                "swap_percent": swap.percent,
                "pressure_level": self._get_pressure_level(memory.percent).value,
                "buffer_size": self.current_size,
                "buffer_utilization": (self.current_size - self.min_size) / (self.max_size - self.min_size) * 100
                    if self.max_size > self.min_size else 0.0
            }
        except Exception as e:
            logger.error(f"Failed to get memory info: {e}")
            return {
                "error": str(e),
                "buffer_size": self.current_size
            }

    def update_statistics(self) -> None:
        """統計情報を更新（ロギング目的）"""
        stats = self.get_statistics()
        logger.debug(
            f"Buffer stats: size={stats.current_size}, "
            f"memory={stats.memory_percent:.1f}%, "
            f"pressure={stats.pressure_level.value}, "
            f"adjustments={stats.adjustment_count}"
        )

    def reset(self) -> None:
        """バッファサイズを最小値にリセット"""
        old_size = self.current_size
        self.current_size = self.min_size
        self._adjustment_count = 0
        self._memory_history.clear()
        logger.info(f"Buffer reset: {old_size} -> {self.current_size}")

    def set_size_limits(self, min_size: Optional[int] = None, max_size: Optional[int] = None) -> None:
        """
        バッファサイズの制限を更新

        Args:
            min_size: 新しい最小サイズ
            max_size: 新しい最大サイズ
        """
        if min_size is not None:
            if min_size <= 0:
                raise ValueError("min_size must be positive")
            self.min_size = min_size

        if max_size is not None:
            if max_size <= 0:
                raise ValueError("max_size must be positive")
            self.max_size = max_size

        if self.min_size > self.max_size:
            raise ValueError("min_size must be <= max_size")

        # 現在のサイズを範囲内に調整
        self.current_size = max(self.min_size, min(self.current_size, self.max_size))

        logger.info(f"Buffer limits updated: min={self.min_size}, max={self.max_size}")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== AdaptiveBufferManager Test ===\n")

    # バッファマネージャ作成
    manager = AdaptiveBufferManager(min_size=1000, max_size=100000)

    # 現在のメモリ情報表示
    print("Current Memory Info:")
    mem_info = manager.get_memory_info()
    for key, value in mem_info.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    print(f"\nInitial buffer size: {manager.get_current_size()}")

    # 調整テスト
    print("\nPerforming buffer adjustments based on memory pressure...")
    for i in range(5):
        new_size = manager.adjust_buffer_size(force=True)
        stats = manager.get_statistics()
        print(f"\nIteration {i+1}:")
        print(f"  Buffer size: {new_size}")
        print(f"  Memory: {stats.memory_percent:.1f}%")
        print(f"  Pressure: {stats.pressure_level.value}")
        print(f"  Total adjustments: {stats.adjustment_count}")
        time.sleep(1)

    # 最終統計
    print("\n=== Final Statistics ===")
    final_stats = manager.get_statistics()
    print(f"Final buffer size: {final_stats.current_size}")
    print(f"Total adjustments: {final_stats.adjustment_count}")
    print(f"Memory pressure: {final_stats.pressure_level.value}")

    print("\nTest completed successfully")
