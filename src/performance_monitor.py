"""
パフォーマンスモニター
ベンチマーク測定、メトリクス収集、パフォーマンス分析
"""

import logging
import time
import psutil
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""
    start_time: float = 0.0
    end_time: float = 0.0
    processing_time: float = 0.0
    cpu_usage_start: float = 0.0
    cpu_usage_end: float = 0.0
    cpu_usage_avg: float = 0.0
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0
    memory_peak_mb: float = 0.0
    memory_delta_mb: float = 0.0
    throughput: float = 0.0  # ファイル/秒
    files_processed: int = 0
    files_failed: int = 0
    total_audio_duration: float = 0.0  # 秒
    realtime_factor: float = 0.0  # RTF (処理時間/音声時間)

    def to_dict(self) -> Dict[str, Any]:
        """辞書に変換"""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "processing_time": self.processing_time,
            "cpu_usage_start": self.cpu_usage_start,
            "cpu_usage_end": self.cpu_usage_end,
            "cpu_usage_avg": self.cpu_usage_avg,
            "memory_start_mb": self.memory_start_mb,
            "memory_end_mb": self.memory_end_mb,
            "memory_peak_mb": self.memory_peak_mb,
            "memory_delta_mb": self.memory_delta_mb,
            "throughput": self.throughput,
            "files_processed": self.files_processed,
            "files_failed": self.files_failed,
            "total_audio_duration": self.total_audio_duration,
            "realtime_factor": self.realtime_factor
        }


class PerformanceMonitor:
    """
    パフォーマンスモニター

    Features:
    - CPU使用率の測定
    - メモリ使用量の追跡
    - 処理時間の計測
    - スループット計算
    - RTF（Real-Time Factor）計算
    - ベンチマークレポート生成
    """

    def __init__(self, enable_detailed_monitoring: bool = True):
        """
        初期化

        Args:
            enable_detailed_monitoring: 詳細モニタリングを有効にするか
        """
        self.enable_detailed_monitoring = enable_detailed_monitoring
        self.process = psutil.Process()

        # 現在のメトリクス
        self.current_metrics = PerformanceMetrics()

        # 履歴
        self.history: List[PerformanceMetrics] = []

        # サンプリング用
        self.cpu_samples: List[float] = []
        self.memory_samples: List[float] = []

        logger.info("PerformanceMonitor initialized")

    def __enter__(self):
        """コンテキストマネージャのエントリポイント"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャのエグジットポイント"""
        self.stop()
        return False

    def start(self) -> None:
        """モニタリング開始"""
        self.current_metrics = PerformanceMetrics()
        self.current_metrics.start_time = time.time()

        # 初期状態を記録
        self.current_metrics.cpu_usage_start = self.process.cpu_percent()
        memory_info = self.process.memory_info()
        self.current_metrics.memory_start_mb = memory_info.rss / 1024 / 1024

        # サンプリングリストをリセット
        self.cpu_samples = [self.current_metrics.cpu_usage_start]
        self.memory_samples = [self.current_metrics.memory_start_mb]

        logger.info("Performance monitoring started")

    def sample(self) -> None:
        """現在のCPU/メモリ使用量をサンプリング"""
        if not self.enable_detailed_monitoring:
            return

        try:
            cpu = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            self.cpu_samples.append(cpu)
            self.memory_samples.append(memory_mb)

            # ピークメモリを更新
            if memory_mb > self.current_metrics.memory_peak_mb:
                self.current_metrics.memory_peak_mb = memory_mb

        except Exception as e:
            logger.error(f"Error sampling performance: {e}")

    def stop(self) -> PerformanceMetrics:
        """
        モニタリング停止

        Returns:
            収集されたメトリクス
        """
        self.current_metrics.end_time = time.time()
        self.current_metrics.processing_time = (
            self.current_metrics.end_time - self.current_metrics.start_time
        )

        # 最終状態を記録
        self.current_metrics.cpu_usage_end = self.process.cpu_percent()
        memory_info = self.process.memory_info()
        self.current_metrics.memory_end_mb = memory_info.rss / 1024 / 1024

        # 平均CPU使用率を計算
        if self.cpu_samples:
            self.current_metrics.cpu_usage_avg = sum(self.cpu_samples) / len(self.cpu_samples)

        # メモリ変化量を計算
        self.current_metrics.memory_delta_mb = (
            self.current_metrics.memory_end_mb - self.current_metrics.memory_start_mb
        )

        # ピークメモリが記録されていない場合は終了時のメモリを使用
        if self.current_metrics.memory_peak_mb == 0:
            self.current_metrics.memory_peak_mb = self.current_metrics.memory_end_mb

        # スループットを計算
        if self.current_metrics.processing_time > 0:
            self.current_metrics.throughput = (
                self.current_metrics.files_processed / self.current_metrics.processing_time
            )

        # RTFを計算
        if self.current_metrics.total_audio_duration > 0:
            self.current_metrics.realtime_factor = (
                self.current_metrics.processing_time / self.current_metrics.total_audio_duration
            )

        # 履歴に追加
        self.history.append(self.current_metrics)

        logger.info(f"Performance monitoring stopped: {self.current_metrics.processing_time:.2f}s")

        return self.current_metrics

    def record_file_processed(self, success: bool = True, audio_duration: float = 0.0) -> None:
        """
        ファイル処理を記録

        Args:
            success: 成功したか
            audio_duration: 音声の長さ（秒）
        """
        if success:
            self.current_metrics.files_processed += 1
        else:
            self.current_metrics.files_failed += 1

        self.current_metrics.total_audio_duration += audio_duration

        # サンプリング
        self.sample()

    def get_current_metrics(self) -> PerformanceMetrics:
        """現在のメトリクスを取得"""
        return self.current_metrics

    def get_history(self) -> List[PerformanceMetrics]:
        """履歴を取得"""
        return self.history

    def generate_report(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        ベンチマークレポートを生成

        Args:
            output_path: レポートを保存するパス（Noneの場合は保存しない）

        Returns:
            レポートデータ
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "current_metrics": self.current_metrics.to_dict(),
            "summary": {
                "total_files_processed": sum(m.files_processed for m in self.history),
                "total_files_failed": sum(m.files_failed for m in self.history),
                "total_processing_time": sum(m.processing_time for m in self.history),
                "average_cpu_usage": (
                    sum(m.cpu_usage_avg for m in self.history) / len(self.history)
                    if self.history else 0
                ),
                "average_memory_mb": (
                    sum(m.memory_peak_mb for m in self.history) / len(self.history)
                    if self.history else 0
                ),
                "average_throughput": (
                    sum(m.throughput for m in self.history) / len(self.history)
                    if self.history else 0
                ),
                "average_rtf": (
                    sum(m.realtime_factor for m in self.history) / len(self.history)
                    if self.history else 0
                )
            },
            "history": [m.to_dict() for m in self.history]
        }

        # ファイルに保存
        if output_path:
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                logger.info(f"Performance report saved to: {output_path}")
            except Exception as e:
                logger.error(f"Error saving report: {e}")

        return report

    def print_summary(self) -> None:
        """サマリーを表示"""
        metrics = self.current_metrics

        print("\n" + "=" * 60)
        print("パフォーマンスサマリー")
        print("=" * 60)
        print(f"処理時間:          {metrics.processing_time:.2f}秒")
        print(f"処理ファイル数:    {metrics.files_processed}件")
        print(f"失敗ファイル数:    {metrics.files_failed}件")
        print(f"スループット:      {metrics.throughput:.2f}ファイル/秒")
        print(f"総音声時間:        {metrics.total_audio_duration:.2f}秒")
        print(f"RTF:               {metrics.realtime_factor:.2f}x")
        print(f"CPU使用率 (平均):  {metrics.cpu_usage_avg:.1f}%")
        print(f"メモリ使用量:")
        print(f"  開始:            {metrics.memory_start_mb:.1f}MB")
        print(f"  終了:            {metrics.memory_end_mb:.1f}MB")
        print(f"  ピーク:          {metrics.memory_peak_mb:.1f}MB")
        print(f"  変化量:          {metrics.memory_delta_mb:+.1f}MB")
        print("=" * 60 + "\n")


def benchmark(func: Callable, *args, **kwargs) -> tuple[Any, PerformanceMetrics]:
    """
    関数のベンチマークを実行

    Args:
        func: ベンチマーク対象の関数
        *args: 関数の引数
        **kwargs: 関数のキーワード引数

    Returns:
        (関数の戻り値, パフォーマンスメトリクス)
    """
    monitor = PerformanceMonitor()

    with monitor:
        result = func(*args, **kwargs)

    return result, monitor.get_current_metrics()


class BenchmarkComparison:
    """
    複数のベンチマーク結果を比較

    Features:
    - 複数の実装を比較
    - パフォーマンス改善率を計算
    - 詳細な比較レポート生成
    """

    def __init__(self):
        """初期化"""
        self.benchmarks: Dict[str, PerformanceMetrics] = {}

    def add_benchmark(self, name: str, metrics: PerformanceMetrics) -> None:
        """
        ベンチマーク結果を追加

        Args:
            name: ベンチマーク名
            metrics: メトリクス
        """
        self.benchmarks[name] = metrics
        logger.info(f"Added benchmark: {name}")

    def compare(self, baseline: str, target: str) -> Dict[str, Any]:
        """
        2つのベンチマークを比較

        Args:
            baseline: ベースラインの名前
            target: 比較対象の名前

        Returns:
            比較結果
        """
        if baseline not in self.benchmarks or target not in self.benchmarks:
            raise ValueError("Benchmark not found")

        base = self.benchmarks[baseline]
        targ = self.benchmarks[target]

        # 改善率を計算（負の値は改善、正の値は悪化）
        def calc_improvement(base_val: float, target_val: float) -> float:
            if base_val == 0:
                return 0.0
            return ((target_val - base_val) / base_val) * 100

        comparison = {
            "baseline": baseline,
            "target": target,
            "processing_time": {
                "baseline": base.processing_time,
                "target": targ.processing_time,
                "improvement_pct": -calc_improvement(base.processing_time, targ.processing_time)
            },
            "throughput": {
                "baseline": base.throughput,
                "target": targ.throughput,
                "improvement_pct": calc_improvement(base.throughput, targ.throughput)
            },
            "memory_peak": {
                "baseline": base.memory_peak_mb,
                "target": targ.memory_peak_mb,
                "improvement_pct": -calc_improvement(base.memory_peak_mb, targ.memory_peak_mb)
            },
            "rtf": {
                "baseline": base.realtime_factor,
                "target": targ.realtime_factor,
                "improvement_pct": -calc_improvement(base.realtime_factor, targ.realtime_factor)
            }
        }

        return comparison

    def print_comparison(self, baseline: str, target: str) -> None:
        """
        比較結果を表示

        Args:
            baseline: ベースライン名
            target: 比較対象名
        """
        comparison = self.compare(baseline, target)

        print("\n" + "=" * 60)
        print(f"ベンチマーク比較: {baseline} vs {target}")
        print("=" * 60)

        for metric, data in comparison.items():
            if metric in ["baseline", "target"]:
                continue

            print(f"\n{metric}:")
            print(f"  {baseline}: {data['baseline']:.2f}")
            print(f"  {target}: {data['target']:.2f}")
            improvement = data['improvement_pct']
            symbol = "↑" if improvement > 0 else "↓"
            print(f"  改善率: {symbol} {abs(improvement):.1f}%")

        print("=" * 60 + "\n")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== PerformanceMonitor Test ===\n")

    # ベンチマーク実行
    def test_function():
        """テスト関数"""
        time.sleep(1.0)
        return "Done"

    # コンテキストマネージャとして使用
    print("1. Running benchmark...")
    with PerformanceMonitor() as monitor:
        for i in range(5):
            time.sleep(0.2)
            monitor.record_file_processed(success=True, audio_duration=10.0)

    # サマリー表示
    print("\n2. Performance summary:")
    monitor.print_summary()

    # レポート生成
    print("\n3. Generating report...")
    report = monitor.generate_report()
    print(f"   Report generated with {len(report['history'])} entries")

    print("\nTest completed!")
