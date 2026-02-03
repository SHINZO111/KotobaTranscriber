"""
会議モードのテスト
"""

import unittest
import tempfile
import time
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meeting_mode import (
    MeetingModeRecorder,
    MeetingModeProcessor,
    MeetingSession,
    RecordingSegment,
    get_meeting_recorder,
    get_meeting_processor
)


class TestMeetingModeRecorder(unittest.TestCase):
    """MeetingModeRecorderのテスト"""

    def setUp(self):
        """テスト前のセットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "auto_split_duration": 60,  # 1分（テスト用に短縮）
            "auto_save": {"enabled": True, "interval": 10},
            "speaker_detection": {"enabled": True, "min_speakers": 2, "max_speakers": 5}
        }
        self.recorder = MeetingModeRecorder(self.config)
        self.recorder.output_dir = Path(self.temp_dir)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """初期化テスト"""
        self.assertIsNotNone(self.recorder)
        self.assertFalse(self.recorder.is_recording)
        self.assertEqual(self.recorder.auto_split_duration, 60)

    def test_start_stop_recording(self):
        """録音開始・停止テスト"""
        session_id = self.recorder.start_recording(title="テスト会議")
        self.assertIsNotNone(session_id)
        self.assertTrue(self.recorder.is_recording)
        self.assertIsNotNone(self.recorder.current_session)

        time.sleep(0.5)  # 少し待機

        session = self.recorder.stop_recording()
        self.assertIsNotNone(session)
        self.assertFalse(self.recorder.is_recording)
        self.assertEqual(session.session_id, session_id)

    def test_session_info(self):
        """セッション情報テスト"""
        title = "テスト会議"
        session_id = self.recorder.start_recording(title=title)

        session = self.recorder.current_session
        self.assertEqual(session.title, title)
        self.assertIsNotNone(session.start_time)

        self.recorder.stop_recording()

    def test_recording_status(self):
        """録音状態テスト"""
        status = self.recorder.get_current_status()
        self.assertFalse(status["recording"])

        self.recorder.start_recording()
        status = self.recorder.get_current_status()
        self.assertTrue(status["recording"])
        self.assertIn("session_id", status)
        self.assertIn("total_duration", status)

        self.recorder.stop_recording()


class TestMeetingModeProcessor(unittest.TestCase):
    """MeetingModeProcessorのテスト"""

    def setUp(self):
        """テスト前のセットアップ"""
        self.config = {
            "speaker_detection": {"enabled": True, "min_speakers": 2, "max_speakers": 5}
        }
        self.processor = MeetingModeProcessor(self.config)

    def test_initialization(self):
        """初期化テスト"""
        self.assertIsNotNone(self.processor)
        self.assertEqual(self.processor.speaker_config["min_speakers"], 2)
        self.assertEqual(self.processor.speaker_config["max_speakers"], 5)

    def test_speaker_config(self):
        """話者設定テスト"""
        self.assertTrue(self.processor.speaker_config["enabled"])
        self.assertEqual(self.processor.speaker_config["clustering_method"], "spectral")


class TestMeetingSession(unittest.TestCase):
    """MeetingSessionのテスト"""

    def test_session_creation(self):
        """セッション作成テスト"""
        session = MeetingSession(
            session_id="test_001",
            start_time=time.time(),
            title="テスト会議"
        )
        self.assertEqual(session.session_id, "test_001")
        self.assertEqual(session.title, "テスト会議")

    def test_to_dict(self):
        """辞書変換テスト"""
        session = MeetingSession(
            session_id="test_001",
            start_time=time.time(),
            title="テスト会議"
        )

        # セグメントを追加
        segment = RecordingSegment(
            index=1,
            start_time=time.time(),
            end_time=time.time() + 60,
            file_path="test.wav",
            duration=60.0
        )
        session.segments.append(segment)

        data = session.to_dict()
        self.assertEqual(data["session_id"], "test_001")
        self.assertEqual(data["title"], "テスト会議")
        self.assertEqual(len(data["segments"]), 1)


class TestRecordingSegment(unittest.TestCase):
    """RecordingSegmentのテスト"""

    def test_segment_creation(self):
        """セグメント作成テスト"""
        segment = RecordingSegment(
            index=1,
            start_time=time.time(),
            end_time=time.time() + 60,
            file_path="test.wav",
            duration=60.0
        )
        self.assertEqual(segment.index, 1)
        self.assertEqual(segment.duration, 60.0)


class TestSingleton(unittest.TestCase):
    """シングルトンテスト"""

    def test_get_meeting_recorder(self):
        """レコーダーシングルトンテスト"""
        recorder1 = get_meeting_recorder()
        recorder2 = get_meeting_recorder()
        self.assertIs(recorder1, recorder2)

    def test_get_meeting_processor(self):
        """プロセッサーシングルトンテスト"""
        processor1 = get_meeting_processor()
        processor2 = get_meeting_processor()
        self.assertIs(processor1, processor2)


if __name__ == "__main__":
    unittest.main()
