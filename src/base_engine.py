"""
基底エンジンクラス
全エンジンで共通する機能を提供
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import gc

logger = logging.getLogger(__name__)


class BaseEngine(ABC):
    """
    全エンジンの基底クラス

    共通機能:
    - デバイス選択（auto/cuda/cpu）
    - モデルロード/アンロード
    - コンテキストマネージャ
    - メモリクリーンアップ
    """

    def __init__(self, model_name: str, device: str = "auto"):
        """
        初期化

        Args:
            model_name: モデル名
            device: 実行デバイス ("auto", "cuda", "cpu")
        """
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.model = None
        self.is_loaded = False
        logger.info(f"{self.__class__.__name__} initialized with device: {self.device}")

    def _resolve_device(self, device: str) -> str:
        """
        デバイスを自動選択

        Args:
            device: デバイス指定 ("auto", "cuda", "cpu")

        Returns:
            解決されたデバイス名
        """
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                logger.warning("PyTorch not available, using CPU")
                return "cpu"
        return device

    def __enter__(self):
        """コンテキストマネージャのエントリポイント"""
        logger.info(f"Entering {self.__class__.__name__} context")
        if not self.is_loaded:
            self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        コンテキストマネージャのエグジットポイント

        Args:
            exc_type: 例外の型
            exc_val: 例外の値
            exc_tb: トレースバック

        Returns:
            False (例外を再送出)
        """
        logger.info(f"Exiting {self.__class__.__name__} context")
        try:
            self.unload_model()
        except Exception as e:
            logger.error(f"Error during context exit cleanup: {e}")

        if exc_type is not None:
            logger.error(f"Exception in context: {exc_type.__name__}: {exc_val}")

        return False

    @abstractmethod
    def load_model(self) -> bool:
        """
        モデルをロード（サブクラスで実装）

        Returns:
            ロード成功ならTrue
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        エンジンが利用可能かチェック（サブクラスで実装）

        Returns:
            利用可能ならTrue
        """
        pass

    def unload_model(self) -> None:
        """
        モデルをアンロード（メモリ解放）

        GPUメモリやCPUメモリを確実に解放するため、
        明示的にdelを呼び出し、ガベージコレクションを促す
        """
        if self.model is not None:
            try:
                logger.info("Unloading model...")
                del self.model
                self.model = None
                self.is_loaded = False

                # ガベージコレクションを明示的に実行してメモリを解放
                gc.collect()

                # CUDA使用時は追加のクリーンアップ
                if self.device == "cuda":
                    self._clear_cuda_cache()

                logger.info("Model unloaded successfully")

            except Exception as e:
                logger.error(f"Error unloading model: {e}")
                # エラーが発生してもNoneに設定
                self.model = None
                self.is_loaded = False
        else:
            logger.info("Model was not loaded")

    def _clear_cuda_cache(self) -> None:
        """CUDAキャッシュをクリア"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("CUDA cache cleared")
        except ImportError:
            pass

    def get_model_info(self) -> Dict[str, Any]:
        """
        モデル情報を取得

        Returns:
            モデル情報の辞書
        """
        return {
            "loaded": self.is_loaded,
            "model_name": self.model_name,
            "device": self.device,
            "engine_type": self.__class__.__name__
        }


class BaseTranscriptionEngine(BaseEngine):
    """
    文字起こしエンジンの基底クラス

    TranscriptionEngine、FasterWhisperEngine、TransformersWhisperEngine
    の共通機能を提供
    """

    def __init__(self, model_name: str, device: str = "auto", language: str = "ja"):
        """
        初期化

        Args:
            model_name: モデル名
            device: 実行デバイス
            language: 言語コード
        """
        super().__init__(model_name, device)
        self.language = language

    @abstractmethod
    def transcribe(self, audio, **kwargs) -> Dict[str, Any]:
        """
        音声を文字起こし（サブクラスで実装）

        Args:
            audio: 音声データ（形式はサブクラス依存）
            **kwargs: 追加パラメータ

        Returns:
            文字起こし結果の辞書
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """モデル情報を取得（言語情報を追加）"""
        info = super().get_model_info()
        info["language"] = self.language
        return info


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("BaseEngine and BaseTranscriptionEngine loaded successfully")
    print("\nUsage example:")
    print("  class MyEngine(BaseTranscriptionEngine):")
    print("      def load_model(self) -> bool:")
    print("          # モデルロード処理")
    print("          self.is_loaded = True")
    print("          return True")
    print("")
    print("      def is_available(self) -> bool:")
    print("          return self.is_loaded")
    print("")
    print("      def transcribe(self, audio, **kwargs):")
    print("          # 文字起こし処理")
    print("          return {'text': '...', 'segments': []}")
