"""
FastAPI 依存性注入（DI）
シングルトン管理: TranscriptionEngine, AppSettings, ConfigManager など。
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# --- シングルトンインスタンス ---

_transcription_engine = None
_faster_whisper_engine = None
_app_settings = None
_config_manager = None
_text_formatter = None
_lock = threading.Lock()


def get_transcription_engine():
    """TranscriptionEngine シングルトンを取得"""
    global _transcription_engine
    if _transcription_engine is None:
        with _lock:
            if _transcription_engine is None:
                from transcription_engine import TranscriptionEngine

                _transcription_engine = TranscriptionEngine()
    return _transcription_engine


def get_faster_whisper_engine():
    """FasterWhisperEngine シングルトンを取得"""
    global _faster_whisper_engine
    if _faster_whisper_engine is None:
        with _lock:
            if _faster_whisper_engine is None:
                try:
                    from faster_whisper_engine import FasterWhisperEngine

                    _faster_whisper_engine = FasterWhisperEngine()
                except ImportError:
                    logger.warning("FasterWhisperEngine not available")
                    return None
    return _faster_whisper_engine


def get_app_settings():
    """AppSettings シングルトンを取得"""
    global _app_settings
    if _app_settings is None:
        with _lock:
            if _app_settings is None:
                from app_settings import AppSettings

                _app_settings = AppSettings("app_settings.json")
    return _app_settings


def get_config_manager():
    """ConfigManager シングルトンを取得"""
    global _config_manager
    if _config_manager is None:
        with _lock:
            if _config_manager is None:
                from config_manager import ConfigManager

                _config_manager = ConfigManager()
    return _config_manager


def get_text_formatter():
    """TextFormatter シングルトンを取得"""
    global _text_formatter
    if _text_formatter is None:
        with _lock:
            if _text_formatter is None:
                from text_formatter import TextFormatter

                _text_formatter = TextFormatter()
    return _text_formatter


# --- 現在のワーカー状態管理 ---


class WorkerState:
    """アクティブなワーカーの状態を管理"""

    def __init__(self):
        self.transcription_worker = None
        self.batch_worker = None
        self.realtime_worker = None
        self.folder_monitor = None
        self._lock = threading.Lock()

    def set_transcription_worker(self, worker):
        with self._lock:
            self.transcription_worker = worker

    def get_transcription_worker(self):
        with self._lock:
            return self.transcription_worker

    def set_batch_worker(self, worker):
        with self._lock:
            self.batch_worker = worker

    def get_batch_worker(self):
        with self._lock:
            return self.batch_worker

    def try_set_batch_worker(self, worker) -> bool:
        """アトミックにcheck-and-set。既存ワーカーが動作中ならFalse。"""
        with self._lock:
            if self.batch_worker is not None and self.batch_worker.is_alive():
                return False
            self.batch_worker = worker
            return True

    def clear_batch_worker(self):
        """バッチワーカーをクリア（終了後に呼び出す）"""
        with self._lock:
            self.batch_worker = None
            logger.debug("Batch worker cleared")

    def set_realtime_worker(self, worker):
        with self._lock:
            self.realtime_worker = worker

    def get_realtime_worker(self):
        with self._lock:
            return self.realtime_worker

    def try_set_realtime_worker(self, worker) -> bool:
        """アトミックにcheck-and-set。既存ワーカーが動作中ならFalse。"""
        with self._lock:
            if self.realtime_worker and self.realtime_worker.is_alive():
                return False
            self.realtime_worker = worker
            return True

    def set_folder_monitor(self, monitor):
        with self._lock:
            self.folder_monitor = monitor

    def get_folder_monitor(self):
        with self._lock:
            return self.folder_monitor

    def try_set_folder_monitor(self, monitor) -> bool:
        """アトミックにcheck-and-set。既存モニターが動作中ならFalse。"""
        with self._lock:
            if self.folder_monitor and self.folder_monitor.is_alive():
                return False
            self.folder_monitor = monitor
            return True


_worker_state: Optional[WorkerState] = None
_worker_state_lock = threading.Lock()


def get_worker_state() -> WorkerState:
    """WorkerState シングルトンを取得"""
    global _worker_state
    if _worker_state is None:
        with _worker_state_lock:
            if _worker_state is None:
                _worker_state = WorkerState()
    return _worker_state
