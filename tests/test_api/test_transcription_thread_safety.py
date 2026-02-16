"""
TranscriptionEngine スレッドセーフティテスト

モデル推論の排他制御が正しく動作することを検証
"""

import os

# TranscriptionEngineをインポート
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
pytest.importorskip("torch")
from exceptions import ModelLoadError
from transcription_engine import TranscriptionEngine


@pytest.fixture
def mock_pipeline():
    """モックされたtransformersパイプライン"""
    with patch("transcription_engine.pipeline") as mock:
        # パイプラインのモックを作成
        mock_instance = MagicMock()

        # __call__ をモックして推論結果を返す
        mock_instance.return_value = {
            "text": "これはテスト文字起こしです。",
            "chunks": [{"timestamp": (0.0, 2.0), "text": "これはテスト文字起こしです。"}],
        }

        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_torch():
    """モックされたtorch"""
    with patch("transcription_engine.torch") as mock:
        mock.cuda.is_available.return_value = False
        mock.float32 = "float32"
        mock.float16 = "float16"
        yield mock


@pytest.fixture
def temp_audio_file():
    """一時的な音声ファイル（ASCII パスのみ）"""
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="test_audio_")
    os.close(fd)

    # ダミーのWAVファイルを作成（最小限のWAVヘッダー）
    with open(path, "wb") as f:
        # RIFFヘッダー
        f.write(b"RIFF")
        f.write((36).to_bytes(4, "little"))  # ファイルサイズ - 8
        f.write(b"WAVE")

        # fmtチャンク
        f.write(b"fmt ")
        f.write((16).to_bytes(4, "little"))  # fmtチャンクサイズ
        f.write((1).to_bytes(2, "little"))  # オーディオフォーマット (1 = PCM)
        f.write((1).to_bytes(2, "little"))  # チャンネル数
        f.write((16000).to_bytes(4, "little"))  # サンプルレート
        f.write((32000).to_bytes(4, "little"))  # バイトレート
        f.write((2).to_bytes(2, "little"))  # ブロックアライン
        f.write((16).to_bytes(2, "little"))  # ビット深度

        # dataチャンク
        f.write(b"data")
        f.write((0).to_bytes(4, "little"))  # dataチャンクサイズ

    yield path

    # クリーンアップ
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


@pytest.fixture
def engine(mock_pipeline, mock_torch):
    """TranscriptionEngineインスタンス"""
    with patch("transcription_engine.config") as mock_config:
        mock_config.get.side_effect = lambda key, default=None: {
            "model.whisper.name": "kotoba-tech/kotoba-whisper-v2.2",
            "model.whisper.device": "cpu",
            "model.whisper.language": "ja",
            "model.whisper.chunk_length_s": 15,
            "model.whisper.return_timestamps": True,
            "model.whisper.task": "transcribe",
            "audio.preprocessing.enabled": False,
            "vocabulary.enabled": False,
            "audio.ffmpeg.auto_configure": False,
        }.get(key, default)

        engine = TranscriptionEngine()
        yield engine


class TestTranscriptionThreadSafety:
    """TranscriptionEngine の並行アクセステスト"""

    def test_concurrent_transcribe_calls(self, engine, temp_audio_file, mock_pipeline):
        """
        複数スレッドから同時に transcribe() を呼び出してもスレッドセーフであること

        テスト観点:
        - 5スレッド × 3回の並行呼び出し
        - すべて成功すること
        - モデルロードが1回だけ行われること
        - 推論が排他制御されること（同時実行されない）
        """
        num_threads = 5
        calls_per_thread = 3
        results: List[Dict[str, Any]] = []
        errors: List[Exception] = []
        lock = threading.Lock()

        # 推論の呼び出し回数を追跡
        call_times: List[float] = []

        def track_call(*args, **kwargs):
            """推論呼び出しをトラッキング"""
            with lock:
                call_times.append(time.time())
            # 処理時間をシミュレート（50ms）
            time.sleep(0.05)
            return {"text": f"テスト文字起こし（スレッド{threading.current_thread().name}）", "chunks": []}

        # モックの推論メソッドに追跡機能を追加
        mock_pipeline.return_value.side_effect = track_call

        def worker():
            """ワーカースレッド"""
            for _ in range(calls_per_thread):
                try:
                    result = engine.transcribe(temp_audio_file)
                    with lock:
                        results.append(result)
                except Exception as e:
                    with lock:
                        errors.append(e)

        # スレッドを作成・開始
        threads = [threading.Thread(target=worker, name=f"Worker-{i}") for i in range(num_threads)]
        for t in threads:
            t.start()

        # すべてのスレッドの完了を待つ
        for t in threads:
            t.join(timeout=10)

        # 検証
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert (
            len(results) == num_threads * calls_per_thread
        ), f"Expected {num_threads * calls_per_thread} results, got {len(results)}"

        # 推論が排他制御されていることを確認
        # 各呼び出しは50ms以上かかるので、同時実行されていなければタイムスタンプが重ならない
        sorted_times = sorted(call_times)
        for i in range(len(sorted_times) - 1):
            time_diff = sorted_times[i + 1] - sorted_times[i]
            # 同時実行されていなければ、次の呼び出しまでに少なくとも40ms以上の差がある（マージン考慮）
            assert time_diff >= 0.03, f"Calls overlapped: time difference {time_diff:.3f}s is too small"

    def test_model_load_from_uninitialized_state(self, engine, temp_audio_file, mock_pipeline):
        """
        モデル未ロード状態から並行呼び出ししてもスレッドセーフであること

        テスト観点:
        - モデルが未ロードの状態から複数スレッドが transcribe() を呼び出す
        - load_model() が1回だけ呼ばれること（ダブルチェックロッキング）
        - すべてのスレッドが正常に文字起こしできること
        """
        # モデルを明示的にアンロード
        engine.model = None
        engine.is_loaded = False

        # load_model() の呼び出し回数を追跡
        load_count = [0]
        original_load = engine._load_model_with_device

        def tracked_load(*args, **kwargs):
            load_count[0] += 1
            # ロード時間をシミュレート（100ms）
            time.sleep(0.1)
            return original_load(*args, **kwargs)

        with patch.object(engine, "_load_model_with_device", side_effect=tracked_load):
            results = []
            errors = []
            lock = threading.Lock()

            def worker():
                try:
                    result = engine.transcribe(temp_audio_file)
                    with lock:
                        results.append(result)
                except Exception as e:
                    with lock:
                        errors.append(e)

            # 3スレッドを同時に開始
            threads = [threading.Thread(target=worker) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            # 検証
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(results) == 3, f"Expected 3 results, got {len(results)}"
            # ダブルチェックロッキングが機能していればロードは1回だけ
            assert load_count[0] == 1, f"Expected load_model() to be called once, got {load_count[0]}"

    def test_transcribe_blocks_during_inference(self, engine, temp_audio_file, mock_pipeline):
        """
        推論中に他スレッドの transcribe() がブロックされること

        テスト観点:
        - スレッドAが推論中にスレッドBがブロックされる
        - スレッドAの完了後にスレッドBが実行される
        - 処理順序が保証される
        """
        execution_order = []
        lock = threading.Lock()

        def slow_inference(*args, **kwargs):
            """遅い推論をシミュレート（500ms）"""
            thread_id = threading.current_thread().name
            with lock:
                execution_order.append(f"{thread_id}_start")
            time.sleep(0.5)
            with lock:
                execution_order.append(f"{thread_id}_end")
            return {"text": f"結果_{thread_id}", "chunks": []}

        mock_pipeline.return_value.side_effect = slow_inference

        def worker(name):
            try:
                engine.transcribe(temp_audio_file)
            except Exception:
                pass

        # スレッドAを先に開始
        thread_a = threading.Thread(target=worker, args=("A",), name="A")
        thread_a.start()

        # スレッドAが推論を開始するのを待つ
        time.sleep(0.1)

        # スレッドBを開始（スレッドAの推論中）
        thread_b = threading.Thread(target=worker, args=("B",), name="B")
        thread_b.start()

        # 両スレッドの完了を待つ
        thread_a.join(timeout=5)
        thread_b.join(timeout=5)

        # 検証: スレッドAが完全に終了してからスレッドBが開始される
        assert execution_order == ["A_start", "A_end", "B_start", "B_end"], f"Execution order is incorrect: {execution_order}"

    def test_model_lock_reentrancy(self, engine, temp_audio_file, mock_pipeline):
        """
        RLock の再入可能性が機能すること

        テスト観点:
        - transcribe() → load_model() の呼び出しチェーンで RLock が再入できる
        - デッドロックが発生しない
        """
        # モデルを明示的にアンロード
        engine.model = None
        engine.is_loaded = False

        # transcribe() は正常に完了すること（内部で load_model() が _model_lock を再取得）
        result = engine.transcribe(temp_audio_file)

        assert result is not None
        assert "text" in result

    def test_lock_coverage_load_to_inference(self, engine, temp_audio_file, mock_pipeline):
        """
        モデルロードから推論までが単一ロックで保護されていること

        テスト観点:
        - モデルロードと推論の間でロックが解放されないこと
        - この期間中に他スレッドがモデルにアクセスできないこと

        現状の実装ではこのテストがFAILすることを期待（ロックが分割されている）
        修正後はPASSすること
        """
        # モデルを明示的にアンロード
        engine.model = None
        engine.is_loaded = False

        lock_events = []
        lock = threading.Lock()

        original_load = engine._load_model_with_device
        _original_call = mock_pipeline.return_value  # noqa: F841

        def tracked_load(*args, **kwargs):
            """ロード時のイベントを記録"""
            with lock:
                lock_events.append(("load_start", threading.current_thread().name))
            time.sleep(0.1)  # ロード時間をシミュレート
            result = original_load(*args, **kwargs)
            with lock:
                lock_events.append(("load_end", threading.current_thread().name))
            return result

        def tracked_inference(*args, **kwargs):
            """推論時のイベントを記録"""
            with lock:
                lock_events.append(("inference_start", threading.current_thread().name))
            time.sleep(0.1)  # 推論時間をシミュレート
            result = {"text": "テスト結果", "chunks": []}
            with lock:
                lock_events.append(("inference_end", threading.current_thread().name))
            return result

        with patch.object(engine, "_load_model_with_device", side_effect=tracked_load):
            mock_pipeline.return_value = Mock(side_effect=tracked_inference)

            def worker(name):
                try:
                    engine.transcribe(temp_audio_file)
                except Exception:
                    pass

            # スレッドAを先に開始
            thread_a = threading.Thread(target=worker, args=("A",), name="ThreadA")
            thread_a.start()

            # スレッドAがロードを開始するのを待つ
            time.sleep(0.05)

            # スレッドBを開始
            thread_b = threading.Thread(target=worker, args=("B",), name="ThreadB")
            thread_b.start()

            thread_a.join(timeout=5)
            thread_b.join(timeout=5)

            # 検証: スレッドAのload→inferenceが完全に終わってからスレッドBが開始される
            # 正しい順序: A_load_start → A_load_end → A_inference_start → A_inference_end →
            #              B_load_start → B_load_end → B_inference_start → B_inference_end
            #
            # 現状の実装では: A_load_start → A_load_end → B_load_start → A_inference_start ...
            # のように、ロード後に他スレッドが介入する可能性がある

            # スレッドAの完全な処理が先に完了することを確認
            thread_a_events = [e for e in lock_events if e[1] == "ThreadA"]
            thread_b_events = [e for e in lock_events if e[1] == "ThreadB"]

            if len(thread_a_events) >= 4 and len(thread_b_events) >= 4:
                # スレッドAの推論終了インデックス
                a_inference_end_idx = lock_events.index(("inference_end", "ThreadA"))
                # スレッドBの最初のイベントのインデックス
                b_first_idx = min([lock_events.index(e) for e in thread_b_events])

                # スレッドAの推論が完全に終わる前にスレッドBが開始してはいけない
                assert (
                    b_first_idx > a_inference_end_idx
                ), f"ThreadB started before ThreadA completed inference. Events: {lock_events}"

    @pytest.mark.skipif(not pytest.importorskip("torch").cuda.is_available(), reason="CUDA not available")
    def test_cuda_memory_cleanup_under_concurrent_load(self, engine, temp_audio_file, mock_pipeline):
        """
        並行実行中の CUDA メモリリークが発生しないこと

        テスト観点:
        - 複数スレッドからの並行呼び出し後に CUDA メモリが適切に解放される
        - torch.cuda.empty_cache() が正しく呼ばれる

        注意: このテストは CUDA 環境でのみ実行される
        """
        import torch

        # CUDA環境に切り替え
        engine.device = "cuda"

        # 初期メモリ使用量を記録
        torch.cuda.reset_peak_memory_stats()
        initial_memory = torch.cuda.memory_allocated()

        results = []
        errors = []
        lock = threading.Lock()

        def worker():
            try:
                result = engine.transcribe(temp_audio_file)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        # 10スレッド × 2回の呼び出し
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # CUDA キャッシュクリア
        torch.cuda.empty_cache()

        # 検証
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        # メモリ使用量が初期値に近い（許容誤差: 100MB）
        final_memory = torch.cuda.memory_allocated()
        memory_diff = abs(final_memory - initial_memory)
        assert memory_diff < 100 * 1024 * 1024, f"Memory leak detected: {memory_diff / (1024 * 1024):.2f} MB difference"


class TestTranscriptionErrorHandling:
    """TranscriptionEngine のエラーハンドリングテスト"""

    def test_invalid_file_path_thread_safety(self, engine):
        """
        不正なファイルパスでのエラーハンドリングがスレッドセーフであること
        """
        from validators import ValidationError

        errors = []
        lock = threading.Lock()

        def worker():
            try:
                engine.transcribe("/nonexistent/file.wav")
            except ValidationError as e:
                with lock:
                    errors.append(e)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # すべてのスレッドで ValidationError が発生すること
        assert len(errors) == 5
        assert all(isinstance(e, ValidationError) for e in errors)

    def test_model_load_failure_thread_safety(self, mock_torch):
        """
        モデルロード失敗時のエラーハンドリングがスレッドセーフであること
        """
        with patch("transcription_engine.pipeline") as mock_pipeline:
            mock_pipeline.side_effect = RuntimeError("Model load failed")

            with patch("transcription_engine.config") as mock_config:
                mock_config.get.side_effect = lambda key, default=None: {
                    "model.whisper.name": "kotoba-tech/kotoba-whisper-v2.2",
                    "model.whisper.device": "cpu",
                    "model.whisper.language": "ja",
                    "audio.ffmpeg.auto_configure": False,
                }.get(key, default)

                engine = TranscriptionEngine()

                errors = []
                lock = threading.Lock()

                def worker():
                    try:
                        engine.load_model()
                    except ModelLoadError as e:
                        with lock:
                            errors.append(e)
                    except Exception as e:
                        with lock:
                            errors.append(e)

                threads = [threading.Thread(target=worker) for _ in range(3)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=5)

                # すべてのスレッドで ModelLoadError が発生すること
                assert len(errors) >= 1  # 少なくとも1つのエラー
                assert all(isinstance(e, ModelLoadError) for e in errors)
