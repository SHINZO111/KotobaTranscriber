"""
ui_responsive.py - UI応答性改善モジュール

長時間処理時のUIフリーズ防止とスムーズな進捗更新を実現
"""

from PySide6.QtCore import QObject, Signal, QTimer, QThread, QRunnable, QThreadPool, Slot
from PySide6.QtWidgets import QApplication
from typing import Callable, Any, Optional, List, Dict
import time
import threading
import logging

logger = logging.getLogger(__name__)


class ResponsiveWorker(QObject):
    """
    UI応答性を保つワーカークラス
    
    処理中もUIイベントを処理し、フリーズを防止する
    """
    
    progress = Signal(int, str)  # (進捗%, メッセージ)
    finished = Signal(object)    # 結果
    error = Signal(str)          # エラーメッセージ
    cancelled = Signal()         # キャンセル通知
    
    def __init__(self, ui_update_interval: float = 0.1):
        """
        初期化
        
        Args:
            ui_update_interval: UI更新間隔（秒）
        """
        super().__init__()
        self._cancelled = False
        self._paused = False
        self._last_ui_update = 0
        self._ui_update_interval = ui_update_interval
    
    def check_cancelled(self) -> bool:
        """
        キャンセル状態をチェック
        
        処理ループ内で定期的に呼び出すこと
        
        Returns:
            True: キャンセル要求あり
        """
        self._process_events()
        
        # 一時停止中は待機
        while self._paused and not self._cancelled:
            self._process_events()
            time.sleep(0.1)
        
        return self._cancelled
    
    def _process_events(self):
        """UIイベントを処理（GUIスレッドからのみ安全）"""
        now = time.time()
        if now - self._last_ui_update >= self._ui_update_interval:
            app = QApplication.instance()
            if app is not None and QThread.currentThread() == app.thread():
                QApplication.processEvents()
            self._last_ui_update = now
    
    def update_progress(self, value: int, message: str = ""):
        """
        進捗を更新（UIブロック防止）
        
        Args:
            value: 進捗値（0-100）
            message: 進捗メッセージ
        """
        self._process_events()
        self.progress.emit(value, message)
    
    def cancel(self):
        """処理をキャンセル"""
        self._cancelled = True
        logger.info("Cancellation requested")
    
    def pause(self):
        """処理を一時停止"""
        self._paused = True
        logger.info("Processing paused")
    
    def resume(self):
        """処理を再開"""
        self._paused = False
        logger.info("Processing resumed")


class WorkerTask(QRunnable):
    """
    QThreadPool用タスク
    
    バックグラウンドでの非同期実行を実現
    """
    
    def __init__(
        self,
        func: Callable,
        *args,
        callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.callback = callback
        self.error_callback = error_callback
    
    @Slot()
    def run(self):
        """タスク実行"""
        try:
            result = self.func(*self.args, **self.kwargs)
            if self.callback:
                self.callback(result)
        except Exception as e:
            logger.error(f"Task failed: {e}")
            if self.error_callback:
                self.error_callback(str(e))


class ProcessingQueue(QObject):
    """
    処理キュー（非同期実行）
    
    複数タスクを順序よく非同期実行する
    """
    
    task_started = Signal(str)        # タスクID
    task_finished = Signal(str, object)  # (タスクID, 結果)
    task_error = Signal(str, str)     # (タスクID, エラー)
    queue_updated = Signal(int)       # 待ち件数
    all_finished = Signal()           # 全タスク完了
    
    def __init__(self, max_workers: int = 2, parent=None):
        """
        初期化
        
        Args:
            max_workers: 同時実行数
        """
        super().__init__(parent)
        self.max_workers = max_workers
        self._queue: List[Dict[str, Any]] = []
        self._running: set = set()
        self._lock = threading.Lock()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._process_queue)
        self._timer.start(100)  # 100ms間隔
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(max_workers)
    
    def add_task(
        self, 
        task_id: str, 
        func: Callable, 
        *args, 
        priority: int = 0,
        **kwargs
    ):
        """
        タスクを追加
        
        Args:
            task_id: タスク識別子
            func: 実行する関数
            priority: 優先度（高いほど先に実行）
        """
        with self._lock:
            self._queue.append({
                'id': task_id,
                'func': func,
                'args': args,
                'kwargs': kwargs,
                'priority': priority
            })
            # 優先度でソート
            self._queue.sort(key=lambda x: x['priority'], reverse=True)
        
        self.queue_updated.emit(len(self._queue))
        logger.debug(f"Task added: {task_id} (queue: {len(self._queue)})")
    
    def cancel_task(self, task_id: str) -> bool:
        """
        待ち状態のタスクをキャンセル
        
        Args:
            task_id: キャンセルするタスクID
            
        Returns:
            True: キャンセル成功
        """
        with self._lock:
            for i, task in enumerate(self._queue):
                if task['id'] == task_id:
                    self._queue.pop(i)
                    self.queue_updated.emit(len(self._queue))
                    logger.info(f"Task cancelled: {task_id}")
                    return True
        return False
    
    def clear_queue(self):
        """キューをクリア"""
        with self._lock:
            self._queue.clear()
        self.queue_updated.emit(0)
        logger.info("Queue cleared")
    
    def _process_queue(self):
        """キューを処理"""
        with self._lock:
            if len(self._running) >= self.max_workers:
                return
            
            if not self._queue:
                return
            
            task = self._queue.pop(0)
            self._running.add(task['id'])
        
        self.queue_updated.emit(len(self._queue))
        self.task_started.emit(task['id'])
        
        # スレッドプールで実行
        worker = WorkerTask(
            task['func'],
            *task['args'],
            callback=lambda r: self._on_task_finished(task['id'], r),
            error_callback=lambda e: self._on_task_error(task['id'], e),
            **task['kwargs']
        )
        self._thread_pool.start(worker)
    
    def _on_task_finished(self, task_id: str, result: Any):
        """タスク完了時"""
        with self._lock:
            self._running.discard(task_id)
        
        self.task_finished.emit(task_id, result)
        logger.debug(f"Task finished: {task_id}")
        
        # 全タスク完了チェック
        self._check_all_finished()
    
    def _on_task_error(self, task_id: str, error: str):
        """タスクエラー時"""
        with self._lock:
            self._running.discard(task_id)
        
        self.task_error.emit(task_id, error)
        logger.error(f"Task error: {task_id} - {error}")
        
        self._check_all_finished()
    
    def _check_all_finished(self):
        """全タスク完了チェック"""
        with self._lock:
            if not self._queue and not self._running:
                self.all_finished.emit()
    
    def get_status(self) -> Dict[str, Any]:
        """
        キュー状態を取得
        
        Returns:
            {'waiting': int, 'running': int, 'total': int}
        """
        with self._lock:
            return {
                'waiting': len(self._queue),
                'running': len(self._running),
                'total': len(self._queue) + len(self._running)
            }


class ProgressAnimator(QObject):
    """
    プログレスバーアニメーション
    
    スムーズな進捗アニメーションを実現
    """
    
    value_changed = Signal(int)
    
    def __init__(self, duration_ms: int = 300):
        super().__init__()
        self.duration = duration_ms
        self._current = 0
        self._target = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._step = 0
    
    def set_value(self, value: int):
        """目標値を設定"""
        self._target = max(0, min(100, value))
        if self._target == self._current:
            return
        self._step = (self._target - self._current) / 20  # 20フレームで到達

        if not self._timer.isActive():
            self._timer.start(16)  # ~60fps
    
    def _animate(self):
        """アニメーションフレーム"""
        if abs(self._target - self._current) < abs(self._step):
            self._current = self._target
            self._timer.stop()
        else:
            self._current += self._step
        
        self.value_changed.emit(int(self._current))


class Debouncer(QObject):
    """
    デバウンサー
    
    高頻度イベントを間引く
    """
    
    triggered = Signal()
    
    def __init__(self, delay_ms: int = 300, parent=None):
        super().__init__(parent)
        self.delay = delay_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.triggered)
    
    def touch(self):
        """トリガー（遅延後に発火）"""
        self._timer.start(self.delay)


if __name__ == "__main__":
    # テスト
    import sys
    from PySide6.QtWidgets import QApplication, QProgressBar, QVBoxLayout, QWidget, QPushButton, QLabel
    
    logging.basicConfig(level=logging.INFO)
    
    app = QApplication(sys.argv)
    
    # テストウィンドウ
    window = QWidget()
    window.setWindowTitle("UI Responsive Test")
    layout = QVBoxLayout(window)
    
    progress = QProgressBar()
    layout.addWidget(progress)
    
    status = QLabel("Ready")
    layout.addWidget(status)
    
    button = QPushButton("Start Long Task")
    layout.addWidget(button)
    
    # 処理キュー
    queue = ProcessingQueue(max_workers=2)
    
    def long_task(n):
        """時間のかかるタスク"""
        for i in range(n):
            time.sleep(0.1)
            # キャンセルチェックは実際のワーカーで行う
        return f"Completed {n} iterations"
    
    def on_click():
        status.setText("Processing...")
        queue.add_task("test_task", long_task, 50)
    
    def on_finished(task_id, result):
        status.setText(f"Finished: {result}")
        progress.setValue(100)
    
    button.clicked.connect(on_click)
    queue.task_finished.connect(on_finished)
    
    window.show()
    sys.exit(app.exec())
