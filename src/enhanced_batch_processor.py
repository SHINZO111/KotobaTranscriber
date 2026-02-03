"""
強化バッチプロセッサー
100ファイル以上対応・チェックポイント機能・動的ワーカー調整
"""

import os
import json
import logging
import time
import psutil
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)


class CheckpointManager:
    """チェックポイント管理クラス"""

    CHECKPOINT_FILE = "batch_checkpoint.json"

    def __init__(self, checkpoint_dir: Optional[str] = None):
        """
        初期化

        Args:
            checkpoint_dir: チェックポイント保存ディレクトリ
        """
        if checkpoint_dir is None:
            checkpoint_dir = os.path.join(os.path.expanduser("~"), ".kotoba_transcriber")

        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / self.CHECKPOINT_FILE

    def save(self,
             batch_id: str,
             processed_files: List[str],
             failed_files: List[Dict],
             remaining_files: List[str],
             stats: Dict[str, Any]) -> bool:
        """
        チェックポイントを保存

        Args:
            batch_id: バッチID
            processed_files: 処理済みファイルリスト
            failed_files: 失敗ファイルリスト
            remaining_files: 残りファイルリスト
            stats: 統計情報

        Returns:
            成功時True
        """
        try:
            checkpoint = {
                "batch_id": batch_id,
                "timestamp": datetime.now().isoformat(),
                "processed_files": processed_files,
                "failed_files": failed_files,
                "remaining_files": remaining_files,
                "stats": stats
            }

            # 一時ファイルに書き込んでからリネーム（アトミック操作）
            temp_file = self.checkpoint_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)

            temp_file.replace(self.checkpoint_file)

            logger.info(f"Checkpoint saved: {len(processed_files)} processed, {len(remaining_files)} remaining")
            return True

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    def load(self, batch_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        チェックポイントを読み込み

        Args:
            batch_id: 特定のバッチID（Noneの場合は最新）

        Returns:
            チェックポイントデータ
        """
        try:
            if not self.checkpoint_file.exists():
                return None

            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)

            # バッチIDが指定されている場合は確認
            if batch_id and checkpoint.get("batch_id") != batch_id:
                logger.warning(f"Checkpoint batch_id mismatch: {checkpoint.get('batch_id')} != {batch_id}")
                return None

            logger.info(f"Checkpoint loaded: {len(checkpoint.get('processed_files', []))} files processed")
            return checkpoint

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def clear(self) -> bool:
        """チェックポイントを削除"""
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                logger.info("Checkpoint cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear checkpoint: {e}")
            return False

    def get_resume_info(self) -> Optional[Dict[str, Any]]:
        """
        再開可能なバッチ情報を取得

        Returns:
            再開情報（存在しない場合None）
        """
        checkpoint = self.load()
        if not checkpoint:
            return None

        remaining = checkpoint.get("remaining_files", [])
        if not remaining:
            return None

        return {
            "batch_id": checkpoint.get("batch_id"),
            "processed_count": len(checkpoint.get("processed_files", [])),
            "failed_count": len(checkpoint.get("failed_files", [])),
            "remaining_count": len(remaining),
            "remaining_files": remaining
        }


class EnhancedBatchProcessor:
    """
    強化バッチプロセッサー
    - 100ファイル以上対応
    - チェックポイント機能
    - 動的ワーカー数調整
    - メモリ監視
    """

    def __init__(self,
                 max_workers: int = 4,
                 auto_adjust_workers: bool = True,
                 enable_checkpoint: bool = True,
                 memory_limit_mb: int = 4096,
                 checkpoint_interval: int = 10):
        """
        初期化

        Args:
            max_workers: 最大ワーカー数
            auto_adjust_workers: 自動調整を有効化
            enable_checkpoint: チェックポイントを有効化
            memory_limit_mb: メモリ制限（MB）
            checkpoint_interval: チェックポイント保存間隔（ファイル数）
        """
        self.max_workers = max_workers
        self.current_workers = max_workers
        self.auto_adjust_workers = auto_adjust_workers
        self.enable_checkpoint = enable_checkpoint
        self.memory_limit_mb = memory_limit_mb
        self.checkpoint_interval = checkpoint_interval

        self.checkpoint_manager = CheckpointManager() if enable_checkpoint else None

        # 処理状態
        self.processed_files: List[str] = []
        self.failed_files: List[Dict] = []
        self.remaining_files: List[str] = []
        self.is_running = False
        self.is_paused = False
        self._cancelled = False

        # ロック
        self._lock = threading.RLock()

        # 統計
        self.stats = {
            "total_files": 0,
            "processed_count": 0,
            "failed_count": 0,
            "start_time": None,
            "elapsed_time": 0,
            "estimated_remaining": 0,
            "current_workers": max_workers,
            "memory_usage_mb": 0
        }

        logger.info(f"EnhancedBatchProcessor initialized: workers={max_workers}, checkpoint={enable_checkpoint}")

    def process_files(self,
                     file_paths: List[str],
                     processor_func: Callable[[str], Dict[str, Any]],
                     progress_callback: Optional[Callable[[Dict], None]] = None,
                     batch_id: Optional[str] = None) -> Dict[str, Any]:
        """
        ファイルをバッチ処理

        Args:
            file_paths: 処理するファイルリスト
            processor_func: 処理関数
            progress_callback: 進捗コールバック
            batch_id: バッチID（チェックポイント用）

        Returns:
            処理結果
        """
        with self._lock:
            self.is_running = True
            self._cancelled = False
            self.stats["start_time"] = time.time()
            self.stats["total_files"] = len(file_paths)

            # チェックポイントから再開
            if self.enable_checkpoint and batch_id:
                checkpoint = self.checkpoint_manager.load(batch_id)
                if checkpoint:
                    self.processed_files = checkpoint.get("processed_files", [])
                    self.failed_files = checkpoint.get("failed_files", [])
                    self.remaining_files = checkpoint.get("remaining_files", [])
                    logger.info(f"Resuming from checkpoint: {len(self.processed_files)} files already processed")
                else:
                    self.remaining_files = file_paths.copy()
            else:
                self.remaining_files = file_paths.copy()
                self.processed_files = []
                self.failed_files = []

        batch_id = batch_id or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            while self.remaining_files and not self._cancelled:
                # 一時停止チェック
                while self.is_paused:
                    time.sleep(0.5)

                # ワーカー数を調整
                if self.auto_adjust_workers:
                    self._adjust_workers()

                # 現在のバッチを処理
                batch_size = self.current_workers * 2  # 各ワーカーに2ファイル程度
                current_batch = self.remaining_files[:batch_size]

                self._process_batch(current_batch, processor_func, progress_callback, batch_id)

                # チェックポイント保存
                if self.enable_checkpoint and self.checkpoint_manager:
                    self._save_checkpoint(batch_id)

            # 完了
            self.stats["elapsed_time"] = time.time() - self.stats["start_time"]

            return {
                "success": not self._cancelled,
                "processed_files": self.processed_files,
                "failed_files": self.failed_files,
                "stats": self.stats.copy()
            }

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            # エラー時もチェックポイントを保存
            if self.enable_checkpoint:
                self._save_checkpoint(batch_id)
            raise

        finally:
            self.is_running = False

    def _process_batch(self,
                      batch: List[str],
                      processor_func: Callable,
                      progress_callback: Optional[Callable],
                      batch_id: str):
        """
        バッチを並列処理

        Args:
            batch: ファイルリスト
            processor_func: 処理関数
            progress_callback: 進捗コールバック
            batch_id: バッチID
        """
        with ThreadPoolExecutor(max_workers=self.current_workers) as executor:
            future_to_file = {
                executor.submit(self._process_single_file, file_path, processor_func): file_path
                for file_path in batch
            }

            for future in as_completed(future_to_file):
                if self._cancelled:
                    break

                file_path = future_to_file[future]

                try:
                    result = future.result()
                    with self._lock:
                        self.processed_files.append(file_path)
                        self.remaining_files.remove(file_path)
                        self.stats["processed_count"] += 1

                except Exception as e:
                    with self._lock:
                        self.failed_files.append({
                            "file": file_path,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        })
                        self.remaining_files.remove(file_path)
                        self.stats["failed_count"] += 1

                # 進捗コールバック
                if progress_callback:
                    self._update_stats()
                    progress_callback(self.stats.copy())

    def _process_single_file(self,
                            file_path: str,
                            processor_func: Callable) -> Dict[str, Any]:
        """
        単一ファイルを処理

        Args:
            file_path: ファイルパス
            processor_func: 処理関数

        Returns:
            処理結果
        """
        start_time = time.time()

        try:
            result = processor_func(file_path)

            return {
                "file": file_path,
                "result": result,
                "processing_time": time.time() - start_time,
                "success": True
            }

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            raise

    def _adjust_workers(self):
        """ワーカー数を動的に調整"""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.stats["memory_usage_mb"] = int(memory_mb)

            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()

            # メモリが80%を超えたらワーカーを減らす
            if memory_mb > self.memory_limit_mb * 0.8:
                new_workers = max(1, self.current_workers - 1)
                if new_workers != self.current_workers:
                    logger.warning(f"Memory high ({memory_mb:.0f}MB), reducing workers: {self.current_workers} -> {new_workers}")
                    self.current_workers = new_workers

            # CPU使用率が低く、メモリに余裕があればワーカーを増やす
            elif cpu_percent < 50 and memory_mb < self.memory_limit_mb * 0.5:
                new_workers = min(self.max_workers, self.current_workers + 1)
                if new_workers != self.current_workers:
                    logger.info(f"Resources available, increasing workers: {self.current_workers} -> {new_workers}")
                    self.current_workers = new_workers

            self.stats["current_workers"] = self.current_workers

        except Exception as e:
            logger.error(f"Error adjusting workers: {e}")

    def _update_stats(self):
        """統計情報を更新"""
        elapsed = time.time() - self.stats["start_time"]
        self.stats["elapsed_time"] = elapsed

        processed = self.stats["processed_count"]
        if processed > 0:
            avg_time = elapsed / processed
            remaining = self.stats["total_files"] - processed
            self.stats["estimated_remaining"] = avg_time * remaining

    def _save_checkpoint(self, batch_id: str):
        """チェックポイントを保存"""
        if not self.checkpoint_manager:
            return

        self.checkpoint_manager.save(
            batch_id=batch_id,
            processed_files=self.processed_files.copy(),
            failed_files=self.failed_files.copy(),
            remaining_files=self.remaining_files.copy(),
            stats=self.stats.copy()
        )

    def cancel(self):
        """処理をキャンセル"""
        self._cancelled = True
        logger.info("Batch processing cancellation requested")

    def pause(self):
        """処理を一時停止"""
        self.is_paused = True
        logger.info("Batch processing paused")

    def resume(self):
        """処理を再開"""
        self.is_paused = False
        logger.info("Batch processing resumed")

    def get_progress(self) -> Dict[str, Any]:
        """
        進捗情報を取得

        Returns:
            進捗情報
        """
        with self._lock:
            self._update_stats()

            total = self.stats["total_files"]
            processed = self.stats["processed_count"]
            failed = self.stats["failed_count"]

            return {
                **self.stats,
                "progress_percent": (processed / total * 100) if total > 0 else 0,
                "remaining_files": len(self.remaining_files),
                "is_running": self.is_running,
                "is_paused": self.is_paused
            }


def can_resume_batch() -> bool:
    """
    再開可能なバッチが存在するかチェック

    Returns:
        再開可能な場合True
    """
    manager = CheckpointManager()
    info = manager.get_resume_info()
    return info is not None and info["remaining_count"] > 0


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== EnhancedBatchProcessor Test ===\n")

    # チェックポイントマネージャーテスト
    print("1. Checkpoint Manager Test:")
    cp = CheckpointManager()

    test_checkpoint = {
        "batch_id": "test_batch",
        "processed_files": ["file1.wav", "file2.wav"],
        "failed_files": [],
        "remaining_files": ["file3.wav", "file4.wav"],
        "stats": {"total_files": 4}
    }

    cp.save(**test_checkpoint)
    loaded = cp.load("test_batch")
    print(f"  Saved/Loaded: {loaded is not None}")

    resume_info = cp.get_resume_info()
    print(f"  Can resume: {resume_info is not None}")

    # バッチプロセッサーテスト
    print("\n2. Batch Processor Test:")

    processor = EnhancedBatchProcessor(
        max_workers=2,
        enable_checkpoint=True
    )

    test_files = [f"test_{i}.wav" for i in range(10)]

    def dummy_processor(file_path: str) -> Dict:
        time.sleep(0.1)
        return {"text": f"Processed {file_path}"}

    def progress_callback(stats: Dict):
        print(f"  Progress: {stats['processed_count']}/{stats['total_files']} "
              f"(workers: {stats['current_workers']}, memory: {stats['memory_usage_mb']}MB)")

    result = processor.process_files(
        test_files,
        dummy_processor,
        progress_callback,
        batch_id="test_batch"
    )

    print(f"\n  Result: {result['stats']['processed_count']} processed, "
          f"{result['stats']['failed_count']} failed")

    cp.clear()
    print("\nTest completed!")
