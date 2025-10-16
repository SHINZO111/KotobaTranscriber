"""
並列プロセッサー
ThreadPoolExecutorとProcessPoolExecutorを使った並列処理
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, Literal
from pathlib import Path
import multiprocessing as mp

logger = logging.getLogger(__name__)


class ParallelProcessor:
    """
    並列ファイル処理マネージャー

    Features:
    - ThreadPoolExecutor: I/Oバウンドな処理用
    - ProcessPoolExecutor: CPUバウンドな処理用
    - 自動ワーカー数調整
    - タイムアウト処理
    - エラーハンドリングとリトライ機能
    """

    def __init__(self,
                 max_workers: Optional[int] = None,
                 executor_type: Literal["thread", "process"] = "thread",
                 timeout: Optional[float] = None):
        """
        初期化

        Args:
            max_workers: 最大ワーカー数（Noneの場合は自動）
            executor_type: エグゼキューターのタイプ（"thread" or "process"）
            timeout: タスクごとのタイムアウト（秒）
        """
        self.executor_type = executor_type
        self.timeout = timeout

        # ワーカー数の自動設定
        if max_workers is None:
            if executor_type == "thread":
                # I/Oバウンドな処理にはCPUコア数の2-4倍
                max_workers = min(32, (mp.cpu_count() or 1) * 4)
            else:
                # CPUバウンドな処理にはCPUコア数
                max_workers = mp.cpu_count() or 1

        self.max_workers = max_workers

        # エグゼキューターの作成
        if executor_type == "thread":
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
        else:
            self.executor = ProcessPoolExecutor(max_workers=max_workers)

        # 統計情報
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0
        }

        logger.info(f"ParallelProcessor initialized: type={executor_type}, "
                   f"max_workers={max_workers}")

    def __enter__(self):
        """コンテキストマネージャのエントリポイント"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャのエグジットポイント"""
        self.shutdown()
        return False

    def process_files(self,
                     file_paths: List[str],
                     processor_func: Callable[[str], Dict[str, Any]],
                     progress_callback: Optional[Callable[[int, int], None]] = None,
                     retry_count: int = 0) -> List[Dict[str, Any]]:
        """
        複数のファイルを並列処理

        Args:
            file_paths: ファイルパスのリスト
            processor_func: 各ファイルを処理する関数（file_path -> result）
            progress_callback: 進捗コールバック関数（completed, total）
            retry_count: エラー時のリトライ回数

        Returns:
            処理結果のリスト
        """
        if not file_paths:
            logger.warning("No files to process")
            return []

        total_files = len(file_paths)
        self.stats["total_tasks"] = total_files

        logger.info(f"Processing {total_files} files in parallel "
                   f"(workers={self.max_workers})...")

        start_time = time.time()
        results = []

        # Futureオブジェクトとファイルパスのマッピング
        future_to_file = {
            self.executor.submit(self._process_with_retry, processor_func, file_path, retry_count): file_path
            for file_path in file_paths
        }

        # 完了した順に結果を収集
        completed = 0
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]

            try:
                result = future.result(timeout=self.timeout)

                results.append({
                    "file_path": file_path,
                    "result": result,
                    "success": True
                })

                self.stats["completed_tasks"] += 1
                completed += 1

                logger.info(f"Completed [{completed}/{total_files}]: {Path(file_path).name}")

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")

                results.append({
                    "file_path": file_path,
                    "result": None,
                    "error": str(e),
                    "success": False
                })

                self.stats["failed_tasks"] += 1
                completed += 1

            # 進捗コールバック
            if progress_callback:
                progress_callback(completed, total_files)

        # 処理時間の記録
        total_time = time.time() - start_time
        self.stats["total_processing_time"] = total_time

        if self.stats["completed_tasks"] > 0:
            self.stats["average_processing_time"] = (
                total_time / self.stats["completed_tasks"]
            )

        logger.info(f"Parallel processing completed: {total_files} files in {total_time:.2f}s "
                   f"(avg {total_time/total_files:.2f}s/file)")

        # 元の順序でソート
        results.sort(key=lambda x: file_paths.index(x["file_path"]))

        return results

    def _process_with_retry(self,
                           processor_func: Callable[[str], Dict[str, Any]],
                           file_path: str,
                           retry_count: int) -> Dict[str, Any]:
        """
        リトライ機能付きでファイルを処理

        Args:
            processor_func: 処理関数
            file_path: ファイルパス
            retry_count: リトライ回数

        Returns:
            処理結果

        Raises:
            最後の例外
        """
        last_exception = None

        for attempt in range(retry_count + 1):
            try:
                return processor_func(file_path)

            except Exception as e:
                last_exception = e
                if attempt < retry_count:
                    logger.warning(f"Retry {attempt + 1}/{retry_count} for {file_path}: {e}")
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"All retries failed for {file_path}: {e}")

        raise last_exception

    def map(self,
            processor_func: Callable[[str], Dict[str, Any]],
            file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        ファイルリストをマップして並列処理（簡易版）

        Args:
            processor_func: 処理関数
            file_paths: ファイルパスのリスト

        Returns:
            処理結果のリスト
        """
        return self.process_files(file_paths, processor_func)

    def get_stats(self) -> Dict[str, Any]:
        """
        処理統計を取得

        Returns:
            統計情報
        """
        success_rate = 0.0
        if self.stats["total_tasks"] > 0:
            success_rate = self.stats["completed_tasks"] / self.stats["total_tasks"]

        return {
            **self.stats,
            "success_rate": success_rate,
            "executor_type": self.executor_type,
            "max_workers": self.max_workers
        }

    def shutdown(self, wait: bool = True) -> None:
        """
        エグゼキューターをシャットダウン

        Args:
            wait: 全タスクの完了を待つか
        """
        if self.executor:
            logger.info("Shutting down executor...")
            self.executor.shutdown(wait=wait)
            logger.info("Executor shutdown complete")


class AdaptiveParallelProcessor(ParallelProcessor):
    """
    アダプティブ並列プロセッサー
    処理時間に基づいてワーカー数を動的に調整
    """

    def __init__(self,
                 max_workers: Optional[int] = None,
                 executor_type: Literal["thread", "process"] = "thread",
                 timeout: Optional[float] = None,
                 adaptive: bool = True):
        """
        初期化

        Args:
            max_workers: 最大ワーカー数
            executor_type: エグゼキューターのタイプ
            timeout: タイムアウト
            adaptive: アダプティブモード有効化
        """
        super().__init__(max_workers, executor_type, timeout)
        self.adaptive = adaptive
        self.initial_workers = self.max_workers

    def process_files(self,
                     file_paths: List[str],
                     processor_func: Callable[[str], Dict[str, Any]],
                     progress_callback: Optional[Callable[[int, int], None]] = None,
                     retry_count: int = 0) -> List[Dict[str, Any]]:
        """
        アダプティブに並列処理

        Args:
            file_paths: ファイルパスのリスト
            processor_func: 処理関数
            progress_callback: 進捗コールバック
            retry_count: リトライ回数

        Returns:
            処理結果のリスト
        """
        # 最初の数ファイルで処理時間を測定
        if self.adaptive and len(file_paths) > 10:
            sample_size = min(5, len(file_paths) // 10)
            sample_files = file_paths[:sample_size]

            logger.info(f"Running adaptive sampling with {sample_size} files...")
            sample_start = time.time()

            sample_results = super().process_files(
                sample_files,
                processor_func,
                None,
                retry_count
            )

            sample_time = time.time() - sample_start
            avg_time_per_file = sample_time / sample_size

            # ワーカー数を調整
            self._adjust_workers(avg_time_per_file, len(file_paths))

            # 残りのファイルを処理
            remaining_files = file_paths[sample_size:]
            remaining_results = super().process_files(
                remaining_files,
                processor_func,
                progress_callback,
                retry_count
            )

            return sample_results + remaining_results

        else:
            # 通常の処理
            return super().process_files(
                file_paths,
                processor_func,
                progress_callback,
                retry_count
            )

    def _adjust_workers(self, avg_time_per_file: float, total_files: int) -> None:
        """
        処理時間に基づいてワーカー数を調整

        Args:
            avg_time_per_file: ファイルあたりの平均処理時間
            total_files: 総ファイル数
        """
        # 処理が速い場合はワーカー数を増やす
        if avg_time_per_file < 1.0 and total_files > 50:
            new_workers = min(self.initial_workers * 2, 64)
            if new_workers != self.max_workers:
                logger.info(f"Fast processing detected ({avg_time_per_file:.2f}s/file), "
                           f"increasing workers from {self.max_workers} to {new_workers}")
                self.max_workers = new_workers
                self._recreate_executor()

        # 処理が遅い場合はワーカー数を減らす
        elif avg_time_per_file > 10.0:
            new_workers = max(self.initial_workers // 2, 1)
            if new_workers != self.max_workers:
                logger.info(f"Slow processing detected ({avg_time_per_file:.2f}s/file), "
                           f"decreasing workers from {self.max_workers} to {new_workers}")
                self.max_workers = new_workers
                self._recreate_executor()

    def _recreate_executor(self) -> None:
        """エグゼキューターを再作成"""
        # 既存のエグゼキューターをシャットダウン
        if self.executor:
            self.executor.shutdown(wait=False)

        # 新しいワーカー数でエグゼキューターを再作成
        if self.executor_type == "thread":
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        else:
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== ParallelProcessor Test ===\n")

    # テストファイルリスト
    test_files = [f"test_file_{i}.wav" for i in range(20)]

    # ダミーの処理関数
    def dummy_processor(file_path: str) -> Dict[str, Any]:
        """ダミーの処理関数"""
        time.sleep(0.2)  # 処理をシミュレート
        return {
            "text": f"Processed {file_path}",
            "duration": 0.2
        }

    # 進捗コールバック
    def progress_callback(completed: int, total: int):
        """進捗表示"""
        print(f"Progress: {completed}/{total} ({100*completed/total:.0f}%)")

    # コンテキストマネージャとして使用
    print("1. Processing files in parallel...")
    with ParallelProcessor(max_workers=4, executor_type="thread") as processor:
        results = processor.process_files(
            test_files,
            dummy_processor,
            progress_callback
        )

        # 結果表示
        print(f"\n2. Processing completed:")
        print(f"   Total results: {len(results)}")
        print(f"   Successful: {sum(1 for r in results if r['success'])}")
        print(f"   Failed: {sum(1 for r in results if not r['success'])}")

        # 統計情報
        print("\n3. Statistics:")
        stats = processor.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")

    print("\nTest completed!")
