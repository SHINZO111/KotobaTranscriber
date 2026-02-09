"""
バリデーションユーティリティ - KotobaTranscriber Validation Utilities

入力値の検証とサニタイズを行うユーティリティクラス。
セキュリティ上重要なパス検証やデータ整合性チェックを提供。
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Union, List, Any

logger = logging.getLogger(__name__)

__all__ = ['Validator', 'ValidationError']


class ValidationError(Exception):
    """バリデーションエラー"""
    pass


class Validator:
    """
    入力値検証のためのユーティリティクラス

    すべてのメソッドは静的メソッドとして実装され、
    クラスをインスタンス化せずに使用可能。
    """

    # 許可されるファイル拡張子
    ALLOWED_AUDIO_EXTENSIONS = {
        '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac',
        '.mp4', '.avi', '.mov', '.mkv', '.webm', '.wma',
        '.opus', '.amr', '.3gp',
    }

    # 許可されるモデル名パターン
    ALLOWED_MODEL_PATTERNS = [
        r'^kotoba-tech/kotoba-whisper[\w.\-]*$',
        r'^openai/whisper[\w.\-]*$',
        r'^distil-whisper/[\w.\-]+$',
        r'^(tiny|base|small|medium|large|large-v[2-9])$',
    ]

    @staticmethod
    def validate_file_path(
        path: Union[str, Path],
        allowed_dirs: Optional[List[Path]] = None,
        must_exist: bool = True,
        allowed_extensions: Optional[set] = None
    ) -> Path:
        """
        ファイルパスを検証

        Args:
            path: 検証するファイルパス
            allowed_dirs: 許可されるディレクトリのリスト（Noneの場合はチェックなし）
            must_exist: ファイルが存在する必要があるか
            allowed_extensions: 許可される拡張子のセット

        Returns:
            検証済みのPathオブジェクト

        Raises:
            ValidationError: パスが無効な場合
        """
        if path is None:
            raise ValidationError("File path cannot be None")

        # resolve() 前の元パスでパストラバーサルをチェック
        original_str = str(path)
        if '..' in original_str.replace('/', os.sep).split(os.sep) or original_str.startswith('~'):
            raise ValidationError(f"Path traversal detected in: {path}")

        try:
            path = Path(path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid path format: {e}") from e

        # 許可されるディレクトリのチェック
        if allowed_dirs:
            is_allowed = False
            for allowed_dir in allowed_dirs:
                try:
                    path.relative_to(allowed_dir.resolve())
                    is_allowed = True
                    break
                except ValueError:
                    continue
            if not is_allowed:
                raise ValidationError(f"Path not in allowed directories: {path}")

        # シンボリックリンク検出（セキュリティ: 許可ディレクトリ外への参照防止）
        if path.is_symlink():
            if allowed_dirs:
                raise ValidationError(f"Symlinks not permitted in validated paths: {path} -> {path.resolve()}")
            logger.warning(f"Symlink detected: {path} -> {path.resolve()}")

        # 存在チェック
        if must_exist and not path.exists():
            raise ValidationError(f"File does not exist: {path}")

        # 拡張子チェック
        if allowed_extensions:
            ext = path.suffix.lower()
            if ext not in allowed_extensions:
                raise ValidationError(
                    f"File extension '{ext}' not allowed. "
                    f"Allowed: {', '.join(allowed_extensions)}"
                )

        return path

    @staticmethod
    def validate_text_length(
        text: str,
        min_length: int = 0,
        max_length: int = 1000000,
        field_name: str = "text"
    ) -> str:
        """
        テキストの長さを検証

        Args:
            text: 検証するテキスト
            min_length: 最小長
            max_length: 最大長
            field_name: エラーメッセージ用のフィールド名

        Returns:
            検証済みのテキスト

        Raises:
            ValidationError: テキスト長が範囲外の場合
        """
        if text is None:
            raise ValidationError(f"{field_name} cannot be None")

        if not isinstance(text, str):
            raise ValidationError(f"{field_name} must be a string")

        length = len(text)
        if length < min_length:
            raise ValidationError(
                f"{field_name} is too short: {length} < {min_length}"
            )
        if length > max_length:
            raise ValidationError(
                f"{field_name} is too long: {length} > {max_length}"
            )

        return text

    @staticmethod
    def validate_positive_integer(
        value: Any,
        name: str = "value",
        default: Optional[int] = None,
        min_value: int = 1,
        max_value: Optional[int] = None,
        # Alternative parameter names for compatibility
        min_val: Optional[int] = None,
        max_val: Optional[int] = None
    ) -> int:
        """
        正の整数を検証

        Args:
            value: 検証する値
            name: エラーメッセージ用の名前
            default: 値がNoneの場合のデフォルト値
            min_value: 最小値
            max_value: 最大値（Noneの場合は上限なし）

        Returns:
            検証済みの整数

        Raises:
            ValidationError: 値が無効な場合
        """
        # Support alternative parameter names
        if min_val is not None:
            min_value = min_val
        if max_val is not None:
            max_value = max_val

        if value is None:
            if default is not None:
                return default
            raise ValidationError(f"{name} cannot be None")

        try:
            int_value = int(value)
        except (TypeError, ValueError) as e:
            raise ValidationError(f"{name} must be an integer, got: {type(value).__name__}") from e

        if int_value < min_value:
            raise ValidationError(f"{name} must be >= {min_value}, got: {int_value}")

        if max_value is not None and int_value > max_value:
            raise ValidationError(f"{name} must be <= {max_value}, got: {int_value}")

        return int_value

    @staticmethod
    def validate_model_name(
        model_name: str,
        model_type: Optional[str] = None
    ) -> str:
        """
        モデル名を検証

        Args:
            model_name: 検証するモデル名
            model_type: モデルタイプ（"whisper"など）

        Returns:
            検証済みのモデル名

        Raises:
            ValidationError: モデル名が無効な場合
        """
        if model_name is None or not model_name.strip():
            raise ValidationError("Model name cannot be empty")

        model_name = model_name.strip()

        # 許可されるパターンのいずれかにマッチするか
        for pattern in Validator.ALLOWED_MODEL_PATTERNS:
            if re.match(pattern, model_name):
                return model_name

        # セキュリティ: パターンにマッチしないモデル名は拒否
        logger.error(f"Model name '{model_name}' does not match any allowed patterns")
        raise ValidationError(
            f"Model name '{model_name}' is not in the allowed list. "
            f"Allowed patterns: {Validator.ALLOWED_MODEL_PATTERNS}"
        )

    @staticmethod
    def validate_chunk_length(
        chunk_length_s: Any,
        default: int = 15,
        min_value: int = 1,
        max_value: int = 60
    ) -> int:
        """
        チャンク長（秒）を検証

        Args:
            chunk_length_s: チャンク長（秒）
            default: デフォルト値
            min_value: 最小値
            max_value: 最大値

        Returns:
            検証済みのチャンク長

        Raises:
            ValidationError: 値が無効な場合
        """
        return Validator.validate_positive_integer(
            chunk_length_s,
            name="chunk_length_s",
            default=default,
            min_value=min_value,
            max_value=max_value
        )

    @staticmethod
    def validate_audio_file(path: Union[str, Path]) -> Path:
        """
        音声/動画ファイルパスを検証

        Args:
            path: 検証するファイルパス

        Returns:
            検証済みのPathオブジェクト

        Raises:
            ValidationError: パスが無効な場合
        """
        return Validator.validate_file_path(
            path,
            must_exist=True,
            allowed_extensions=Validator.ALLOWED_AUDIO_EXTENSIONS
        )

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        ファイル名をサニタイズ

        Args:
            filename: サニタイズするファイル名

        Returns:
            サニタイズ済みのファイル名
        """
        if not filename:
            return "untitled"

        # 危険な文字を削除（制御文字 + ファイルシステム予約文字）
        sanitized = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', filename)

        # 先頭・末尾の空白とドットを削除
        sanitized = sanitized.strip(' .')

        # 空になった場合
        if not sanitized:
            return "untitled"

        # 予約名のチェック（Windows）
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        name_without_ext = sanitized.split('.')[0].upper()
        if name_without_ext in reserved_names:
            sanitized = f"_{sanitized}"

        # ファイル名長制限 (Windows MAX_PATH対策)
        MAX_FILENAME_LENGTH = 200
        if len(sanitized) > MAX_FILENAME_LENGTH:
            name_part, _, ext_part = sanitized.rpartition('.')
            if ext_part and len(ext_part) < 10:
                sanitized = name_part[:MAX_FILENAME_LENGTH - len(ext_part) - 1] + '.' + ext_part
            else:
                sanitized = sanitized[:MAX_FILENAME_LENGTH]

        return sanitized


# テスト用
if __name__ == "__main__":
    print("Testing Validator class...")

    # validate_positive_integer
    try:
        result = Validator.validate_positive_integer(5, "test_value")
        print(f"validate_positive_integer(5): {result}")
    except ValidationError as e:
        print(f"Error: {e}")

    # validate_text_length
    try:
        result = Validator.validate_text_length("Hello, World!", min_length=0, max_length=100)
        print(f"validate_text_length: {result}")
    except ValidationError as e:
        print(f"Error: {e}")

    # validate_model_name
    try:
        result = Validator.validate_model_name("kotoba-tech/kotoba-whisper-v2.2", model_type="whisper")
        print(f"validate_model_name: {result}")
    except ValidationError as e:
        print(f"Error: {e}")

    # sanitize_filename
    result = Validator.sanitize_filename("test<file>:name?.txt")
    print(f"sanitize_filename: {result}")

    print("\nAll tests completed!")
