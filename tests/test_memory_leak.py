"""
1時間連続動作テスト - メモリリーク検証スクリプト

このスクリプトは以下を検証します:
- RealtimeAudioCaptureの繰り返し start/stop でのメモリリーク
- FasterWhisperEngineの繰り返し load/unload でのメモリリーク
- 長時間実行時のメモリ使用量の推移
- リソースリークの兆候検出

使用方法:
    python test_memory_leak.py [オプション]

オプション:
    --duration MINUTES     テスト時間（分）デフォルト: 60
    --interval SECONDS     測定間隔（秒）デフォルト: 30
    --quick-test           クイックテスト（5分）
    --output-dir DIR       出力ディレクトリ デフォルト: logs/memory_test
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import gc

# プロジェクトのsrcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# メモリプロファイリング用ライブラリ
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    print("WARNING: psutil not available. Install with: pip install psutil")
    PSUTIL_AVAILABLE = False

# グラフ生成用ライブラリ
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("WARNING: matplotlib not available. Install with: pip install matplotlib")
    MATPLOTLIB_AVAILABLE = False

# プロジェクトモジュール
from realtime_audio_capture import RealtimeAudioCapture
from faster_whisper_engine import FasterWhisperEngine, FASTER_WHISPER_AVAILABLE
from simple_vad import AdaptiveVAD
import numpy as np


class MemoryMonitor:
    """メモリ使用量のモニタリングクラス"""

    def __init__(self):
        if not PSUTIL_AVAILABLE:
            raise ImportError("psutil is required for memory monitoring")

        self.process = psutil.Process()
        self.measurements: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def measure(self, label: str = "") -> Dict[str, Any]:
        """現在のメモリ使用量を測定"""
        memory_info = self.process.memory_info()

        measurement = {
            "timestamp": time.time() - self.start_time,
            "datetime": datetime.now(),
            "label": label,
            "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size (物理メモリ)
            "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            "cpu_percent": self.process.cpu_percent(),
            "num_threads": self.process.num_threads(),
        }

        # システム全体のメモリ使用率も取得
        system_memory = psutil.virtual_memory()
        measurement["system_memory_percent"] = system_memory.percent

        self.measurements.append(measurement)
        return measurement

    def get_summary(self) -> Dict[str, Any]:
        """測定結果のサマリーを取得"""
        if not self.measurements:
            return {}

        rss_values = [m["rss_mb"] for m in self.measurements]
        vms_values = [m["vms_mb"] for m in self.measurements]

        return {
            "total_measurements": len(self.measurements),
            "duration_seconds": self.measurements[-1]["timestamp"],
            "rss_mb": {
                "initial": rss_values[0],
                "final": rss_values[-1],
                "min": min(rss_values),
                "max": max(rss_values),
                "average": sum(rss_values) / len(rss_values),
                "increase": rss_values[-1] - rss_values[0],
            },
            "vms_mb": {
                "initial": vms_values[0],
                "final": vms_values[-1],
                "min": min(vms_values),
                "max": max(vms_values),
                "average": sum(vms_values) / len(vms_values),
                "increase": vms_values[-1] - vms_values[0],
            },
        }

    def detect_memory_leak(self, threshold_mb: float = 50.0) -> bool:
        """メモリリークの兆候を検出"""
        summary = self.get_summary()
        if not summary:
            return False

        # RSS（物理メモリ）の増加量をチェック
        rss_increase = summary["rss_mb"]["increase"]

        return rss_increase > threshold_mb

    def plot_memory_usage(self, output_path: str) -> bool:
        """メモリ使用量をグラフ化"""
        if not MATPLOTLIB_AVAILABLE:
            print("matplotlib not available, skipping plot generation")
            return False

        if not self.measurements:
            print("No measurements to plot")
            return False

        # データの準備
        timestamps = [m["datetime"] for m in self.measurements]
        rss_values = [m["rss_mb"] for m in self.measurements]
        vms_values = [m["vms_mb"] for m in self.measurements]
        cpu_values = [m["cpu_percent"] for m in self.measurements]

        # グラフ作成
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # メモリ使用量のグラフ
        ax1.plot(timestamps, rss_values, label="RSS (Physical Memory)", marker="o", markersize=3)
        ax1.plot(timestamps, vms_values, label="VMS (Virtual Memory)", marker="s", markersize=3)
        ax1.set_xlabel("Time")
        ax1.set_ylabel("Memory (MB)")
        ax1.set_title("Memory Usage Over Time")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # CPU使用率のグラフ
        ax2.plot(timestamps, cpu_values, label="CPU Usage", color="green", marker="^", markersize=3)
        ax2.set_xlabel("Time")
        ax2.set_ylabel("CPU (%)")
        ax2.set_title("CPU Usage Over Time")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        print(f"Memory usage plot saved to: {output_path}")
        return True


class AudioCaptureStressTest:
    """RealtimeAudioCaptureのストレステスト"""

    def __init__(self, monitor: MemoryMonitor, logger: logging.Logger):
        self.monitor = monitor
        self.logger = logger
        self.iterations = 0

    def run_cycles(self, num_cycles: int = 10, cycle_duration: float = 5.0) -> bool:
        """
        繰り返し start/stop サイクルを実行

        Args:
            num_cycles: サイクル回数
            cycle_duration: 各サイクルの録音時間（秒）

        Returns:
            成功フラグ
        """
        self.logger.info(f"Starting AudioCapture stress test: {num_cycles} cycles")

        for i in range(num_cycles):
            self.logger.info(f"Cycle {i + 1}/{num_cycles}")

            # メモリ測定（サイクル開始前）
            self.monitor.measure(f"AudioCapture Cycle {i + 1} - Before")

            try:
                # コンテキストマネージャを使用
                with RealtimeAudioCapture() as capture:
                    # キャプチャ開始
                    if not capture.start_capture():
                        self.logger.error(f"Failed to start capture in cycle {i + 1}")
                        return False

                    # 録音
                    time.sleep(cycle_duration)

                    # キャプチャ停止
                    capture.stop_capture()

                    # メモリ測定（サイクル終了後）
                    self.monitor.measure(f"AudioCapture Cycle {i + 1} - After")

                # コンテキストマネージャを抜ける（自動クリーンアップ）

                # ガベージコレクション強制実行
                gc.collect()

                self.iterations += 1

            except Exception as e:
                self.logger.error(f"Error in cycle {i + 1}: {e}")
                return False

            # 短い待機時間（次のサイクルへ）
            time.sleep(1.0)

        self.logger.info(f"AudioCapture stress test completed: {self.iterations} iterations")
        return True


class WhisperEngineStressTest:
    """FasterWhisperEngineのストレステスト"""

    def __init__(self, monitor: MemoryMonitor, logger: logging.Logger):
        self.monitor = monitor
        self.logger = logger
        self.iterations = 0

    def run_cycles(self, num_cycles: int = 10, model_size: str = "tiny") -> bool:
        """
        繰り返し load/transcribe/unload サイクルを実行

        Args:
            num_cycles: サイクル回数
            model_size: モデルサイズ

        Returns:
            成功フラグ
        """
        if not FASTER_WHISPER_AVAILABLE:
            self.logger.error("faster-whisper not available")
            return False

        self.logger.info(f"Starting WhisperEngine stress test: {num_cycles} cycles")

        # テスト用音声データ（3秒の無音）
        test_audio = np.zeros(16000 * 3, dtype=np.float32)

        for i in range(num_cycles):
            self.logger.info(f"Cycle {i + 1}/{num_cycles}")

            # メモリ測定（サイクル開始前）
            self.monitor.measure(f"WhisperEngine Cycle {i + 1} - Before")

            try:
                # コンテキストマネージャを使用
                with FasterWhisperEngine(model_size=model_size, device="auto") as engine:
                    # 文字起こし実行
                    result = engine.transcribe(test_audio)

                    self.logger.info(
                        f"Transcription RTF: {result.get('realtime_factor', 0):.2f}x"
                    )

                    # メモリ測定（処理後）
                    self.monitor.measure(f"WhisperEngine Cycle {i + 1} - After")

                # コンテキストマネージャを抜ける（自動アンロード）

                # ガベージコレクション強制実行
                gc.collect()

                self.iterations += 1

            except Exception as e:
                self.logger.error(f"Error in cycle {i + 1}: {e}")
                return False

            # 短い待機時間（次のサイクルへ）
            time.sleep(2.0)

        self.logger.info(f"WhisperEngine stress test completed: {self.iterations} iterations")
        return True


class IntegratedStressTest:
    """統合ストレステスト（AudioCapture + WhisperEngine + VAD）"""

    def __init__(self, monitor: MemoryMonitor, logger: logging.Logger):
        self.monitor = monitor
        self.logger = logger
        self.iterations = 0

    def run_cycles(
        self,
        num_cycles: int = 5,
        cycle_duration: float = 10.0,
        model_size: str = "tiny"
    ) -> bool:
        """
        統合テストサイクルを実行

        Args:
            num_cycles: サイクル回数
            cycle_duration: 各サイクルの録音時間（秒）
            model_size: Whisperモデルサイズ

        Returns:
            成功フラグ
        """
        if not FASTER_WHISPER_AVAILABLE:
            self.logger.error("faster-whisper not available")
            return False

        self.logger.info(f"Starting Integrated stress test: {num_cycles} cycles")

        for i in range(num_cycles):
            self.logger.info(f"Cycle {i + 1}/{num_cycles}")

            # メモリ測定（サイクル開始前）
            self.monitor.measure(f"Integrated Cycle {i + 1} - Before")

            try:
                # 全コンポーネントをコンテキストマネージャで作成
                with RealtimeAudioCapture() as capture, \
                     FasterWhisperEngine(model_size=model_size) as engine:

                    # VAD作成
                    vad = AdaptiveVAD()

                    # 音声キャプチャ開始
                    transcription_count = 0

                    def on_audio_chunk(audio_chunk):
                        nonlocal transcription_count

                        # VADチェック
                        is_speech, energy = vad.is_speech_present(audio_chunk)

                        if is_speech:
                            # 文字起こし実行
                            text = engine.transcribe_stream(audio_chunk)
                            if text and text.strip():
                                transcription_count += 1
                                self.logger.debug(f"Transcribed: {text[:50]}...")

                    capture.on_audio_chunk = on_audio_chunk

                    if not capture.start_capture():
                        self.logger.error(f"Failed to start capture in cycle {i + 1}")
                        return False

                    # 録音
                    time.sleep(cycle_duration)

                    # 停止
                    capture.stop_capture()

                    self.logger.info(
                        f"Cycle {i + 1} completed: {transcription_count} transcriptions"
                    )

                    # メモリ測定（サイクル終了後）
                    self.monitor.measure(f"Integrated Cycle {i + 1} - After")

                # コンテキストマネージャを抜ける（自動クリーンアップ）

                # ガベージコレクション強制実行
                gc.collect()

                self.iterations += 1

            except Exception as e:
                self.logger.error(f"Error in cycle {i + 1}: {e}")
                return False

            # 次のサイクルへの待機時間
            time.sleep(2.0)

        self.logger.info(f"Integrated stress test completed: {self.iterations} iterations")
        return True


def setup_logging(output_dir: Path) -> logging.Logger:
    """ロギング設定"""
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = output_dir / f"memory_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Log file: {log_file}")

    return logger


def generate_report(
    monitor: MemoryMonitor,
    output_dir: Path,
    test_duration: float,
    audio_iterations: int,
    whisper_iterations: int,
    integrated_iterations: int
) -> None:
    """テストレポートを生成"""
    report_file = output_dir / f"memory_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    summary = monitor.get_summary()
    memory_leak_detected = monitor.detect_memory_leak()

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("メモリリーク検証テスト - レポート\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"テスト日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"テスト時間: {test_duration:.2f} 秒 ({test_duration / 60:.2f} 分)\n")
        f.write(f"測定回数: {summary.get('total_measurements', 0)}\n\n")

        f.write("=" * 80 + "\n")
        f.write("テスト実行回数\n")
        f.write("=" * 80 + "\n")
        f.write(f"AudioCapture サイクル: {audio_iterations}\n")
        f.write(f"WhisperEngine サイクル: {whisper_iterations}\n")
        f.write(f"統合テスト サイクル: {integrated_iterations}\n\n")

        f.write("=" * 80 + "\n")
        f.write("メモリ使用量サマリー (RSS - 物理メモリ)\n")
        f.write("=" * 80 + "\n")
        if "rss_mb" in summary:
            rss = summary["rss_mb"]
            f.write(f"初期値:   {rss['initial']:.2f} MB\n")
            f.write(f"最終値:   {rss['final']:.2f} MB\n")
            f.write(f"最小値:   {rss['min']:.2f} MB\n")
            f.write(f"最大値:   {rss['max']:.2f} MB\n")
            f.write(f"平均値:   {rss['average']:.2f} MB\n")
            f.write(f"増加量:   {rss['increase']:.2f} MB\n\n")

        f.write("=" * 80 + "\n")
        f.write("メモリ使用量サマリー (VMS - 仮想メモリ)\n")
        f.write("=" * 80 + "\n")
        if "vms_mb" in summary:
            vms = summary["vms_mb"]
            f.write(f"初期値:   {vms['initial']:.2f} MB\n")
            f.write(f"最終値:   {vms['final']:.2f} MB\n")
            f.write(f"最小値:   {vms['min']:.2f} MB\n")
            f.write(f"最大値:   {vms['max']:.2f} MB\n")
            f.write(f"平均値:   {vms['average']:.2f} MB\n")
            f.write(f"増加量:   {vms['increase']:.2f} MB\n\n")

        f.write("=" * 80 + "\n")
        f.write("メモリリーク検出結果\n")
        f.write("=" * 80 + "\n")
        if memory_leak_detected:
            f.write("警告: メモリリークの兆候が検出されました！\n")
            f.write(f"      物理メモリが 50MB 以上増加しています\n")
        else:
            f.write("OK: メモリリークの兆候は検出されませんでした\n")

        f.write("\n" + "=" * 80 + "\n")

    print(f"\nレポートファイル: {report_file}")


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="KotobaTranscriber メモリリーク検証テスト",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="テスト時間（分）デフォルト: 60"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="測定間隔（秒）デフォルト: 30"
    )

    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="クイックテスト（5分）"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="logs/memory_test",
        help="出力ディレクトリ デフォルト: logs/memory_test"
    )

    args = parser.parse_args()

    # クイックテストモード
    if args.quick_test:
        args.duration = 5
        args.interval = 15

    # 必須ライブラリのチェック
    if not PSUTIL_AVAILABLE:
        print("ERROR: psutil is required for memory monitoring")
        print("Install with: pip install psutil")
        return 1

    # 出力ディレクトリの準備
    output_dir = Path(args.output_dir)
    logger = setup_logging(output_dir)

    logger.info("=" * 80)
    logger.info("KotobaTranscriber メモリリーク検証テスト")
    logger.info("=" * 80)
    logger.info(f"テスト時間: {args.duration} 分")
    logger.info(f"測定間隔: {args.interval} 秒")
    logger.info(f"出力ディレクトリ: {output_dir.absolute()}")
    logger.info("=" * 80)

    # メモリモニター初期化
    monitor = MemoryMonitor()
    monitor.measure("Test Start")

    # テスト開始時刻
    start_time = time.time()
    end_time = start_time + (args.duration * 60)

    # テスト統計
    audio_iterations = 0
    whisper_iterations = 0
    integrated_iterations = 0

    # ストレステストインスタンス作成
    audio_test = AudioCaptureStressTest(monitor, logger)
    whisper_test = WhisperEngineStressTest(monitor, logger)
    integrated_test = IntegratedStressTest(monitor, logger)

    try:
        # メインループ
        cycle_count = 0
        while time.time() < end_time:
            cycle_count += 1
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Test Cycle {cycle_count}")
            logger.info(f"{'=' * 80}")

            # 1. AudioCapture ストレステスト
            logger.info("\n[1/3] AudioCapture Stress Test")
            if audio_test.run_cycles(num_cycles=3, cycle_duration=3.0):
                audio_iterations = audio_test.iterations
            else:
                logger.error("AudioCapture stress test failed")

            time.sleep(2)

            # 2. WhisperEngine ストレステスト
            logger.info("\n[2/3] WhisperEngine Stress Test")
            if whisper_test.run_cycles(num_cycles=2, model_size="tiny"):
                whisper_iterations = whisper_test.iterations
            else:
                logger.error("WhisperEngine stress test failed")

            time.sleep(2)

            # 3. 統合ストレステスト
            logger.info("\n[3/3] Integrated Stress Test")
            if integrated_test.run_cycles(num_cycles=2, cycle_duration=5.0):
                integrated_iterations = integrated_test.iterations
            else:
                logger.error("Integrated stress test failed")

            # 測定間隔まで待機
            elapsed = time.time() - start_time
            remaining = end_time - time.time()

            logger.info(f"\nElapsed: {elapsed / 60:.2f} min, Remaining: {remaining / 60:.2f} min")
            logger.info(f"Total iterations - Audio: {audio_iterations}, "
                       f"Whisper: {whisper_iterations}, Integrated: {integrated_iterations}")

            # メモリ測定
            measurement = monitor.measure(f"Cycle {cycle_count} End")
            logger.info(f"Memory - RSS: {measurement['rss_mb']:.2f} MB, "
                       f"VMS: {measurement['vms_mb']:.2f} MB, "
                       f"CPU: {measurement['cpu_percent']:.1f}%")

            # 次の測定まで待機（残り時間を考慮）
            if remaining > args.interval:
                logger.info(f"Waiting {args.interval} seconds until next cycle...\n")
                time.sleep(args.interval)
            elif remaining > 0:
                logger.info(f"Waiting {remaining:.1f} seconds until test end...\n")
                time.sleep(remaining)

    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")

    except Exception as e:
        logger.error(f"\n\nTest failed with error: {e}", exc_info=True)

    finally:
        # 最終測定
        monitor.measure("Test End")

        # テスト時間の計算
        test_duration = time.time() - start_time

        logger.info("\n" + "=" * 80)
        logger.info("テスト完了")
        logger.info("=" * 80)
        logger.info(f"実行時間: {test_duration:.2f} 秒 ({test_duration / 60:.2f} 分)")
        logger.info(f"総イテレーション数:")
        logger.info(f"  - AudioCapture: {audio_iterations}")
        logger.info(f"  - WhisperEngine: {whisper_iterations}")
        logger.info(f"  - Integrated: {integrated_iterations}")

        # メモリリーク検出
        if monitor.detect_memory_leak():
            logger.warning("\n警告: メモリリークの兆候が検出されました！")
        else:
            logger.info("\nOK: メモリリークの兆候は検出されませんでした")

        # グラフ生成
        plot_path = output_dir / f"memory_usage_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        if monitor.plot_memory_usage(str(plot_path)):
            logger.info(f"グラフ保存: {plot_path}")

        # レポート生成
        generate_report(
            monitor,
            output_dir,
            test_duration,
            audio_iterations,
            whisper_iterations,
            integrated_iterations
        )

        logger.info("\nすべての結果は以下に保存されました:")
        logger.info(f"  {output_dir.absolute()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
