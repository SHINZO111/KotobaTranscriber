"""
memory_optimizer.py - メモリ最適化ユーティリティ

長時間実行時のメモリリーク防止と最適化を行う
"""

import gc

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MemoryStatus:
    """メモリ状態"""

    rss_mb: float
    vms_mb: float
    system_percent: float
    system_available_mb: float
    cuda_allocated_mb: Optional[float] = None
    cuda_reserved_mb: Optional[float] = None
    level: str = "normal"  # normal, warning, critical


class MemoryOptimizer:
    """
    メモリ最適化ユーティリティ

    推論処理の前後でメモリをクリーンアップし、
    メモリリークを検出・防止する
    """

    def __init__(self, warning_threshold_mb: int = 6144, critical_threshold_mb: int = 8192):
        """
        初期化

        Args:
            warning_threshold_mb: 警告閾値（MB）
            critical_threshold_mb: クリティカル閾値（MB）
        """
        self.warning_threshold = warning_threshold_mb
        self.critical_threshold = critical_threshold_mb
        self._baseline_memory = 0
        self._peak_memory: float = 0.0
        # psutil.Process をキャッシュ（毎回生成のオーバーヘッド削減）
        self._process = psutil.Process() if PSUTIL_AVAILABLE else None

    @contextmanager
    def optimized_inference(self, device: str = "cuda"):
        """
        推論用コンテキストマネージャ

        使用例:
            optimizer = MemoryOptimizer()
            with optimizer.optimized_inference("cuda"):
                result = model(input_data)

        Args:
            device: デバイス名（"cuda", "cpu", "mps"）
        """
        try:
            # 推論前のクリーンアップ
            self._pre_inference_cleanup(device)

            yield self

        finally:
            # 推論後のクリーンアップ
            self._post_inference_cleanup(device)

    def _pre_inference_cleanup(self, device: str):
        """推論前クリーンアップ"""
        gc.collect()

        if TORCH_AVAILABLE and device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

            # ベースライン記録
            self._baseline_memory = torch.cuda.memory_allocated() / (1024**2)
            logger.debug(f"Pre-inference CUDA memory: {self._baseline_memory:.1f}MB")

    def _post_inference_cleanup(self, device: str):
        """推論後クリーンアップ"""
        gc.collect()

        if TORCH_AVAILABLE and device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()

            # メモリリークチェック
            current_memory = torch.cuda.memory_allocated() / (1024**2)
            self._peak_memory = max(self._peak_memory, current_memory)

            if current_memory > self._baseline_memory * 1.5:
                logger.warning(f"Potential memory leak detected: " f"{self._baseline_memory:.1f}MB -> {current_memory:.1f}MB")

    def check_memory(self, action: Optional[Callable] = None) -> MemoryStatus:
        """
        メモリ状態をチェック

        Args:
            action: クリティカル時に実行するコールバック関数

        Returns:
            MemoryStatus: メモリ状態
        """
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available, memory check limited")
            return MemoryStatus(rss_mb=0, vms_mb=0, system_percent=0, system_available_mb=0)

        memory_info = self._process.memory_info()
        system_memory = psutil.virtual_memory()

        status = MemoryStatus(
            rss_mb=memory_info.rss / (1024 * 1024),
            vms_mb=memory_info.vms / (1024 * 1024),
            system_percent=system_memory.percent,
            system_available_mb=system_memory.available / (1024 * 1024),
        )

        # CUDA情報
        if TORCH_AVAILABLE and torch.cuda.is_available():
            status.cuda_allocated_mb = torch.cuda.memory_allocated() / (1024**2)
            status.cuda_reserved_mb = torch.cuda.memory_reserved() / (1024**2)

        # 閾値チェック
        if status.rss_mb > self.critical_threshold:
            status.level = "critical"
            logger.error(f"CRITICAL: Memory usage {status.rss_mb:.0f}MB")
            if action:
                action()
        elif status.rss_mb > self.warning_threshold:
            status.level = "warning"
            logger.warning(f"WARNING: Memory usage {status.rss_mb:.0f}MB")

        return status

    def force_cleanup(self):
        """強制クリーンアップ"""
        gc.collect()

        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        logger.info("Forced memory cleanup completed")

    def get_peak_memory(self) -> Dict[str, float]:
        """ピークメモリ使用量を取得"""
        result = {"peak_mb": self._peak_memory}

        if TORCH_AVAILABLE and torch.cuda.is_available():
            result["cuda_peak_mb"] = torch.cuda.max_memory_allocated() / (1024**2)
            torch.cuda.reset_peak_memory_stats()

        return result


if TORCH_AVAILABLE:

    class MemoryEfficientModel:
        """
        メモリ効率的なモデルラッパー

        大きなモデルをチャンク単位で処理する
        """

        def __init__(self, model: torch.nn.Module, max_chunk_size: int = 1000):
            self.model = model
            self.max_chunk_size = max_chunk_size
            self.optimizer = MemoryOptimizer()

        def process_in_chunks(self, data: torch.Tensor, process_fn: Optional[Callable] = None) -> torch.Tensor:
            """
            データをチャンク単位で処理

            Args:
                data: 入力テンソル
                process_fn: 処理関数（Noneの場合はモデルのforward）

            Returns:
                処理結果
            """
            if process_fn is None:
                process_fn = self.model

            results = []

            with self.optimizer.optimized_inference(str(data.device)):
                for i in range(0, len(data), self.max_chunk_size):
                    chunk = data[i : i + self.max_chunk_size]

                    with torch.no_grad():
                        result = process_fn(chunk)

                    results.append(result.cpu())  # GPUメモリ解放のためCPUに移動

                    # 定期的なクリーンアップ
                    if i % (self.max_chunk_size * 10) == 0:
                        self.optimizer.force_cleanup()

            return torch.cat(results, dim=0)


if __name__ == "__main__":
    # テスト
    logging.basicConfig(level=logging.INFO)

    print("=== MemoryOptimizer Test ===\n")

    optimizer = MemoryOptimizer()

    # メモリ状態チェック
    print("1. Memory Status Check:")
    status = optimizer.check_memory()
    print(f"   RSS: {status.rss_mb:.1f}MB")
    print(f"   System: {status.system_percent:.1f}%")
    if status.cuda_allocated_mb:
        print(f"   CUDA Allocated: {status.cuda_allocated_mb:.1f}MB")

    # コンテキストマネージャテスト
    print("\n2. Context Manager Test:")
    device = "cuda" if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
    with optimizer.optimized_inference(device):
        print("   Inside optimized context")
        if TORCH_AVAILABLE and torch.cuda.is_available():
            x = torch.randn(1000, 1000, device="cuda")
            y = x @ x.T
            del x, y
    print("   Outside optimized context")

    # ピークメモリ
    print("\n3. Peak Memory:")
    peaks = optimizer.get_peak_memory()
    for key, value in peaks.items():
        print(f"   {key}: {value:.1f}MB")

    print("\nTest completed!")
