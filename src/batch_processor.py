"""
バッチプロセッサー
複数の音声ファイルを効率的にバッチ処理
"""

import logging
import time
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    音声ファイルのバッチ処理マネージャー

    Features:
    - バッチサイズの自動調整
    - GPU効率化のためのバッチ処理
    - メモリ使用量の監視と調整
    - 進捗レポート
    """

    def __init__(self,
                 batch_size: int = 10,
                 auto_adjust_batch_size: bool = True,
                 max_memory_mb: int = 2048):
        """
        初期化

        Args:
            batch_size: バッチサイズ（同時に処理するファイル数）
            auto_adjust_batch_size: メモリ使用量に応じてバッチサイズを自動調整
            max_memory_mb: 最大メモリ使用量（MB）
        """
        self.batch_size = batch_size
        self.initial_batch_size = batch_size
        self.auto_adjust_batch_size = auto_adjust_batch_size
        self.max_memory_mb = max_memory_mb

        self.queue: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []

        # 統計情報
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "batches_processed": 0
        }

        logger.info(f"BatchProcessor initialized: batch_size={batch_size}, "
                   f"max_memory={max_memory_mb}MB")

    def add(self, file_path: str, metadata: Optional[Dict] = None) -> None:
        """
        ファイルをバッチキューに追加

        Args:
            file_path: ファイルパス
            metadata: メタデータ（任意）
        """
        self.queue.append({
            "file_path": file_path,
            "metadata": metadata or {},
            "added_time": time.time()
        })

        self.stats["total_files"] += 1
        logger.debug(f"Added to queue: {Path(file_path).name} (queue size: {len(self.queue)})")

    def add_multiple(self, file_paths: List[str]) -> None:
        """
        複数のファイルをバッチキューに追加

        Args:
            file_paths: ファイルパスのリスト
        """
        for file_path in file_paths:
            self.add(file_path)

        logger.info(f"Added {len(file_paths)} files to queue")

    def process_batch(self,
                     processor_func: Callable[[str], Dict[str, Any]],
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict[str, Any]]:
        """
        現在のキューをバッチ処理

        Args:
            processor_func: 各ファイルを処理する関数（file_path -> result）
            progress_callback: 進捗コールバック関数（processed, total）

        Returns:
            処理結果のリスト
        """
        if not self.queue:
            logger.warning("Queue is empty, nothing to process")
            return []

        batch_results = []
        batch_start_time = time.time()

        total_files = len(self.queue)
        logger.info(f"Processing batch of {total_files} files...")

        for i, item in enumerate(self.queue):
            file_path = item["file_path"]
            start_time = time.time()

            try:
                # ファイルを処理
                result = processor_func(file_path)

                processing_time = time.time() - start_time

                # 結果を記録
                batch_results.append({
                    "file_path": file_path,
                    "result": result,
                    "metadata": item["metadata"],
                    "processing_time": processing_time,
                    "success": True
                })

                self.stats["processed_files"] += 1
                self.stats["total_processing_time"] += processing_time

                logger.info(f"Processed [{i+1}/{total_files}]: {Path(file_path).name} "
                           f"({processing_time:.2f}s)")

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}", exc_info=True)

                batch_results.append({
                    "file_path": file_path,
                    "result": None,
                    "metadata": item["metadata"],
                    "error": str(e),
                    "success": False
                })

                self.stats["failed_files"] += 1

            # 進捗コールバック
            if progress_callback:
                progress_callback(i + 1, total_files)

        # バッチ処理完了
        batch_time = time.time() - batch_start_time
        self.stats["batches_processed"] += 1

        # キューをクリア
        self.queue.clear()

        # 平均処理時間を更新
        if self.stats["processed_files"] > 0:
            self.stats["average_processing_time"] = (
                self.stats["total_processing_time"] / self.stats["processed_files"]
            )

        logger.info(f"Batch completed: {total_files} files in {batch_time:.2f}s "
                   f"(avg {batch_time/total_files:.2f}s/file)")

        self.results.extend(batch_results)
        return batch_results

    def process_all(self,
                   processor_func: Callable[[str], Dict[str, Any]],
                   progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict[str, Any]]:
        """
        キュー内の全ファイルをバッチ処理（バッチサイズごとに分割）

        Args:
            processor_func: 各ファイルを処理する関数
            progress_callback: 進捗コールバック関数

        Returns:
            全処理結果のリスト
        """
        all_results = []
        total_files = len(self.queue)

        if total_files == 0:
            logger.warning("Queue is empty")
            return []

        logger.info(f"Processing {total_files} files in batches of {self.batch_size}...")

        # バッチごとに処理
        processed = 0
        while self.queue:
            # 現在のバッチサイズ分を取り出す
            batch_items = self.queue[:self.batch_size]
            remaining_items = self.queue[self.batch_size:]

            # 一時的にキューを置き換え
            self.queue = batch_items

            # バッチ処理
            batch_results = self.process_batch(
                processor_func,
                lambda p, t: progress_callback(processed + p, total_files) if progress_callback else None
            )

            all_results.extend(batch_results)
            processed += len(batch_items)

            # 残りをキューに戻す
            self.queue = remaining_items

            # バッチサイズの自動調整
            if self.auto_adjust_batch_size:
                self._adjust_batch_size()

        logger.info(f"All batches completed: {total_files} files processed")
        return all_results

    def _adjust_batch_size(self) -> None:
        """
        メモリ使用量に応じてバッチサイズを自動調整
        """
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb > self.max_memory_mb * 0.9:
                # メモリ使用量が90%を超えたらバッチサイズを減らす
                self.batch_size = max(1, self.batch_size // 2)
                logger.warning(f"Memory usage high ({memory_mb:.0f}MB), reducing batch size to {self.batch_size}")

            elif memory_mb < self.max_memory_mb * 0.5 and self.batch_size < self.initial_batch_size:
                # メモリに余裕があればバッチサイズを増やす
                self.batch_size = min(self.initial_batch_size, self.batch_size * 2)
                logger.info(f"Memory usage low ({memory_mb:.0f}MB), increasing batch size to {self.batch_size}")

        except ImportError:
            # psutilが利用できない場合はスキップ
            pass
        except Exception as e:
            logger.error(f"Error adjusting batch size: {e}", exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """
        処理統計を取得

        Returns:
            統計情報
        """
        success_rate = 0.0
        if self.stats["total_files"] > 0:
            success_rate = self.stats["processed_files"] / self.stats["total_files"]

        return {
            **self.stats,
            "success_rate": success_rate,
            "queue_size": len(self.queue),
            "current_batch_size": self.batch_size
        }

    def get_results(self) -> List[Dict[str, Any]]:
        """
        全処理結果を取得

        Returns:
            結果のリスト
        """
        return self.results

    def get_successful_results(self) -> List[Dict[str, Any]]:
        """
        成功した処理結果のみを取得

        Returns:
            成功した結果のリスト
        """
        return [r for r in self.results if r.get("success", False)]

    def get_failed_results(self) -> List[Dict[str, Any]]:
        """
        失敗した処理結果のみを取得

        Returns:
            失敗した結果のリスト
        """
        return [r for r in self.results if not r.get("success", False)]

    def clear(self) -> None:
        """キューと結果をクリア"""
        self.queue.clear()
        self.results.clear()
        logger.info("Queue and results cleared")

    def clear_queue(self) -> None:
        """キューのみクリア"""
        self.queue.clear()
        logger.info("Queue cleared")

    def clear_results(self) -> None:
        """結果のみクリア"""
        self.results.clear()
        logger.info("Results cleared")


class SmartBatchProcessor(BatchProcessor):
    """
    スマートバッチプロセッサー
    ファイルサイズに基づいて動的にバッチサイズを調整
    """

    def __init__(self,
                 batch_size: int = 10,
                 auto_adjust_batch_size: bool = True,
                 max_memory_mb: int = 2048,
                 size_based_batching: bool = True):
        """
        初期化

        Args:
            batch_size: バッチサイズ
            auto_adjust_batch_size: 自動調整
            max_memory_mb: 最大メモリ
            size_based_batching: ファイルサイズベースのバッチング
        """
        super().__init__(batch_size, auto_adjust_batch_size, max_memory_mb)
        self.size_based_batching = size_based_batching

    def add(self, file_path: str, metadata: Optional[Dict] = None) -> None:
        """
        ファイルサイズ情報を含めて追加

        Args:
            file_path: ファイルパス
            metadata: メタデータ
        """
        # ファイルサイズを取得
        file_size = 0
        try:
            file_size = Path(file_path).stat().st_size
        except Exception as e:
            logger.error(f"Error getting file size: {e}")

        metadata = metadata or {}
        metadata["file_size"] = file_size

        super().add(file_path, metadata)

    def process_all(self,
                   processor_func: Callable[[str], Dict[str, Any]],
                   progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict[str, Any]]:
        """
        ファイルサイズでソートしてから処理

        Args:
            processor_func: 処理関数
            progress_callback: 進捗コールバック

        Returns:
            処理結果
        """
        if self.size_based_batching:
            # ファイルサイズでソート（大きいファイルから処理）
            self.queue.sort(key=lambda x: x["metadata"].get("file_size", 0), reverse=True)
            logger.info("Queue sorted by file size (largest first)")

        return super().process_all(processor_func, progress_callback)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== BatchProcessor Test ===\n")

    # バッチプロセッサー作成
    processor = BatchProcessor(batch_size=3)

    # テストファイルを追加
    test_files = [f"test_file_{i}.wav" for i in range(10)]
    processor.add_multiple(test_files)

    # ダミーの処理関数
    def dummy_processor(file_path: str) -> Dict[str, Any]:
        """ダミーの処理関数"""
        time.sleep(0.1)  # 処理をシミュレート
        return {"text": f"Processed {file_path}", "duration": 0.1}

    # 進捗コールバック
    def progress_callback(processed: int, total: int):
        """進捗表示"""
        print(f"Progress: {processed}/{total} ({100*processed/total:.0f}%)")

    # バッチ処理実行
    print("\n1. Processing all files in batches...")
    results = processor.process_all(dummy_processor, progress_callback)

    # 結果表示
    print("\n2. Processing completed:")
    print(f"   Total results: {len(results)}")
    print(f"   Successful: {len(processor.get_successful_results())}")
    print(f"   Failed: {len(processor.get_failed_results())}")

    # 統計情報
    print("\n3. Statistics:")
    stats = processor.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\nTest completed!")
