"""
TranscriptionLogic ユニットテスト

共通の文字起こしロジック（Qt/API非依存）のテストスイート。
TranscriptionLogic の正常系・異常系をカバー。
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

pytest.importorskip("torch")

from exceptions import (
    AudioFormatError,
    FileProcessingError,
    InsufficientMemoryError,
    ModelLoadError,
    TranscriptionFailedError,
)

# モジュールインポート
from transcription_worker_base import TranscriptionLogic
from validators import ValidationError


@pytest.fixture
def mock_engine():
    """モックTranscriptionEngineを提供"""
    with patch("transcription_worker_base.TranscriptionEngine") as mock_cls:
        engine_instance = MagicMock()
        engine_instance.is_loaded = False
        engine_instance.load_model.return_value = None
        engine_instance.transcribe.return_value = {
            "text": "これはテストの文字起こし結果です。",
            "segments": [
                {"text": "これは", "start": 0.0, "end": 1.0},
                {"text": "テストの", "start": 1.0, "end": 2.0},
                {"text": "文字起こし結果です。", "start": 2.0, "end": 4.0},
            ],
        }
        mock_cls.return_value = engine_instance
        yield engine_instance


@pytest.fixture
def mock_validator():
    """モックValidatorを提供"""
    with patch("transcription_worker_base.Validator") as mock_cls:
        mock_cls.validate_file_path.side_effect = lambda path, must_exist=True: Path(path)
        yield mock_cls


@pytest.fixture
def progress_callback():
    """進捗コールバックのモック"""
    return Mock()


@pytest.fixture
def error_callback():
    """エラーコールバックのモック"""
    return Mock()


class TestTranscriptionLogic:
    """TranscriptionLogic の単体テスト"""

    def test_init(self):
        """初期化が正しく行われること"""
        logic = TranscriptionLogic(
            audio_path="test.wav",
            enable_diarization=True,
            enable_llm_correction=True,
            llm_provider="claude",
        )

        assert logic.audio_path == "test.wav"
        assert logic.enable_diarization is True
        assert logic.enable_llm_correction is True
        assert logic.llm_provider == "claude"

    def test_process_success(self, mock_engine, mock_validator, progress_callback, error_callback):
        """正常系: 文字起こしが成功すること"""
        logic = TranscriptionLogic(
            audio_path="test.wav",
            enable_diarization=False,
            enable_llm_correction=False,
            progress_callback=progress_callback,
            error_callback=error_callback,
        )

        result = logic.process()

        # 結果検証
        assert result is not None
        assert "text" in result
        assert "result" in result
        assert result["text"] == "これはテストの文字起こし結果です。"
        assert "segments" in result["result"]

        # Validatorが呼ばれたことを確認
        mock_validator.validate_file_path.assert_called_once_with("test.wav", must_exist=True)

        # エンジンメソッドが呼ばれたことを確認
        mock_engine.load_model.assert_called_once()
        mock_engine.transcribe.assert_called_once()

        # 進捗コールバックが呼ばれたことを確認
        assert progress_callback.call_count >= 4  # 5, 10, 20, 40, 70, 100
        progress_callback.assert_any_call(5)
        progress_callback.assert_any_call(100)

        # エラーコールバックは呼ばれないこと
        error_callback.assert_not_called()

    def test_process_validation_error(self, mock_engine, mock_validator, error_callback):
        """異常系: ファイルパス検証エラー"""
        mock_validator.validate_file_path.side_effect = ValidationError("Invalid path")

        logic = TranscriptionLogic(
            audio_path="invalid.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        # 結果がNoneであること
        assert result is None

        # エラーコールバックが呼ばれたこと
        error_callback.assert_called_once()
        error_msg = error_callback.call_args[0][0]
        assert "ファイルパスが不正です" in error_msg

        # エンジンメソッドは呼ばれないこと
        mock_engine.load_model.assert_not_called()

    def test_process_model_load_error(self, mock_engine, mock_validator, error_callback):
        """異常系: モデルロードエラー"""
        mock_engine.load_model.side_effect = ModelLoadError("Model load failed")

        logic = TranscriptionLogic(
            audio_path="test.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        # 結果がNoneであること
        assert result is None

        # エラーコールバックが呼ばれたこと
        error_callback.assert_called_once()
        error_msg = error_callback.call_args[0][0]
        assert "モデルのロードに失敗しました" in error_msg

    def test_process_transcription_error(self, mock_engine, mock_validator, error_callback):
        """異常系: 文字起こしエラー"""
        mock_engine.transcribe.side_effect = TranscriptionFailedError("Transcription failed", audio_duration=10.0)

        logic = TranscriptionLogic(
            audio_path="test.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        # 結果がNoneであること
        assert result is None

        # エラーコールバックが呼ばれたこと
        error_callback.assert_called_once()
        error_msg = error_callback.call_args[0][0]
        assert "文字起こし処理中にエラーが発生しました" in error_msg

    def test_process_file_not_found_error(self, mock_engine, mock_validator, error_callback):
        """異常系: ファイル未検出エラー"""
        mock_engine.transcribe.side_effect = FileNotFoundError("File not found")

        logic = TranscriptionLogic(
            audio_path="missing.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        assert result is None
        error_callback.assert_called_once()

    def test_process_permission_error(self, mock_engine, mock_validator, error_callback):
        """異常系: パーミッションエラー"""
        mock_engine.transcribe.side_effect = PermissionError("Access denied")

        logic = TranscriptionLogic(
            audio_path="protected.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        assert result is None
        error_callback.assert_called_once()

    def test_process_memory_error(self, mock_engine, mock_validator, error_callback):
        """異常系: メモリ不足エラー"""
        mock_engine.transcribe.side_effect = MemoryError("Out of memory")

        logic = TranscriptionLogic(
            audio_path="large.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        assert result is None
        error_callback.assert_called_once()

    def test_process_io_error(self, mock_engine, mock_validator, error_callback):
        """異常系: I/Oエラー"""
        mock_engine.transcribe.side_effect = IOError("I/O error")

        logic = TranscriptionLogic(
            audio_path="test.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        assert result is None
        error_callback.assert_called_once()

    def test_process_value_error(self, mock_engine, mock_validator, error_callback):
        """異常系: 音声フォーマットエラー"""
        mock_engine.transcribe.side_effect = ValueError("Invalid audio format")

        logic = TranscriptionLogic(
            audio_path="corrupt.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        assert result is None
        error_callback.assert_called_once()

    def test_process_unexpected_error(self, mock_engine, mock_validator, error_callback):
        """異常系: 予期しないエラー"""
        mock_engine.transcribe.side_effect = RuntimeError("Unexpected error")

        logic = TranscriptionLogic(
            audio_path="test.wav",
            error_callback=error_callback,
        )

        result = logic.process()

        assert result is None
        error_callback.assert_called_once()
        error_msg = error_callback.call_args[0][0]
        assert "予期しないエラーが発生しました" in error_msg

    def test_process_without_callbacks(self, mock_engine, mock_validator):
        """コールバックなしでも動作すること"""
        logic = TranscriptionLogic(
            audio_path="test.wav",
            progress_callback=None,
            error_callback=None,
        )

        # エラーが発生しないこと
        result = logic.process()
        assert result is not None
        assert result["text"] == "これはテストの文字起こし結果です。"

    def test_process_with_diarization(self, mock_engine, mock_validator, progress_callback):
        """話者分離が有効な場合（基本実装ではスキップ）"""
        logic = TranscriptionLogic(
            audio_path="test.wav",
            enable_diarization=True,  # 基本実装では無視される
            progress_callback=progress_callback,
        )

        result = logic.process()

        # 基本実装では話者分離は行わない
        assert result is not None
        assert result["text"] == "これはテストの文字起こし結果です。"

    def test_process_with_llm_correction(self, mock_engine, mock_validator, progress_callback):
        """LLM補正が有効な場合（基本実装ではスキップ）"""
        logic = TranscriptionLogic(
            audio_path="test.wav",
            enable_llm_correction=True,
            llm_provider="claude",
            progress_callback=progress_callback,
        )

        result = logic.process()

        # 基本実装では補正は行わない（サブクラスでオーバーライド可能）
        assert result is not None
        assert result["text"] == "これはテストの文字起こし結果です。"

    def test_progress_callback_called_at_checkpoints(self, mock_engine, mock_validator, progress_callback):
        """進捗コールバックが適切なタイミングで呼ばれること"""
        logic = TranscriptionLogic(
            audio_path="test.wav",
            progress_callback=progress_callback,
        )

        logic.process()

        # 進捗が順序通りに呼ばれることを確認
        calls = [call[0][0] for call in progress_callback.call_args_list]
        assert 5 in calls  # バリデーション後
        assert 10 in calls  # エンジン初期化後
        assert 20 in calls  # モデルロード後
        assert 40 in calls  # 文字起こし前
        assert 70 in calls  # 文字起こし後
        assert 100 in calls  # 完了

    def test_empty_transcription_result(self, mock_engine, mock_validator):
        """文字起こし結果が空の場合でもエラーにならないこと"""
        mock_engine.transcribe.return_value = {"text": ""}

        logic = TranscriptionLogic(audio_path="silent.wav")
        result = logic.process()

        # 空文字列が返ること
        assert result is not None
        assert result["text"] == ""

    def test_transcription_result_without_text_key(self, mock_engine, mock_validator):
        """textキーがない結果でも処理できること"""
        mock_engine.transcribe.return_value = {"segments": []}

        logic = TranscriptionLogic(audio_path="test.wav")
        result = logic.process()

        # デフォルト値（空文字列）が返ること
        assert result is not None
        assert result["text"] == ""


@pytest.mark.integration
class TestTranscriptionLogicIntegration:
    """TranscriptionLogic の統合テスト（実エンジン使用は想定しない）"""

    def test_full_workflow_with_mocks(self, mock_engine, mock_validator):
        """モック使用の完全なワークフロー"""
        progress_values = []
        error_values = []

        def record_progress(val):
            progress_values.append(val)

        def record_error(msg):
            error_values.append(msg)

        logic = TranscriptionLogic(
            audio_path="test.wav",
            enable_diarization=False,
            enable_llm_correction=False,
            progress_callback=record_progress,
            error_callback=record_error,
        )

        result = logic.process()

        # 成功
        assert result is not None
        assert len(result) > 0

        # 進捗が記録されたこと
        assert len(progress_values) >= 4

        # エラーが記録されていないこと
        assert len(error_values) == 0
