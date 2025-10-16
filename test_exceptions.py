"""
Test script to verify custom exception implementation
Tests all custom exceptions to ensure they work correctly
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from exceptions import (
    RealtimeTranscriptionError,
    AudioDeviceNotFoundError,
    AudioStreamError,
    PyAudioInitializationError,
    InvalidVADThresholdError,
    ModelLoadingError,
    TranscriptionFailedError,
    UnsupportedModelError,
    ResourceNotAvailableError,
    InsufficientMemoryError,
    InvalidConfigurationError,
    is_realtime_transcription_error,
    get_error_category
)


def test_exception_hierarchy():
    """Test exception inheritance and hierarchy"""
    print("Testing exception hierarchy...")

    exceptions_to_test = [
        (AudioDeviceNotFoundError(5), "audio"),
        (AudioStreamError("test", 0), "audio"),
        (PyAudioInitializationError(ValueError("test")), "audio"),
        (InvalidVADThresholdError(1.5, (0.0, 1.0)), "vad"),
        (ModelLoadingError("base", ValueError("test")), "transcription"),
        (TranscriptionFailedError("test", 5.0), "transcription"),
        (UnsupportedModelError("huge", ["tiny", "base"]), "transcription"),
        (ResourceNotAvailableError("GPU"), "resource"),
        (InsufficientMemoryError(2048, 512), "resource"),
        (InvalidConfigurationError("threshold", 1.5, "out of range"), "configuration"),
    ]

    for exception, expected_category in exceptions_to_test:
        # Test inheritance
        assert isinstance(exception, RealtimeTranscriptionError), \
            f"{exception.__class__.__name__} should inherit from RealtimeTranscriptionError"

        # Test utility functions
        assert is_realtime_transcription_error(exception), \
            f"is_realtime_transcription_error should return True for {exception.__class__.__name__}"

        assert get_error_category(exception) == expected_category, \
            f"Expected category '{expected_category}' for {exception.__class__.__name__}, got '{get_error_category(exception)}'"

        print(f"  [OK] {exception.__class__.__name__}: {exception}")

    print("  [OK] All hierarchy tests passed!\n")


def test_exception_attributes():
    """Test that exceptions store attributes correctly"""
    print("Testing exception attributes...")

    # AudioDeviceNotFoundError
    e = AudioDeviceNotFoundError(5)
    assert e.device_index == 5
    print(f"  [OK] AudioDeviceNotFoundError stores device_index")

    # AudioStreamError
    e = AudioStreamError("test error", 3)
    assert e.device_index == 3
    assert "test error" in str(e)
    print(f"  [OK] AudioStreamError stores message and device_index")

    # PyAudioInitializationError
    original = ValueError("original error")
    e = PyAudioInitializationError(original)
    assert e.original_error == original
    print(f"  [OK] PyAudioInitializationError stores original_error")

    # InvalidVADThresholdError
    e = InvalidVADThresholdError(1.5, (0.0, 1.0))
    assert e.threshold == 1.5
    assert e.valid_range == (0.0, 1.0)
    print(f"  [OK] InvalidVADThresholdError stores threshold and valid_range")

    # ModelLoadingError
    original = RuntimeError("network error")
    e = ModelLoadingError("base", original)
    assert e.model_name == "base"
    assert e.original_error == original
    print(f"  [OK] ModelLoadingError stores model_name and original_error")

    # TranscriptionFailedError
    e = TranscriptionFailedError("test error", 5.5)
    assert e.audio_duration == 5.5
    print(f"  [OK] TranscriptionFailedError stores audio_duration")

    # UnsupportedModelError
    e = UnsupportedModelError("huge", ["tiny", "base", "small"])
    assert e.model_name == "huge"
    assert e.supported_models == ["tiny", "base", "small"]
    print(f"  [OK] UnsupportedModelError stores model_name and supported_models")

    # InsufficientMemoryError
    e = InsufficientMemoryError(2048, 512)
    assert e.required_mb == 2048
    assert e.available_mb == 512
    print(f"  [OK] InsufficientMemoryError stores memory amounts")

    # InvalidConfigurationError
    e = InvalidConfigurationError("threshold", 1.5, "out of range")
    assert e.param_name == "threshold"
    assert e.param_value == 1.5
    assert e.reason == "out of range"
    print(f"  [OK] InvalidConfigurationError stores parameter details")

    print("  [OK] All attribute tests passed!\n")


def test_exception_chaining():
    """Test that exceptions preserve original error via chaining"""
    print("Testing exception chaining...")

    try:
        original = ValueError("original error")
        raise AudioStreamError("stream error", 0) from original
    except AudioStreamError as e:
        assert e.__cause__ == original
        print(f"  [OK] Exception chaining works correctly")

    print("  [OK] All chaining tests passed!\n")


def test_exception_messages():
    """Test that exception messages are informative"""
    print("Testing exception messages...")

    exceptions = [
        (AudioDeviceNotFoundError(5), "Audio device not found: index=5"),
        (InvalidVADThresholdError(1.5, (0.0, 1.0)), "Invalid VAD threshold: 1.5 (valid range: 0.0 ~ 1.0)"),
        (InsufficientMemoryError(2048, 512), "Insufficient memory: required 2048MB, available 512MB"),
    ]

    for exception, expected_message in exceptions:
        assert str(exception) == expected_message, \
            f"Expected '{expected_message}', got '{str(exception)}'"
        print(f"  [OK] {exception.__class__.__name__}: '{exception}'")

    print("  [OK] All message tests passed!\n")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Custom Exception System Verification")
    print("="*60 + "\n")

    try:
        test_exception_hierarchy()
        test_exception_attributes()
        test_exception_chaining()
        test_exception_messages()

        print("="*60)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("="*60)
        return 0

    except AssertionError as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
