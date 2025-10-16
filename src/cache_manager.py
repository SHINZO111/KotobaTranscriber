"""
キャッシュマネージャー
LRU/TTLキャッシュによる文字起こし結果とモデル設定のキャッシング
"""

import hashlib
import logging
import time
from functools import lru_cache, wraps
from typing import Optional, Dict, Any, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from cachetools import TTLCache, LRUCache
    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False
    logger.warning("cachetools not available, using basic dict cache. Install with: pip install cachetools")


class CacheManager:
    """
    文字起こし結果とモデル設定のキャッシュマネージャー

    Features:
    - TTLCache: 時間ベースの自動削除（デフォルト1時間）
    - LRUCache: 最近使用されていないエントリを自動削除
    - ファイルハッシュベースのキャッシュキー生成
    - キャッシュヒット率の追跡
    """

    def __init__(self,
                 maxsize: int = 1000,
                 ttl: int = 3600,
                 enable_stats: bool = True):
        """
        初期化

        Args:
            maxsize: キャッシュの最大サイズ（エントリ数）
            ttl: Time-To-Live（秒）、デフォルト1時間
            enable_stats: 統計情報を収集するか
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.enable_stats = enable_stats

        # TTLキャッシュ（時間制限付き）
        if CACHETOOLS_AVAILABLE:
            self.transcription_cache = TTLCache(maxsize=maxsize, ttl=ttl)
            self.model_config_cache = LRUCache(maxsize=128)
        else:
            # フォールバック: 通常のdict
            self.transcription_cache = {}
            self.model_config_cache = {}

        # 統計情報
        self.stats = {
            "hits": 0,
            "misses": 0,
            "cache_size": 0,
            "total_requests": 0,
            "hit_rate": 0.0
        }

        logger.info(f"CacheManager initialized: maxsize={maxsize}, ttl={ttl}s")

    def get_file_hash(self, file_path: str) -> str:
        """
        ファイルのハッシュ値を計算（キャッシュキーとして使用）

        Args:
            file_path: ファイルパス

        Returns:
            SHA256ハッシュ値（16進数文字列）
        """
        try:
            # ファイルサイズと最終更新時刻を組み合わせてハッシュ化
            # 大きなファイルの場合、全体を読むのは遅いため
            path = Path(file_path)
            if not path.exists():
                return ""

            stat = path.stat()
            hash_input = f"{file_path}:{stat.st_size}:{stat.st_mtime}"

            return hashlib.sha256(hash_input.encode()).hexdigest()

        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return ""

    def cache_transcription(self,
                           audio_path: str,
                           result: Dict[str, Any],
                           params: Optional[Dict] = None) -> None:
        """
        文字起こし結果をキャッシュ

        Args:
            audio_path: 音声ファイルパス
            result: 文字起こし結果
            params: 追加パラメータ（モデルサイズ、言語など）
        """
        cache_key = self._generate_cache_key(audio_path, params)
        if not cache_key:
            return

        try:
            self.transcription_cache[cache_key] = {
                "result": result,
                "timestamp": time.time(),
                "audio_path": audio_path,
                "params": params or {}
            }

            logger.debug(f"Cached transcription result: {cache_key[:16]}...")

        except Exception as e:
            logger.error(f"Error caching transcription: {e}")

    def get_cached_transcription(self,
                                audio_path: str,
                                params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        キャッシュから文字起こし結果を取得

        Args:
            audio_path: 音声ファイルパス
            params: 追加パラメータ

        Returns:
            キャッシュされた結果、または None
        """
        cache_key = self._generate_cache_key(audio_path, params)
        if not cache_key:
            self._record_miss()
            return None

        try:
            cached = self.transcription_cache.get(cache_key)

            if cached:
                self._record_hit()
                logger.info(f"Cache hit for: {Path(audio_path).name}")
                return cached["result"]
            else:
                self._record_miss()
                return None

        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            self._record_miss()
            return None

    def _generate_cache_key(self, audio_path: str, params: Optional[Dict] = None) -> str:
        """
        キャッシュキーを生成

        Args:
            audio_path: 音声ファイルパス
            params: 追加パラメータ

        Returns:
            キャッシュキー
        """
        file_hash = self.get_file_hash(audio_path)
        if not file_hash:
            return ""

        # パラメータも含めてハッシュ化
        if params:
            params_str = str(sorted(params.items()))
            full_hash = hashlib.sha256(f"{file_hash}:{params_str}".encode()).hexdigest()
            return full_hash

        return file_hash

    @lru_cache(maxsize=128)
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        モデル設定をキャッシュから取得（LRUキャッシュ使用）

        Args:
            model_name: モデル名

        Returns:
            モデル設定
        """
        # 実装はユースケースに応じてカスタマイズ
        # ここではプレースホルダー
        config = self.model_config_cache.get(model_name, {})
        logger.debug(f"Model config for {model_name}: {config}")
        return config

    def cache_model_config(self, model_name: str, config: Dict[str, Any]) -> None:
        """
        モデル設定をキャッシュ

        Args:
            model_name: モデル名
            config: 設定
        """
        self.model_config_cache[model_name] = config
        logger.debug(f"Cached model config: {model_name}")

    def _record_hit(self) -> None:
        """キャッシュヒットを記録"""
        if not self.enable_stats:
            return

        self.stats["hits"] += 1
        self.stats["total_requests"] += 1
        self._update_hit_rate()

    def _record_miss(self) -> None:
        """キャッシュミスを記録"""
        if not self.enable_stats:
            return

        self.stats["misses"] += 1
        self.stats["total_requests"] += 1
        self._update_hit_rate()

    def _update_hit_rate(self) -> None:
        """ヒット率を更新"""
        total = self.stats["total_requests"]
        if total > 0:
            self.stats["hit_rate"] = self.stats["hits"] / total
            self.stats["cache_size"] = len(self.transcription_cache)

    def get_stats(self) -> Dict[str, Any]:
        """
        キャッシュ統計を取得

        Returns:
            統計情報
        """
        return {
            **self.stats,
            "cache_size": len(self.transcription_cache),
            "model_config_cache_size": len(self.model_config_cache),
            "ttl": self.ttl,
            "maxsize": self.maxsize
        }

    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self.transcription_cache.clear()
        self.model_config_cache.clear()
        logger.info("Cache cleared")

    def clear_transcription_cache(self) -> None:
        """文字起こしキャッシュのみクリア"""
        self.transcription_cache.clear()
        logger.info("Transcription cache cleared")

    def clear_old_entries(self, max_age: int = 3600) -> int:
        """
        古いエントリを削除（TTLCacheを使っていない場合の手動削除）

        Args:
            max_age: 最大年齢（秒）

        Returns:
            削除されたエントリ数
        """
        if CACHETOOLS_AVAILABLE:
            # TTLCacheは自動削除するのでスキップ
            return 0

        current_time = time.time()
        removed = 0

        keys_to_remove = []
        for key, value in self.transcription_cache.items():
            if current_time - value.get("timestamp", 0) > max_age:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.transcription_cache[key]
            removed += 1

        logger.info(f"Removed {removed} old cache entries")
        return removed


def cached_transcription(cache_manager: CacheManager):
    """
    文字起こし関数用のデコレータ（キャッシング機能を追加）

    使用例:
        @cached_transcription(cache_manager)
        def transcribe(audio_path: str, **kwargs):
            # 文字起こし処理
            return result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(audio_path: str, *args, **kwargs):
            # キャッシュから取得を試みる
            params = kwargs.copy()
            cached = cache_manager.get_cached_transcription(audio_path, params)

            if cached is not None:
                return cached

            # キャッシュにない場合は実行
            result = func(audio_path, *args, **kwargs)

            # 結果をキャッシュ
            cache_manager.cache_transcription(audio_path, result, params)

            return result

        return wrapper
    return decorator


# グローバルキャッシュマネージャー（シングルトンパターン）
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager(maxsize: int = 1000, ttl: int = 3600) -> CacheManager:
    """
    グローバルキャッシュマネージャーを取得

    Args:
        maxsize: 最大サイズ
        ttl: TTL（秒）

    Returns:
        CacheManagerインスタンス
    """
    global _global_cache_manager

    if _global_cache_manager is None:
        _global_cache_manager = CacheManager(maxsize=maxsize, ttl=ttl)

    return _global_cache_manager


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== CacheManager Test ===\n")

    # キャッシュマネージャー作成
    cache = CacheManager(maxsize=10, ttl=60)

    # テストデータ
    test_audio = "test_audio.wav"
    test_result = {"text": "こんにちは、世界", "segments": []}

    # キャッシュに保存
    print("1. Caching result...")
    cache.cache_transcription(test_audio, test_result)

    # キャッシュから取得
    print("2. Retrieving from cache...")
    cached = cache.get_cached_transcription(test_audio)
    print(f"   Cached result: {cached}")

    # 存在しないファイルを取得（ミス）
    print("\n3. Cache miss test...")
    missed = cache.get_cached_transcription("nonexistent.wav")
    print(f"   Result: {missed}")

    # 統計情報
    print("\n4. Cache statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\nTest completed!")
