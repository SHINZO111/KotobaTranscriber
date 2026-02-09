"""
enhanced_folder_monitor.py - 強化フォルダ監視モジュール

watchdogを使用したイベント駆動型フォルダ監視
"""

import os
import time
import asyncio
import logging
from typing import List, Set, Callable, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from threading import Lock

try:
    from watchdog.observers import Observer
    from watchdog.events import (
        FileSystemEventHandler, 
        FileCreatedEvent, 
        FileMovedEvent,
        FileModifiedEvent
    )
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logging.warning("watchdog not available, falling back to polling")

from PySide6.QtCore import QObject, Signal, QTimer
from workers import SharedConstants

logger = logging.getLogger(__name__)


@dataclass
class FileEvent:
    """ファイルイベント"""
    path: str
    event_type: str  # 'created', 'modified', 'moved'
    timestamp: float
    size: int = 0


class AsyncFolderMonitor(QObject):
    """
    強化フォルダ監視クラス
    
    watchdogによるイベント駆動監視と、
    複数フォルダ同時監視に対応
    """
    
    # シグナル
    new_files_detected = Signal(list)  # 新規ファイル検出
    status_update = Signal(str)        # ステータス更新
    file_processed = Signal(str, bool)  # (ファイルパス, 成功)
    
    # 対応する音声/動画フォーマット（SharedConstants から参照）
    AUDIO_EXTENSIONS = SharedConstants.AUDIO_EXTENSIONS

    def __init__(
        self,
        folder_paths: Optional[List[str]] = None,
        check_interval: float = 1.0,
        parent=None
    ):
        """
        初期化
        
        Args:
            folder_paths: 監視するフォルダパスのリスト
            check_interval: ファイル準備確認間隔（秒）
        """
        super().__init__(parent)
        self.folder_paths: Set[Path] = set()
        if folder_paths:
            self.folder_paths.update(Path(p) for p in folder_paths)
        
        self.check_interval = check_interval
        self._observer: Optional[Observer] = None
        self._pending_files: Dict[Path, FileEvent] = {}
        self._processed_files: Set[str] = set()
        self._processing: Set[Path] = set()
        self._lock = Lock()
        
        # ファイル準備確認用タイマー
        self._ready_check_timer = QTimer(self)
        self._ready_check_timer.timeout.connect(self._check_pending_files)
        self._ready_check_timer.start(int(check_interval * 1000))
        
        # 保存済みリストのパス
        self._processed_list_path = Path.home() / ".kotoba_transcriber" / "processed_files.json"
        
        self._load_processed_files()
    
    def add_folder(self, folder_path: str) -> bool:
        """
        監視フォルダを追加
        
        Args:
            folder_path: 追加するフォルダパス
            
        Returns:
            True: 追加成功
        """
        path = Path(folder_path)
        if not path.exists():
            logger.error(f"Folder does not exist: {folder_path}")
            return False
        
        with self._lock:
            self.folder_paths.add(path)
        
        # 監視中なら再起動
        if self._observer:
            self.stop()
            self.start()
        
        logger.info(f"Added folder to monitor: {folder_path}")
        return True
    
    def remove_folder(self, folder_path: str) -> bool:
        """
        監視フォルダを削除
        
        Args:
            folder_path: 削除するフォルダパス
        """
        path = Path(folder_path)
        with self._lock:
            self.folder_paths.discard(path)
        
        if self._observer:
            self.stop()
            self.start()
        
        return True
    
    def start(self):
        """監視を開始"""
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog not available, using polling mode")
            self._start_polling()
            return
        
        if self._observer:
            return
        
        self._observer = Observer()
        
        for folder in self.folder_paths:
            if folder.exists():
                handler = self._create_handler()
                self._observer.schedule(handler, str(folder), recursive=False)
                logger.info(f"Monitoring: {folder}")
                
                # 既存ファイルをチェック
                self._check_existing_files(folder)
        
        self._observer.start()
        self.status_update.emit(f"監視開始: {len(self.folder_paths)}フォルダ")
        logger.info("Folder monitoring started")
    
    def stop(self):
        """監視を停止"""
        if self._ready_check_timer.isActive():
            self._ready_check_timer.stop()
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Folder monitoring stopped")
            self.status_update.emit("監視停止")
    
    def _create_handler(self) -> FileSystemEventHandler:
        """watchdogイベントハンドラを作成"""
        monitor = self
        
        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    monitor._on_file_event(event.src_path, 'created')
            
            def on_modified(self, event):
                if not event.is_directory:
                    monitor._on_file_event(event.src_path, 'modified')
            
            def on_moved(self, event):
                if not event.is_directory:
                    monitor._on_file_event(event.dest_path, 'moved')
        
        return Handler()
    
    def _on_file_event(self, file_path: str, event_type: str):
        """
        ファイルイベント処理
        
        Args:
            file_path: ファイルパス
            event_type: イベントタイプ
        """
        path = Path(file_path)
        
        # 拡張子チェック
        if path.suffix.lower() not in self.AUDIO_EXTENSIONS:
            return
        
        # 重複チェック + 保留リストに追加（単一ロックで TOCTOU 防止）
        with self._lock:
            if path in self._processing:
                return

            # 処理済みチェック
            abs_path = str(path.resolve())
            if abs_path in self._processed_files:
                return

            self._pending_files[path] = FileEvent(
                path=file_path,
                event_type=event_type,
                timestamp=time.time()
            )
        
        logger.debug(f"File event: {event_type} - {path.name}")
    
    def _check_pending_files(self):
        """保留中ファイルの準備確認"""
        ready_files = []

        with self._lock:
            pending_items = list(self._pending_files.items())

        for path, event in pending_items:
            if self._is_file_ready(path, event):
                ready_files.append(str(path.resolve()))
                with self._lock:
                    self._pending_files.pop(path, None)
                    self._processing.add(path)
        
        if ready_files:
            self.new_files_detected.emit(ready_files)
            self.status_update.emit(f"{len(ready_files)}個のファイルを検出")
    
    def _is_file_ready(self, path: Path, event: 'FileEvent') -> bool:
        """
        ファイルが読み取り可能か確認（ノンブロッキング）

        前回のタイマーtickで記録したサイズと今回のサイズを比較し、
        安定していれば読み取りテストを行う。time.sleepは使わない。

        Args:
            path: ファイルパス
            event: ファイルイベント（前回サイズをsizeフィールドに記録）

        Returns:
            True: 読み取り可能
        """
        try:
            if not path.exists():
                return False

            stat = path.stat()
            current_size = stat.st_size

            # サイズチェック
            if current_size == 0:
                return False

            # 安定性チェック: 前回記録したサイズと比較
            previous_size = event.size
            event.size = current_size

            if previous_size == 0 or previous_size != current_size:
                # 初回またはサイズ変化あり → 次のtickで再チェック
                return False

            # 書き込みロックチェック
            try:
                with open(path, 'rb') as f:
                    f.read(1)
                return True
            except PermissionError:
                return False

        except (OSError, IOError) as e:
            logger.debug(f"File not ready: {path} - {e}")
            return False
    
    def _check_existing_files(self, folder: Path):
        """既存の未処理ファイルをチェック"""
        if not folder.exists():
            return
        
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in self.AUDIO_EXTENSIONS:
                abs_path = str(path.resolve())
                if abs_path not in self._processed_files:
                    with self._lock:
                        self._pending_files[path] = FileEvent(
                            path=str(path),
                            event_type='existing',
                            timestamp=time.time()
                        )
    
    def mark_as_processed(self, file_path: str, success: bool = True):
        """
        ファイルを処理済みとしてマーク
        
        Args:
            file_path: ファイルパス
            success: 処理成功かどうか
        """
        path = Path(file_path)
        abs_path = str(path.resolve())
        
        with self._lock:
            self._processed_files.add(abs_path)
            self._processing.discard(path)
        
        self.file_processed.emit(file_path, success)
        self._save_processed_files()
        
        logger.info(f"Marked as processed: {path.name} (success={success})")
    
    def mark_as_unprocessed(self, file_path: str):
        """
        ファイルを未処理に戻す
        
        Args:
            file_path: ファイルパス
        """
        path = Path(file_path)
        abs_path = str(path.resolve())
        
        with self._lock:
            self._processed_files.discard(abs_path)
        
        self._save_processed_files()
        logger.info(f"Marked as unprocessed: {path.name}")
    
    def _load_processed_files(self):
        """処理済みリストを読み込み"""
        try:
            if self._processed_list_path.exists():
                # ファイルサイズ制限 (50MB)
                MAX_PROCESSED_SIZE = 50 * 1024 * 1024
                file_size = self._processed_list_path.stat().st_size
                if file_size > MAX_PROCESSED_SIZE:
                    logger.error(f"Processed files list too large: {file_size} bytes, skipping")
                    self._processed_files = set()
                    return
                import json
                data = json.loads(self._processed_list_path.read_text(encoding='utf-8'))
                self._processed_files = set(data.get('files', []))
                logger.info(f"Loaded {len(self._processed_files)} processed files")
        except Exception as e:
            logger.warning(f"Failed to load processed files: {e}")
            self._processed_files = set()
    
    def _save_processed_files(self):
        """処理済みリストを保存（アトミック書き込み）"""
        try:
            import json
            import tempfile
            self._processed_list_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'files': list(self._processed_files),
                'updated': datetime.now().isoformat()
            }
            content = json.dumps(data, ensure_ascii=False, indent=2)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._processed_list_path.parent), suffix='.tmp'
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                os.replace(tmp_path, str(self._processed_list_path))
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.warning(f"Failed to save processed files: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """監視統計を取得"""
        with self._lock:
            return {
                'folders': len(self.folder_paths),
                'pending': len(self._pending_files),
                'processing': len(self._processing),
                'processed_total': len(self._processed_files),
                'is_running': self._observer is not None
            }
    
    def clear_history(self):
        """処理履歴をクリア"""
        with self._lock:
            self._processed_files.clear()
        self._save_processed_files()
        logger.info("Processing history cleared")
    
    def _start_polling(self):
        """ポーリングモードで開始（watchdog非対応時）"""
        # ポーリング用の実装（省略: folder_monitor.pyを参照）
        pass


if __name__ == "__main__":
    # テスト
    import sys
    from PySide6.QtWidgets import QApplication
    
    logging.basicConfig(level=logging.INFO)
    
    app = QApplication(sys.argv)
    
    # テスト用フォルダ
    test_folder = Path.home() / "Desktop" / "test_watch"
    test_folder.mkdir(exist_ok=True)
    
    print(f"Test folder: {test_folder}")
    print("Add audio files to test monitoring")
    
    monitor = AsyncFolderMonitor([str(test_folder)])
    
    def on_new_files(files):
        print(f"\nNew files detected: {len(files)}")
        for f in files:
            print(f"  - {os.path.basename(f)}")
            # テスト用: 即座に処理済みにマーク
            monitor.mark_as_processed(f)
    
    def on_status(status):
        print(f"Status: {status}")
    
    monitor.new_files_detected.connect(on_new_files)
    monitor.status_update.connect(on_status)
    
    monitor.start()
    
    print("\nPress Ctrl+C to exit")
    
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        monitor.stop()
        print("\nStopped")
