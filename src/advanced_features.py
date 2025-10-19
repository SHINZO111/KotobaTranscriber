"""
高度な機能モジュール
自動起動、Webhook通知、ホットキーなど
"""

import os
import sys
import winreg
import logging

logger = logging.getLogger(__name__)


class StartupManager:
    """Windows スタートアップ管理クラス"""

    @staticmethod
    def get_app_path() -> str:
        """アプリケーションの実行パスを取得"""
        if getattr(sys, 'frozen', False):
            # PyInstallerでビルドされた実行ファイルの場合
            return sys.executable
        else:
            # 開発環境の場合
            python_exe = sys.executable
            script_path = os.path.abspath(__file__)
            main_path = os.path.join(os.path.dirname(script_path), 'main.py')
            return f'"{python_exe}" "{main_path}"'

    @staticmethod
    def is_startup_enabled() -> bool:
        """スタートアップ登録されているかチェック"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ
            )
            try:
                value, _ = winreg.QueryValueEx(key, "KotobaTranscriber")
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception as e:
            logger.error(f"Failed to check startup: {e}")
            return False

    @staticmethod
    def enable_startup() -> bool:
        """スタートアップに登録"""
        try:
            app_path = StartupManager.get_app_path()
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_WRITE
            )
            winreg.SetValueEx(key, "KotobaTranscriber", 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
            logger.info(f"Startup enabled: {app_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable startup: {e}")
            return False

    @staticmethod
    def disable_startup() -> bool:
        """スタートアップから削除"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_WRITE
            )
            try:
                winreg.DeleteValue(key, "KotobaTranscriber")
                winreg.CloseKey(key)
                logger.info("Startup disabled")
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return True
        except Exception as e:
            logger.error(f"Failed to disable startup: {e}")
            return False


class FileOrganizer:
    """ファイル整理クラス"""

    @staticmethod
    def move_completed_file(source_path: str, dest_folder: str) -> bool:
        """
        完了したファイルを指定フォルダに移動

        Args:
            source_path: 元のファイルパス
            dest_folder: 移動先フォルダ

        Returns:
            成功した場合True
        """
        try:
            # 移動先フォルダが存在しない場合は作成
            os.makedirs(dest_folder, exist_ok=True)

            # ファイル名を取得
            filename = os.path.basename(source_path)
            dest_path = os.path.join(dest_folder, filename)

            # 同名ファイルが存在する場合は番号を付ける
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                    counter += 1

            # ファイルを移動
            import shutil
            shutil.move(source_path, dest_path)
            logger.info(f"File moved: {source_path} -> {dest_path}")

            # 文字起こしファイルも移動
            transcription_file = f"{os.path.splitext(source_path)[0]}_文字起こし.txt"
            if os.path.exists(transcription_file):
                trans_filename = os.path.basename(transcription_file)
                trans_dest = os.path.join(dest_folder, trans_filename)

                # 同名チェック
                if os.path.exists(trans_dest):
                    base, ext = os.path.splitext(trans_filename)
                    counter = 1
                    while os.path.exists(trans_dest):
                        trans_dest = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                        counter += 1

                shutil.move(transcription_file, trans_dest)
                logger.info(f"Transcription moved: {transcription_file} -> {trans_dest}")

            return True

        except Exception as e:
            logger.error(f"Failed to move file: {e}")
            return False


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== StartupManager Test ===")
    print(f"App path: {StartupManager.get_app_path()}")
    print(f"Startup enabled: {StartupManager.is_startup_enabled()}")
