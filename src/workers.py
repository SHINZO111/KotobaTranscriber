"""
KotobaTranscriber - 共有ワーカー・定数モジュール
TranscriptionWorker, BatchTranscriptionWorker, SharedConstants を提供
main.py と monitor_app.py の両方から使用される
"""

import os
import sys
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal

from transcription_engine import TranscriptionEngine
from text_formatter import TextFormatter
from speaker_diarization_free import FreeSpeakerDiarizer
from validators import Validator, ValidationError
from exceptions import (
    FileProcessingError,
    AudioFormatError,
    ModelLoadError,
    TranscriptionFailedError,
    InsufficientMemoryError
)

logger = logging.getLogger(__name__)


def _normalize_segments(result: dict) -> list:
    """エンジン出力のセグメントを正規化（chunks/segments/timestampタプル対応）"""
    segments = result.get("chunks", result.get("segments", []))
    normalized = []
    for seg in segments:
        if "timestamp" in seg and isinstance(seg["timestamp"], (list, tuple)):
            ts = seg["timestamp"]
            normalized.append({
                "text": seg.get("text", ""),
                "start": ts[0] if len(ts) > 0 else 0,
                "end": ts[1] if len(ts) > 1 else 0,
            })
        elif "start" in seg:
            normalized.append(seg)
        else:
            normalized.append({"text": seg.get("text", ""), "start": 0, "end": 0})
    return normalized


class SharedConstants:
    """main.py / monitor_app.py で共有する定数"""
    # 進捗値
    PROGRESS_MODEL_LOAD = 20
    PROGRESS_BEFORE_TRANSCRIBE = 40
    PROGRESS_AFTER_TRANSCRIBE = 70
    PROGRESS_DIARIZATION_START = 75
    PROGRESS_DIARIZATION_END = 85
    PROGRESS_COMPLETE = 100

    # 並列処理数
    BATCH_WORKERS_DEFAULT = 3
    MONITOR_BATCH_WORKERS = 2

    # タイムアウト設定（ミリ秒）
    THREAD_WAIT_TIMEOUT = 10000  # 10秒
    MONITOR_WAIT_TIMEOUT = 5000   # 5秒
    BATCH_WAIT_TIMEOUT = 30000    # 30秒

    # 処理中ファイルTTL（秒）
    PROCESSING_FILES_TTL = 3600  # 1時間

    # ボタンスタイル
    BUTTON_STYLE_NORMAL = "font-size: 12px; padding: 5px; background-color: #4CAF50; color: white; font-weight: bold;"
    BUTTON_STYLE_MONITOR = "font-size: 12px; padding: 5px; background-color: #FF9800; color: white; font-weight: bold;"
    BUTTON_STYLE_STOP = "font-size: 12px; padding: 5px; background-color: #F44336; color: white; font-weight: bold;"

    # ウィンドウサイズ制限（共通）
    WINDOW_MAX_WIDTH = 3840
    WINDOW_MAX_HEIGHT = 2160

    # ステータスメッセージ表示時間（ミリ秒）
    STATUS_MESSAGE_TIMEOUT = 3000  # 3秒
    TRAY_NOTIFICATION_TIMEOUT = 2000  # 2秒（トレイ通知用）
    ERROR_NOTIFICATION_TIMEOUT = 5000  # 5秒（エラー通知用）

    # サポートする音声/動画ファイル拡張子
    SUPPORTED_EXTENSIONS = (
        '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma', '.opus', '.amr',
        '.mp4', '.avi', '.mov', '.mkv', '.3gp', '.webm',
    )

    # 拡張子セット（folder_monitor / enhanced_folder_monitor 共通）
    AUDIO_EXTENSIONS = set(SUPPORTED_EXTENSIONS)

    # QFileDialog 用フィルタ文字列
    AUDIO_FILE_FILTER = (
        "Audio Files ("
        + " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
        + ");;All Files (*)"
    )


def stop_worker(worker, name: str, timeout: int = 10000,
                cancel: bool = False, stop: bool = False):
    """ワーカースレッドを安全に停止する共通関数"""
    if not worker or not worker.isRunning():
        return
    logger.info(f"Stopping {name}...")
    if cancel and hasattr(worker, 'cancel'):
        worker.cancel()
    elif stop and hasattr(worker, 'stop'):
        worker.stop()
    else:
        worker.quit()
    if not worker.wait(timeout):
        logger.warning(f"{name} did not finish within timeout, terminating...")
        worker.terminate()
        if not worker.wait(5000):
            logger.error(f"{name} failed to terminate within 5s")


# ---------------------------------------------------------------------------
# Worker Signal Naming Convention
# ---------------------------------------------------------------------------
# TranscriptionWorker (単一ファイル):
#   progress(int)        - 進捗パーセンテージ (0-100)
#   finished(str)        - 完了シグナル (結果テキスト)
#   error(str)           - エラーシグナル (エラーメッセージ)
#
# BatchTranscriptionWorker (バッチ):
#   progress(int,int,str)  - 進捗 (完了数, 総数, ファイル名)
#   file_finished(str,str,bool) - 個別ファイル完了 (パス, テキスト, 成功)
#   all_finished(int,int)  - 全完了 (成功数, 失敗数)
#   error(str)             - エラーシグナル (エラーメッセージ)
#
# シグナル名の違い (finished vs all_finished) は意図的な設計です。
# 単一ワーカーは結果テキストを直接返し、バッチワーカーは統計を返します。
# ---------------------------------------------------------------------------


class BatchTranscriptionWorker(QThread):
    """複数ファイルの並列文字起こし処理"""
    progress = Signal(int, int, str)  # (完了数, 総数, ファイル名)
    file_finished = Signal(str, str, bool)  # (ファイルパス, 結果テキスト, 成功/失敗)
    all_finished = Signal(int, int)  # (成功数, 失敗数)
    error = Signal(str)

    def __init__(self, audio_paths: list, enable_diarization: bool = False,
                 max_workers: int = 3, formatter=None,
                 use_llm_correction: bool = False):
        super().__init__()
        self.audio_paths = audio_paths
        self.enable_diarization = enable_diarization
        self.max_workers = max_workers
        self.formatter = formatter
        self.use_llm_correction = use_llm_correction
        self.completed = 0
        self.success_count = 0
        self.failed_count = 0
        self.lock = threading.Lock()
        self._cancelled = False  # キャンセルフラグ
        self._executor = None  # ThreadPoolExecutor参照保持

        # 共有TranscriptionEngineインスタンス（並列処理での再利用）
        self._shared_engine = None
        self._engine_lock = threading.Lock()  # エンジン使用の排他制御

    def cancel(self):
        """バッチ処理をキャンセル"""
        logger.info("Batch processing cancellation requested")
        self._cancelled = True
        # ThreadPoolExecutorのシャットダウン（実行中のタスクは完了を待つ）
        if self._executor:
            self._executor.shutdown(wait=False)

    def process_single_file(self, audio_path: str):
        """単一ファイルを処理"""
        # キャンセルチェック
        if self._cancelled:
            return audio_path, "処理がキャンセルされました", False

        try:
            logger.info(f"Processing file: {audio_path}")

            # Validate file path first
            try:
                validated_path = Validator.validate_file_path(
                    audio_path,
                    must_exist=True
                )
            except ValidationError as e:
                error_msg = f"ファイルパスが不正です: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e

            # Load transcription engine (shared instance with locking)
            try:
                # エンジンロックを取得（1つのファイルのみが同時にモデルを使用）
                with self._engine_lock:
                    # 共有エンジンが未初期化の場合はロード
                    if self._shared_engine is None:
                        logger.info("Initializing shared transcription engine...")
                        self._shared_engine = TranscriptionEngine()
                        self._shared_engine.load_model()
                        logger.info("Shared transcription engine loaded successfully")

                    # 文字起こし実行（ロック内で実行して並列実行を防ぐ）
                    result = self._shared_engine.transcribe(str(validated_path), return_timestamps=True)
                    text = result.get("text", "")
            except ModelLoadError as e:
                error_msg = f"モデルのロードに失敗しました: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except TranscriptionFailedError as e:
                error_msg = f"文字起こしに失敗しました: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except FileNotFoundError as e:
                error_msg = f"ファイルが見つかりません: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except PermissionError as e:
                error_msg = f"ファイルへのアクセス権限がありません: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except MemoryError as e:
                error_msg = f"メモリ不足です: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise InsufficientMemoryError(message=error_msg) from e
            except (IOError, OSError) as e:
                error_msg = f"ファイル読み込みエラー: {audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except ValueError as e:
                error_msg = f"音声フォーマットエラー: {audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                raise AudioFormatError(error_msg) from e
            except Exception as e:
                error_msg = f"予期しないエラー ({type(e).__name__}): {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e

            # Optional speaker diarization (failure is non-critical)
            if self.enable_diarization:
                try:
                    logger.debug(f"Applying speaker diarization to '{audio_path}'")
                    diarizer = FreeSpeakerDiarizer()
                    diar_segments = diarizer.diarize(str(validated_path))
                    trans_segments = _normalize_segments(result)
                    text = diarizer.format_with_speakers(trans_segments, diar_segments)
                    logger.info(f"Speaker diarization completed for '{audio_path}'")
                except ImportError as e:
                    logger.warning(
                        f"Speaker diarization library not available for '{audio_path}': {e}",
                        exc_info=False
                    )
                except (IOError, OSError) as e:
                    logger.warning(
                        f"I/O error during diarization for '{audio_path}': {e}",
                        exc_info=True
                    )
                except Exception as e:
                    logger.warning(
                        f"Speaker diarization failed for '{audio_path}': {type(e).__name__} - {e}",
                        exc_info=True
                    )
                    # Continue with non-diarized text

            # Text formatting（バッチ処理では常にルールベース句読点を使用）
            try:
                if self.formatter:
                    formatted_text = self.formatter.format_all(
                        text,
                        remove_fillers=True,
                        add_punctuation=True,  # バッチ処理ではルールベース句読点を使用
                        format_paragraphs=True,  # バッチ処理ではルールベース段落整形を使用
                        clean_repeated=True
                    )
                else:
                    formatted_text = text
            except ValidationError as e:
                logger.warning(f"Text formatting validation error for '{audio_path}': {e}")
                formatted_text = text  # Use unformatted text as fallback
            except Exception as e:
                logger.warning(
                    f"Text formatting failed for '{audio_path}': {type(e).__name__} - {e}",
                    exc_info=True
                )
                formatted_text = text  # Use unformatted text as fallback

            # バッチ処理ではLLM補正をスキップ（速度重視）
            # 単一ファイル処理でのみLLM補正を適用

            # Save output file
            try:
                base_name = os.path.splitext(audio_path)[0]
                output_file = f"{base_name}_文字起こし.txt"

                # Validate output path (path traversal protection)
                validated_output = Validator.validate_file_path(
                    output_file,
                    allowed_extensions=[".txt"],
                    must_exist=False
                )

                with open(str(validated_output), 'w', encoding='utf-8') as f:
                    f.write(formatted_text)

                logger.info(f"Successfully processed '{audio_path}' -> '{output_file}'")
                return audio_path, formatted_text, True

            except ValidationError as e:
                error_msg = f"出力パスが不正です: {audio_path}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e
            except (IOError, OSError, PermissionError) as e:
                error_msg = f"出力ファイルの保存に失敗しました: {audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                raise FileProcessingError(error_msg) from e

        except FileProcessingError as e:
            # Already logged and formatted
            return audio_path, str(e), False
        except InsufficientMemoryError as e:
            error_msg = f"メモリ不足です。ファイルサイズが大きすぎる可能性があります: {audio_path}"
            logger.error(error_msg, exc_info=True)
            return audio_path, error_msg, False
        except AudioFormatError as e:
            # Already logged
            return audio_path, str(e), False
        except Exception as e:
            # Unexpected error - last resort fallback
            error_msg = f"予期しないエラーが発生しました ({type(e).__name__}): {audio_path} - {e}"
            logger.error(error_msg, exc_info=True)
            return audio_path, error_msg, False

    def run(self):
        """並列処理実行"""
        try:
            total = len(self.audio_paths)

            # ThreadPoolExecutorで並列処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self._executor = executor  # 参照を保持（キャンセル用）

                # 全ファイルを投入
                future_to_path = {
                    executor.submit(self.process_single_file, path): path
                    for path in self.audio_paths
                }

                # 完了したものから処理
                for future in as_completed(future_to_path):
                    # キャンセルチェック
                    if self._cancelled:
                        logger.info("Batch processing cancelled by user")
                        break

                    try:
                        audio_path, result_text, success = future.result(timeout=600)  # 10分タイムアウト

                        with self.lock:
                            self.completed += 1
                            if success:
                                self.success_count += 1
                            else:
                                self.failed_count += 1

                        # 進捗通知
                        filename = os.path.basename(audio_path)
                        self.progress.emit(self.completed, total, filename)
                        self.file_finished.emit(audio_path, result_text, success)

                    except Exception as future_error:
                        logger.error(f"Future result error: {future_error}")
                        with self.lock:
                            self.completed += 1
                            self.failed_count += 1

                self._executor = None  # 参照をクリア

            # 全完了通知
            completion_msg = f"Batch processing completed: {self.success_count} success, {self.failed_count} failed"
            if self._cancelled:
                completion_msg += " (cancelled)"
            logger.info(completion_msg)
            self.all_finished.emit(self.success_count, self.failed_count)

        except Exception as e:
            error_msg = f"Batch processing error: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)
        finally:
            self._executor = None  # 確実にクリア
            # 共有エンジンのモデル解放
            try:
                if hasattr(self, '_shared_engine') and self._shared_engine is not None:
                    self._shared_engine.unload_model()
                    self._shared_engine = None
            except Exception as e:
                logger.debug(f"Shared engine unload failed: {e}")


class TranscriptionWorker(QThread):
    """文字起こし処理を別スレッドで実行"""
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, audio_path: str, enable_diarization: bool = False):
        super().__init__()
        self.audio_path = audio_path
        self.engine = TranscriptionEngine()
        self.enable_diarization = enable_diarization
        self.diarizer = None
        self._cancelled = False

        if enable_diarization:
            try:
                from speaker_diarization_free import FreeSpeakerDiarizer
                self.diarizer = FreeSpeakerDiarizer()
            except Exception as e:
                logger.warning(f"Failed to initialize speaker diarization: {e}")

    def cancel(self):
        """文字起こし処理をキャンセル"""
        logger.info("Transcription cancellation requested")
        self._cancelled = True

    def run(self):
        """文字起こし実行"""
        try:
            self.progress.emit(SharedConstants.PROGRESS_MODEL_LOAD)
            logger.info(f"Starting transcription for: {self.audio_path}")

            # モデルロード
            try:
                self.engine.load_model()
                self.progress.emit(SharedConstants.PROGRESS_BEFORE_TRANSCRIBE)
            except ModelLoadError as e:
                error_msg = f"モデルのロードに失敗しました: {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except (IOError, OSError) as e:
                error_msg = f"モデルファイルの読み込みエラー: {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except Exception as e:
                error_msg = f"予期しないモデルロードエラー: {type(e).__name__} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return

            # キャンセルチェック（モデルロード後）
            if self._cancelled:
                logger.info("Transcription cancelled after model load")
                self.error.emit("文字起こしがキャンセルされました")
                return

            # 文字起こし実行
            try:
                result = self.engine.transcribe(self.audio_path, return_timestamps=True)
                self.progress.emit(SharedConstants.PROGRESS_AFTER_TRANSCRIBE)
            except ValidationError as e:
                error_msg = f"ファイルパスが不正です: {self.audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except TranscriptionFailedError as e:
                error_msg = f"文字起こしに失敗しました: {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except FileNotFoundError as e:
                error_msg = f"ファイルが見つかりません: {self.audio_path}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except PermissionError as e:
                error_msg = f"ファイルへのアクセス権限がありません: {self.audio_path}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except (IOError, OSError) as e:
                error_msg = f"ファイル読み込みエラー: {self.audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except MemoryError as e:
                error_msg = f"メモリ不足です。ファイルサイズが大きすぎる可能性があります: {self.audio_path}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except ValueError as e:
                error_msg = f"音声フォーマットエラー: {self.audio_path} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return
            except Exception as e:
                error_msg = f"予期しない文字起こしエラー: {type(e).__name__} - {e}"
                logger.error(error_msg, exc_info=True)
                self.error.emit(error_msg)
                return

            # 結果取得
            text = result.get("text", "")
            if not text:
                logger.warning(f"Transcription returned empty text for: {self.audio_path}")

            # キャンセルチェック（文字起こし後、話者分離前）
            if self._cancelled:
                logger.info("Transcription cancelled before diarization")
                self.error.emit("文字起こしがキャンセルされました")
                return

            # 話者分離が有効な場合（非クリティカル処理）
            if self.enable_diarization and self.diarizer:
                try:
                    logger.info("Running speaker diarization...")
                    self.progress.emit(SharedConstants.PROGRESS_DIARIZATION_START)

                    # 話者分離実行
                    diar_segments = self.diarizer.diarize(self.audio_path)
                    self.progress.emit(SharedConstants.PROGRESS_DIARIZATION_END)

                    # タイムスタンプ付き文字起こしセグメント（エンジン出力を正規化）
                    trans_segments = _normalize_segments(result)

                    # 話者情報を追加
                    text = self.diarizer.format_with_speakers(
                        trans_segments,
                        diar_segments
                    )

                    # 統計情報をログに出力
                    stats = self.diarizer.get_speaker_statistics(diar_segments)
                    logger.info(f"Speaker statistics: {stats}")

                except ImportError as e:
                    logger.warning(
                        f"Speaker diarization library not available: {e}",
                        exc_info=False
                    )
                except (IOError, OSError) as e:
                    logger.warning(
                        f"I/O error during speaker diarization: {e}",
                        exc_info=True
                    )
                except MemoryError as e:
                    logger.warning(
                        f"Memory error during speaker diarization: {e}",
                        exc_info=True
                    )
                except Exception as e:
                    logger.warning(
                        f"Speaker diarization failed: {type(e).__name__} - {e}",
                        exc_info=True
                    )
                    # 話者分離に失敗しても文字起こし結果は返す

            self.progress.emit(SharedConstants.PROGRESS_COMPLETE)
            self.finished.emit(text)
            logger.info(f"Transcription completed successfully for: {self.audio_path}")

        except Exception as e:
            # 最後のフォールバック - 予期しないエラー
            error_msg = f"予期しないエラーが発生しました: {type(e).__name__} - {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)
        finally:
            # モデルリソースの解放
            try:
                if hasattr(self, 'engine') and self.engine is not None:
                    self.engine.unload_model()
            except Exception as e:
                logger.debug(f"Engine unload failed: {e}")
            self.diarizer = None
