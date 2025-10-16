"""
プロトコル定義モジュール
依存性注入のためのインターフェース定義
"""

from typing import Protocol, Optional, Callable, List, Dict, Any, Tuple
import numpy as np


class AudioCaptureProtocol(Protocol):
    """
    音声キャプチャのプロトコル

    RealtimeAudioCaptureなどの実装クラスがこのインターフェースに従う
    """

    # プロパティ
    device_index: Optional[int]
    sample_rate: int
    is_recording: bool
    on_audio_chunk: Optional[Callable[[np.ndarray], None]]

    def list_devices(self) -> List[Dict[str, Any]]:
        """
        利用可能な音声デバイス一覧を取得

        Returns:
            デバイス情報のリスト
            各要素: {"index": int, "name": str, "channels": int, "sample_rate": int}
        """
        ...

    def start_capture(self) -> bool:
        """
        音声キャプチャ開始

        Returns:
            成功時True、失敗時False
        """
        ...

    def stop_capture(self) -> bool:
        """
        音声キャプチャ停止

        Returns:
            成功時True、失敗時False
        """
        ...

    def save_recording(self, filepath: str) -> bool:
        """
        録音データをWAVファイルとして保存

        Args:
            filepath: 保存先ファイルパス

        Returns:
            成功時True、失敗時False
        """
        ...

    def clear_recording(self) -> None:
        """録音データをクリア"""
        ...

    def cleanup(self) -> None:
        """リソースのクリーンアップ"""
        ...


class VADProtocol(Protocol):
    """
    VAD (Voice Activity Detection) のプロトコル

    SimpleVAD、AdaptiveVADなどの実装クラスがこのインターフェースに従う
    """

    # プロパティ
    threshold: float
    sample_rate: int

    def is_speech_present(self, audio: np.ndarray) -> Tuple[bool, float]:
        """
        音声が存在するか判定

        Args:
            audio: 音声データ（NumPy配列、float32、-1.0〜1.0）

        Returns:
            (音声存在フラグ, エネルギー値)のタプル
        """
        ...

    def reset(self) -> None:
        """VAD状態をリセット"""
        ...


class TranscriptionEngineProtocol(Protocol):
    """
    文字起こしエンジンのプロトコル

    FasterWhisperEngine、TransformersWhisperEngineなどの実装クラスがこのインターフェースに従う
    """

    # プロパティ
    is_loaded: bool

    def load_model(self) -> bool:
        """
        モデルをロード

        Returns:
            成功時True、失敗時False
        """
        ...

    def transcribe_stream(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        """
        音声チャンクを文字起こし（ストリーミング用）

        Args:
            audio_chunk: 音声データ（NumPy配列、float32、-1.0〜1.0）
            sample_rate: サンプリングレート（Hz）

        Returns:
            文字起こし結果のテキスト（エラー時はNone）
        """
        ...

    def is_available(self) -> bool:
        """
        エンジンが利用可能かチェック

        Returns:
            利用可能ならTrue
        """
        ...

    def unload_model(self) -> None:
        """モデルをアンロード（メモリ解放）"""
        ...


# 型エイリアス
AudioChunkCallback = Callable[[np.ndarray], None]
