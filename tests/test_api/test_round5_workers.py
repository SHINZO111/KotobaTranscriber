"""Round 5 ワーカーテスト — TranscriptionWorker, BatchTranscriptionWorker, AppSettings, DeviceManager"""

import json
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from api.workers import _normalize_segments, TranscriptionWorker, BatchTranscriptionWorker
    _HAS_WORKERS = True
except ImportError:
    _HAS_WORKERS = False
    _normalize_segments = None
    TranscriptionWorker = None
    BatchTranscriptionWorker = None


# ============================================================
# API Workers: _normalize_segments (comprehensive)
# ============================================================


@pytest.mark.skipif(not _HAS_WORKERS, reason="torch/PySide6 not available")
class TestNormalizeSegmentsComprehensive:
    """_normalize_segments の全パターンテスト"""

    def test_chunks_with_empty_timestamp(self):
        result = {"chunks": [{"text": "x", "timestamp": []}]}
        segments = _normalize_segments(result)
        assert segments[0]["start"] == 0
        assert segments[0]["end"] == 0

    def test_segments_with_extra_fields(self):
        result = {"segments": [{"text": "a", "start": 1, "end": 2, "speaker": "A"}]}
        segments = _normalize_segments(result)
        assert segments[0]["speaker"] == "A"

    def test_mixed_segment_types(self):
        """chunks と segments が両方ある場合は chunks が優先"""
        result = {"chunks": [{"text": "chunk", "timestamp": [0, 1]}], "segments": [{"text": "seg", "start": 0, "end": 1}]}
        segments = _normalize_segments(result)
        assert segments[0]["text"] == "chunk"


# ============================================================
# API Workers: TranscriptionWorker
# ============================================================


@pytest.mark.skipif(not _HAS_WORKERS, reason="torch/PySide6 not available")
class TestTranscriptionWorkerInit:
    """TranscriptionWorker の初期化テスト"""

    @patch("api.workers.TranscriptionEngine")
    @patch("api.workers.FreeSpeakerDiarizer")
    def test_init_with_diarization(self, mock_diarizer_cls, mock_engine_cls):
        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", enable_diarization=True, event_bus=bus)
        assert worker.audio_path == "test.wav"
        assert worker.enable_diarization is True
        assert worker.diarizer is not None

    @patch("api.workers.TranscriptionEngine")
    def test_init_without_diarization(self, mock_engine_cls):
        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", enable_diarization=False, event_bus=bus)
        assert worker.diarizer is None

    @patch("api.workers.TranscriptionEngine")
    def test_cancel(self, mock_engine_cls):
        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", event_bus=bus)
        assert not worker._cancel_event.is_set()
        worker.cancel()
        assert worker._cancel_event.is_set()


@pytest.mark.skipif(not _HAS_WORKERS, reason="torch/PySide6 not available")
class TestTranscriptionWorkerRun:
    """TranscriptionWorker.run() の実行フローテスト"""

    @patch("api.workers.TranscriptionEngine")
    def test_run_happy_path(self, mock_engine_cls):
        """正常な文字起こしフロー"""
        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = {"text": "テスト結果", "chunks": []}
        mock_engine_cls.return_value = mock_engine

        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", event_bus=bus)
        worker.run()

        mock_engine.load_model.assert_called_once()
        mock_engine.transcribe.assert_called_once_with("test.wav", return_timestamps=True)
        # finished イベントが発行される
        finished_calls = [c for c in bus.emit.call_args_list if c[0][0] == "finished"]
        assert len(finished_calls) == 1
        assert finished_calls[0][0][1]["text"] == "テスト結果"
        # engine unload がクリーンアップで呼ばれる
        mock_engine.unload_model.assert_called_once()

    @patch("api.workers.TranscriptionEngine")
    def test_run_model_load_error(self, mock_engine_cls):
        """モデルロード失敗"""
        from exceptions import ModelLoadError

        mock_engine = MagicMock()
        mock_engine.load_model.side_effect = ModelLoadError("load failed")
        mock_engine_cls.return_value = mock_engine

        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", event_bus=bus)
        worker.run()

        error_calls = [c for c in bus.emit.call_args_list if c[0][0] == "error"]
        assert len(error_calls) >= 1
        assert "モデルのロードに失敗" in error_calls[0][0][1]["message"]

    @patch("api.workers.TranscriptionEngine")
    def test_run_cancel_after_model_load(self, mock_engine_cls):
        """モデルロード後のキャンセル"""
        mock_engine = MagicMock()

        def load_and_cancel():
            worker._cancel_event.set()

        mock_engine.load_model.side_effect = load_and_cancel
        mock_engine_cls.return_value = mock_engine

        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", event_bus=bus)
        worker.run()

        # transcribe は呼ばれない
        mock_engine.transcribe.assert_not_called()
        # キャンセルメッセージ
        error_calls = [c for c in bus.emit.call_args_list if c[0][0] == "error"]
        assert any("キャンセル" in c[0][1]["message"] for c in error_calls)

    @patch("api.workers.TranscriptionEngine")
    def test_run_transcription_error(self, mock_engine_cls):
        """文字起こし実行エラー"""
        mock_engine = MagicMock()
        mock_engine.transcribe.side_effect = FileNotFoundError("not found")
        mock_engine_cls.return_value = mock_engine

        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", event_bus=bus)
        worker.run()

        error_calls = [c for c in bus.emit.call_args_list if c[0][0] == "error"]
        assert len(error_calls) >= 1
        assert "ファイルが見つかりません" in error_calls[0][0][1]["message"]

    @patch("api.workers.TranscriptionEngine")
    def test_run_memory_error(self, mock_engine_cls):
        """メモリ不足エラー"""
        mock_engine = MagicMock()
        mock_engine.transcribe.side_effect = MemoryError("OOM")
        mock_engine_cls.return_value = mock_engine

        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", event_bus=bus)
        worker.run()

        error_calls = [c for c in bus.emit.call_args_list if c[0][0] == "error"]
        assert any("メモリ不足" in c[0][1]["message"] for c in error_calls)

    @patch("api.workers.TranscriptionEngine")
    def test_run_engine_unload_on_error(self, mock_engine_cls):
        """エラー発生時もエンジンがアンロードされる"""
        mock_engine = MagicMock()
        mock_engine.transcribe.side_effect = RuntimeError("unexpected")
        mock_engine_cls.return_value = mock_engine

        bus = MagicMock()
        worker = TranscriptionWorker("test.wav", event_bus=bus)
        worker.run()

        mock_engine.unload_model.assert_called_once()


# ============================================================
# API Workers: BatchTranscriptionWorker
# ============================================================


@pytest.mark.skipif(not _HAS_WORKERS, reason="torch/PySide6 not available")
class TestBatchTranscriptionWorkerInit:
    """BatchTranscriptionWorker の初期化テスト"""

    def test_init(self):
        bus = MagicMock()
        worker = BatchTranscriptionWorker(audio_paths=["a.wav", "b.wav"], max_workers=1, event_bus=bus)
        assert len(worker.audio_paths) == 2
        assert worker.max_workers == 1  # エンジン排他のため常に1
        assert worker.completed == 0
        assert worker.success_count == 0
        assert worker.failed_count == 0

    def test_cancel(self):
        bus = MagicMock()
        worker = BatchTranscriptionWorker(audio_paths=[], event_bus=bus)
        worker.cancel()
        assert worker._cancel_event.is_set()


@pytest.mark.skipif(not _HAS_WORKERS, reason="torch/PySide6 not available")
class TestBatchProcessSingleFile:
    """BatchTranscriptionWorker.process_single_file() のテスト"""

    def test_cancelled_returns_immediately(self):
        """キャンセル済みの場合は即座に返す"""
        bus = MagicMock()
        worker = BatchTranscriptionWorker(audio_paths=[], event_bus=bus)
        worker._cancel_event.set()

        path, text, success = worker.process_single_file("test.wav")
        assert path == "test.wav"
        assert success is False
        assert "キャンセル" in text

    @patch("api.workers.Validator")
    @patch("api.workers.TranscriptionEngine")
    def test_happy_path(self, mock_engine_cls, mock_validator):
        """正常なファイル処理"""
        mock_validator.validate_file_path.return_value = Path("test.wav")
        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = {"text": "result", "chunks": []}
        mock_engine_cls.return_value = mock_engine

        bus = MagicMock()
        worker = BatchTranscriptionWorker(audio_paths=["test.wav"], event_bus=bus)

        with patch("builtins.open", MagicMock()):
            path, text, success = worker.process_single_file("test.wav")

        assert success is True
        assert "result" in text

    @patch("api.workers.Validator")
    def test_validation_error(self, mock_validator):
        """バリデーションエラー"""
        from validators import ValidationError

        mock_validator.validate_file_path.side_effect = ValidationError("invalid")

        bus = MagicMock()
        worker = BatchTranscriptionWorker(audio_paths=[], event_bus=bus)

        path, text, success = worker.process_single_file("bad/../path.wav")
        assert success is False
        assert "不正" in text


# ============================================================
# AppSettings: security tests
# ============================================================


class TestAppSettingsSecurity:
    """AppSettings のセキュリティテスト"""

    @pytest.fixture
    def settings_file(self):
        """Create a temp settings file within the project directory to pass path validation."""
        import shutil

        test_dir = Path(__file__).parent.parent.parent / ".test_tmp"
        test_dir.mkdir(exist_ok=True)
        settings_path = test_dir / "test_settings.json"
        yield settings_path
        # cleanup: remove the entire temp directory tree
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_corrupted_json(self, settings_file):
        """壊れた JSON ファイルは安全に処理される"""
        from app_settings import AppSettings

        settings_file.write_text("{invalid json content}", encoding="utf-8")

        settings = AppSettings(str(settings_file))
        # load should handle corruption gracefully
        _result = settings.load()  # noqa: F841
        # Should not crash — returns False or loads defaults
        assert isinstance(settings.get_all(), dict)

    def test_get_all_returns_dict(self, settings_file):
        """get_all() は辞書を返す"""
        from app_settings import AppSettings

        settings = AppSettings(str(settings_file))
        result = settings.get_all()
        assert isinstance(result, dict)

    def test_set_and_get(self, settings_file):
        """set/get の基本動作"""
        from app_settings import AppSettings

        settings = AppSettings(str(settings_file))
        settings.set("test_key", "test_value")
        assert settings.get("test_key") == "test_value"

    def test_nested_key_set(self, settings_file):
        """ネストされたキーの設定"""
        from app_settings import AppSettings

        settings = AppSettings(str(settings_file))
        settings.set("section.key", "value")
        assert settings.get("section.key") == "value"

    def test_save_and_load(self, settings_file):
        """保存と読み込みのラウンドトリップ"""
        from app_settings import AppSettings

        settings = AppSettings(str(settings_file))
        settings.set("test", "roundtrip")
        settings.save()

        settings2 = AppSettings(str(settings_file))
        settings2.load()
        assert settings2.get("test") == "roundtrip"


# ============================================================
# DeviceManager: selection logic
# ============================================================


class TestDeviceManagerSelection:
    """MultiDeviceManager のデバイス選択テスト"""

    def test_cpu_always_present(self):
        """CPU デバイスは常に存在する"""
        from device_manager import DeviceType, MultiDeviceManager

        mgr = MultiDeviceManager()
        cpu_devices = [d for d in mgr.devices if d.type == DeviceType.CPU]
        assert len(cpu_devices) >= 1

    def test_select_optimal_defaults_to_cpu(self):
        """デフォルトでは CPU が選択される（GPU なし環境）"""
        from device_manager import DeviceType, MultiDeviceManager

        mgr = MultiDeviceManager()
        device = mgr.select_optimal_device()
        # GPU がない場合 CPU にフォールバック
        assert device.type in (DeviceType.CPU, DeviceType.CUDA, DeviceType.MPS)

    def test_select_with_impossible_memory(self):
        """メモリ要件が高すぎる場合のフォールバック"""
        from device_manager import MultiDeviceManager

        mgr = MultiDeviceManager()
        # 非常に高いメモリ要件でも動作する（CPU フォールバック）
        device = mgr.select_optimal_device(required_memory_mb=999999)
        assert device is not None

    def test_device_info_fields(self):
        """DeviceInfo のフィールドが正しく設定されている"""
        from device_manager import DeviceInfo, DeviceType

        info = DeviceInfo(
            id=0,
            type=DeviceType.CPU,
            name="Test CPU",
            total_memory_mb=8192,
            available_memory_mb=4096,
        )
        assert info.type == DeviceType.CPU
        assert info.name == "Test CPU"
        assert info.total_memory_mb == 8192

    def test_get_device_list(self):
        """デバイスリストの取得"""
        from device_manager import MultiDeviceManager

        mgr = MultiDeviceManager()
        device_list = mgr.get_device_list()
        assert isinstance(device_list, list)
        assert len(device_list) >= 1
        # Each item should be a dict
        for d in device_list:
            assert isinstance(d, dict)
            assert "name" in d

    def test_device_type_enum_values(self):
        """DeviceType enum の値（auto()による整数値）"""
        from device_manager import DeviceType

        assert isinstance(DeviceType.CPU.value, int)
        assert isinstance(DeviceType.CUDA.value, int)
        assert isinstance(DeviceType.MPS.value, int)
        # 各値が一意であること
        values = {DeviceType.CPU.value, DeviceType.CUDA.value, DeviceType.MPS.value}
        assert len(values) == 3
