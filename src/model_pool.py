"""
モデルプーリングマネージャ
LRU戦略でモデルをキャッシュし、メモリ使用量を最適化する
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from collections import OrderedDict
import weakref

logger = logging.getLogger(__name__)

# ジェネリック型変数
T = TypeVar('T')


@dataclass
class ModelEntry:
    """モデルエントリ情報"""
    model: Any
    model_name: str
    load_time: float
    last_used: float
    access_count: int
    memory_size_mb: Optional[float] = None


class ModelPool(Generic[T]):
    """
    モデルプールマネージャ

    LRU (Least Recently Used) 戦略でモデルをキャッシュし、
    メモリ使用量を最適化する。

    使用例:
        pool = ModelPool(max_models=2, model_loader=load_whisper_model)
        model = pool.get_model("base")
        # ... モデル使用 ...
        pool.release_model("base")
    """

    def __init__(
        self,
        max_models: int = 2,
        model_loader: Optional[Callable[[str], T]] = None,
        auto_unload: bool = True,
        idle_timeout: float = 300.0  # 5分
    ):
        """
        初期化

        Args:
            max_models: プールに保持する最大モデル数
            model_loader: モデルロード関数 (model_name) -> model
            auto_unload: アイドル状態のモデルを自動アンロード
            idle_timeout: アイドルタイムアウト（秒）
        """
        if max_models < 1:
            raise ValueError("max_models must be at least 1")

        self.max_models = max_models
        self.model_loader = model_loader
        self.auto_unload = auto_unload
        self.idle_timeout = idle_timeout

        # モデルプール（OrderedDictでLRU実装）
        self._pool: OrderedDict[str, ModelEntry] = OrderedDict()

        # スレッドセーフティ
        self._lock = threading.RLock()

        # 統計情報
        self._total_loads = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._evictions = 0

        # 自動アンロードスレッド
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

        if self.auto_unload:
            self._start_cleanup_thread()

        logger.info(
            f"ModelPool initialized: max_models={max_models}, "
            f"auto_unload={auto_unload}, idle_timeout={idle_timeout}s"
        )

    def __enter__(self):
        """コンテキストマネージャのエントリポイント"""
        logger.info("Entering ModelPool context")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャのエグジットポイント"""
        logger.info("Exiting ModelPool context")
        try:
            self.clear()
        except Exception as e:
            logger.error(f"Error during context exit: {e}")

        if exc_type is not None:
            logger.error(f"Exception in context: {exc_type.__name__}: {exc_val}")

        return False

    def set_model_loader(self, loader: Callable[[str], T]) -> None:
        """
        モデルローダー関数を設定

        Args:
            loader: モデルロード関数
        """
        self.model_loader = loader
        logger.info("Model loader function set")

    def get_model(
        self,
        model_name: str,
        loader: Optional[Callable[[str], T]] = None
    ) -> T:
        """
        モデルを取得（キャッシュから取得、なければロード）

        Args:
            model_name: モデル名
            loader: オプションのモデルローダー関数

        Returns:
            モデルオブジェクト

        Raises:
            ValueError: ローダー関数が設定されていない
            Exception: モデルロード失敗
        """
        with self._lock:
            # キャッシュヒットチェック
            if model_name in self._pool:
                entry = self._pool[model_name]
                entry.last_used = time.time()
                entry.access_count += 1
                self._cache_hits += 1

                # LRU: 最近使用したものを末尾に移動
                self._pool.move_to_end(model_name)

                logger.info(
                    f"Model cache HIT: {model_name} "
                    f"(access_count={entry.access_count})"
                )
                return entry.model

            # キャッシュミス: ロードが必要
            self._cache_misses += 1
            logger.info(f"Model cache MISS: {model_name}")

            # ローダー関数の確認
            effective_loader = loader or self.model_loader
            if effective_loader is None:
                raise ValueError(
                    "No model loader provided. "
                    "Set model_loader in __init__ or pass loader to get_model()"
                )

            # プールが満杯なら最も古いモデルを削除
            if len(self._pool) >= self.max_models:
                self._evict_lru_model()

            # モデルロード
            try:
                logger.info(f"Loading model: {model_name}")
                load_start = time.time()

                model = effective_loader(model_name)

                load_time = time.time() - load_start
                self._total_loads += 1

                # プールに追加
                entry = ModelEntry(
                    model=model,
                    model_name=model_name,
                    load_time=load_time,
                    last_used=time.time(),
                    access_count=1
                )

                # メモリサイズを推定（可能な場合）
                try:
                    memory_size = self._estimate_model_size(model)
                    entry.memory_size_mb = memory_size
                except Exception as e:
                    logger.debug(f"Could not estimate model size: {e}")

                self._pool[model_name] = entry

                logger.info(
                    f"Model loaded successfully: {model_name} "
                    f"(load_time={load_time:.2f}s, pool_size={len(self._pool)})"
                )

                return model

            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
                raise

    def release_model(self, model_name: str) -> None:
        """
        モデルの使用を終了（実際にはアンロードしない）

        Args:
            model_name: モデル名
        """
        with self._lock:
            if model_name in self._pool:
                entry = self._pool[model_name]
                entry.last_used = time.time()
                logger.debug(f"Model released: {model_name}")

    def unload_model(self, model_name: str) -> bool:
        """
        特定のモデルをアンロード

        Args:
            model_name: モデル名

        Returns:
            成功した場合True
        """
        with self._lock:
            if model_name not in self._pool:
                logger.warning(f"Model not in pool: {model_name}")
                return False

            try:
                entry = self._pool.pop(model_name)
                self._cleanup_model(entry.model)

                logger.info(
                    f"Model unloaded: {model_name} "
                    f"(access_count={entry.access_count})"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to unload model {model_name}: {e}")
                return False

    def _evict_lru_model(self) -> None:
        """LRU戦略で最も古いモデルを削除"""
        if not self._pool:
            return

        # OrderedDictの先頭が最も古いモデル
        lru_name, lru_entry = self._pool.popitem(last=False)

        try:
            self._cleanup_model(lru_entry.model)
            self._evictions += 1

            logger.info(
                f"Evicted LRU model: {lru_name} "
                f"(idle_time={time.time() - lru_entry.last_used:.1f}s)"
            )

        except Exception as e:
            logger.error(f"Error evicting model {lru_name}: {e}")

    def _cleanup_model(self, model: Any) -> None:
        """
        モデルをクリーンアップ（メモリ解放）

        Args:
            model: モデルオブジェクト
        """
        try:
            # unload_model メソッドがあれば呼び出す
            if hasattr(model, 'unload_model'):
                model.unload_model()

            # モデルへの参照を削除
            del model

            # ガベージコレクションを促す
            import gc
            gc.collect()

            # CUDAキャッシュクリア
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

        except Exception as e:
            logger.error(f"Error during model cleanup: {e}")

    def _estimate_model_size(self, model: Any) -> Optional[float]:
        """
        モデルのメモリサイズを推定（MB）

        Args:
            model: モデルオブジェクト

        Returns:
            メモリサイズ（MB）、推定できない場合None
        """
        try:
            import sys

            # PyTorchモデルの場合
            if hasattr(model, 'parameters'):
                total_params = sum(
                    p.numel() * p.element_size()
                    for p in model.parameters()
                )
                return total_params / (1024 ** 2)

            # その他のオブジェクト
            return sys.getsizeof(model) / (1024 ** 2)

        except Exception as e:
            logger.debug(f"Could not estimate model size: {e}")
            return None

    def _start_cleanup_thread(self) -> None:
        """自動クリーンアップスレッドを開始"""
        if self._cleanup_thread is not None:
            return

        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="ModelPoolCleanup"
        )
        self._cleanup_thread.start()
        logger.info("Cleanup thread started")

    def _cleanup_loop(self) -> None:
        """アイドル状態のモデルをクリーンアップするループ"""
        while not self._stop_cleanup.is_set():
            try:
                time.sleep(60)  # 1分ごとにチェック

                current_time = time.time()
                models_to_unload = []

                with self._lock:
                    for name, entry in self._pool.items():
                        idle_time = current_time - entry.last_used
                        if idle_time > self.idle_timeout:
                            models_to_unload.append(name)

                # ロックの外でアンロード
                for name in models_to_unload:
                    logger.info(f"Auto-unloading idle model: {name}")
                    self.unload_model(name)

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def clear(self) -> None:
        """プール内のすべてのモデルをアンロード"""
        with self._lock:
            logger.info(f"Clearing model pool ({len(self._pool)} models)...")

            # すべてのモデルをクリーンアップ
            for name, entry in list(self._pool.items()):
                try:
                    self._cleanup_model(entry.model)
                    logger.info(f"Cleared model: {name}")
                except Exception as e:
                    logger.error(f"Error clearing model {name}: {e}")

            self._pool.clear()
            logger.info("Model pool cleared")

    def shutdown(self) -> None:
        """プールをシャットダウン（クリーンアップスレッド停止）"""
        logger.info("Shutting down ModelPool...")

        # クリーンアップスレッド停止
        if self._cleanup_thread is not None:
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5.0)
            self._cleanup_thread = None

        # すべてのモデルをクリア
        self.clear()

        logger.info("ModelPool shut down")

    def get_statistics(self) -> Dict[str, Any]:
        """
        統計情報を取得

        Returns:
            統計情報の辞書
        """
        with self._lock:
            total_memory_mb = sum(
                entry.memory_size_mb or 0.0
                for entry in self._pool.values()
            )

            cache_hit_rate = (
                self._cache_hits / (self._cache_hits + self._cache_misses) * 100
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            )

            return {
                "pool_size": len(self._pool),
                "max_models": self.max_models,
                "total_loads": self._total_loads,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_hit_rate": cache_hit_rate,
                "evictions": self._evictions,
                "total_memory_mb": total_memory_mb,
                "models": {
                    name: {
                        "load_time": entry.load_time,
                        "last_used": entry.last_used,
                        "access_count": entry.access_count,
                        "idle_time": time.time() - entry.last_used,
                        "memory_mb": entry.memory_size_mb
                    }
                    for name, entry in self._pool.items()
                }
            }

    def get_model_names(self) -> list[str]:
        """プール内のモデル名リストを取得"""
        with self._lock:
            return list(self._pool.keys())

    def contains(self, model_name: str) -> bool:
        """モデルがプールに存在するかチェック"""
        with self._lock:
            return model_name in self._pool

    def __len__(self) -> int:
        """プール内のモデル数"""
        return len(self._pool)

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ModelPool(size={len(self._pool)}/{self.max_models}, "
                f"hits={self._cache_hits}, misses={self._cache_misses})"
            )


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== ModelPool Test ===\n")

    # ダミーモデルローダー
    def dummy_loader(model_name: str) -> Dict[str, Any]:
        """ダミーのモデルロード関数"""
        time.sleep(0.5)  # ロード時間をシミュレート
        return {
            "name": model_name,
            "data": f"Model data for {model_name}",
            "size": 100
        }

    # コンテキストマネージャとして使用
    with ModelPool(max_models=2, model_loader=dummy_loader) as pool:
        print(f"Initial pool: {pool}\n")

        # モデル取得テスト
        print("Loading model 'base'...")
        model1 = pool.get_model("base")
        print(f"Model loaded: {model1}\n")

        print("Loading model 'small'...")
        model2 = pool.get_model("small")
        print(f"Model loaded: {model2}\n")

        # キャッシュヒットテスト
        print("Re-loading model 'base' (should be cache hit)...")
        model1_again = pool.get_model("base")
        print(f"Model retrieved: {model1_again}\n")

        # LRU eviction テスト
        print("Loading model 'medium' (should evict 'small')...")
        model3 = pool.get_model("medium")
        print(f"Model loaded: {model3}\n")

        # 統計情報表示
        print("=== Pool Statistics ===")
        stats = pool.get_statistics()
        print(f"Pool size: {stats['pool_size']}/{stats['max_models']}")
        print(f"Cache hits: {stats['cache_hits']}")
        print(f"Cache misses: {stats['cache_misses']}")
        print(f"Hit rate: {stats['cache_hit_rate']:.1f}%")
        print(f"Evictions: {stats['evictions']}")
        print(f"\nModels in pool:")
        for name, info in stats['models'].items():
            print(f"  {name}: access_count={info['access_count']}, "
                  f"idle_time={info['idle_time']:.1f}s")

    # with ブロックを抜けると自動的にクリアされる
    print("\nPool automatically cleared on exit")
    print("Test completed successfully")
