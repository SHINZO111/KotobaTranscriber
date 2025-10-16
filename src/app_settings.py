"""
アプリケーション設定の永続化モジュール
ユーザー設定をJSONファイルに保存・復元します
"""

import copy
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AppSettings:
    """
    アプリケーション設定の管理クラス

    設定をJSONファイルに保存し、次回起動時に復元します
    スレッドセーフな実装と包括的な入力検証を提供します
    """

    DEFAULT_SETTINGS_FILE = "app_settings.json"

    # デフォルト設定
    DEFAULT_SETTINGS = {
        # フォルダ監視設定
        "monitored_folder": None,
        "monitor_interval": 10,
        "completed_folder": None,
        "auto_move_completed": False,

        # テキスト整形オプション
        "remove_fillers": True,
        "add_punctuation": True,
        "format_paragraphs": True,
        "enable_diarization": False,
        "enable_llm_correction": False,
        "use_advanced_llm": False,

        # リアルタイム文字起こし設定
        "realtime": {
            "device_index": None,
            "model_size": "base",
            "vad_enabled": True,
            "vad_threshold": 10,  # 0.010 * 1000
        },

        # ウィンドウ設定
        "window": {
            "width": 900,
            "height": 700,
            "x": 100,
            "y": 100
        }
    }

    # 設定値の型定義
    SETTING_TYPES = {
        'monitored_folder': (str, type(None)),
        'monitor_interval': int,
        'completed_folder': (str, type(None)),
        'auto_move_completed': bool,
        'remove_fillers': bool,
        'add_punctuation': bool,
        'format_paragraphs': bool,
        'enable_diarization': bool,
        'enable_llm_correction': bool,
        'use_advanced_llm': bool,
        'realtime.device_index': (int, type(None)),
        'realtime.model_size': str,
        'realtime.vad_enabled': bool,
        'realtime.vad_threshold': int,
        'window.width': int,
        'window.height': int,
        'window.x': int,
        'window.y': int,
    }

    def __init__(self, settings_file: Optional[str] = None):
        """
        初期化

        Args:
            settings_file: 設定ファイルのパス（Noneの場合はデフォルト）

        Raises:
            ValueError: 設定ファイルのパスが許可されたディレクトリ外の場合
        """
        if settings_file is None:
            # 実行ファイルと同じディレクトリに保存
            self.settings_file = Path(__file__).parent.parent / self.DEFAULT_SETTINGS_FILE
        else:
            # セキュリティ検証: パストラバーサル対策
            custom_path = Path(settings_file).resolve()

            # 許可されたディレクトリ
            project_root = Path(__file__).parent.parent.resolve()
            user_home = Path.home().resolve()

            # パスが許可されたディレクトリ配下かチェック
            is_allowed = False
            try:
                custom_path.relative_to(project_root)
                is_allowed = True
            except ValueError:
                try:
                    custom_path.relative_to(user_home)
                    is_allowed = True
                except ValueError:
                    pass

            if not is_allowed:
                raise ValueError(
                    f"Settings file must be within project directory ({project_root}) "
                    f"or user home ({user_home}): {custom_path}"
                )

            self.settings_file = custom_path

        self.settings: Dict[str, Any] = copy.deepcopy(self.DEFAULT_SETTINGS)

        # デバウンス用のタイマーとロック
        self._save_timer: Optional[threading.Timer] = None
        self._save_debounce_delay = 2.0  # 2秒の遅延
        self._lock = threading.RLock()  # 再入可能ロック

        logger.info(f"AppSettings initialized: {self.settings_file}")

    def __del__(self):
        """デストラクタ：保留中のタイマーをクリーンアップ"""
        try:
            self.cancel_pending_save()
        except:
            pass

    def _validate_key(self, key: str) -> None:
        """
        キーのフォーマットを検証

        Args:
            key: 検証するキー

        Raises:
            ValueError: キーが無効な場合
        """
        if not key or not isinstance(key, str):
            raise ValueError(f"Invalid key: {key}")

        # キーは英小文字、数字、アンダースコア、ドットのみ許可
        if not re.match(r'^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$', key):
            raise ValueError(f"Key contains invalid characters: {key}")

    def _validate_value_type(self, key: str, value: Any) -> None:
        """
        値の型を検証

        Args:
            key: 設定キー
            value: 検証する値

        Raises:
            TypeError: 値の型が期待される型と異なる場合
        """
        expected_types = self.SETTING_TYPES.get(key)
        if expected_types and not isinstance(value, expected_types):
            type_names = (
                expected_types.__name__ if hasattr(expected_types, '__name__')
                else ', '.join(t.__name__ for t in expected_types)
            )
            raise TypeError(
                f"Setting '{key}' expects {type_names}, got {type(value).__name__}"
            )

    def _validate_value_range(self, key: str, value: Any) -> None:
        """
        値の範囲を検証

        Args:
            key: 設定キー
            value: 検証する値

        Raises:
            ValueError: 値が許容範囲外の場合
        """
        if key == 'monitor_interval' and isinstance(value, int):
            if not (5 <= value <= 60):
                raise ValueError(f"monitor_interval must be between 5 and 60, got {value}")

        elif key == 'realtime.vad_threshold' and isinstance(value, int):
            if not (5 <= value <= 50):
                raise ValueError(f"vad_threshold must be between 5 and 50, got {value}")

        elif key == 'realtime.model_size' and isinstance(value, str):
            valid_models = ['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3']
            if value not in valid_models:
                raise ValueError(f"Invalid model size: {value}. Must be one of {valid_models}")

        elif key in ['window.width', 'window.height'] and isinstance(value, int):
            if value < 100 or value > 10000:
                raise ValueError(f"{key} must be between 100 and 10000, got {value}")

        elif key in ['window.x', 'window.y'] and isinstance(value, int):
            if value < -5000 or value > 10000:
                raise ValueError(f"{key} must be between -5000 and 10000, got {value}")

    def load(self) -> bool:
        """
        設定ファイルを読み込む

        Returns:
            読み込み成功ならTrue
        """
        if not self.settings_file.exists():
            logger.info(f"Settings file not found: {self.settings_file}, using defaults")
            return False

        with self._lock:
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)

                # デフォルト設定とマージ（新しい設定項目が追加された場合に対応）
                self._merge_settings(self.settings, loaded_settings)

                logger.info(f"Settings loaded successfully from: {self.settings_file}")
                return True

            except json.JSONDecodeError as e:
                logger.error(f"Settings file is corrupted (invalid JSON): {e}", exc_info=True)
                return False

            except (IOError, OSError, PermissionError) as e:
                logger.error(f"Failed to read settings file: {e}", exc_info=True)
                return False

            except Exception as e:
                logger.exception(f"Unexpected error loading settings: {e}")
                return False

    def save(self) -> bool:
        """
        設定ファイルに保存（アトミック書き込み）

        Returns:
            保存成功ならTrue
        """
        with self._lock:
            temp_file = None
            try:
                # ディレクトリが存在しない場合は作成
                self.settings_file.parent.mkdir(parents=True, exist_ok=True)

                # 一時ファイルに書き込み
                temp_file = self.settings_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, ensure_ascii=False, indent=2)

                # アトミックにリネーム（既存ファイルを上書き）
                os.replace(temp_file, self.settings_file)

                logger.info(f"Settings saved successfully to: {self.settings_file}")
                return True

            except (IOError, OSError, PermissionError) as e:
                logger.error(f"Failed to write settings file: {e}", exc_info=True)
                # エラー時は一時ファイルを削除
                if temp_file and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                return False

            except Exception as e:
                logger.exception(f"Unexpected error saving settings: {e}")
                # エラー時は一時ファイルを削除
                if temp_file and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                return False

    def save_debounced(self) -> None:
        """
        デバウンス付きで保存

        連続した保存要求を遅延させ、最後の要求から指定時間経過後に実際の保存を実行する。
        これによりI/O操作を削減してパフォーマンスを向上させる。
        """
        with self._lock:
            # 既存のタイマーをキャンセル
            if self._save_timer is not None:
                self._save_timer.cancel()

            # 新しいタイマーをスケジュール
            self._save_timer = threading.Timer(
                self._save_debounce_delay,
                self._execute_debounced_save
            )
            self._save_timer.daemon = True
            self._save_timer.start()
            logger.debug("Debounced save scheduled")

    def _execute_debounced_save(self) -> None:
        """デバウンスされた保存を実行（内部用）"""
        with self._lock:
            self._save_timer = None
            self.save()

    def save_immediate(self) -> bool:
        """
        即座に保存（デバウンスなし）

        アプリケーション終了時など、確実に保存が必要な場合に使用する。

        Returns:
            保存成功ならTrue
        """
        with self._lock:
            # 保留中のタイマーをキャンセル
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None

            return self.save()

    def cancel_pending_save(self) -> None:
        """保留中の保存をキャンセル"""
        with self._lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
                logger.debug("Pending save cancelled")

    def _merge_settings(self, base: Dict, updates: Dict) -> None:
        """
        設定を再帰的にマージ

        Args:
            base: ベース設定（変更される）
            updates: 更新する設定
        """
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                # 辞書の場合は再帰的にマージ
                self._merge_settings(base[key], value)
            else:
                # それ以外は上書き
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        設定値を取得（検証付き）

        Args:
            key: 設定キー（ドット区切りで階層指定可能: "realtime.model_size"）
            default: デフォルト値

        Returns:
            設定値

        Raises:
            ValueError: キーが無効な場合
        """
        self._validate_key(key)

        with self._lock:
            keys = key.split('.')
            value = self.settings

            for k in keys:
                if not isinstance(value, dict):
                    logger.warning(f"Key path '{key}' traverses non-dict value")
                    return default
                if k not in value:
                    return default
                value = value[k]

            return value

    def set(self, key: str, value: Any) -> None:
        """
        設定値を設定（検証付き）

        Args:
            key: 設定キー（ドット区切りで階層指定可能）
            value: 設定値

        Raises:
            ValueError: キーまたは値が無効な場合
            TypeError: 値の型が期待される型と異なる場合
        """
        self._validate_key(key)
        self._validate_value_type(key, value)
        self._validate_value_range(key, value)

        with self._lock:
            keys = key.split('.')
            target = self.settings

            # 親階層をたどる（辞書を確保）
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                elif not isinstance(target[k], dict):
                    raise ValueError(
                        f"Cannot set '{key}': intermediate key '{k}' is not a dict"
                    )
                target = target[k]

            # 値を設定
            target[keys[-1]] = value

    def get_all(self) -> Dict[str, Any]:
        """
        すべての設定を取得

        Returns:
            設定辞書（コピー）
        """
        with self._lock:
            return copy.deepcopy(self.settings)

    def reset(self) -> None:
        """設定をデフォルトにリセット"""
        with self._lock:
            self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
            logger.info("Settings reset to defaults")


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("\n=== AppSettings Test ===")

    # 設定インスタンス作成
    settings = AppSettings()

    # デフォルト設定表示
    print("\n1. Default settings:")
    print(f"  monitored_folder: {settings.get('monitored_folder')}")
    print(f"  realtime.model_size: {settings.get('realtime.model_size')}")

    # 設定変更
    print("\n2. Changing settings:")
    settings.set('monitored_folder', 'C:/test/folder')
    settings.set('realtime.model_size', 'medium')
    print(f"  monitored_folder: {settings.get('monitored_folder')}")
    print(f"  realtime.model_size: {settings.get('realtime.model_size')}")

    # 保存
    print("\n3. Saving settings:")
    if settings.save():
        print("  [OK] Settings saved successfully")

    # 新しいインスタンスで読み込み
    print("\n4. Loading settings in new instance:")
    settings2 = AppSettings()
    if settings2.load():
        print("  [OK] Settings loaded successfully")
        print(f"  monitored_folder: {settings2.get('monitored_folder')}")
        print(f"  realtime.model_size: {settings2.get('realtime.model_size')}")

    # 検証テスト
    print("\n5. Validation tests:")

    # 正常な値
    try:
        settings.set('monitor_interval', 15)
        print("  [OK] Valid monitor_interval accepted")
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")

    # 範囲外の値
    try:
        settings.set('monitor_interval', 100)
        print("  [FAIL] Invalid monitor_interval accepted (should fail)")
    except ValueError as e:
        print(f"  [OK] Range validation working: {e}")

    # 型エラー
    try:
        settings.set('monitor_interval', "invalid")
        print("  [FAIL] Invalid type accepted (should fail)")
    except TypeError as e:
        print(f"  [OK] Type validation working: {e}")

    # 無効なキー
    try:
        settings.set('INVALID-KEY', 'value')
        print("  [FAIL] Invalid key accepted (should fail)")
    except ValueError as e:
        print(f"  [OK] Key validation working: {e}")

    # 無効なモデルサイズ
    try:
        settings.set('realtime.model_size', 'invalid_model')
        print("  [FAIL] Invalid model size accepted (should fail)")
    except ValueError as e:
        print(f"  [OK] Model size validation working: {e}")

    # 正常なウィンドウサイズ
    try:
        settings.set('window.width', 1200)
        settings.set('window.height', 800)
        print("  [OK] Valid window dimensions accepted")
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")

    # 無効なウィンドウサイズ
    try:
        settings.set('window.width', 50)
        print("  [FAIL] Invalid window width accepted (should fail)")
    except ValueError as e:
        print(f"  [OK] Window size validation working: {e}")

    # VAD閾値テスト
    try:
        settings.set('realtime.vad_threshold', 15)
        print("  [OK] Valid vad_threshold accepted")
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}")

    try:
        settings.set('realtime.vad_threshold', 100)
        print("  [FAIL] Invalid vad_threshold accepted (should fail)")
    except ValueError as e:
        print(f"  [OK] VAD threshold validation working: {e}")

    print("\nTest completed")
