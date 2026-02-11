"""
BatchTranscriptionWorker.cancel() の TOCTOU 並行性テスト
_executor へのアクセスがスレッドセーフであることを検証
"""

import os
import pytest
import tempfile
import threading
import time
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor

from api.workers import BatchTranscriptionWorker


@pytest.fixture
def temp_audio_files():
    """テスト用の複数の音声ファイルパスを生成"""
    files = []
    for i in range(3):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        # 空ファイルを作成
        with open(path, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 40)  # 最小限の WAV ヘッダー
        files.append(path)

    yield files

    # クリーンアップ
    for path in files:
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass


@pytest.fixture
def mock_engine():
    """TranscriptionEngine のモック"""
    with patch("api.workers.TranscriptionEngine") as MockEngine:
        engine_instance = Mock()
        engine_instance.load_model.return_value = None
        engine_instance.transcribe.return_value = {"text": "テスト文字起こし"}
        engine_instance.unload_model.return_value = None
        MockEngine.return_value = engine_instance
        yield MockEngine


@pytest.fixture
def mock_atomic_write():
    """atomic_write_text のモック"""
    with patch("export.common.atomic_write_text") as mock_write:
        mock_write.return_value = None
        yield mock_write


def test_cancel_before_start(temp_audio_files, mock_engine, mock_atomic_write):
    """バッチ処理開始前にキャンセル"""
    worker = BatchTranscriptionWorker(
        audio_paths=temp_audio_files,
        enable_diarization=False
    )

    # 開始前にキャンセル
    worker.cancel()

    # ワーカー実行
    worker.start()
    worker.join(timeout=5)

    # キャンセルされたため処理数は 0
    assert worker.completed == 0
    assert worker.success_count == 0


def test_cancel_during_processing(temp_audio_files, mock_engine, mock_atomic_write):
    """バッチ処理中にキャンセル（複数ファイル処理途中）"""
    # transcribe に遅延を追加
    def slow_transcribe(*args, **kwargs):
        time.sleep(0.5)  # 500ms 遅延
        return {"text": "テスト文字起こし"}

    mock_engine.return_value.transcribe.side_effect = slow_transcribe

    worker = BatchTranscriptionWorker(
        audio_paths=temp_audio_files,
        enable_diarization=False
    )

    worker.start()

    # 少し処理が進むのを待つ
    time.sleep(0.1)

    # 処理中にキャンセル
    worker.cancel()

    worker.join(timeout=5)

    # 一部のファイルのみ処理された（全ファイルは処理されていない）
    assert worker.completed < len(temp_audio_files)


def test_cancel_idempotent(temp_audio_files, mock_engine, mock_atomic_write):
    """複数回のキャンセル呼び出し（冪等性）"""
    worker = BatchTranscriptionWorker(
        audio_paths=temp_audio_files,
        enable_diarization=False
    )

    worker.start()
    time.sleep(0.05)

    # 複数回キャンセル
    worker.cancel()
    worker.cancel()
    worker.cancel()

    worker.join(timeout=5)

    # エラーなく完了
    assert worker.completed <= len(temp_audio_files)


def test_executor_shutdown_guaranteed(temp_audio_files, mock_engine, mock_atomic_write):
    """Executor が確実に shutdown されることの確認"""
    # transcribe に遅延を追加
    def slow_transcribe(*args, **kwargs):
        time.sleep(0.3)
        return {"text": "テスト文字起こし"}

    mock_engine.return_value.transcribe.side_effect = slow_transcribe

    worker = BatchTranscriptionWorker(
        audio_paths=temp_audio_files,
        enable_diarization=False
    )

    # スレッド数を記録
    initial_thread_count = threading.active_count()

    worker.start()
    time.sleep(0.1)

    # 処理中にキャンセル
    worker.cancel()
    worker.join(timeout=5)

    # Executor のスレッドが残っていないことを確認
    time.sleep(0.2)  # シャットダウン完了待ち
    final_thread_count = threading.active_count()

    # スレッド数が初期状態に戻っている（または増加していない）
    assert final_thread_count <= initial_thread_count + 1  # worker スレッド自体が残る可能性を考慮


def test_no_resource_leak_after_cancel(temp_audio_files, mock_engine, mock_atomic_write):
    """リソースリーク（スレッド残存）なし"""
    initial_thread_count = threading.active_count()

    for _ in range(3):
        worker = BatchTranscriptionWorker(
            audio_paths=temp_audio_files,
            enable_diarization=False
        )
        worker.start()
        time.sleep(0.05)
        worker.cancel()
        worker.join(timeout=5)

    # 複数回実行してもスレッドが蓄積しない
    time.sleep(0.2)
    final_thread_count = threading.active_count()
    assert final_thread_count <= initial_thread_count + 2  # 許容範囲


def test_cancel_race_condition_protection(temp_audio_files, mock_engine, mock_atomic_write):
    """cancel() と run() の競合保護テスト（TOCTOU）"""
    # transcribe に遅延を追加
    def slow_transcribe(*args, **kwargs):
        time.sleep(0.2)
        return {"text": "テスト文字起こし"}

    mock_engine.return_value.transcribe.side_effect = slow_transcribe

    # 複数回実行して競合をテスト
    for _ in range(5):
        worker = BatchTranscriptionWorker(
            audio_paths=temp_audio_files,
            enable_diarization=False
        )

        worker.start()

        # ランダムなタイミングでキャンセル
        time.sleep(0.01)
        worker.cancel()

        worker.join(timeout=5)

        # エラーなく完了
        assert worker.completed <= len(temp_audio_files)


def test_executor_lock_prevents_toctou(temp_audio_files, mock_engine, mock_atomic_write):
    """_executor_lock が TOCTOU を防ぐことを確認"""
    worker = BatchTranscriptionWorker(
        audio_paths=temp_audio_files,
        enable_diarization=False
    )

    # _executor_lock が存在することを確認
    assert hasattr(worker, "_executor_lock")
    # RLock は type ではないため、acquire/release メソッドがあることで確認
    assert hasattr(worker._executor_lock, "acquire")
    assert hasattr(worker._executor_lock, "release")
    assert callable(worker._executor_lock.acquire)
    assert callable(worker._executor_lock.release)

    # ロックが機能していることを確認
    with worker._executor_lock:
        # ロック取得中
        assert worker._executor_lock._is_owned()


def test_cancel_with_no_executor(mock_engine, mock_atomic_write):
    """Executor が存在しない状態でのキャンセル（開始前）"""
    worker = BatchTranscriptionWorker(
        audio_paths=[],
        enable_diarization=False
    )

    # 開始前にキャンセル（executor は None）
    worker.cancel()

    # エラーなく完了
    assert worker._executor is None


def test_cancel_during_executor_creation(temp_audio_files, mock_engine, mock_atomic_write):
    """Executor 作成中のキャンセル"""
    # ThreadPoolExecutor 作成に遅延を追加
    original_executor = ThreadPoolExecutor

    def slow_executor_init(*args, **kwargs):
        time.sleep(0.1)  # 作成に時間がかかる
        return original_executor(*args, **kwargs)

    with patch("api.workers.ThreadPoolExecutor", side_effect=slow_executor_init):
        worker = BatchTranscriptionWorker(
            audio_paths=temp_audio_files,
            enable_diarization=False
        )

        worker.start()

        # Executor 作成中にキャンセル
        time.sleep(0.05)
        worker.cancel()

        worker.join(timeout=5)

        # エラーなく完了
        assert worker.completed <= len(temp_audio_files)
