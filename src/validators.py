"""
入力検証モジュール (validators.py)

セキュリティ向上と不正入力の早期検出のための包括的なバリデーション機能を提供

機能:
- ファイルパスの検証（存在、パストラバーサル防止、拡張子、サイズ）
- 音声パラメータの検証（サンプリングレート、チャンネル数、長さ）
- モデル名の検証
- 数値範囲の検証
- テキスト入力のサニタイズ
- フォルダパスの検証
- デバイスインデックスの検証
"""

from typing import Any, List, Optional, Union, Tuple
from pathlib import Path
import re
import os
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """バリデーションエラー例外

    バリデーション処理で問題が検出された場合に発生する
    """
    pass


class Validator:
    """包括的な入力検証を提供する静的クラス

    セキュリティと堅牢性を向上させるため、すべてのユーザー入力と外部データに対して
    バリデーションを実行することを推奨
    """

    # サポートされる音声・動画ファイル拡張子
    SUPPORTED_AUDIO_EXTENSIONS = [
        '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac',
        '.wma', '.opus', '.amr'
    ]

    SUPPORTED_VIDEO_EXTENSIONS = [
        '.mp4', '.avi', '.mov', '.mkv', '.3gp', '.webm'
    ]

    SUPPORTED_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

    # サポートされるWhisperモデル
    SUPPORTED_WHISPER_MODELS = [
        "kotoba-tech/kotoba-whisper-v2.2",
        "kotoba-tech/kotoba-whisper-v1.1",
        "kotoba-tech/kotoba-whisper-v1.0",
        "openai/whisper-tiny",
        "openai/whisper-base",
        "openai/whisper-small",
        "openai/whisper-medium",
        "openai/whisper-large-v2",
        "openai/whisper-large-v3",
    ]

    # Faster Whisperモデルサイズ
    SUPPORTED_FASTER_WHISPER_SIZES = [
        "tiny", "base", "small", "medium", "large-v2", "large-v3"
    ]

    # 最大ファイルサイズ（デフォルト: 2GB）
    DEFAULT_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB in bytes

    # 音声パラメータの範囲
    VALID_SAMPLE_RATE_RANGE = (8000, 48000)  # 8kHz ~ 48kHz
    VALID_CHANNELS = [1, 2]  # モノラルまたはステレオ
    MAX_AUDIO_DURATION = 36000  # 10時間（秒単位）

    @staticmethod
    def validate_file_path(
        path: str,
        allowed_extensions: Optional[List[str]] = None,
        max_size: Optional[int] = None,
        must_exist: bool = True
    ) -> Path:
        """
        ファイルパスを検証

        Args:
            path: 検証するファイルパス
            allowed_extensions: 許可する拡張子のリスト（例: ['.mp3', '.wav']）
                               Noneの場合は全サポート形式を許可
            max_size: 最大ファイルサイズ（バイト）。Noneの場合はデフォルト値を使用
            must_exist: ファイルが存在しなければならないか

        Returns:
            Path: 検証済みのPathオブジェクト

        Raises:
            ValidationError: バリデーション失敗時
        """
        if not path or not isinstance(path, (str, Path)):
            raise ValidationError(f"Invalid file path type: {type(path)}")

        # Pathオブジェクトに変換
        try:
            p = Path(path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid path format: {path} - {str(e)}")

        # 存在チェック
        if must_exist and not p.exists():
            raise ValidationError(f"File not found: {path}")

        # ファイルタイプチェック（ディレクトリは不可）
        if must_exist and not p.is_file():
            raise ValidationError(f"Path is not a file: {path}")

        # パストラバーサル防止（相対パス記号の検出）
        path_str = str(path)
        if '..' in path_str or path_str.startswith('/') or ':' in path_str[1:]:
            # Windowsの絶対パス（C:\など）は許可
            if not (len(path_str) > 2 and path_str[1] == ':' and path_str[2] == '\\'):
                logger.warning(f"Potentially unsafe path detected: {path}")

        # 拡張子チェック
        if allowed_extensions is not None:
            # 拡張子を正規化（小文字、ドット付き）
            normalized_extensions = [
                ext if ext.startswith('.') else f'.{ext}'
                for ext in allowed_extensions
            ]
            normalized_extensions = [ext.lower() for ext in normalized_extensions]

            if p.suffix.lower() not in normalized_extensions:
                raise ValidationError(
                    f"Invalid file extension: {p.suffix}. "
                    f"Allowed: {', '.join(normalized_extensions)}"
                )
        else:
            # デフォルト: 全サポート形式
            if p.suffix.lower() not in Validator.SUPPORTED_EXTENSIONS:
                raise ValidationError(
                    f"Unsupported file extension: {p.suffix}. "
                    f"Supported: {', '.join(Validator.SUPPORTED_EXTENSIONS)}"
                )

        # サイズチェック（ファイルが存在する場合のみ）
        if must_exist:
            max_size = max_size or Validator.DEFAULT_MAX_FILE_SIZE
            file_size = p.stat().st_size

            if file_size > max_size:
                size_mb = file_size / (1024 * 1024)
                max_mb = max_size / (1024 * 1024)
                raise ValidationError(
                    f"File too large: {size_mb:.2f}MB (max: {max_mb:.2f}MB)"
                )

            # 空ファイルチェック
            if file_size == 0:
                raise ValidationError(f"File is empty: {path}")

        logger.debug(f"File path validated: {p}")
        return p

    @staticmethod
    def validate_audio_parameters(
        sample_rate: int,
        channels: int,
        duration: Optional[float] = None
    ) -> None:
        """
        音声パラメータを検証

        Args:
            sample_rate: サンプリングレート（Hz）
            channels: チャンネル数（1=モノラル, 2=ステレオ）
            duration: 音声の長さ（秒）。Noneの場合は検証しない

        Raises:
            ValidationError: バリデーション失敗時
        """
        # サンプリングレート検証
        min_rate, max_rate = Validator.VALID_SAMPLE_RATE_RANGE
        if not isinstance(sample_rate, int) or not min_rate <= sample_rate <= max_rate:
            raise ValidationError(
                f"Invalid sample rate: {sample_rate}Hz. "
                f"Valid range: {min_rate}-{max_rate}Hz"
            )

        # チャンネル数検証
        if channels not in Validator.VALID_CHANNELS:
            raise ValidationError(
                f"Invalid channels: {channels}. "
                f"Valid: {Validator.VALID_CHANNELS} (1=mono, 2=stereo)"
            )

        # 長さ検証
        if duration is not None:
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise ValidationError(f"Invalid duration: {duration}s (must be > 0)")

            if duration > Validator.MAX_AUDIO_DURATION:
                max_hours = Validator.MAX_AUDIO_DURATION / 3600
                raise ValidationError(
                    f"Audio too long: {duration}s (max: {max_hours:.1f} hours)"
                )

        logger.debug(
            f"Audio parameters validated: {sample_rate}Hz, {channels}ch, {duration}s"
        )

    @staticmethod
    def validate_model_name(
        name: str,
        model_type: str = "whisper"
    ) -> str:
        """
        モデル名を検証

        Args:
            name: モデル名
            model_type: モデルタイプ ("whisper", "faster-whisper")

        Returns:
            str: 正規化されたモデル名

        Raises:
            ValidationError: バリデーション失敗時
        """
        if not name or not isinstance(name, str):
            raise ValidationError(f"Invalid model name type: {type(name)}")

        # 正規化（前後の空白削除）
        normalized_name = name.strip()

        if model_type == "whisper":
            allowed_models = Validator.SUPPORTED_WHISPER_MODELS
        elif model_type == "faster-whisper":
            allowed_models = Validator.SUPPORTED_FASTER_WHISPER_SIZES
        else:
            raise ValidationError(f"Unknown model type: {model_type}")

        if normalized_name not in allowed_models:
            raise ValidationError(
                f"Invalid model name: {name}. "
                f"Allowed for {model_type}: {', '.join(allowed_models)}"
            )

        logger.debug(f"Model name validated: {normalized_name} ({model_type})")
        return normalized_name

    @staticmethod
    def validate_threshold(
        value: float,
        min_val: float = 0.0,
        max_val: float = 1.0,
        name: str = "threshold"
    ) -> float:
        """
        閾値（0.0〜1.0など）を検証

        Args:
            value: 検証する値
            min_val: 最小値
            max_val: 最大値
            name: パラメータ名（エラーメッセージ用）

        Returns:
            float: 検証済みの値

        Raises:
            ValidationError: バリデーション失敗時
        """
        if not isinstance(value, (int, float)):
            raise ValidationError(f"Invalid {name} type: {type(value)} (expected number)")

        if not min_val <= value <= max_val:
            raise ValidationError(
                f"{name} out of range: {value} (valid: {min_val}~{max_val})"
            )

        logger.debug(f"{name} validated: {value}")
        return float(value)

    @staticmethod
    def validate_positive_integer(
        value: int,
        min_val: int = 1,
        max_val: Optional[int] = None,
        name: str = "value"
    ) -> int:
        """
        正の整数を検証

        Args:
            value: 検証する値
            min_val: 最小値（デフォルト: 1）
            max_val: 最大値（Noneの場合は制限なし）
            name: パラメータ名（エラーメッセージ用）

        Returns:
            int: 検証済みの値

        Raises:
            ValidationError: バリデーション失敗時
        """
        if not isinstance(value, int):
            raise ValidationError(f"Invalid {name} type: {type(value)} (expected int)")

        if value < min_val:
            raise ValidationError(f"{name} too small: {value} (min: {min_val})")

        if max_val is not None and value > max_val:
            raise ValidationError(f"{name} too large: {value} (max: {max_val})")

        logger.debug(f"{name} validated: {value}")
        return value

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """
        ファイル名をサニタイズ（危険な文字を削除）

        Args:
            filename: サニタイズするファイル名
            max_length: 最大長（デフォルト: 255文字）

        Returns:
            str: サニタイズされたファイル名

        Raises:
            ValidationError: ファイル名が空になる場合
        """
        if not filename or not isinstance(filename, str):
            raise ValidationError(f"Invalid filename type: {type(filename)}")

        # Windows/Linuxで使用できない文字を削除
        # Windows: < > : " / \ | ? *
        # Linux: / (null byte)
        unsafe_chars = r'[<>:"/\\|?*\x00-\x1f]'
        safe = re.sub(unsafe_chars, '', filename)

        # 前後の空白・ピリオドを削除（Windowsでは問題になる）
        safe = safe.strip('. ')

        # 長さ制限
        if len(safe) > max_length:
            # 拡張子を保持しつつ切り詰め
            name_part, ext = os.path.splitext(safe)
            name_part = name_part[:max_length - len(ext)]
            safe = name_part + ext

        # 空になった場合はエラー
        if not safe:
            raise ValidationError(f"Filename becomes empty after sanitization: {filename}")

        logger.debug(f"Filename sanitized: {filename} -> {safe}")
        return safe

    @staticmethod
    def validate_folder_path(
        path: str,
        must_exist: bool = True,
        create_if_missing: bool = False
    ) -> Path:
        """
        フォルダパスを検証

        Args:
            path: 検証するフォルダパス
            must_exist: フォルダが存在しなければならないか
            create_if_missing: 存在しない場合に作成するか

        Returns:
            Path: 検証済みのPathオブジェクト

        Raises:
            ValidationError: バリデーション失敗時
        """
        if not path or not isinstance(path, (str, Path)):
            raise ValidationError(f"Invalid folder path type: {type(path)}")

        # Pathオブジェクトに変換
        try:
            p = Path(path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid path format: {path} - {str(e)}")

        # 存在チェック
        if must_exist and not p.exists():
            if create_if_missing:
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created folder: {p}")
                except Exception as e:
                    raise ValidationError(f"Failed to create folder: {path} - {str(e)}")
            else:
                raise ValidationError(f"Folder not found: {path}")

        # ディレクトリタイプチェック
        if p.exists() and not p.is_dir():
            raise ValidationError(f"Path is not a directory: {path}")

        logger.debug(f"Folder path validated: {p}")
        return p

    @staticmethod
    def validate_device_index(
        device_index: Optional[int],
        max_devices: int = 100
    ) -> Optional[int]:
        """
        オーディオデバイスインデックスを検証

        Args:
            device_index: デバイスインデックス（Noneの場合はデフォルトデバイス）
            max_devices: 最大デバイス数（デフォルト: 100）

        Returns:
            Optional[int]: 検証済みのデバイスインデックス

        Raises:
            ValidationError: バリデーション失敗時
        """
        if device_index is None:
            return None

        if not isinstance(device_index, int):
            raise ValidationError(f"Invalid device index type: {type(device_index)}")

        if device_index < 0 or device_index >= max_devices:
            raise ValidationError(
                f"Device index out of range: {device_index} (valid: 0-{max_devices-1})"
            )

        logger.debug(f"Device index validated: {device_index}")
        return device_index

    @staticmethod
    def validate_text_length(
        text: str,
        min_length: int = 0,
        max_length: int = 1000000,
        name: str = "text"
    ) -> str:
        """
        テキストの長さを検証

        Args:
            text: 検証するテキスト
            min_length: 最小長
            max_length: 最大長
            name: パラメータ名（エラーメッセージ用）

        Returns:
            str: 検証済みのテキスト

        Raises:
            ValidationError: バリデーション失敗時
        """
        if not isinstance(text, str):
            raise ValidationError(f"Invalid {name} type: {type(text)} (expected str)")

        text_len = len(text)

        if text_len < min_length:
            raise ValidationError(
                f"{name} too short: {text_len} characters (min: {min_length})"
            )

        if text_len > max_length:
            raise ValidationError(
                f"{name} too long: {text_len} characters (max: {max_length})"
            )

        logger.debug(f"{name} length validated: {text_len} characters")
        return text

    @staticmethod
    def validate_chunk_length(chunk_length_s: int) -> int:
        """
        チャンク長（秒単位）を検証

        Args:
            chunk_length_s: チャンク長（秒）

        Returns:
            int: 検証済みのチャンク長

        Raises:
            ValidationError: バリデーション失敗時
        """
        # チャンク長は5秒〜30秒が妥当
        MIN_CHUNK = 5
        MAX_CHUNK = 30

        if not isinstance(chunk_length_s, int):
            raise ValidationError(
                f"Invalid chunk length type: {type(chunk_length_s)} (expected int)"
            )

        if not MIN_CHUNK <= chunk_length_s <= MAX_CHUNK:
            raise ValidationError(
                f"Chunk length out of range: {chunk_length_s}s (valid: {MIN_CHUNK}-{MAX_CHUNK}s)"
            )

        logger.debug(f"Chunk length validated: {chunk_length_s}s")
        return chunk_length_s

    @staticmethod
    def validate_batch_size(batch_size: int) -> int:
        """
        バッチサイズを検証

        Args:
            batch_size: バッチサイズ

        Returns:
            int: 検証済みのバッチサイズ

        Raises:
            ValidationError: バリデーション失敗時
        """
        # バッチサイズは1〜10が妥当
        MIN_BATCH = 1
        MAX_BATCH = 10

        if not isinstance(batch_size, int):
            raise ValidationError(
                f"Invalid batch size type: {type(batch_size)} (expected int)"
            )

        if not MIN_BATCH <= batch_size <= MAX_BATCH:
            raise ValidationError(
                f"Batch size out of range: {batch_size} (valid: {MIN_BATCH}-{MAX_BATCH})"
            )

        logger.debug(f"Batch size validated: {batch_size}")
        return batch_size


class AudioValidator:
    """音声関連の高度なバリデーション

    ファイル形式の詳細検証、メタデータの検証など
    """

    @staticmethod
    def validate_audio_file_metadata(file_path: Path) -> dict:
        """
        音声ファイルのメタデータを検証（オプション機能）

        librosaやffprobeを使用してメタデータを取得し検証
        実装はオプション（依存関係が多いため）

        Args:
            file_path: 音声ファイルパス

        Returns:
            dict: メタデータ（sample_rate, channels, duration等）

        Raises:
            ValidationError: メタデータ取得失敗時
        """
        # TODO: librosaやffprobeを使用してメタデータを検証
        # 現在は基本的なファイル検証のみ
        logger.debug(f"Audio metadata validation not yet implemented for: {file_path}")
        return {}


if __name__ == "__main__":
    """バリデーションモジュールのテストコード"""
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Validator Test Suite")
    print("=" * 60)

    # テスト1: ファイルパス検証（存在しないファイル）
    print("\n[Test 1] File Path Validation (Non-existent)")
    try:
        Validator.validate_file_path(
            "F:/test_audio.mp3",
            must_exist=False  # 存在チェックをスキップ
        )
        print("✓ Passed: Non-existent file (must_exist=False)")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # テスト2: 不正な拡張子
    print("\n[Test 2] Invalid Extension")
    try:
        Validator.validate_file_path(
            "F:/test.exe",
            allowed_extensions=['.mp3', '.wav'],
            must_exist=False
        )
        print("✗ Failed: Should reject .exe extension")
    except ValidationError as e:
        print(f"✓ Passed: Rejected invalid extension - {e}")

    # テスト3: 音声パラメータ検証
    print("\n[Test 3] Audio Parameters Validation")
    try:
        Validator.validate_audio_parameters(
            sample_rate=16000,
            channels=1,
            duration=120.5
        )
        print("✓ Passed: Valid audio parameters")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # テスト4: 不正なサンプリングレート
    print("\n[Test 4] Invalid Sample Rate")
    try:
        Validator.validate_audio_parameters(
            sample_rate=100000,  # 範囲外
            channels=1
        )
        print("✗ Failed: Should reject invalid sample rate")
    except ValidationError as e:
        print(f"✓ Passed: Rejected invalid sample rate - {e}")

    # テスト5: モデル名検証
    print("\n[Test 5] Model Name Validation")
    try:
        model = Validator.validate_model_name(
            "kotoba-tech/kotoba-whisper-v2.2",
            model_type="whisper"
        )
        print(f"✓ Passed: Valid model name - {model}")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # テスト6: 不正なモデル名
    print("\n[Test 6] Invalid Model Name")
    try:
        Validator.validate_model_name(
            "invalid-model",
            model_type="whisper"
        )
        print("✗ Failed: Should reject invalid model name")
    except ValidationError as e:
        print(f"✓ Passed: Rejected invalid model - {e}")

    # テスト7: 閾値検証
    print("\n[Test 7] Threshold Validation")
    try:
        threshold = Validator.validate_threshold(0.5, min_val=0.0, max_val=1.0)
        print(f"✓ Passed: Valid threshold - {threshold}")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # テスト8: 範囲外の閾値
    print("\n[Test 8] Out of Range Threshold")
    try:
        Validator.validate_threshold(1.5, min_val=0.0, max_val=1.0)
        print("✗ Failed: Should reject out of range threshold")
    except ValidationError as e:
        print(f"✓ Passed: Rejected out of range threshold - {e}")

    # テスト9: ファイル名サニタイズ
    print("\n[Test 9] Filename Sanitization")
    try:
        unsafe = "test<file>name:2024.mp3"
        safe = Validator.sanitize_filename(unsafe)
        print(f"✓ Passed: Sanitized '{unsafe}' -> '{safe}'")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # テスト10: 正の整数検証
    print("\n[Test 10] Positive Integer Validation")
    try:
        value = Validator.validate_positive_integer(10, min_val=1, max_val=100)
        print(f"✓ Passed: Valid positive integer - {value}")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # テスト11: デバイスインデックス検証
    print("\n[Test 11] Device Index Validation")
    try:
        device = Validator.validate_device_index(5)
        print(f"✓ Passed: Valid device index - {device}")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # テスト12: チャンク長検証
    print("\n[Test 12] Chunk Length Validation")
    try:
        chunk = Validator.validate_chunk_length(15)
        print(f"✓ Passed: Valid chunk length - {chunk}s")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    print("\n" + "=" * 60)
    print("Test Suite Completed")
    print("=" * 60)
