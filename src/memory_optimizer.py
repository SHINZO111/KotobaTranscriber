"""
メモリ最適化ユーティリティ
ガベージコレクション、CUDAキャッシュ管理、メモリマッピングを提供
"""

import gc
import logging
import os
import tempfile
import numpy as np
import psutil
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)


class MemoryOptimizer:
    """
    メモリ最適化マネージャ

    ガベージコレクション、CUDAキャッシュクリア、メモリ統計を提供する。

    使用例:
        # 手動クリーンアップ
        MemoryOptimizer.cleanup()

        # コンテキストマネージャで自動クリーンアップ
        with MemoryOptimizer.auto_cleanup():
            # ... メモリを使用する処理 ...
        # 自動的にクリーンアップ
    """

    # クリーンアップ統計
    _cleanup_count = 0
    _total_freed_mb = 0.0
    _last_cleanup_time = 0.0

    @classmethod
    def cleanup(cls, aggressive: bool = False) -> Dict[str, Any]:
        """
        メモリをクリーンアップ

        Args:
            aggressive: より積極的なクリーンアップ（複数回GC実行）

        Returns:
            クリーンアップ結果の辞書
        """
        start_time = time.time()
        memory_before = cls.get_memory_usage()

        logger.info(f"Starting memory cleanup (aggressive={aggressive})...")

        try:
            # Python ガベージコレクション
            if aggressive:
                # 積極的モード: 3世代すべてを複数回収集
                for generation in [2, 1, 0]:
                    collected = gc.collect(generation)
                    logger.debug(f"GC generation {generation}: collected {collected} objects")
            else:
                # 通常モード: 1回のみ
                collected = gc.collect()
                logger.debug(f"GC collected: {collected} objects")

            # CUDA キャッシュクリア
            cuda_cleared = cls._clear_cuda_cache()

            # NumPy メモリクリーンアップ
            cls._cleanup_numpy()

            # クリーンアップ後のメモリ使用量
            memory_after = cls.get_memory_usage()
            freed_mb = memory_before["used_mb"] - memory_after["used_mb"]

            # 統計更新
            cls._cleanup_count += 1
            cls._total_freed_mb += max(0, freed_mb)
            cls._last_cleanup_time = time.time()

            cleanup_time = time.time() - start_time

            result = {
                "success": True,
                "freed_mb": freed_mb,
                "memory_before_mb": memory_before["used_mb"],
                "memory_after_mb": memory_after["used_mb"],
                "cuda_cleared": cuda_cleared,
                "cleanup_time_s": cleanup_time,
                "total_cleanups": cls._cleanup_count
            }

            logger.info(
                f"Memory cleanup completed: freed {freed_mb:.1f}MB in {cleanup_time:.2f}s "
                f"(before={memory_before['used_mb']:.1f}MB, after={memory_after['used_mb']:.1f}MB)"
            )

            return result

        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "freed_mb": 0.0
            }

    @classmethod
    def _clear_cuda_cache(cls) -> bool:
        """CUDAキャッシュをクリア"""
        try:
            import torch
            if torch.cuda.is_available():
                # すべてのCUDAデバイスのキャッシュをクリア
                torch.cuda.empty_cache()

                # CUDA同期（すべてのストリームが完了するまで待機）
                torch.cuda.synchronize()

                # 各デバイスの統計をリセット
                for device_id in range(torch.cuda.device_count()):
                    torch.cuda.reset_peak_memory_stats(device_id)
                    torch.cuda.reset_accumulated_memory_stats(device_id)

                logger.debug("CUDA cache cleared successfully")
                return True
            else:
                logger.debug("CUDA not available")
                return False

        except ImportError:
            logger.debug("PyTorch not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to clear CUDA cache: {e}")
            return False

    @classmethod
    def _cleanup_numpy(cls) -> None:
        """NumPyメモリクリーンアップ"""
        try:
            # NumPyの内部キャッシュをクリア（可能な場合）
            # Note: NumPyは明示的なキャッシュクリア機能を提供していないため、
            # ガベージコレクションに依存
            pass
        except Exception as e:
            logger.debug(f"NumPy cleanup: {e}")

    @classmethod
    @contextmanager
    def auto_cleanup(cls, aggressive: bool = False):
        """
        コンテキストマネージャで自動クリーンアップ

        Args:
            aggressive: より積極的なクリーンアップ

        使用例:
            with MemoryOptimizer.auto_cleanup():
                # ... メモリを使用する処理 ...
            # 自動的にクリーンアップ
        """
        memory_before = cls.get_memory_usage()
        logger.info(f"Entering auto-cleanup context (memory: {memory_before['used_mb']:.1f}MB)")

        try:
            yield
        finally:
            logger.info("Exiting auto-cleanup context, performing cleanup...")
            result = cls.cleanup(aggressive=aggressive)
            logger.info(f"Auto-cleanup freed {result.get('freed_mb', 0):.1f}MB")

    @classmethod
    def get_memory_usage(cls) -> Dict[str, Any]:
        """
        現在のメモリ使用量を取得

        Returns:
            メモリ情報の辞書
        """
        try:
            # システムメモリ
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # プロセスメモリ
            process = psutil.Process()
            process_info = process.memory_info()

            result = {
                # システムメモリ
                "total_mb": memory.total / (1024 ** 2),
                "available_mb": memory.available / (1024 ** 2),
                "used_mb": memory.used / (1024 ** 2),
                "percent": memory.percent,

                # スワップ
                "swap_total_mb": swap.total / (1024 ** 2),
                "swap_used_mb": swap.used / (1024 ** 2),
                "swap_percent": swap.percent,

                # プロセス
                "process_rss_mb": process_info.rss / (1024 ** 2),
                "process_vms_mb": process_info.vms / (1024 ** 2),
            }

            # CUDA メモリ（利用可能な場合）
            cuda_info = cls.get_cuda_memory()
            if cuda_info:
                result["cuda"] = cuda_info

            return result

        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {"error": str(e)}

    @classmethod
    def get_cuda_memory(cls) -> Optional[Dict[str, Any]]:
        """
        CUDAメモリ使用量を取得

        Returns:
            CUDAメモリ情報、利用不可の場合None
        """
        try:
            import torch
            if not torch.cuda.is_available():
                return None

            devices = []
            for device_id in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(device_id) / (1024 ** 2)
                reserved = torch.cuda.memory_reserved(device_id) / (1024 ** 2)
                max_allocated = torch.cuda.max_memory_allocated(device_id) / (1024 ** 2)

                devices.append({
                    "device_id": device_id,
                    "name": torch.cuda.get_device_name(device_id),
                    "allocated_mb": allocated,
                    "reserved_mb": reserved,
                    "max_allocated_mb": max_allocated,
                    "free_mb": reserved - allocated
                })

            return {
                "device_count": torch.cuda.device_count(),
                "devices": devices
            }

        except ImportError:
            return None
        except Exception as e:
            logger.error(f"Failed to get CUDA memory: {e}")
            return None

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """
        クリーンアップ統計を取得

        Returns:
            統計情報の辞書
        """
        return {
            "cleanup_count": cls._cleanup_count,
            "total_freed_mb": cls._total_freed_mb,
            "last_cleanup_time": cls._last_cleanup_time,
            "avg_freed_mb": cls._total_freed_mb / cls._cleanup_count if cls._cleanup_count > 0 else 0.0
        }

    @classmethod
    def print_memory_report(cls) -> None:
        """メモリレポートを出力"""
        print("\n" + "=" * 60)
        print("MEMORY REPORT")
        print("=" * 60)

        memory = cls.get_memory_usage()

        print("\nSystem Memory:")
        print(f"  Total:     {memory.get('total_mb', 0):.1f} MB")
        print(f"  Used:      {memory.get('used_mb', 0):.1f} MB ({memory.get('percent', 0):.1f}%)")
        print(f"  Available: {memory.get('available_mb', 0):.1f} MB")

        print("\nProcess Memory:")
        print(f"  RSS:       {memory.get('process_rss_mb', 0):.1f} MB")
        print(f"  VMS:       {memory.get('process_vms_mb', 0):.1f} MB")

        if "cuda" in memory:
            print("\nCUDA Memory:")
            for device in memory["cuda"]["devices"]:
                print(f"  Device {device['device_id']} ({device['name']}):")
                print(f"    Allocated: {device['allocated_mb']:.1f} MB")
                print(f"    Reserved:  {device['reserved_mb']:.1f} MB")
                print(f"    Peak:      {device['max_allocated_mb']:.1f} MB")

        stats = cls.get_statistics()
        print("\nCleanup Statistics:")
        print(f"  Total cleanups: {stats['cleanup_count']}")
        print(f"  Total freed:    {stats['total_freed_mb']:.1f} MB")
        print(f"  Avg freed:      {stats['avg_freed_mb']:.1f} MB")

        print("=" * 60 + "\n")


class MemoryMappedArray:
    """
    メモリマップド配列（大規模ファイル処理用）

    RAMの代わりにディスクを使用してデータを保存し、
    必要な部分だけをメモリにマッピングする。

    使用例:
        with MemoryMappedArray.create(shape=(1000000,), dtype=np.float32) as mmap_array:
            mmap_array[:1000] = data  # 部分的に書き込み
            result = process(mmap_array[:1000])  # 部分的に読み込み
    """

    def __init__(
        self,
        filepath: Path,
        shape: Tuple[int, ...],
        dtype: np.dtype,
        mode: str = 'r+'
    ):
        """
        初期化

        Args:
            filepath: メモリマップファイルのパス
            shape: 配列の形状
            dtype: データ型
            mode: アクセスモード ('r', 'r+', 'w+', 'c')
        """
        self.filepath = Path(filepath)
        self.shape = shape
        self.dtype = np.dtype(dtype)
        self.mode = mode
        self.array: Optional[np.memmap] = None
        self._is_temp = False

    def __enter__(self) -> np.memmap:
        """コンテキストマネージャのエントリ"""
        self.array = np.memmap(
            self.filepath,
            dtype=self.dtype,
            mode=self.mode,
            shape=self.shape
        )
        logger.debug(f"Memory-mapped array opened: {self.filepath}")
        return self.array

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャのエグジット"""
        if self.array is not None:
            # 変更をディスクにフラッシュ
            if self.mode in ['r+', 'w+']:
                self.array.flush()

            # 参照を削除
            del self.array
            self.array = None

            logger.debug(f"Memory-mapped array closed: {self.filepath}")

        # 一時ファイルの場合は削除
        if self._is_temp and self.filepath.exists():
            try:
                self.filepath.unlink()
                logger.debug(f"Temporary file deleted: {self.filepath}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")

        return False

    @classmethod
    @contextmanager
    def create(
        cls,
        shape: Tuple[int, ...],
        dtype: np.dtype = np.float32,
        temp: bool = True
    ):
        """
        メモリマップド配列を作成

        Args:
            shape: 配列の形状
            dtype: データ型
            temp: 一時ファイルを使用するか

        Yields:
            メモリマップド配列

        使用例:
            with MemoryMappedArray.create(shape=(1000000,), dtype=np.float32) as arr:
                arr[:] = data
        """
        if temp:
            # 一時ファイルを作成
            fd, filepath = tempfile.mkstemp(suffix='.dat', prefix='memmap_')
            os.close(fd)  # ファイル記述子を閉じる
            filepath = Path(filepath)
        else:
            # カレントディレクトリに作成
            filepath = Path(f"memmap_{int(time.time())}.dat")

        instance = cls(filepath, shape, dtype, mode='w+')
        instance._is_temp = temp

        try:
            with instance as array:
                yield array
        finally:
            # クリーンアップは __exit__ で実行される
            pass

    @classmethod
    def load(cls, filepath: Path, shape: Tuple[int, ...], dtype: np.dtype = np.float32):
        """
        既存のメモリマップファイルを読み込み

        Args:
            filepath: ファイルパス
            shape: 配列の形状
            dtype: データ型

        Returns:
            MemoryMappedArrayインスタンス
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Memory-mapped file not found: {filepath}")

        return cls(filepath, shape, dtype, mode='r')


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== MemoryOptimizer Test ===\n")

    # 初期メモリ状態
    print("Initial Memory State:")
    MemoryOptimizer.print_memory_report()

    # テスト用の大きな配列を作成してメモリを消費
    print("\nAllocating large arrays...")
    large_arrays = []
    for i in range(5):
        arr = np.random.random((1000, 1000)).astype(np.float32)
        large_arrays.append(arr)

    print("After allocation:")
    memory = MemoryOptimizer.get_memory_usage()
    print(f"  Process RSS: {memory['process_rss_mb']:.1f} MB")

    # クリーンアップテスト（配列は残ったまま）
    print("\nTesting cleanup (arrays still referenced)...")
    result = MemoryOptimizer.cleanup(aggressive=False)
    print(f"  Freed: {result['freed_mb']:.1f} MB")

    # 配列を削除してクリーンアップ
    print("\nDeleting arrays and cleaning up...")
    del large_arrays
    result = MemoryOptimizer.cleanup(aggressive=True)
    print(f"  Freed: {result['freed_mb']:.1f} MB")

    # 最終メモリ状態
    print("\nFinal Memory State:")
    MemoryOptimizer.print_memory_report()

    # コンテキストマネージャテスト
    print("\n=== Auto-Cleanup Context Manager Test ===\n")
    with MemoryOptimizer.auto_cleanup(aggressive=True):
        print("Inside context: allocating memory...")
        temp_data = np.random.random((2000, 2000)).astype(np.float32)
        print(f"  Allocated: {temp_data.nbytes / (1024**2):.1f} MB")
    # 自動的にクリーンアップされる
    print("Exited context (auto-cleanup completed)")

    # メモリマップド配列テスト
    print("\n=== MemoryMappedArray Test ===\n")
    print("Creating memory-mapped array (10M elements)...")
    with MemoryMappedArray.create(shape=(10000000,), dtype=np.float32) as mmap_arr:
        print(f"  Array shape: {mmap_arr.shape}")
        print(f"  Array dtype: {mmap_arr.dtype}")

        # データ書き込み
        mmap_arr[:1000] = np.arange(1000, dtype=np.float32)
        print("  Wrote 1000 elements")

        # データ読み込み
        data = mmap_arr[:10]
        print(f"  Read first 10 elements: {data}")

    print("Memory-mapped array closed and cleaned up")

    print("\nAll tests completed successfully")
