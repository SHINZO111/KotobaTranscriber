"""
WorkerState 並行性のテスト。
is_alive() 競合条件とクリーンアップロジックを検証。
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from api.dependencies import WorkerState, get_worker_state


class TestWorkerStateConcurrency:
    """WorkerState の並行性テスト"""

    @pytest.fixture
    def worker_state(self):
        """各テストで新しい WorkerState を提供"""
        return WorkerState()

    @pytest.fixture
    def mock_worker(self):
        """モックワーカーを提供"""
        worker = MagicMock()
        worker.is_alive.return_value = True
        worker.start = MagicMock()
        worker.join = MagicMock()
        return worker

    def test_clear_batch_worker_exists(self, worker_state):
        """clear_batch_worker メソッドが存在する"""
        assert hasattr(worker_state, "clear_batch_worker")
        assert callable(worker_state.clear_batch_worker)

    def test_clear_batch_worker_sets_none(self, worker_state, mock_worker):
        """clear_batch_worker が batch_worker を None に設定する"""
        worker_state.batch_worker = mock_worker
        assert worker_state.batch_worker is not None

        worker_state.clear_batch_worker()
        assert worker_state.batch_worker is None

    def test_clear_batch_worker_idempotent(self, worker_state):
        """clear_batch_worker は冪等（複数回呼び出しても安全）"""
        worker_state.clear_batch_worker()
        worker_state.clear_batch_worker()
        worker_state.clear_batch_worker()
        # エラーが発生しないことを確認
        assert worker_state.batch_worker is None

    def test_try_set_after_clear(self, worker_state, mock_worker):
        """clear_batch_worker 後は新しいワーカーを設定できる"""
        # 最初のワーカーを設定
        first_worker = MagicMock()
        first_worker.is_alive.return_value = True
        assert worker_state.try_set_batch_worker(first_worker) is True

        # まだ alive なので拒否される
        assert worker_state.try_set_batch_worker(mock_worker) is False

        # クリア後は成功する
        worker_state.clear_batch_worker()
        assert worker_state.try_set_batch_worker(mock_worker) is True

    def test_concurrent_try_set_only_one_succeeds(self, worker_state):
        """並行 try_set_batch_worker で 1 つだけ成功する"""
        results = []
        barrier = threading.Barrier(5)  # 5 スレッドが同時にスタート

        def try_set():
            barrier.wait()  # 全スレッドが準備完了まで待機
            worker = MagicMock()
            worker.is_alive.return_value = True
            success = worker_state.try_set_batch_worker(worker)
            results.append(success)

        threads = [threading.Thread(target=try_set) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 5 つのうち 1 つだけ True、残りは False
        assert results.count(True) == 1
        assert results.count(False) == 4

    def test_try_set_none_is_ignored(self, worker_state):
        """try_set_batch_worker で None は alive チェックをスキップ"""
        # batch_worker が None の状態で try_set は成功する
        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = True
        assert worker_state.try_set_batch_worker(mock_worker) is True

    def test_try_set_dead_worker_allows_new(self, worker_state):
        """is_alive() == False のワーカーは上書きできる"""
        old_worker = MagicMock()
        old_worker.is_alive.return_value = False  # 死んでいる

        worker_state.batch_worker = old_worker

        new_worker = MagicMock()
        new_worker.is_alive.return_value = True
        assert worker_state.try_set_batch_worker(new_worker) is True
        assert worker_state.batch_worker is new_worker

    def test_lifecycle_set_start_clear(self, worker_state):
        """完全なライフサイクル: try_set → start → clear"""
        worker = MagicMock()
        worker.is_alive.return_value = True
        worker.start = MagicMock()
        worker.join = MagicMock()

        # 設定
        assert worker_state.try_set_batch_worker(worker) is True

        # 開始
        worker.start()
        worker.start.assert_called_once()

        # 終了シミュレーション
        worker.is_alive.return_value = False

        # クリーンアップ
        worker_state.clear_batch_worker()
        assert worker_state.batch_worker is None

    def test_race_condition_near_worker_end(self, worker_state):
        """ワーカー終了直前の競合シミュレーション"""
        first_worker = MagicMock()
        # 最初は alive、その後 dead になる
        first_worker.is_alive.side_effect = [False, False]

        worker_state.batch_worker = first_worker

        # T1: is_alive() → False（終了直前）
        second_worker = MagicMock()
        second_worker.is_alive.return_value = True
        result1 = worker_state.try_set_batch_worker(second_worker)

        # T2: 2つ目の試行（既に second_worker が設定されている）
        third_worker = MagicMock()
        third_worker.is_alive.return_value = True
        result2 = worker_state.try_set_batch_worker(third_worker)

        # 1 つ目は成功、2 つ目は失敗する
        assert result1 is True
        assert result2 is False

    def test_clear_batch_worker_thread_safe(self, worker_state):
        """clear_batch_worker は並行呼び出しで安全"""
        mock_worker = MagicMock()
        worker_state.batch_worker = mock_worker

        def clear():
            worker_state.clear_batch_worker()

        threads = [threading.Thread(target=clear) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # エラーなく完了
        assert worker_state.batch_worker is None

    def test_try_set_batch_worker_checks_not_none(self, worker_state):
        """try_set_batch_worker は batch_worker が None でないことを確認"""
        # 初期状態は None
        assert worker_state.batch_worker is None

        # None の状態では alive チェックをスキップして成功
        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = True
        assert worker_state.try_set_batch_worker(mock_worker) is True


class TestWorkerStateSingleton:
    """get_worker_state() シングルトンのテスト"""

    def test_get_worker_state_returns_same_instance(self):
        """get_worker_state() は常に同じインスタンスを返す"""
        state1 = get_worker_state()
        state2 = get_worker_state()
        assert state1 is state2

    def test_get_worker_state_thread_safe(self):
        """get_worker_state() は並行呼び出しで安全"""
        instances = []

        def get():
            instances.append(get_worker_state())

        threads = [threading.Thread(target=get) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # すべて同じインスタンス
        assert all(inst is instances[0] for inst in instances)
