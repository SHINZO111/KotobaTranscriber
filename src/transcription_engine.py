"""
KotobaTranscriber - 文字起こしエンジン
kotoba-whisper v2.2を使用した日本語音声文字起こし
"""

import os
import atexit
import torch
from transformers import pipeline
from typing import Optional, Dict, Any, List
import logging
from pathlib import Path
from base_engine import BaseTranscriptionEngine
from validators import Validator, ValidationError
from config_manager import get_config
from exceptions import ModelLoadError, TranscriptionFailedError

# オプション: 音声前処理とカスタム語彙
try:
    from audio_preprocessor import AudioPreprocessor
    PREPROCESSOR_AVAILABLE = True
except ImportError:
    PREPROCESSOR_AVAILABLE = False

try:
    from custom_vocabulary import CustomVocabulary
    VOCABULARY_AVAILABLE = True
except ImportError:
    VOCABULARY_AVAILABLE = False

# 設定マネージャーを初期化
config = get_config()

# ロガーを早期に初期化（ffmpeg検証で使用するため）
logger = logging.getLogger(__name__)


def _validate_ffmpeg_path(path: str) -> bool:
    """
    ffmpegパスの安全性を検証（PATHインジェクション対策）

    Args:
        path: 検証するffmpegパス

    Returns:
        bool: 検証成功時True、失敗時False
    """
    if not path:
        return False

    # 実パス取得（シンボリックリンク解決）
    try:
        real_path = os.path.realpath(path)
    except Exception as e:
        logger.error(f"Failed to resolve ffmpeg path: {e}")
        return False

    # 許可リストチェック（Windows/Linux両対応）
    allowed_paths = [
        Path(r"C:\ffmpeg"),
        Path(r"C:\Program Files\ffmpeg"),
        Path(r"C:\Program Files (x86)\ffmpeg"),
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/opt/ffmpeg")
    ]

    # パスが許可リストのいずれかの配下にあるか厳密にチェック
    real_path_obj = Path(real_path)
    is_allowed = False
    for allowed in allowed_paths:
        try:
            # relative_to()で親子関係を厳密に確認
            real_path_obj.relative_to(allowed)
            is_allowed = True
            break
        except ValueError:
            # 親子関係がない場合はValueErrorが発生
            continue

    if not is_allowed:
        logger.error(f"ffmpeg path not in allowed list: {real_path}")
        return False

    # ffmpeg実行ファイルの存在確認
    ffmpeg_exe = os.path.join(real_path, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
    if not os.path.isfile(ffmpeg_exe):
        logger.error(f"ffmpeg executable not found: {ffmpeg_exe}")
        return False

    logger.debug(f"ffmpeg path validated: {real_path}")
    return True


# ffmpegのパスを環境変数に追加（設定ファイルから取得、検証済み）
ffmpeg_path = config.get("audio.ffmpeg.path", default=r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin")
auto_configure = config.get("audio.ffmpeg.auto_configure", default=True)

if auto_configure and _validate_ffmpeg_path(ffmpeg_path) and ffmpeg_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")
    logger.info(f"ffmpeg path configured: {ffmpeg_path}")
else:
    if auto_configure:
        logger.warning("ffmpeg path validation failed, using system PATH")


class DeviceSelector:
    """
    デバイス選択とフォールバックロジックを管理するクラス

    CUDA/CPUの自動選択と、CUDAロード失敗時のフォールバックを処理
    """

    @staticmethod
    def select_device(device_config: str = "auto") -> str:
        """
        デバイスを選択

        Args:
            device_config: 設定値 ("auto", "cuda", "cpu")

        Returns:
            str: 選択されたデバイス ("cuda" or "cpu")
        """
        if device_config == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = device_config

        logger.info(f"Device selected: {device}")
        return device

    @staticmethod
    def get_torch_dtype(device: str) -> torch.dtype:
        """
        デバイスに適したtorch dtypeを取得

        Args:
            device: デバイス名 ("cuda" or "cpu")

        Returns:
            torch.dtype: 適切なデータ型
        """
        return torch.float16 if device == "cuda" else torch.float32

    @staticmethod
    def get_device_id(device: str) -> int:
        """
        パイプライン用のデバイスIDを取得

        Args:
            device: デバイス名 ("cuda" or "cpu")

        Returns:
            int: デバイスID (CUDA: 0, CPU: -1)
        """
        return 0 if device == "cuda" else -1


class TranscriptionEngine(BaseTranscriptionEngine):
    """kotoba-whisper v2.2を使用した文字起こしエンジン"""

    def __init__(self, model_name: Optional[str] = None):
        """
        初期化

        Args:
            model_name: 使用するモデル名（Noneの場合は設定ファイルから取得）

        Raises:
            ValidationError: モデル名が不正な場合
        """
        # モデル名を設定ファイルから取得（引数が指定されていない場合）
        if model_name is None:
            model_name = config.get("model.whisper.name", default="kotoba-tech/kotoba-whisper-v2.2")

        # モデル名を検証
        try:
            model_name = Validator.validate_model_name(model_name, model_type="whisper")
        except ValidationError as e:
            logger.error(f"Invalid model name: {model_name} - {e}")
            # デフォルト値にフォールバック
            default_model = config.get("model.whisper.name", default="kotoba-tech/kotoba-whisper-v2.2")
            logger.warning(f"Falling back to default model: {default_model}")
            model_name = default_model

        # デバイス設定を取得
        device_config = config.get("model.whisper.device", default="auto")
        device = DeviceSelector.select_device(device_config)
        language = config.get("model.whisper.language", default="ja")

        # 基底クラスの初期化
        super().__init__(model_name, device, language)

        # 一時ファイル追跡（リソースリーク対策）
        self._temp_files: List[str] = []
        atexit.register(self._cleanup_temp_files)

        # 音声前処理の初期化（オプション）
        self.preprocessor = None
        if PREPROCESSOR_AVAILABLE:
            enable_preprocessing = config.get("audio.preprocessing.enabled", default=False)
            if enable_preprocessing:
                self.preprocessor = AudioPreprocessor(
                    noise_reduce=config.get("audio.preprocessing.noise_reduction", default=True),
                    normalize=config.get("audio.preprocessing.normalize", default=True),
                    remove_silence=config.get("audio.preprocessing.remove_silence", default=False)
                )
                logger.info("Audio preprocessing enabled")

        # カスタム語彙の初期化（オプション）
        self.vocabulary = None
        if VOCABULARY_AVAILABLE:
            enable_vocabulary = config.get("vocabulary.enabled", default=False)
            if enable_vocabulary:
                self.vocabulary = CustomVocabulary()
                logger.info(f"Custom vocabulary loaded: {len(self.vocabulary.hotwords)} hotwords")

        logger.info(f"TranscriptionEngine initialized with device: {self.device}, model: {self.model_name}")

    def _load_model_with_device(self, device: str) -> None:
        """
        指定されたデバイスでモデルをロード

        Args:
            device: デバイス名 ("cuda" or "cpu")

        Raises:
            Exception: モデルロード失敗時
        """
        dtype = DeviceSelector.get_torch_dtype(device)
        device_id = DeviceSelector.get_device_id(device)

        # シンプルなdevice引数のみを使用（device_mapは使わない）
        # セキュリティ: trust_remote_code=Falseで安全にモデルをロード
        self.model = pipeline(
            "automatic-speech-recognition",
            model=self.model_name,
            device=device_id,
            torch_dtype=dtype,
            trust_remote_code=False,
        )

        logger.info(f"Model loaded successfully on {device}")

    def load_model(self) -> bool:
        """モデルをロード（自動フォールバック機能付き）"""
        try:
            logger.info(f"Loading model: {self.model_name}")

            try:
                # 設定されたデバイスでロード試行
                self._load_model_with_device(self.device)
            except Exception as cuda_error:
                # CUDAで失敗した場合はCPUにフォールバック
                if self.device == "cuda":
                    logger.warning(f"CUDA model load failed: {cuda_error}")
                    logger.info("Falling back to CPU mode...")
                    self.device = "cpu"
                    self._load_model_with_device(self.device)
                    logger.info("Model loaded successfully on CPU (fallback)")
                else:
                    raise

            self.is_loaded = True
            return True

        except ModelLoadError:
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ModelLoadError(f"Failed to load model '{self.model_name}': {e}") from e

    def _cleanup_temp_files(self) -> None:
        """
        一時ファイルをクリーンアップ（リソースリーク対策）
        積極的なクリーンアップで一時ファイルの蓄積を防止
        """
        import tempfile
        import glob
        import time

        # 登録された一時ファイルのクリーンアップ
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_file}: {e}")
        self._temp_files.clear()

        # 追加: システム一時フォルダ内の古い音声一時ファイルをクリーンアップ
        try:
            temp_dir = tempfile.gettempdir()
            # 1日以上古い一時音声ファイルを削除
            current_time = time.time()
            day_in_seconds = 86400

            for pattern in ['tmp*.wav', 'tmp*.mp3', 'preprocessed_*.wav']:
                for temp_file in glob.glob(os.path.join(temp_dir, pattern)):
                    try:
                        file_age = current_time - os.path.getmtime(temp_file)
                        if file_age > day_in_seconds:
                            os.unlink(temp_file)
                            logger.debug(f"Cleaned up old temp file: {temp_file}")
                    except Exception as e:
                        logger.debug(f"Failed to cleanup old temp file {temp_file}: {e}")
        except Exception as e:
            logger.debug(f"Failed to cleanup system temp files: {e}")

    def transcribe(
        self,
        audio_path: str,
        chunk_length_s: Optional[int] = None,
        add_punctuation: Optional[bool] = None,
        return_timestamps: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        音声ファイルを文字起こし

        Args:
            audio_path: 音声ファイルのパス
            chunk_length_s: チャンク長（秒、Noneの場合は設定ファイルから取得）
            add_punctuation: 句読点を追加するか（現在未使用）
            return_timestamps: タイムスタンプを返すか（Noneの場合は設定ファイルから取得）

        Returns:
            文字起こし結果（text, timestamps等を含む辞書）

        Raises:
            ValidationError: 入力パラメータが不正な場合
            Exception: 文字起こし処理失敗時
        """
        # 設定ファイルからデフォルト値を取得
        if chunk_length_s is None:
            chunk_length_s = config.get("model.whisper.chunk_length_s", default=15)
        if return_timestamps is None:
            return_timestamps = config.get("model.whisper.return_timestamps", default=True)

        # ファイルパスを検証
        try:
            validated_path = Validator.validate_file_path(
                audio_path,
                allowed_extensions=None,  # 全サポート形式を許可
                must_exist=True
            )
            logger.debug(f"File path validated: {validated_path}")
        except ValidationError as e:
            logger.error(f"File validation failed: {e}")
            raise

        # チャンク長を検証
        try:
            chunk_length_s = Validator.validate_chunk_length(chunk_length_s)
        except ValidationError as e:
            logger.error(f"Chunk length validation failed: {e}")
            raise

        if self.model is None:
            self.load_model()

        # 日本語パス対策: ASCII専用の一時パスにコピー
        temp_ascii_path = None
        try:
            # パスに非ASCII文字が含まれているかチェック
            path_str = str(validated_path)
            if not path_str.isascii():
                logger.info("Non-ASCII characters detected in path, creating temporary copy...")
                import tempfile

                # 拡張子を取得
                file_ext = Path(validated_path).suffix

                # 一時ファイルを作成（ASCII専用パス）
                temp_fd, temp_ascii_path = tempfile.mkstemp(suffix=file_ext, prefix="transcribe_")

                # バイナリモードで完全コピー（メタデータも含む）
                with open(validated_path, 'rb') as src:
                    with os.fdopen(temp_fd, 'wb') as dst:
                        # 大きなファイルにも対応するためチャンク単位でコピー
                        chunk_size = 1024 * 1024  # 1MB
                        while True:
                            chunk = src.read(chunk_size)
                            if not chunk:
                                break
                            dst.write(chunk)

                logger.info(f"Temporary ASCII path created: {temp_ascii_path}")

                # 一時ファイルを追跡リストに追加
                self._temp_files.append(temp_ascii_path)

                # 処理対象を一時ファイルに変更
                validated_path = Path(temp_ascii_path)
        except Exception as e:
            logger.warning(f"Failed to create ASCII path copy: {e}, using original path")
            if temp_ascii_path and os.path.exists(temp_ascii_path):
                try:
                    os.unlink(temp_ascii_path)
                except OSError:
                    pass

        # 音声前処理を適用（有効な場合）
        processed_audio_path = validated_path
        if self.preprocessor is not None:
            try:
                logger.info("Applying audio preprocessing...")
                processed_audio_path = self.preprocessor.preprocess(str(validated_path))
                # 一時ファイルを追跡リストに追加
                self._temp_files.append(str(processed_audio_path))
                logger.info(f"Preprocessing completed: {processed_audio_path}")
            except Exception as e:
                logger.warning(f"Preprocessing failed, using original audio: {e}")
                processed_audio_path = validated_path

        try:
            logger.info(f"Transcribing audio: {processed_audio_path}")
            # 設定ファイルから言語とタスクを取得
            language = config.get("model.whisper.language", default="ja")
            task = config.get("model.whisper.task", default="transcribe")

            # generate_kwargsを構築
            generate_kwargs = {
                "language": language,
                "task": task
            }

            # ホットワード（初期プロンプト）を追加（有効な場合）
            if self.vocabulary is not None:
                prompt = self.vocabulary.get_whisper_prompt()
                if prompt:
                    generate_kwargs["initial_prompt"] = prompt
                    logger.info(f"Using hotwords prompt: {prompt[:100]}...")

            result = self.model(
                str(processed_audio_path),  # Pathオブジェクトを文字列に変換
                chunk_length_s=chunk_length_s,
                return_timestamps=return_timestamps,
                generate_kwargs=generate_kwargs
            )

            # 後処理: カスタム語彙の置換を適用
            if self.vocabulary is not None:
                original_text = result.get("text", "")
                corrected_text = self.vocabulary.apply_replacements(original_text)
                if corrected_text != original_text:
                    result["text"] = corrected_text
                    logger.info("Applied vocabulary replacements")

            logger.info("Transcription completed successfully")
            return result

        except TranscriptionFailedError:
            raise
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise TranscriptionFailedError(f"Transcription failed for '{audio_path}': {e}") from e

        finally:
            # CUDAメモリキャッシュをクリア（メモリリーク防止）
            if self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("CUDA cache cleared")

            # 一時ファイルの削除（すべての一時ファイルをクリーンアップ）
            # 前処理で作成された一時ファイル
            if processed_audio_path != validated_path and str(processed_audio_path) in self._temp_files:
                try:
                    Path(processed_audio_path).unlink(missing_ok=True)
                    self._temp_files.remove(str(processed_audio_path))
                    logger.debug(f"Cleaned up temporary file: {processed_audio_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")

            # ASCII専用パスの一時ファイル
            if temp_ascii_path and temp_ascii_path in self._temp_files:
                try:
                    Path(temp_ascii_path).unlink(missing_ok=True)
                    self._temp_files.remove(temp_ascii_path)
                    logger.debug(f"Cleaned up ASCII temporary file: {temp_ascii_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete ASCII temporary file: {e}")

    def is_available(self) -> bool:
        """エンジンが利用可能かチェック"""
        return self.is_loaded or self.model is not None


# テストファイルとの後方互換性エイリアス
KotobaTranscriptionEngine = TranscriptionEngine


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    engine = TranscriptionEngine()
    print(f"Device: {engine.device}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    # モデルロードテスト
    try:
        engine.load_model()
        print("Model loaded successfully!")
    except Exception as e:
        print(f"Failed to load model: {e}")
