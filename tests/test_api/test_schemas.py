"""Pydantic スキーマテスト"""

import os
import sys

import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from api.schemas import (
        BatchTranscribeRequest,
        BatchTranscribeResponse,
        ConfigModel,
        CorrectTextRequest,
        DiarizeRequest,
        ExportRequest,
        ExportResponse,
        FormatTextRequest,
        HealthResponse,
        MessageResponse,
        ModelInfoResponse,
        MonitorRequest,
        MonitorStatusResponse,
        RealtimeControlRequest,
        RealtimeStatusResponse,
        SettingsModel,
        TranscribeRequest,
        TranscribeResponse,
    )

    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False


@pytest.mark.skipif(not SCHEMAS_AVAILABLE, reason="schemas not importable")
class TestSchemas:
    """Pydantic モデルテスト"""

    def test_transcribe_request_defaults(self):
        """TranscribeRequest デフォルト値"""
        req = TranscribeRequest(file_path="/test/audio.mp3")
        assert req.file_path == "/test/audio.mp3"
        assert req.enable_diarization is False
        assert req.remove_fillers is True
        assert req.add_punctuation is True
        assert req.format_paragraphs is True
        assert req.use_llm_correction is False

    def test_transcribe_response(self):
        """TranscribeResponse"""
        resp = TranscribeResponse(text="テスト", segments=[], duration=1.5)
        assert resp.text == "テスト"
        assert resp.segments == []
        assert resp.duration == 1.5

    def test_batch_request_validation(self):
        """BatchTranscribeRequest バリデーション"""
        req = BatchTranscribeRequest(
            file_paths=["/a.mp3", "/b.mp3"],
            max_workers=1,
        )
        assert len(req.file_paths) == 2
        assert req.max_workers == 1  # エンジン排他のため常に1

    def test_batch_request_max_workers_range(self):
        """max_workers の範囲チェック"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BatchTranscribeRequest(
                file_paths=["/a.mp3"],
                max_workers=0,  # ge=1 に違反
            )

    def test_realtime_request(self):
        """RealtimeControlRequest"""
        req = RealtimeControlRequest()
        assert req.model_size == "base"
        assert req.device == "auto"
        assert req.buffer_duration == 3.0

    def test_monitor_request(self):
        """MonitorRequest"""
        req = MonitorRequest(folder_path="/test/folder")
        assert req.folder_path == "/test/folder"
        assert req.check_interval == 10
        assert req.auto_move is False

    def test_export_request(self):
        """ExportRequest"""
        req = ExportRequest(
            text="テスト",
            output_path="/test/out.txt",
        )
        assert req.format == "txt"
        assert req.include_timestamps is True

    def test_health_response(self):
        """HealthResponse"""
        resp = HealthResponse(engines={"kotoba_whisper": True, "faster_whisper": False})
        assert resp.status == "ok"
        assert resp.engines["kotoba_whisper"] is True

    def test_settings_model_optional(self):
        """SettingsModel の全フィールドが Optional"""
        settings = SettingsModel()
        assert settings.theme is None
        assert settings.language is None

    def test_format_text_request(self):
        """FormatTextRequest"""
        req = FormatTextRequest(text="テスト")
        assert req.remove_fillers is True
        assert req.clean_repeated is True

    def test_correct_text_request(self):
        """CorrectTextRequest"""
        req = CorrectTextRequest(text="テスト", provider="claude")
        assert req.provider == "claude"

    def test_model_info_response(self):
        """ModelInfoResponse"""
        resp = ModelInfoResponse(engine="kotoba_whisper")
        assert resp.is_loaded is False
        assert resp.model_name is None
