"""
pytest設定とフィクスチャ定義

全テストで共通利用するフィクスチャとマーカー設定
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path
from typing import Generator


# ==================== ディレクトリとパスのフィクスチャ ====================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """一時ディレクトリを作成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_audio_file(temp_dir: Path) -> Path:
    """テスト用の一時音声ファイルを作成"""
    audio_path = temp_dir / "test_audio.wav"
    # ダミーの音声データを作成
    import wave
    import struct

    with wave.open(str(audio_path), 'wb') as wav_file:
        wav_file.setnchannels(1)  # モノラル
        wav_file.setsampwidth(2)  # 16bit
        wav_file.setframerate(16000)  # 16kHz

        # 1秒分の440Hz正弦波を生成
        duration = 1.0
        sample_rate = 16000
        num_samples = int(duration * sample_rate)

        for i in range(num_samples):
            value = int(32767 * 0.3 * np.sin(2 * np.pi * 440 * i / sample_rate))
            wav_file.writeframes(struct.pack('<h', value))

    return audio_path


# ==================== 音声データのフィクスチャ ====================

@pytest.fixture
def sample_audio_array() -> np.ndarray:
    """テスト用の音声データ配列を返す（16kHz, 1秒）"""
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    # 440Hz正弦波（A4音）
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)
    return audio.astype(np.float32)


@pytest.fixture
def silence_array() -> np.ndarray:
    """無音データ配列を返す（16kHz, 0.5秒）"""
    sample_rate = 16000
    duration = 0.5
    # 微小なノイズを含む無音
    audio = np.random.normal(0, 0.001, int(sample_rate * duration))
    return audio.astype(np.float32)


@pytest.fixture
def speech_silence_audio() -> np.ndarray:
    """音声→無音のパターンを含む音声データ"""
    sample_rate = 16000

    # 0.5秒無音
    silence1 = np.random.normal(0, 0.005, sample_rate // 2)
    # 1秒音声
    t = np.linspace(0, 1.0, sample_rate)
    speech = 0.3 * np.sin(2 * np.pi * 440 * t)
    # 0.5秒無音
    silence2 = np.random.normal(0, 0.005, sample_rate // 2)

    audio = np.concatenate([silence1, speech, silence2])
    return audio.astype(np.float32)


# ==================== テキストデータのフィクスチャ ====================

@pytest.fixture
def sample_japanese_text() -> str:
    """テスト用の日本語テキスト"""
    return "これはテストです今日はいい天気ですね明日も晴れるといいですね"


@pytest.fixture
def text_with_fillers() -> str:
    """フィラー語を含む日本語テキスト"""
    return "あのーこれはテストですねえーと今日はいい天気ですあのー明日も晴れるといいですね"


@pytest.fixture
def text_with_repeated_words() -> str:
    """繰り返し単語を含むテキスト"""
    return "これは これは テストです テストです"


@pytest.fixture
def long_text_for_paragraphs() -> str:
    """段落整形用の長文テキスト"""
    return (
        "これは最初の文です。"
        "これは2番目の文です。"
        "これは3番目の文です。"
        "これは4番目の文です。"
        "しかしここで状況が変わります。"
        "新しい段落が始まるはずです。"
        "最後の文です。"
    )


# ==================== モックオブジェクトのフィクスチャ ====================

@pytest.fixture
def mock_torch(mocker):
    """torchモジュールのモック"""
    mock = mocker.patch('torch.cuda.is_available')
    mock.return_value = False
    return mock


@pytest.fixture
def mock_pipeline(mocker):
    """transformers.pipelineのモック"""
    mock = mocker.patch('transformers.pipeline')

    # モックのパイプラインが返すダミー結果
    mock_pipe = mocker.MagicMock()
    mock_pipe.return_value = {
        'text': 'これはテスト文字起こしです。',
        'chunks': []
    }
    mock.return_value = mock_pipe

    return mock


# ==================== エラーシミュレーション用フィクスチャ ====================

@pytest.fixture
def raise_value_error():
    """ValueError を発生させるヘルパー"""
    def _raise():
        raise ValueError("Test error")
    return _raise


@pytest.fixture
def raise_runtime_error():
    """RuntimeError を発生させるヘルパー"""
    def _raise():
        raise RuntimeError("Test runtime error")
    return _raise


# ==================== パラメトライズテスト用データ ====================

def pytest_configure(config):
    """pytest設定のカスタマイズ"""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "gpu: mark test as requiring GPU"
    )
    config.addinivalue_line(
        "markers", "audio: mark test as requiring audio files or devices"
    )


# ==================== テスト環境情報の表示 ====================

@pytest.fixture(scope="session", autouse=True)
def print_test_environment():
    """テスト環境情報を表示"""
    import sys
    import platform

    print("\n" + "="*60)
    print("Test Environment Information")
    print("="*60)
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Processor: {platform.processor()}")

    try:
        import torch
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
    except ImportError:
        print("PyTorch: Not installed")

    try:
        import numpy as np
        print(f"NumPy version: {np.__version__}")
    except ImportError:
        print("NumPy: Not installed")

    print("="*60 + "\n")
