"""
Qt-free フォルダ監視サービス
threading.Thread + EventBus によるフォルダ監視。
"""

import os
import time
import logging
import tempfile
import threading
from typing import List, Set, Optional

from constants import SharedConstants
from api.event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)


class FolderMonitorService(threading.Thread):
    """
    フォルダ監視サービス（Qt非依存）。
    EventBus 経由で new_files_detected / status_update イベントを発行。
    """

    AUDIO_EXTENSIONS = SharedConstants.AUDIO_EXTENSIONS
    MAX_PROCESSED_ENTRIES = 50_000

    def __init__(self, folder_path: str, check_interval: int = 10,
                 event_bus: Optional[EventBus] = None):
        super().__init__(daemon=True)
        self.folder_path = folder_path
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._processed_lock = threading.Lock()
        self.processed_files: Set[str] = set()
        self._bus = event_bus or get_event_bus()
        self.load_processed_files()

        logger.info(f"FolderMonitorService initialized: {folder_path}, interval: {check_interval}s")

    def load_processed_files(self):
        """処理済みファイルリストを読み込み"""
        try:
            processed_file_path = os.path.join(self.folder_path, '.processed_files.txt')
            if os.path.exists(processed_file_path):
                MAX_PROCESSED_SIZE = 50 * 1024 * 1024
                file_size = os.path.getsize(processed_file_path)
                if file_size > MAX_PROCESSED_SIZE:
                    logger.error(f"Processed files list too large: {file_size} bytes")
                    self.processed_files = set()
                    return
                with open(processed_file_path, 'r', encoding='utf-8') as f:
                    self.processed_files = set(line.strip() for line in f if line.strip())
                logger.info(f"Loaded {len(self.processed_files)} processed files")
        except (IOError, OSError, UnicodeDecodeError) as e:
            logger.error(f"Failed to load processed files: {e}")
            self.processed_files = set()
        except Exception as e:
            logger.error(f"Failed to load processed files: {e}")
            self.processed_files = set()

    def save_processed_files(self):
        """処理済みファイルリストを保存（アトミック書き込み）"""
        try:
            with self._processed_lock:
                files_copy = sorted(self.processed_files)
            processed_file_path = os.path.join(self.folder_path, '.processed_files.txt')
            fd, tmp_path = tempfile.mkstemp(dir=self.folder_path, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    for file_path in files_copy:
                        f.write(f"{file_path}\n")
                os.replace(tmp_path, processed_file_path)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except (IOError, OSError) as e:
            logger.error(f"Failed to save processed files: {e}")
        except Exception as e:
            logger.error(f"Failed to save processed files: {e}")

    def is_audio_file(self, file_path: str) -> bool:
        """音声/動画ファイルかチェック"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.AUDIO_EXTENSIONS

    def is_processed(self, file_path: str) -> bool:
        """処理済みかチェック"""
        base_name = os.path.splitext(file_path)[0]
        transcription_file = f"{base_name}_文字起こし.txt"
        abs_path = os.path.abspath(file_path)
        with self._processed_lock:
            return os.path.exists(transcription_file) or abs_path in self.processed_files

    def get_unprocessed_files(self) -> List[str]:
        """未処理ファイルを取得"""
        unprocessed = []
        try:
            if not os.path.exists(self.folder_path):
                logger.warning(f"Folder does not exist: {self.folder_path}")
                return []
            for item in os.listdir(self.folder_path):
                file_path = os.path.join(self.folder_path, item)
                if not os.path.isfile(file_path):
                    continue
                if not self.is_audio_file(file_path):
                    continue
                if self.is_processed(file_path):
                    continue
                if self.is_file_ready(file_path):
                    unprocessed.append(file_path)
        except (IOError, OSError) as e:
            logger.error(f"I/O error getting unprocessed files: {e}")
        except Exception as e:
            logger.error(f"Error getting unprocessed files: {e}")
        return unprocessed

    def is_file_ready(self, file_path: str) -> bool:
        """ファイルが読み取り可能かチェック"""
        try:
            if os.path.getsize(file_path) == 0:
                return False
            try:
                with open(file_path, 'r+b') as f:
                    if os.name == 'nt':
                        import msvcrt
                        try:
                            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                        except IOError:
                            return False
                    else:
                        import fcntl
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except IOError:
                            return False
                    f.read(1)
            except PermissionError:
                return False

            size1 = os.path.getsize(file_path)
            time.sleep(1)
            size2 = os.path.getsize(file_path)
            return size1 == size2
        except (OSError, IOError):
            return False

    def _validate_within_folder(self, file_path: str) -> str:
        """ファイルパスが監視フォルダ内であることを検証"""
        abs_path = os.path.abspath(file_path)
        folder_abs = os.path.abspath(self.folder_path)
        if not abs_path.startswith(folder_abs + os.sep) and abs_path != folder_abs:
            raise ValueError("パスが監視フォルダ外です")
        return abs_path

    def _prune_processed_files(self):
        """メモリ上の処理済みセットがMAX_PROCESSED_ENTRIESを超えた場合、ディスク不在エントリを除去"""
        with self._processed_lock:
            if len(self.processed_files) <= self.MAX_PROCESSED_ENTRIES:
                return
            before = len(self.processed_files)
            self.processed_files = {p for p in self.processed_files if os.path.exists(p)}
            after = len(self.processed_files)
        if before != after:
            logger.info(f"Pruned processed_files: {before} -> {after}")
            self.save_processed_files()

    def mark_as_processed(self, file_path: str):
        """ファイルを処理済みとしてマーク"""
        abs_path = self._validate_within_folder(file_path)
        with self._processed_lock:
            self.processed_files.add(abs_path)
        self._prune_processed_files()
        self.save_processed_files()
        logger.info(f"Marked as processed: {abs_path}")

    def remove_from_processed(self, file_path: str):
        """処理済みリストからファイルを削除"""
        abs_path = self._validate_within_folder(file_path)
        with self._processed_lock:
            if abs_path in self.processed_files:
                self.processed_files.remove(abs_path)
                needs_save = True
            else:
                needs_save = False
        if needs_save:
            self.save_processed_files()

    def run(self):
        """監視ループ"""
        self._stop_event.clear()
        logger.info(f"Folder monitoring started: {self.folder_path}")
        self._bus.emit("status_update", {"status": f"フォルダ監視開始: {self.folder_path}"})

        # 起動時に即座に全ファイルスキャン
        try:
            logger.info("Initial scan: checking all files in folder")
            unprocessed_files = self.get_unprocessed_files()

            if unprocessed_files:
                logger.info(f"Initial scan: found {len(unprocessed_files)} unprocessed files")
                self._bus.emit("status_update", {
                    "status": f"初回スキャン: {len(unprocessed_files)}個の未処理ファイルを検出"
                })
                self._bus.emit("new_files_detected", {"files": unprocessed_files})
            else:
                logger.info("Initial scan: no unprocessed files found")
                self._bus.emit("status_update", {"status": "初回スキャン: 未処理ファイルなし"})
        except Exception as e:
            logger.error(f"Error in initial scan: {e}")

        while not self._stop_event.is_set():
            try:
                unprocessed_files = self.get_unprocessed_files()
                if unprocessed_files:
                    logger.info(f"Found {len(unprocessed_files)} unprocessed files")
                    self._bus.emit("status_update", {
                        "status": f"{len(unprocessed_files)}個の未処理ファイルを検出"
                    })
                    self._bus.emit("new_files_detected", {"files": unprocessed_files})

                if self._stop_event.wait(timeout=self.check_interval):
                    break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                if self._stop_event.wait(timeout=self.check_interval):
                    break

        logger.info("Folder monitoring stopped")
        self._bus.emit("status_update", {"status": "フォルダ監視停止"})

    def stop(self):
        """監視停止"""
        self._stop_event.set()
        logger.info("Stopping folder monitor...")
