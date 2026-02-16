"""
処理パイプライン最適化モジュール
KotobaTranscriber v2.2 - パフォーマンス改善
"""

import gc
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """処理統計データ"""

    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_duration: float = 0.0
    total_audio_seconds: float = 0.0
    avg_processing_time: float = 0.0
    memory_peak_mb: float = 0.0
    start_time: Optional[float] = None

    @property
    def progress_percent(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    @property
    def elapsed_time(self) -> float:
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    @property
    def estimated_remaining(self) -> float:
        if self.processed_files == 0:
            return 0.0
        avg_time = self.elapsed_time / self.processed_files
        remaining_files = self.total_files - self.processed_files
        return avg_time * remaining_files


class MemoryMonitor:
    """メモリ使用量モニター"""

    def __init__(self, limit_mb: int = 4096, check_interval: float = 1.0):
        self.limit_mb = limit_mb
        self.check_interval = check_interval
        self.peak_mb = 0.0
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[float], None]] = []
        self._callbacks_lock = threading.Lock()

    def start(self):
        """モニタリング開始"""
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Memory monitoring started (limit: {self.limit_mb}MB)")

    def stop(self):
        """モニタリング停止"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)

    def _monitor_loop(self):
        """モニタリングループ"""
        while self._monitoring:
            current_mb = self.get_current_memory_mb()
            self.peak_mb = max(self.peak_mb, current_mb)

            # コールバック実行
            with self._callbacks_lock:
                callbacks = list(self._callbacks)
            for callback in callbacks:
                try:
                    callback(current_mb)
                except Exception as e:
                    logger.error(f"Memory callback error: {e}")

            # 制限超過チェック
            if current_mb > self.limit_mb:
                logger.warning(f"Memory limit exceeded: {current_mb:.1f}MB / {self.limit_mb}MB")
                self._trigger_gc()

            time.sleep(self.check_interval)

    def get_current_memory_mb(self) -> float:
        """現在のメモリ使用量を取得（MB）"""
        if not PSUTIL_AVAILABLE:
            return 0.0
        process = psutil.Process(os.getpid())
        return float(process.memory_info().rss / 1024 / 1024)

    def _trigger_gc(self):
        """ガベージコレクション実行"""
        gc.collect()
        if hasattr(gc, "collect") and hasattr(gc, "get_threshold"):
            # 強制GC
            gc.collect(2)

    def register_callback(self, callback: Callable[[float], None]):
        """メモリ使用量コールバックを登録"""
        with self._callbacks_lock:
            self._callbacks.append(callback)

    def is_memory_available(self, required_mb: float = 500.0) -> bool:
        """必要なメモリが利用可能かチェック"""
        current = self.get_current_memory_mb()
        return (current + required_mb) <= self.limit_mb


class OptimizedPipeline:
    """最適化された処理パイプライン"""

    def __init__(
        self,
        max_workers: int = 1,  # FIXED: TranscriptionEngine is not thread-safe
        memory_limit_mb: int = 4096,
        enable_caching: bool = True,
        cache_dir: Optional[str] = None,
    ):
        # CRITICAL: TranscriptionEngineはスレッドセーフではないため、max_workersを強制的に1に設定
        self.max_workers = 1
        self.memory_limit_mb = memory_limit_mb
        self.enable_caching = enable_caching
        self.cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".kotoba_cache")

        self._memory_monitor = MemoryMonitor(memory_limit_mb)
        self._executor: Optional[ThreadPoolExecutor] = None
        self._stats = ProcessingStats()
        self._stats_lock = threading.Lock()
        self._progress_callbacks: List[Callable[[ProcessingStats], None]] = []

        # キャッシュディレクトリ作成
        if self.enable_caching:
            os.makedirs(self.cache_dir, exist_ok=True)

    def start(self):
        """パイプライン開始"""
        self._memory_monitor.start()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._stats.start_time = time.time()
        logger.info(f"Pipeline started with {self.max_workers} workers")

    def stop(self):
        """パイプライン停止"""
        self._memory_monitor.stop()
        if self._executor:
            self._executor.shutdown(wait=True)
        logger.info("Pipeline stopped")

    def process_files(
        self,
        file_paths: List[str],
        process_func: Callable[[str], Any],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        複数ファイルを並列処理

        Args:
            file_paths: 処理するファイルパスのリスト
            process_func: 各ファイルの処理関数
            progress_callback: 進捗コールバック (current, total, filename)

        Returns:
            処理結果の辞書
        """
        self._stats.total_files = len(file_paths)
        results = {}

        if not self._executor:
            self.start()

        # Futureを追跡
        future_to_file = {self._executor.submit(self._process_with_stats, path, process_func): path for path in file_paths}

        # 完了を待機
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]

            try:
                result = future.result()
                results[file_path] = {"success": True, "result": result}
                with self._stats_lock:
                    self._stats.processed_files += 1
            except Exception as e:
                results[file_path] = {"success": False, "error": str(e)}
                with self._stats_lock:
                    self._stats.failed_files += 1
                logger.error(f"Processing failed for {file_path}: {e}")

            # 進捗コールバック
            if progress_callback:
                progress_callback(self._stats.processed_files, self._stats.total_files, os.path.basename(file_path))

            # 定期的なGC
            if self._stats.processed_files % 5 == 0:
                self._memory_monitor._trigger_gc()

        return results

    def _process_with_stats(self, file_path: str, process_func: Callable) -> Any:
        """統計付きで処理実行"""
        start_time = time.time()

        result = process_func(file_path)

        duration = time.time() - start_time
        with self._stats_lock:
            self._stats.total_duration += duration
            self._stats.avg_processing_time = self._stats.total_duration / max(self._stats.processed_files, 1)

        return result

    def get_cache_path(self, file_path: str, suffix: str = ".cache") -> str:
        """キャッシュパスを取得"""
        file_hash = self._get_file_hash(file_path)
        return os.path.join(self.cache_dir, f"{file_hash}{suffix}")

    def _get_file_hash(self, file_path: str) -> str:
        """ファイルハッシュを取得"""
        import hashlib

        stat = os.stat(file_path)
        hash_input = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()

    def is_cached(self, file_path: str, suffix: str = ".cache") -> bool:
        """キャッシュが存在するかチェック"""
        if not self.enable_caching:
            return False
        cache_path = self.get_cache_path(file_path, suffix)
        return os.path.exists(cache_path)

    def get_stats(self) -> ProcessingStats:
        """統計情報を取得"""
        with self._stats_lock:
            # 浅いコピーで一貫したスナップショットを返す
            import copy

            return copy.copy(self._stats)


class PipelineStage:
    """パイプラインステージ基底クラス"""

    def __init__(self, name: str):
        self.name = name
        self.next_stage: Optional[PipelineStage] = None
        self._enabled = True

    def set_next(self, stage: "PipelineStage") -> "PipelineStage":
        """次のステージを設定"""
        self.next_stage = stage
        return stage

    def process(self, data: Any) -> Any:
        """データを処理"""
        if not self._enabled:
            return data

        result = self._process_impl(data)

        if self.next_stage:
            return self.next_stage.process(result)

        return result

    def _process_impl(self, data: Any) -> Any:
        """実装クラスでオーバーライド"""
        raise NotImplementedError

    def enable(self):
        """ステージを有効化"""
        self._enabled = True

    def disable(self):
        """ステージを無効化"""
        self._enabled = False


class AudioPreprocessingStage(PipelineStage):
    """音声前処理ステージ"""

    def __init__(self, noise_reduction: bool = True, normalize: bool = True):
        super().__init__("AudioPreprocessing")
        self.noise_reduction = noise_reduction
        self.normalize = normalize

    def _process_impl(self, data: str) -> str:
        """音声ファイルを前処理"""
        # 実装は既存のAudioPreprocessorを使用
        logger.debug(f"Preprocessing: {data}")
        return data


class TranscriptionStage(PipelineStage):
    """文字起こしステージ"""

    def __init__(self, engine: Any):
        super().__init__("Transcription")
        self.engine = engine

    def _process_impl(self, data: str) -> Dict[str, Any]:
        """文字起こし実行"""
        result = self.engine.transcribe(data, return_timestamps=True)
        return {"audio_path": data, "transcription": result}


class TextFormattingStage(PipelineStage):
    """テキスト整形ステージ"""

    def __init__(self, formatter: Any):
        super().__init__("TextFormatting")
        self.formatter = formatter

    def _process_impl(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """テキスト整形"""
        transcription = data.get("transcription", {})
        text = transcription.get("text", "")

        formatted_text = self.formatter.format_all(text)
        data["formatted_text"] = formatted_text

        return data


class SpeakerDiarizationStage(PipelineStage):
    """話者分離ステージ"""

    def __init__(self, diarizer: Any, enabled: bool = False):
        super().__init__("SpeakerDiarization")
        self.diarizer = diarizer
        self._enabled = enabled

    def _process_impl(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """話者分離実行"""
        audio_path = data.get("audio_path")

        if audio_path and self.diarizer:
            try:
                segments = self.diarizer.diarize(audio_path)
                data["speaker_segments"] = segments
            except Exception as e:
                logger.warning(f"Speaker diarization failed: {e}")

        return data


class ExportStage(PipelineStage):
    """エクスポートステージ"""

    def __init__(self, exporter: Any, formats: List[str] = None):
        super().__init__("Export")
        self.exporter = exporter
        self.formats = formats or ["txt"]

    def _process_impl(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """複数形式でエクスポート"""
        audio_path = data.get("audio_path", "")
        formatted_text = data.get("formatted_text", "")

        base_path = os.path.splitext(audio_path)[0]

        export_results = {}
        for fmt in self.formats:
            try:
                if fmt == "txt":
                    output_path = f"{base_path}.txt"
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(formatted_text)
                    export_results[fmt] = output_path

                elif fmt in ["srt", "vtt"] and self.exporter:
                    segments = data.get("transcription", {}).get("segments", [])
                    output_path = f"{base_path}.{fmt}"
                    if fmt == "srt":
                        self.exporter.export_srt(segments, output_path)
                    else:
                        self.exporter.export_vtt(segments, output_path)
                    export_results[fmt] = output_path

            except Exception as e:
                logger.error(f"Export failed for {fmt}: {e}")
                export_results[fmt] = None

        data["export_results"] = export_results
        return data


def create_optimized_pipeline(
    transcription_engine: Any,
    text_formatter: Any,
    subtitle_exporter: Any = None,
    speaker_diarizer: Any = None,
    enable_diarization: bool = False,
    export_formats: List[str] = None,
) -> PipelineStage:
    """
    最適化された処理パイプラインを作成

    Args:
        transcription_engine: 文字起こしエンジン
        text_formatter: テキスト整形器
        subtitle_exporter: 字幕エクスポート（オプション）
        speaker_diarizer: 話者分離器（オプション）
        enable_diarization: 話者分離を有効化
        export_formats: エクスポート形式リスト

    Returns:
        最初のパイプラインステージ
    """
    # ステージ作成
    transcription = TranscriptionStage(transcription_engine)
    formatting = TextFormattingStage(text_formatter)
    diarization = SpeakerDiarizationStage(speaker_diarizer, enabled=enable_diarization)
    export_stage = ExportStage(subtitle_exporter, formats=export_formats or ["txt"])

    # パイプライン接続
    transcription.set_next(diarization)
    diarization.set_next(formatting)
    formatting.set_next(export_stage)

    return transcription


if __name__ == "__main__":
    # テスト
    logging.basicConfig(level=logging.INFO)

    print("=== Optimized Pipeline Test ===\n")

    # メモリモニタリングテスト
    monitor = MemoryMonitor(limit_mb=2048)
    monitor.start()

    print(f"Current memory: {monitor.get_current_memory_mb():.1f}MB")

    time.sleep(2)

    print(f"Peak memory: {monitor.peak_mb:.1f}MB")

    monitor.stop()

    # パイプラインステージテスト
    print("\nPipeline stages available:")
    stages = [AudioPreprocessingStage, TranscriptionStage, TextFormattingStage, SpeakerDiarizationStage, ExportStage]

    for stage_class in stages:
        print(f"  ✓ {stage_class.__name__}")

    print("\nTest completed!")
