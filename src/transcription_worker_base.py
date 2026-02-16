"""
TranscriptionWorker の共通ロジック

Qt版（workers.py）とAPI版（api/workers.py）で共有する文字起こし処理の基底クラス。
シグナル/EventBus への通知はサブクラスで実装。
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from exceptions import (
    AudioFormatError,
    FileProcessingError,
    InsufficientMemoryError,
    ModelLoadError,
    TranscriptionFailedError,
)
from transcription_engine import TranscriptionEngine
from validators import ValidationError, Validator

logger = logging.getLogger(__name__)

__all__ = ["TranscriptionLogic"]


class TranscriptionLogic:
    """
    文字起こし処理の共通ロジック（Qt/API非依存）

    単一ファイルの文字起こし処理を実行し、結果を返す。
    Qt版（QThread Signal）とAPI版（threading.Thread + EventBus）の両方から使用される。
    """

    def __init__(
        self,
        audio_path: str,
        enable_diarization: bool = False,
        enable_llm_correction: bool = False,
        llm_provider: Optional[str] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初期化

        Args:
            audio_path: 音声ファイルパス
            enable_diarization: 話者分離を有効化（基本実装ではスキップ）
            enable_llm_correction: LLM補正を有効化（基本実装ではスキップ）
            llm_provider: LLMプロバイダ ("local", "claude", "openai")
            progress_callback: 進捗通知コールバック progress_callback(percentage)
            error_callback: エラー通知コールバック error_callback(message)
        """
        self.audio_path = audio_path
        self.enable_diarization = enable_diarization
        self.enable_llm_correction = enable_llm_correction
        self.llm_provider = llm_provider
        self._progress_callback = progress_callback
        self._error_callback = error_callback

    def process(self) -> Optional[Dict[str, Any]]:
        """
        文字起こし処理を実行

        Returns:
            成功時: {"text": str, "result": dict} 形式の辞書
                    - text: 文字起こし結果テキスト
                    - result: エンジンの完全な結果（segments等を含む）
            失敗時: None
        """
        try:
            # バリデーション（5%）
            self._notify_progress(5)
            validated_path = self._validate_audio_path()

            # エンジン初期化（10%）
            self._notify_progress(10)
            engine = TranscriptionEngine()

            # モデルロード（20%）
            self._notify_progress(20)
            self._load_model(engine)

            # 文字起こし実行（40% → 70%）
            self._notify_progress(40)
            result = self._transcribe_audio(engine, validated_path)
            self._notify_progress(70)

            # テキスト抽出
            text = result.get("text", "")

            # LLM補正（オプション、80%）
            if self.enable_llm_correction and text:
                self._notify_progress(80)
                text = self._apply_llm_correction(text)

            # 完了（100%）
            self._notify_progress(100)

            # テキストと完全な結果を返す（話者分離用にセグメント情報を保持）
            return {"text": text, "result": result}

        except ValidationError as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            self._notify_error("ファイルパスが不正です")
            return None
        except ModelLoadError as e:
            logger.error(f"Model load error: {e}", exc_info=True)
            self._notify_error("モデルのロードに失敗しました")
            return None
        except TranscriptionFailedError as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            self._notify_error("文字起こし処理中にエラーが発生しました")
            return None
        except FileNotFoundError:
            logger.error(f"File not found: {self.audio_path}", exc_info=True)
            self._notify_error("ファイルが見つかりません")
            return None
        except PermissionError:
            logger.error(f"Permission error: {self.audio_path}", exc_info=True)
            self._notify_error("ファイルへのアクセス権限がありません")
            return None
        except MemoryError:
            logger.error(f"Memory error: {self.audio_path}", exc_info=True)
            self._notify_error("メモリ不足です")
            return None
        except (IOError, OSError) as e:
            logger.error(f"I/O error: {self.audio_path} - {e}", exc_info=True)
            self._notify_error("ファイル読み込みエラーが発生しました")
            return None
        except ValueError as e:
            logger.error(f"Value error: {self.audio_path} - {e}", exc_info=True)
            self._notify_error("音声フォーマットエラーが発生しました")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__} - {e}", exc_info=True)
            self._notify_error("予期しないエラーが発生しました")
            return None

    def _validate_audio_path(self) -> Path:
        """
        音声ファイルパスをバリデーション

        Returns:
            検証済みのPathオブジェクト

        Raises:
            ValidationError: パスが不正な場合
        """
        return Path(Validator.validate_file_path(self.audio_path, must_exist=True))

    def _load_model(self, engine: TranscriptionEngine) -> None:
        """
        モデルをロード

        Args:
            engine: TranscriptionEngineインスタンス

        Raises:
            ModelLoadError: モデルロードに失敗した場合
            IOError, OSError: ファイル読み込みエラー
        """
        try:
            if not engine.is_loaded:
                engine.load_model()
        except ModelLoadError:
            raise
        except (IOError, OSError) as e:
            logger.error(f"Model file I/O error: {e}", exc_info=True)
            raise ModelLoadError(f"モデルファイルの読み込みエラー: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected model load error: {type(e).__name__} - {e}", exc_info=True)
            raise ModelLoadError(f"予期しないモデルロードエラー: {e}") from e

    def _transcribe_audio(self, engine: TranscriptionEngine, validated_path: Path) -> Dict[str, Any]:
        """
        音声ファイルを文字起こし

        Args:
            engine: TranscriptionEngineインスタンス
            validated_path: 検証済みの音声ファイルパス

        Returns:
            文字起こし結果（text, segments等を含む辞書）

        Raises:
            TranscriptionFailedError: 文字起こしに失敗した場合
            FileNotFoundError: ファイルが見つからない場合
            PermissionError: アクセス権限がない場合
            MemoryError: メモリ不足の場合
            IOError, OSError: I/Oエラー
            ValueError: 音声フォーマットエラー
        """
        return dict(engine.transcribe(str(validated_path), return_timestamps=True))

    def _apply_llm_correction(self, text: str) -> str:
        """
        LLM補正を適用（サブクラスでオーバーライド可能）

        基本実装では何もせず、そのままテキストを返す。
        Qt版・API版の各ワーカーで必要に応じてオーバーライド。

        Args:
            text: 元のテキスト

        Returns:
            補正後のテキスト（基本実装では元のまま）
        """
        return text

    def _notify_progress(self, percentage: int) -> None:
        """
        進捗を通知

        Args:
            percentage: 進捗パーセンテージ（0-100）
        """
        if self._progress_callback:
            self._progress_callback(percentage)

    def _notify_error(self, message: str) -> None:
        """
        エラーを通知

        Args:
            message: エラーメッセージ（ユーザー向け、セキュアな汎用メッセージ）
        """
        if self._error_callback:
            self._error_callback(message)
