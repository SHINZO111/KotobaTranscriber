"""constants.py テスト — SharedConstants が workers.py と一致することを確認"""

import sys
import os
import pytest

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from constants import SharedConstants


class TestSharedConstants:
    """SharedConstants テスト"""

    def test_progress_values(self):
        """進捗値が正しい範囲"""
        assert 0 < SharedConstants.PROGRESS_MODEL_LOAD < 100
        assert SharedConstants.PROGRESS_MODEL_LOAD < SharedConstants.PROGRESS_BEFORE_TRANSCRIBE
        assert SharedConstants.PROGRESS_BEFORE_TRANSCRIBE < SharedConstants.PROGRESS_AFTER_TRANSCRIBE
        assert SharedConstants.PROGRESS_AFTER_TRANSCRIBE < SharedConstants.PROGRESS_COMPLETE
        assert SharedConstants.PROGRESS_COMPLETE == 100

    def test_supported_extensions(self):
        """サポートする拡張子"""
        assert '.mp3' in SharedConstants.SUPPORTED_EXTENSIONS
        assert '.wav' in SharedConstants.SUPPORTED_EXTENSIONS
        assert '.m4a' in SharedConstants.SUPPORTED_EXTENSIONS
        assert '.mp4' in SharedConstants.SUPPORTED_EXTENSIONS

    def test_audio_extensions_is_set(self):
        """AUDIO_EXTENSIONS が set であること"""
        assert isinstance(SharedConstants.AUDIO_EXTENSIONS, set)
        assert len(SharedConstants.AUDIO_EXTENSIONS) == len(SharedConstants.SUPPORTED_EXTENSIONS)

    def test_audio_file_filter(self):
        """QFileDialog フィルタ文字列"""
        assert "*.mp3" in SharedConstants.AUDIO_FILE_FILTER
        assert "*.wav" in SharedConstants.AUDIO_FILE_FILTER
        assert "All Files" in SharedConstants.AUDIO_FILE_FILTER

    def test_batch_workers_default(self):
        """バッチワーカーデフォルト数"""
        assert SharedConstants.BATCH_WORKERS_MAX >= 1

    def test_timeout_values(self):
        """タイムアウト値が正の数"""
        assert SharedConstants.THREAD_WAIT_TIMEOUT > 0
        assert SharedConstants.MONITOR_WAIT_TIMEOUT > 0
        assert SharedConstants.BATCH_WAIT_TIMEOUT > 0

    def test_backward_compat_with_workers(self):
        """workers.py からの SharedConstants インポートが動作すること"""
        # workers.py は from constants import SharedConstants を使う
        # 両方のインポートパスで同じクラスが取得できること
        from workers import SharedConstants as WorkersSharedConstants
        assert WorkersSharedConstants.PROGRESS_COMPLETE == SharedConstants.PROGRESS_COMPLETE
        assert WorkersSharedConstants.AUDIO_EXTENSIONS == SharedConstants.AUDIO_EXTENSIONS
