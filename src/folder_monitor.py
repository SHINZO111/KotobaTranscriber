"""
フォルダ監視モジュール
指定フォルダを監視し、未処理のファイルを自動文字起こし
"""

import os
import time
import logging
from typing import List, Set, Callable
from pathlib import Path
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class FolderMonitor(QThread):
    """フォルダ監視クラス"""

    # シグナル
    new_files_detected = Signal(list)  # 新規ファイル検出
    status_update = Signal(str)  # ステータス更新

    # 対応する音声/動画フォーマット
    AUDIO_EXTENSIONS = {
        '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac',
        '.wma', '.opus', '.amr', '.3gp', '.webm',
        '.mp4', '.avi', '.mov', '.mkv'
    }

    def __init__(self, folder_path: str, check_interval: int = 10):
        """
        初期化

        Args:
            folder_path: 監視するフォルダパス
            check_interval: チェック間隔（秒）
        """
        super().__init__()
        self.folder_path = folder_path
        self.check_interval = check_interval
        self.running = False
        self.processed_files: Set[str] = set()
        self.load_processed_files()

        logger.info(f"FolderMonitor initialized: {folder_path}, interval: {check_interval}s")

    def load_processed_files(self):
        """処理済みファイルリストを読み込み"""
        try:
            # 監視フォルダ内の.processed_filesファイルから読み込み
            processed_file_path = os.path.join(self.folder_path, '.processed_files.txt')
            if os.path.exists(processed_file_path):
                with open(processed_file_path, 'r', encoding='utf-8') as f:
                    self.processed_files = set(line.strip() for line in f if line.strip())
                logger.info(f"Loaded {len(self.processed_files)} processed files")
        except Exception as e:
            logger.error(f"Failed to load processed files: {e}")
            self.processed_files = set()

    def save_processed_files(self):
        """処理済みファイルリストを保存"""
        try:
            processed_file_path = os.path.join(self.folder_path, '.processed_files.txt')
            with open(processed_file_path, 'w', encoding='utf-8') as f:
                for file_path in sorted(self.processed_files):
                    f.write(f"{file_path}\n")
            logger.debug(f"Saved {len(self.processed_files)} processed files")
        except Exception as e:
            logger.error(f"Failed to save processed files: {e}")

    def is_audio_file(self, file_path: str) -> bool:
        """音声/動画ファイルかチェック"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.AUDIO_EXTENSIONS

    def is_processed(self, file_path: str) -> bool:
        """
        処理済みかチェック
        フルパスベースで判定（ファイル名衝突を防止）
        """
        # 文字起こしファイルが存在するかチェック
        base_name = os.path.splitext(file_path)[0]
        transcription_file = f"{base_name}_文字起こし.txt"

        # フルパスで比較（同名ファイルの衝突を防止）
        abs_path = os.path.abspath(file_path)

        # 文字起こしファイルが存在するか、処理済みリストに含まれているか
        return os.path.exists(transcription_file) or abs_path in self.processed_files

    def get_unprocessed_files(self) -> List[str]:
        """未処理ファイルを取得"""
        unprocessed = []

        try:
            if not os.path.exists(self.folder_path):
                logger.warning(f"Folder does not exist: {self.folder_path}")
                return []

            # フォルダ内のすべてのファイルをチェック
            for item in os.listdir(self.folder_path):
                file_path = os.path.join(self.folder_path, item)

                # ファイルかチェック（ディレクトリは除外）
                if not os.path.isfile(file_path):
                    continue

                # 音声/動画ファイルかチェック
                if not self.is_audio_file(file_path):
                    continue

                # 処理済みかチェック
                if self.is_processed(file_path):
                    continue

                # ファイルが完全にコピー/移動されているかチェック（書き込み中でない）
                if self.is_file_ready(file_path):
                    unprocessed.append(file_path)

        except Exception as e:
            logger.error(f"Error getting unprocessed files: {e}")

        return unprocessed

    def is_file_ready(self, file_path: str, timeout: int = 5, check_interval: float = 0.5) -> bool:
        """
        ファイルが読み取り可能かチェック（TOCTOU対策強化版）
        （ファイルコピー/移動中でないか確認）

        Args:
            file_path: チェックするファイルパス
            timeout: タイムアウト（秒）
            check_interval: チェック間隔（秒）

        Returns:
            ファイルが読み取り可能ならTrue
        """
        start_time = time.time()
        previous_size = -1

        while time.time() - start_time < timeout:
            try:
                # 排他的読み取りを試みる（ロックを保持したままサイズチェック）
                with open(file_path, 'rb') as f:
                    # ファイル全体をロック（Windows: msvcrt, Unix: fcntl）
                    if os.name == 'nt':
                        import msvcrt
                        try:
                            # ノンブロッキングでロックを試みる
                            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                        except IOError:
                            logger.debug(f"File is locked by another process: {file_path}")
                            time.sleep(check_interval)
                            continue

                        try:
                            # ロックを保持したままサイズと読み取りテスト
                            current_size = os.fstat(f.fileno()).st_size

                            if current_size == 0:
                                return False

                            if current_size == previous_size:
                                # サイズが安定している - 一部読み取りテスト
                                f.seek(0)
                                f.read(min(1024, current_size))
                                return True

                            previous_size = current_size
                        finally:
                            # ロックを解放
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        try:
                            # ノンブロッキングでロックを試みる
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except IOError:
                            logger.debug(f"File is locked by another process: {file_path}")
                            time.sleep(check_interval)
                            continue

                        try:
                            # ロックを保持したままサイズと読み取りテスト
                            current_size = os.fstat(f.fileno()).st_size

                            if current_size == 0:
                                return False

                            if current_size == previous_size:
                                # サイズが安定している - 一部読み取りテスト
                                f.seek(0)
                                f.read(min(1024, current_size))
                                return True

                            previous_size = current_size
                        finally:
                            # ロックを解放
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            except (OSError, IOError, PermissionError) as e:
                logger.debug(f"File not ready: {file_path} - {e}")
                time.sleep(check_interval)
                continue

            time.sleep(check_interval)

        logger.debug(f"Timeout waiting for file to be ready: {file_path}")
        return False

    def mark_as_processed(self, file_path: str):
        """
        ファイルを処理済みとしてマーク
        フルパスで記録（ファイル名衝突を防止）
        """
        # フルパスを記録
        abs_path = os.path.abspath(file_path)
        self.processed_files.add(abs_path)
        self.save_processed_files()
        logger.info(f"Marked as processed: {abs_path}")

    def remove_from_processed(self, file_path: str):
        """
        処理済みリストからファイルを削除（移動時に使用）
        フルパスで削除
        """
        # フルパスで削除
        abs_path = os.path.abspath(file_path)
        if abs_path in self.processed_files:
            self.processed_files.remove(abs_path)
            self.save_processed_files()
            logger.info(f"Removed from processed list: {abs_path}")

    def run(self):
        """監視ループ"""
        self.running = True
        logger.info(f"Folder monitoring started: {self.folder_path}")
        self.status_update.emit(f"フォルダ監視開始: {self.folder_path}")

        while self.running:
            try:
                # 未処理ファイルをチェック
                unprocessed_files = self.get_unprocessed_files()

                if unprocessed_files:
                    logger.info(f"Found {len(unprocessed_files)} unprocessed files")
                    self.status_update.emit(f"{len(unprocessed_files)}個の未処理ファイルを検出")
                    self.new_files_detected.emit(unprocessed_files)

                    # 注意: 処理済みマークは文字起こし成功後にmain.pyから呼ばれる

                # 指定間隔待機
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)

        logger.info("Folder monitoring stopped")
        self.status_update.emit("フォルダ監視停止")

    def stop(self):
        """監視停止"""
        self.running = False
        logger.info("Stopping folder monitor...")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    test_folder = r"F:\VoiceToText\KotobaTranscriber\test_watch"
    os.makedirs(test_folder, exist_ok=True)

    monitor = FolderMonitor(test_folder, check_interval=5)

    def on_new_files(files):
        print(f"\n新規ファイル検出: {len(files)}個")
        for file in files:
            print(f"  - {os.path.basename(file)}")

    def on_status(status):
        print(f"ステータス: {status}")

    monitor.new_files_detected.connect(on_new_files)
    monitor.status_update.connect(on_status)

    print(f"監視開始: {test_folder}")
    print("Ctrl+Cで停止")

    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n監視停止中...")
        monitor.stop()
        monitor.wait()
        print("停止完了")
