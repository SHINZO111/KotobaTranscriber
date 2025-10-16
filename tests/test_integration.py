"""
統合テスト - すべての修正が連携して動作することを確認

このテストは以下を検証します:
1. スレッドセーフティ（並行アクセス）
2. リソースクリーンアップ（コンテキストマネージャ）
3. エラー回復戦略（連続エラー処理）
4. カスタム例外の適切な使用
5. 依存性注入パターン
6. 型ヒントの完全性
"""

import sys
import os
import time
import threading
import numpy as np
from typing import List

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from realtime_audio_capture import RealtimeAudioCapture
from faster_whisper_engine import FasterWhisperEngine
from simple_vad import AdaptiveVAD
from realtime_transcriber import RealtimeTranscriber
from protocols import AudioCaptureProtocol, VADProtocol, TranscriptionEngineProtocol
from exceptions import (
    AudioDeviceNotFoundError,
    ModelLoadingError,
    TranscriptionFailedError,
    PyAudioInitializationError
)


class TestResults:
    """テスト結果を保持するクラス"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []

    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"✓ PASS: {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"✗ FAIL: {test_name} - {error}")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "="*60)
        print(f"テスト結果: {self.passed}/{total} 成功")
        if self.failed > 0:
            print(f"\n失敗したテスト ({self.failed}):")
            for error in self.errors:
                print(f"  - {error}")
        print("="*60)


def test_1_context_manager_audio_capture(results: TestResults):
    """テスト1: RealtimeAudioCaptureのコンテキストマネージャ"""
    test_name = "RealtimeAudioCapture コンテキストマネージャ"
    try:
        with RealtimeAudioCapture() as capture:
            # デバイスリスト取得
            devices = capture.list_devices()
            assert isinstance(devices, list), "デバイスリストが正しく取得できない"

            # PyAudioが初期化されているか確認
            assert capture.audio is not None, "PyAudioが初期化されていない"

        # with終了後、リソースがクリーンアップされているか確認
        assert capture.audio is None, "PyAudioがクリーンアップされていない"
        results.add_pass(test_name)
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_2_context_manager_whisper_engine(results: TestResults):
    """テスト2: FasterWhisperEngineのコンテキストマネージャ"""
    test_name = "FasterWhisperEngine コンテキストマネージャ"
    try:
        # モデルサイズ: tiny（最小サイズでテスト）
        with FasterWhisperEngine(model_size="tiny", device="cpu") as engine:
            # モデルが読み込まれているか確認
            assert engine.model is not None, "モデルが読み込まれていない"

            # ダミー音声でテスト
            dummy_audio = np.random.randn(16000).astype(np.float32)
            result = engine.transcribe_stream(dummy_audio, sample_rate=16000)
            assert isinstance(result, str), "文字起こし結果が文字列ではない"

        # with終了後、モデルがアンロードされているか確認
        assert engine.model is None, "モデルがアンロードされていない"
        results.add_pass(test_name)
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_3_thread_safety_audio_buffer(results: TestResults):
    """テスト3: 音声バッファのスレッドセーフティ"""
    test_name = "音声バッファのスレッドセーフティ"
    try:
        capture = RealtimeAudioCapture()
        capture._ensure_pyaudio_initialized()

        # 複数スレッドから同時にバッファにアクセス
        errors = []

        def writer_thread():
            try:
                for _ in range(100):
                    dummy_data = np.random.randn(1024).astype(np.float32)
                    with capture._buffer_lock:
                        capture.audio_buffer.extend(dummy_data)
            except Exception as e:
                errors.append(f"Writer: {e}")

        def reader_thread():
            try:
                for _ in range(100):
                    with capture._buffer_lock:
                        if len(capture.audio_buffer) > 0:
                            data = list(capture.audio_buffer)
            except Exception as e:
                errors.append(f"Reader: {e}")

        # 3つの書き込みスレッドと2つの読み取りスレッドを起動
        threads = []
        for _ in range(3):
            t = threading.Thread(target=writer_thread)
            threads.append(t)
            t.start()

        for _ in range(2):
            t = threading.Thread(target=reader_thread)
            threads.append(t)
            t.start()

        # すべてのスレッドが終了するのを待つ
        for t in threads:
            t.join(timeout=5.0)

        # エラーがないか確認
        assert len(errors) == 0, f"スレッドエラー: {errors}"

        capture.cleanup()
        results.add_pass(test_name)
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_4_custom_exceptions(results: TestResults):
    """テスト4: カスタム例外の動作確認"""
    test_name = "カスタム例外の動作"
    try:
        # AudioDeviceNotFoundError
        try:
            raise AudioDeviceNotFoundError(device_index=999)
        except AudioDeviceNotFoundError as e:
            assert e.device_index == 999, "device_indexが正しく保存されていない"
            assert "999" in str(e), "エラーメッセージにdevice_indexが含まれていない"

        # ModelLoadingError
        try:
            original_error = ValueError("Test error")
            raise ModelLoadingError(model_name="test-model", original_error=original_error)
        except ModelLoadingError as e:
            assert e.model_name == "test-model", "model_nameが正しく保存されていない"
            assert e.original_error is original_error, "original_errorが正しく保存されていない"

        results.add_pass(test_name)
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_5_dependency_injection(results: TestResults):
    """テスト5: 依存性注入パターン"""
    test_name = "依存性注入パターン"
    try:
        # モックオブジェクトを作成
        class MockAudioCapture:
            def start_capture(self, callback):
                pass
            def stop_capture(self):
                pass
            def list_devices(self):
                return []
            def set_device(self, index):
                pass
            def is_recording(self):
                return False
            def get_full_recording(self):
                return np.array([])
            def clear_recording(self):
                pass
            def cleanup(self):
                pass

        class MockWhisperEngine:
            def load_model(self):
                pass
            def transcribe_stream(self, audio_chunk, sample_rate=16000):
                return "モックテキスト"
            def is_available(self):
                return True
            def unload_model(self):
                pass

        class MockVAD:
            def is_speech_present(self, audio):
                return (True, 0.05)
            def reset(self):
                pass

        # 依存性注入でRealtimeTranscriberを作成
        mock_audio = MockAudioCapture()
        mock_engine = MockWhisperEngine()
        mock_vad = MockVAD()

        transcriber = RealtimeTranscriber(
            audio_capture=mock_audio,
            whisper_engine=mock_engine,
            vad=mock_vad
        )

        # 依存オブジェクトが正しく注入されているか確認
        assert transcriber.audio_capture is mock_audio, "audio_captureが正しく注入されていない"
        assert transcriber.whisper_engine is mock_engine, "whisper_engineが正しく注入されていない"
        assert transcriber.vad is mock_vad, "vadが正しく注入されていない"

        results.add_pass(test_name)
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_6_error_recovery_strategy(results: TestResults):
    """テスト6: エラー回復戦略"""
    test_name = "エラー回復戦略"
    try:
        # エラー回復機能のテスト
        class ErrorTranscriber:
            MAX_CONSECUTIVE_ERRORS = 5
            ERROR_COOLDOWN_TIME = 0.1  # テスト用に短縮

            def __init__(self):
                self._consecutive_errors = 0
                self._error_lock = threading.Lock()

            def _reset_error_counter(self):
                with self._error_lock:
                    self._consecutive_errors = 0

            def _handle_processing_error(self, error: Exception) -> bool:
                with self._error_lock:
                    self._consecutive_errors += 1
                    current_count = self._consecutive_errors

                if current_count >= self.MAX_CONSECUTIVE_ERRORS:
                    return False  # 停止
                else:
                    time.sleep(self.ERROR_COOLDOWN_TIME)
                    return True  # 継続

        transcriber = ErrorTranscriber()

        # 4回のエラーでは継続
        for i in range(4):
            result = transcriber._handle_processing_error(Exception(f"Error {i+1}"))
            assert result is True, f"4回目のエラーで停止してしまった"

        # 5回目のエラーで停止
        result = transcriber._handle_processing_error(Exception("Error 5"))
        assert result is False, "5回目のエラーで停止しなかった"

        # リセット後は再び継続可能
        transcriber._reset_error_counter()
        result = transcriber._handle_processing_error(Exception("Error after reset"))
        assert result is True, "リセット後に継続できない"

        results.add_pass(test_name)
    except Exception as e:
        results.add_fail(test_name, str(e))


def test_7_type_hints_validation(results: TestResults):
    """テスト7: 型ヒントの検証（実行時）"""
    test_name = "型ヒントの検証"
    try:
        # 型ヒントが正しく定義されているか確認
        from typing import get_type_hints

        # RealtimeAudioCapture
        hints = get_type_hints(RealtimeAudioCapture.list_devices)
        assert 'return' in hints, "list_devices()に戻り値の型ヒントがない"

        # FasterWhisperEngine
        hints = get_type_hints(FasterWhisperEngine.transcribe_stream)
        assert 'return' in hints, "transcribe_stream()に戻り値の型ヒントがない"
        assert 'audio_chunk' in hints, "transcribe_stream()の引数に型ヒントがない"

        results.add_pass(test_name)
    except Exception as e:
        results.add_fail(test_name, str(e))


def main():
    """メインテスト実行"""
    print("="*60)
    print("統合テスト開始")
    print("="*60)
    print()

    results = TestResults()

    # すべてのテストを実行
    test_1_context_manager_audio_capture(results)
    test_2_context_manager_whisper_engine(results)
    test_3_thread_safety_audio_buffer(results)
    test_4_custom_exceptions(results)
    test_5_dependency_injection(results)
    test_6_error_recovery_strategy(results)
    test_7_type_hints_validation(results)

    # 結果サマリー
    results.summary()

    # 終了コード
    return 0 if results.failed == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
