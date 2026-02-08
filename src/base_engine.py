"""
ベーストランスクリプションエンジン - Base Transcription Engine

すべての文字起こしエンジンの基底クラス。
共通インターフェースとコンテキストマネージャサポートを提供。
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

__all__ = ['BaseTranscriptionEngine']


class BaseTranscriptionEngine(ABC):
    """
    文字起こしエンジンの抽象基底クラス

    すべての文字起こしエンジンはこのクラスを継承し、
    load_model()とtranscribe()メソッドを実装する必要がある。

    コンテキストマネージャとして使用可能:
        with SomeEngine(model_name="model") as engine:
            result = engine.transcribe(audio_data)
        # 自動的にモデルがアンロードされる
    """

    def __init__(
        self,
        model_name: str,
        device: str = "auto",
        language: str = "ja"
    ):
        """
        初期化

        Args:
            model_name: モデル名またはパス
            device: 実行デバイス ("cpu", "cuda", "auto")
            language: 言語コード
        """
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.language = language
        self.model: Optional[Any] = None
        self.is_loaded: bool = False

        logger.debug(
            f"{self.__class__.__name__} initialized: "
            f"model={model_name}, device={self.device}, language={language}"
        )

    def _resolve_device(self, device: str) -> str:
        """
        デバイスを解決

        Args:
            device: 指定されたデバイス ("auto", "cpu", "cuda")

        Returns:
            解決されたデバイス名
        """
        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except ImportError:
                pass
            return "cpu"
        return device

    @abstractmethod
    def load_model(self) -> bool:
        """
        モデルをロード

        Returns:
            成功時True

        Raises:
            ModelLoadError: モデルのロードに失敗した場合
        """
        pass

    @abstractmethod
    def transcribe(self, audio: Any, **kwargs) -> Dict[str, Any]:
        """
        音声を文字起こし

        Args:
            audio: 音声データ
            **kwargs: 追加パラメータ

        Returns:
            文字起こし結果の辞書
        """
        pass

    def unload_model(self) -> None:
        """
        モデルをアンロードしてメモリを解放
        """
        if self.model is not None:
            try:
                self.model = None
                self.is_loaded = False

                # GPUキャッシュをクリア
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass

                logger.info(f"{self.__class__.__name__}: Model unloaded")

            except Exception as e:
                logger.warning(f"Error during model unload: {e}")
                self.model = None
                self.is_loaded = False

    def __enter__(self) -> 'BaseTranscriptionEngine':
        """
        コンテキストマネージャのエントリ

        Returns:
            self
        """
        try:
            self.load_model()
        except Exception:
            # 部分的にロードされた場合のクリーンアップ
            self.unload_model()
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        コンテキストマネージャの終了

        Args:
            exc_type: 例外タイプ
            exc_val: 例外値
            exc_tb: トレースバック

        Returns:
            False（例外を再送出）
        """
        try:
            self.unload_model()
        except Exception as e:
            # unload_model() の例外で元の例外がマスクされないようにする
            if exc_type is None:
                raise
            logger.warning(f"Error during model unload in __exit__: {e}")
        return False  # 例外を再送出

    def __del__(self):
        """
        デストラクタ - モデルのクリーンアップ
        """
        try:
            self.unload_model()
        except Exception as e:
            # デストラクタでは例外をログに記録するのみ
            try:
                logger.debug(f"Error during cleanup in __del__: {e}")
            except Exception:
                pass  # ログ出力自体が失敗する場合は無視

    def is_available(self) -> bool:
        """
        エンジンが利用可能かどうか

        Returns:
            利用可能な場合True
        """
        return True  # サブクラスでオーバーライド

    def get_model_info(self) -> Dict[str, Any]:
        """
        エンジン情報を取得

        Returns:
            エンジン情報の辞書
        """
        return {
            "engine": self.__class__.__name__,
            "model_name": self.model_name,
            "device": self.device,
            "language": self.language,
            "is_loaded": self.is_loaded
        }


# テスト用
if __name__ == "__main__":
    print("BaseTranscriptionEngine is an abstract class.")
    print("It should be subclassed by concrete engine implementations.")
    print("\nRequired methods to implement:")
    print("  - load_model() -> bool")
    print("  - transcribe(audio, **kwargs) -> Dict[str, Any]")
