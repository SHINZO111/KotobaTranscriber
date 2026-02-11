"""
Qt-free ワーカーモジュール
threading.Thread + EventBus による TranscriptionWorker / BatchTranscriptionWorker。
FastAPI バックエンドから使用。
"""

import os
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List

from constants import SharedConstants, normalize_segments
from transcription_engine import TranscriptionEngine
from text_formatter import TextFormatter
from speaker_diarization_free import FreeSpeakerDiarizer
from validators import Validator, ValidationError
from exceptions import (
    FileProcessingError,
    AudioFormatError,
    ModelLoadError,
    TranscriptionFailedError,
    InsufficientMemoryError,
)
from api.event_bus import EventBus, get_event_bus
from transcription_worker_base import TranscriptionLogic

logger = logging.getLogger(__name__)

# バッチ処理: 1ファイルあたりのタイムアウト（秒）
BATCH_FILE_TIMEOUT_SECONDS = 600

# 後方互換: 旧名でもアクセス可能
_normalize_segments = normalize_segments


class TranscriptionWorker(threading.Thread):
    """
    単一ファイル文字起こしワーカー（Qt非依存）。
    EventBus 経由で progress / finished / error イベントを発行。
    """

    def __init__(self, audio_path: str, enable_diarization: bool = False,
                 event_bus: Optional[EventBus] = None):
        super().__init__(daemon=True)
        self.audio_path = audio_path
        self.enable_diarization = enable_diarization
        self.diarizer = None
        self._cancel_event = threading.Event()
        self._bus = event_bus or get_event_bus()

        if enable_diarization:
            try:
                self.diarizer = FreeSpeakerDiarizer()
            except Exception as e:
                logger.warning(f"Failed to initialize speaker diarization: {e}")

    def cancel(self):
        """文字起こし処理をキャンセル"""
        logger.info("Transcription cancellation requested")
        self._cancel_event.set()

    def run(self):
        """文字起こし実行"""
        try:
            logger.info(f"Starting transcription for: {self.audio_path}")

            # キャンセルチェック（開始前）
            if self._cancel_event.is_set():
                logger.info("Transcription cancelled before start")
                self._bus.emit("error", {"message": "文字起こしがキャンセルされました"})
                return

            # TranscriptionLogic を使用して共通処理を実行
            logic = TranscriptionLogic(
                audio_path=self.audio_path,
                enable_diarization=False,  # 話者分離は後で個別処理
                progress_callback=self._on_progress,
                error_callback=self._on_error,
            )

            # 文字起こし実行（エンジン準備含む）
            transcription_result = logic.process()

            if transcription_result is None:
                # エラーコールバック経由でエラーが通知済み
                return

            # 結果を展開
            result_text = transcription_result["text"]
            engine_result = transcription_result["result"]

            # キャンセルチェック（文字起こし後、話者分離前）
            if self._cancel_event.is_set():
                self._bus.emit("error", {"message": "文字起こしがキャンセルされました"})
                return

            # 話者分離が有効な場合（非クリティカル処理）
            if self.enable_diarization and self.diarizer:
                result_text = self._apply_diarization(result_text, engine_result)

            # 完了通知
            self._bus.emit("progress", {"value": SharedConstants.PROGRESS_COMPLETE})
            self._bus.emit("finished", {"text": result_text})
            logger.info(f"Transcription completed for: {self.audio_path}")

        except Exception as e:
            logger.error(f"予期しないエラー: {type(e).__name__} - {e}", exc_info=True)
            self._bus.emit("error", {"message": "予期しないエラーが発生しました"})

    def _on_progress(self, percentage: int):
        """進捗コールバック（TranscriptionLogicから呼ばれる）"""
        self._bus.emit("progress", {"value": percentage})

    def _on_error(self, message: str):
        """エラーコールバック（TranscriptionLogicから呼ばれる）"""
        self._bus.emit("error", {"message": message})

    def _apply_diarization(self, text: str, engine_result: dict) -> str:
        """
        話者分離を適用（非クリティカル処理）

        Args:
            text: 文字起こし結果テキスト
            engine_result: エンジンの完全な結果（segments等を含む）

        Returns:
            話者情報が追加されたテキスト（失敗時は元のテキスト）
        """
        try:
            self._bus.emit("progress", {"value": SharedConstants.PROGRESS_DIARIZATION_START})
            diar_segments = self.diarizer.diarize(self.audio_path)
            self._bus.emit("progress", {"value": SharedConstants.PROGRESS_DIARIZATION_END})
            trans_segments = _normalize_segments(engine_result)
            text = self.diarizer.format_with_speakers(trans_segments, diar_segments)
            return text
        except Exception as e:
            logger.warning(f"Speaker diarization failed: {type(e).__name__} - {e}", exc_info=True)
            return text


class BatchTranscriptionWorker(threading.Thread):
    """
    複数ファイル並列文字起こしワーカー（Qt非依存）。
    EventBus 経由で batch_progress / file_finished / all_finished / error イベントを発行。
    """

    def __init__(self, audio_paths: List[str], enable_diarization: bool = False,
                 max_workers: int = 1, formatter=None,
                 use_llm_correction: bool = False,
                 event_bus: Optional[EventBus] = None):
        super().__init__(daemon=True)
        self.audio_paths = audio_paths
        self.enable_diarization = enable_diarization
        # 文字起こしエンジンはスレッドセーフでないため常に直列実行
        self.max_workers = 1
        self.formatter = formatter
        self.use_llm_correction = use_llm_correction
        self.completed = 0
        self.success_count = 0
        self.failed_count = 0
        self.lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._executor = None
        self._executor_lock = threading.RLock()  # TOCTOU 競合防止用ロック
        self._shared_engine = None
        self._engine_lock = threading.Lock()
        self._bus = event_bus or get_event_bus()

    def cancel(self):
        """バッチ処理をキャンセル"""
        logger.info("Batch processing cancellation requested")
        self._cancel_event.set()

        # _executor_lock でアトミックに executor を取得・シャットダウン
        with self._executor_lock:
            executor = self._executor
            if executor:
                executor.shutdown(wait=False)
                logger.debug("Executor shutdown requested")

    def process_single_file(self, audio_path: str):
        """単一ファイルを処理"""
        if self._cancel_event.is_set():
            return audio_path, "処理がキャンセルされました", False

        try:
            logger.info(f"Processing file: {audio_path}")

            try:
                validated_path = Validator.validate_file_path(audio_path, must_exist=True)
            except ValidationError as e:
                raise FileProcessingError(f"ファイルパスが不正です: {audio_path}") from e

            # エンジンロック取得・文字起こし
            try:
                with self._engine_lock:
                    if self._shared_engine is None:
                        self._shared_engine = TranscriptionEngine()
                        self._shared_engine.load_model()
                    result = self._shared_engine.transcribe(str(validated_path), return_timestamps=True)
                    text = result.get("text", "")
            except ModelLoadError as e:
                raise FileProcessingError(f"モデルのロードに失敗しました: {audio_path}") from e
            except TranscriptionFailedError as e:
                raise FileProcessingError(f"文字起こしに失敗しました: {audio_path}") from e
            except FileNotFoundError as e:
                raise FileProcessingError(f"ファイルが見つかりません: {audio_path}") from e
            except PermissionError as e:
                raise FileProcessingError(f"アクセス権限がありません: {audio_path}") from e
            except MemoryError as e:
                raise InsufficientMemoryError(message=f"メモリ不足: {audio_path}") from e
            except (IOError, OSError) as e:
                raise FileProcessingError(f"ファイル読み込みエラー: {audio_path} - {e}") from e
            except ValueError as e:
                raise AudioFormatError(f"音声フォーマットエラー: {audio_path} - {e}") from e
            except Exception as e:
                raise FileProcessingError(f"予期しないエラー ({type(e).__name__}): {audio_path}") from e

            # 話者分離（非クリティカル）
            if self.enable_diarization:
                try:
                    diarizer = FreeSpeakerDiarizer()
                    diar_segments = diarizer.diarize(str(validated_path))
                    trans_segments = _normalize_segments(result)
                    text = diarizer.format_with_speakers(trans_segments, diar_segments)
                except Exception as e:
                    logger.warning(f"Speaker diarization failed for '{audio_path}': {e}", exc_info=True)

            # テキストフォーマット
            try:
                if self.formatter:
                    formatted_text = self.formatter.format_all(
                        text, remove_fillers=True, add_punctuation=True,
                        format_paragraphs=True, clean_repeated=True
                    )
                else:
                    formatted_text = text
            except Exception as e:
                logger.warning(f"Text formatting failed for '{audio_path}': {e}", exc_info=True)
                formatted_text = text

            # 出力ファイル保存（アトミック書き込み）
            try:
                from export.common import atomic_write_text
                base_name = os.path.splitext(audio_path)[0]
                output_file = f"{base_name}_文字起こし.txt"
                validated_output = Validator.validate_file_path(
                    output_file, allowed_extensions=[".txt"], must_exist=False
                )
                atomic_write_text(str(validated_output), formatted_text)
                return audio_path, formatted_text, True
            except ValidationError as e:
                raise FileProcessingError(f"出力パスが不正です: {audio_path}") from e
            except (IOError, OSError, PermissionError) as e:
                raise FileProcessingError(f"出力ファイル保存失敗: {audio_path} - {e}") from e

        except (FileProcessingError, InsufficientMemoryError, AudioFormatError) as e:
            return audio_path, str(e), False
        except Exception as e:
            error_msg = f"予期しないエラー ({type(e).__name__}): {audio_path} - {e}"
            logger.error(error_msg, exc_info=True)
            return audio_path, error_msg, False

    def run(self):
        """並列処理実行"""
        try:
            total = len(self.audio_paths)

            # Executor 作成（ロックで保護）
            with self._executor_lock:
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

            try:
                future_to_path = {
                    self._executor.submit(self.process_single_file, path): path
                    for path in self.audio_paths
                }

                for future in as_completed(future_to_path):
                    if self._cancel_event.is_set():
                        break

                    try:
                        audio_path, result_text, success = future.result(timeout=BATCH_FILE_TIMEOUT_SECONDS)
                        with self.lock:
                            self.completed += 1
                            if success:
                                self.success_count += 1
                            else:
                                self.failed_count += 1
                            completed_snapshot = self.completed

                        filename = os.path.basename(audio_path)
                        self._bus.emit("batch_progress", {
                            "completed": completed_snapshot,
                            "total": total,
                            "filename": filename,
                        })
                        self._bus.emit("file_finished", {
                            "file_path": audio_path,
                            "text": result_text,
                            "success": success,
                        })

                    except Exception as future_error:
                        file_path = future_to_path.get(future, "unknown")
                        logger.error(f"Future result error for {file_path}: {future_error}", exc_info=True)
                        with self.lock:
                            self.completed += 1
                            self.failed_count += 1
                            completed_snapshot = self.completed
                        filename = os.path.basename(file_path) if file_path != "unknown" else "unknown"
                        self._bus.emit("batch_progress", {
                            "completed": completed_snapshot,
                            "total": total,
                            "filename": filename,
                        })
                        self._bus.emit("file_finished", {
                            "file_path": file_path,
                            "text": "処理中にエラーが発生しました",
                            "success": False,
                        })

            finally:
                # Executor シャットダウン（ロックで保護）
                with self._executor_lock:
                    if self._executor:
                        self._executor.shutdown(wait=True)
                        self._executor = None

            self._bus.emit("all_finished", {
                "success_count": self.success_count,
                "failed_count": self.failed_count,
            })

        except Exception as e:
            logger.error(f"Batch processing error: {e}", exc_info=True)
            self._bus.emit("error", {"message": "バッチ処理中にエラーが発生しました"})
        finally:
            # 二重 finally で確実にクリーンアップ
            with self._executor_lock:
                if self._executor:
                    self._executor.shutdown(wait=True)
                    self._executor = None
            try:
                if self._shared_engine is not None:
                    self._shared_engine.unload_model()
                    self._shared_engine = None
            except Exception as e:
                logger.debug(f"Shared engine unload failed: {e}")
