"""Round 5 追加テスト — error_recovery, app_settings backup, schemas edge cases"""

import json
import os
import sys
import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


# ============================================================
# ErrorRecoveryManager
# ============================================================

class TestErrorRecoveryManager:
    """ErrorRecoveryManager のテスト"""

    def test_init_creates_log_dir(self, tmp_path):
        """初期化時にログディレクトリを作成"""
        from error_recovery import ErrorRecoveryManager
        log_dir = tmp_path / "test_logs"
        mgr = ErrorRecoveryManager(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_classify_transient_error(self, tmp_path):
        """一時的エラーの分類"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        assert mgr._classify_error(ConnectionError("connection reset")) == 'transient'
        assert mgr._classify_error(TimeoutError("timeout")) == 'transient'

    def test_classify_resource_error(self, tmp_path):
        """リソースエラーの分類"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        assert mgr._classify_error(MemoryError("out of memory")) == 'resource'
        assert mgr._classify_error(FileNotFoundError("not found")) == 'resource'
        assert mgr._classify_error(PermissionError("permission denied")) == 'resource'

    def test_classify_permanent_error(self, tmp_path):
        """恒久的エラーの分類"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        assert mgr._classify_error(ValueError("bad value")) == 'permanent'
        assert mgr._classify_error(TypeError("type error")) == 'permanent'

    def test_handle_error_skip(self, tmp_path):
        """回復不能エラーはスキップ"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        result = mgr.handle_error(ValueError("test"), "test.wav")
        assert result['success'] is False
        assert result['action'] == 'skip'
        assert result['error'] == 'test'

    def test_handle_error_fallback(self, tmp_path):
        """リソースエラーのフォールバック"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        result = mgr.handle_error(
            MemoryError("oom"),
            "test.wav",
            fallback_func=lambda: "fallback_result"
        )
        assert result['success'] is True
        assert result['action'] == 'fallback'
        assert result['result'] == "fallback_result"

    def test_handle_error_retry_success(self, tmp_path):
        """リトライ成功"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))

        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("temp")
            return "ok"

        result = mgr.handle_error(
            ConnectionError("initial"),
            "test.wav",
            retry_func=flaky,
            max_retries=3
        )
        assert result['success'] is True
        assert 'retry_success' in result['action']

    def test_handle_error_retry_all_fail(self, tmp_path):
        """全リトライ失敗"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))

        def always_fail():
            raise ConnectionError("always fails")

        result = mgr.handle_error(
            ConnectionError("initial"),
            "test.wav",
            retry_func=always_fail,
            max_retries=1  # 1回だけリトライ（高速テスト）
        )
        assert result['success'] is False
        assert result['retries'] == 1

    def test_error_logging(self, tmp_path):
        """エラーログの記録"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        mgr.handle_error(ValueError("test_error"), "test.wav")

        assert mgr.error_log_file.exists()
        with open(mgr.error_log_file, 'r') as f:
            line = f.readline()
            record = json.loads(line)
            assert record['error_type'] == 'ValueError'
            assert record['error_message'] == 'test_error'
            assert record['file_path'] == 'test.wav'

    def test_get_error_summary_empty(self, tmp_path):
        """空のサマリー"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        summary = mgr.get_error_summary()
        assert summary['total_errors'] == 0

    def test_get_error_summary_with_errors(self, tmp_path):
        """エラーがある場合のサマリー"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        mgr.handle_error(ValueError("e1"), "a.wav")
        mgr.handle_error(ValueError("e2"), "b.wav")

        summary = mgr.get_error_summary()
        assert summary['total_errors'] == 2
        assert 'ValueError' in summary['error_types']

    def test_clear_logs(self, tmp_path):
        """ログクリア"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))
        mgr.handle_error(ValueError("test"), "test.wav")
        assert mgr.error_log_file.exists()

        mgr.clear_logs()
        assert not mgr.error_log_file.exists()
        assert mgr._error_count == 0

    def test_register_callback(self, tmp_path):
        """コールバック登録と実行"""
        from error_recovery import ErrorRecoveryManager
        mgr = ErrorRecoveryManager(log_dir=str(tmp_path))

        callback_called = []
        mgr.register_callback('permanent', lambda e, fp: callback_called.append((str(e), fp)))

        mgr.handle_error(ValueError("cb_test"), "file.wav")
        assert len(callback_called) == 1
        assert callback_called[0] == ("cb_test", "file.wav")


# ============================================================
# resilient デコレータ
# ============================================================

class TestResilientDecorator:
    """resilient デコレータのテスト"""

    def test_successful_call(self, tmp_path):
        """成功する関数はそのまま返す"""
        from error_recovery import resilient

        @resilient(max_retries=1, log_dir=str(tmp_path))
        def good_func(file_path):
            return "success"

        result = good_func("test.wav")
        assert result == "success"

    def test_failing_call_returns_result(self, tmp_path):
        """失敗する関数は handle_error の結果を返す"""
        from error_recovery import resilient

        @resilient(max_retries=1, fallback_value="default", log_dir=str(tmp_path))
        def bad_func(file_path):
            raise ValueError("fail")

        result = bad_func("test.wav")
        assert isinstance(result, dict)
        assert result['success'] is False


# ============================================================
# ErrorRecord
# ============================================================

class TestErrorRecord:
    """ErrorRecord データクラスのテスト"""

    def test_default_values(self):
        """デフォルト値の確認"""
        from error_recovery import ErrorRecord
        record = ErrorRecord(
            timestamp="2024-01-01T00:00:00",
            file_path="test.wav",
            error_type="ValueError",
            error_message="test"
        )
        assert record.stack_trace is None
        assert record.recovery_action is None
        assert record.recovered is False
        assert record.retry_count == 0

    def test_to_dict(self):
        """asdict 変換"""
        from error_recovery import ErrorRecord
        from dataclasses import asdict
        record = ErrorRecord(
            timestamp="2024-01-01",
            file_path="test.wav",
            error_type="ValueError",
            error_message="msg"
        )
        d = asdict(record)
        assert d['error_type'] == 'ValueError'
        assert d['recovered'] is False


# ============================================================
# Schemas edge cases
# ============================================================

class TestSchemasEdgeCases:
    """API スキーマの境界値テスト"""

    def test_export_request_default_segments(self):
        """ExportRequest のデフォルトセグメント"""
        from api.schemas import ExportRequest
        req = ExportRequest(text="test", output_path="/tmp/out.txt")
        assert req.segments == []
        assert req.include_timestamps is True
        assert req.include_speakers is False
        assert req.format == "txt"

    def test_transcribe_request_defaults(self):
        """TranscribeRequest のデフォルト値"""
        from api.schemas import TranscribeRequest
        req = TranscribeRequest(file_path="/tmp/test.wav")
        assert req.enable_diarization is False
        assert req.remove_fillers is True
        assert req.add_punctuation is True
        assert req.format_paragraphs is True
        assert req.use_llm_correction is False

    def test_batch_transcribe_request(self):
        """BatchTranscribeRequest の検証"""
        from api.schemas import BatchTranscribeRequest
        req = BatchTranscribeRequest(file_paths=["/a.wav", "/b.wav"])
        assert len(req.file_paths) == 2
        assert req.max_workers == 1  # エンジン排他のため常に1

    def test_format_text_request(self):
        """FormatTextRequest のフィールド"""
        from api.schemas import FormatTextRequest
        req = FormatTextRequest(text="テスト")
        assert req.remove_fillers is True
        assert req.add_punctuation is True
        assert req.format_paragraphs is True
        assert req.clean_repeated is True

    def test_diarize_request(self):
        """DiarizeRequest のフィールド"""
        from api.schemas import DiarizeRequest
        req = DiarizeRequest(file_path="/tmp/test.wav")
        assert req.segments == []

    def test_correct_text_request(self):
        """CorrectTextRequest のフィールド"""
        from api.schemas import CorrectTextRequest
        req = CorrectTextRequest(text="テスト")
        assert req.provider == "local"

    def test_message_response(self):
        """MessageResponse の構造"""
        from api.schemas import MessageResponse
        resp = MessageResponse(message="ok")
        assert resp.message == "ok"

    def test_monitor_request(self):
        """MonitorRequest のフィールド"""
        from api.schemas import MonitorRequest
        req = MonitorRequest(folder_path="/tmp/watch")
        assert req.check_interval == 10
        assert req.enable_diarization is False
        assert req.auto_move is False

    def test_realtime_control_request(self):
        """RealtimeControlRequest のフィールド"""
        from api.schemas import RealtimeControlRequest
        req = RealtimeControlRequest()
        assert req.model_size == "base"
        assert req.device == "auto"


# ============================================================
# RecoveryAction enum
# ============================================================

class TestRecoveryAction:
    """RecoveryAction enum のテスト"""

    def test_values(self):
        from error_recovery import RecoveryAction
        assert RecoveryAction.RETRY.value == "retry"
        assert RecoveryAction.SKIP.value == "skip"
        assert RecoveryAction.ABORT.value == "abort"
        assert RecoveryAction.FALLBACK.value == "fallback"
