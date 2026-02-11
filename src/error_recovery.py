"""
error_recovery.py - エラー回復マネージャー

エラー発生時の自動リトライ、フォールバック、ログ記録を行う
"""

import json
import logging
import time
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class RecoveryAction(Enum):
    """回復アクション"""
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    FALLBACK = "fallback"


@dataclass
class ErrorRecord:
    """エラーレコード"""
    timestamp: str
    file_path: str
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    recovery_action: Optional[str] = None
    recovered: bool = False
    retry_count: int = 0


class ErrorRecoveryManager:
    """
    エラー回復マネージャー
    
    処理中のエラーを検出し、自動的に回復を試みる
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """
        初期化
        
        Args:
            log_dir: エラーログ保存ディレクトリ
        """
        if log_dir is None:
            log_dir = Path.home() / ".kotoba_transcriber" / "error_logs"
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.error_log_file = self.log_dir / "errors.jsonl"
        self._error_count = 0
        self._lock = Lock()
        self._error_callbacks: Dict[str, List[Callable]] = {
            'transient': [],
            'resource': [],
            'permanent': []
        }
    
    def register_callback(self, error_category: str, callback: Callable):
        """
        エラーカテゴリごとのコールバックを登録

        Args:
            error_category: 'transient', 'resource', 'permanent'
            callback: コールバック関数
        """
        with self._lock:
            if error_category in self._error_callbacks:
                self._error_callbacks[error_category].append(callback)
    
    def handle_error(
        self,
        error: Exception,
        file_path: str,
        retry_func: Optional[Callable] = None,
        fallback_func: Optional[Callable] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        エラーを処理して回復を試行
        
        Args:
            error: 発生した例外
            file_path: 処理中のファイルパス
            retry_func: リトライ時に実行する関数
            fallback_func: フォールバック時に実行する関数
            max_retries: 最大リトライ回数
            
        Returns:
            {'success': bool, 'action': str, 'result': any, 'error': str}
        """
        import traceback
        
        error_record = ErrorRecord(
            timestamp=datetime.now().isoformat(),
            file_path=file_path,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc()
        )
        
        # エラー分類
        error_category = self._classify_error(error)
        
        # コールバック実行（ロック下でコピーしてからイテレーション）
        with self._lock:
            callbacks = list(self._error_callbacks.get(error_category, []))
        for callback in callbacks:
            try:
                callback(error, file_path)
            except Exception as e:
                logger.warning(f"Error callback failed: {e}")
        
        # 回復戦略の決定
        if error_category == 'transient' and retry_func:
            # 一時的エラー: リトライ
            return self._retry_with_backoff(retry_func, error_record, max_retries)
        
        elif error_category == 'resource' and fallback_func:
            # リソースエラー: フォールバック
            try:
                result = fallback_func()
                error_record.recovered = True
                error_record.recovery_action = RecoveryAction.FALLBACK.value
                self._log_error(error_record)
                return {
                    'success': True, 
                    'action': RecoveryAction.FALLBACK.value, 
                    'result': result,
                    'error': None
                }
            except Exception as fallback_error:
                error_record.error_message += f" | Fallback failed: {fallback_error}"
        
        # 記録してスキップ
        error_record.recovery_action = RecoveryAction.SKIP.value
        self._log_error(error_record)
        return {
            'success': False, 
            'action': RecoveryAction.SKIP.value, 
            'result': None,
            'error': str(error)
        }
    
    def _classify_error(self, error: Exception) -> str:
        """
        エラーを分類
        
        Args:
            error: 例外
            
        Returns:
            'transient', 'resource', 'permanent'
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # 一時的エラー
        transient_errors = [
            'TimeoutError', 'ConnectionError', 'TemporaryFailure',
            'ChunkedEncodingError', 'ReadTimeout'
        ]
        transient_keywords = ['timeout', 'temporary', 'retry', 'connection reset']
        
        # リソースエラー
        resource_errors = [
            'MemoryError', 'OSError', 'IOError', 'FileNotFoundError',
            'PermissionError', 'DiskFullError'
        ]
        resource_keywords = ['no space', 'not found', 'permission', 'memory']
        
        if error_type in transient_errors or any(k in error_msg for k in transient_keywords):
            return 'transient'
        elif error_type in resource_errors or any(k in error_msg for k in resource_keywords):
            return 'resource'
        
        return 'permanent'
    
    def _retry_with_backoff(
        self,
        func: Callable,
        error_record: ErrorRecord,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        指数バックオフでリトライ
        
        Args:
            func: 実行する関数
            error_record: エラーレコード
            max_retries: 最大リトライ回数
            
        Returns:
            実行結果
        """
        for attempt in range(max_retries):
            try:
                wait_time = min(2 ** attempt, 60)  # 最大60秒
                logger.info(f"Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                
                result = func()
                
                error_record.recovered = True
                error_record.recovery_action = f"retry_success_{attempt + 1}"
                error_record.retry_count = attempt + 1
                self._log_error(error_record)
                
                return {
                    'success': True, 
                    'action': error_record.recovery_action, 
                    'result': result,
                    'error': None,
                    'retries': attempt + 1
                }
                
            except Exception as e:
                logger.warning(f"Retry {attempt + 1} failed: {e}")
                continue
        
        # すべてのリトライ失敗
        error_record.recovery_action = f"retry_failed_{max_retries}"
        error_record.retry_count = max_retries
        self._log_error(error_record)
        
        return {
            'success': False, 
            'action': RecoveryAction.SKIP.value, 
            'result': None,
            'error': f'Max retries ({max_retries}) exceeded',
            'retries': max_retries
        }
    
    # エラーログの最大サイズ (10MB)
    MAX_LOG_SIZE = 10 * 1024 * 1024

    def _log_error(self, record: ErrorRecord):
        """エラーをログに記録"""
        with self._lock:
            try:
                # ログローテーション: サイズ上限超過時にローテート
                if self.error_log_file.exists():
                    try:
                        file_size = self.error_log_file.stat().st_size
                        if file_size > self.MAX_LOG_SIZE:
                            rotated = self.error_log_file.with_suffix('.jsonl.1')
                            if rotated.exists():
                                rotated.unlink()
                            self.error_log_file.rename(rotated)
                            logger.info(f"Error log rotated: {file_size} bytes")
                    except OSError as e:
                        logger.warning(f"Failed to rotate error log: {e}")

                with open(self.error_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(asdict(record), ensure_ascii=False) + '\n')
                self._error_count += 1
            except Exception as e:
                logger.error(f"Failed to log error: {e}")
    
    def get_error_summary(self, since_hours: Optional[int] = None) -> Dict[str, Any]:
        """
        エラーサマリーを取得
        
        Args:
            since_hours: 何時間前からのエラーを集計するか
            
        Returns:
            エラーサマリー
        """
        if not self.error_log_file.exists():
            return {'total_errors': 0}

        # ファイルサイズチェック
        try:
            file_size = self.error_log_file.stat().st_size
            if file_size > self.MAX_LOG_SIZE * 2:
                logger.warning(f"Error log too large for summary: {file_size} bytes")
                return {'total_errors': -1, 'error': 'log_too_large'}
        except OSError:
            return {'total_errors': 0}

        errors = []
        cutoff_time = None
        
        if since_hours:
            from datetime import timedelta
            cutoff_time = datetime.now() - timedelta(hours=since_hours)
        
        with open(self.error_log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    error = json.loads(line)
                    
                    # 時間フィルタ
                    if cutoff_time:
                        error_time = datetime.fromisoformat(error['timestamp'])
                        if error_time < cutoff_time:
                            continue
                    
                    errors.append(error)
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # 集計
        error_types: Dict[str, int] = {}
        recovery_stats = {
            'retry': 0, 
            'fallback': 0, 
            'skip': 0, 
            'recovered': 0,
            'retry_success': 0,
            'retry_failed': 0
        }
        file_errors: Dict[str, int] = {}
        
        for e in errors:
            # エラータイプ集計
            error_types[e['error_type']] = error_types.get(e['error_type'], 0) + 1
            
            # 回復統計
            action = e.get('recovery_action', 'unknown')
            if 'retry_success' in action:
                recovery_stats['retry_success'] += 1
                recovery_stats['recovered'] += 1
            elif 'retry_failed' in action:
                recovery_stats['retry_failed'] += 1
            elif 'retry' in action:
                recovery_stats['retry'] += 1
            elif 'fallback' in action:
                recovery_stats['fallback'] += 1
                recovery_stats['recovered'] += 1
            else:
                recovery_stats['skip'] += 1
            
            # ファイル別エラー
            file_path = e.get('file_path', 'unknown')
            file_errors[file_path] = file_errors.get(file_path, 0) + 1
        
        return {
            'total_errors': len(errors),
            'error_types': error_types,
            'recovery_stats': recovery_stats,
            'recovery_rate': recovery_stats['recovered'] / len(errors) if errors else 0,
            'most_problematic_files': sorted(
                file_errors.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
        }
    
    def clear_logs(self):
        """エラーログをクリア"""
        with self._lock:
            if self.error_log_file.exists():
                self.error_log_file.unlink()
            self._error_count = 0
        logger.info("Error logs cleared")


# デコレータ版
class Resilient:
    """
    エラー回復デコレータ
    
    使用例:
        @resilient(max_retries=3)
        def process_file(file_path):
            # 処理
            pass
    """
    
    def __init__(
        self, 
        max_retries: int = 3, 
        fallback_value: Any = None,
        log_dir: Optional[str] = None
    ):
        self.max_retries = max_retries
        self.fallback_value = fallback_value
        self.manager = ErrorRecoveryManager(log_dir)
    
    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            file_path = args[0] if args else kwargs.get('file_path', 'unknown')
            
            def retry_fn():
                return func(*args, **kwargs)
            
            def fallback_fn():
                return self.fallback_value
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return self.manager.handle_error(
                    e, 
                    str(file_path), 
                    retry_fn, 
                    fallback_fn,
                    self.max_retries
                )
        
        return wrapper


# 後方互換エイリアス
resilient = Resilient


if __name__ == "__main__":
    # テスト
    logging.basicConfig(level=logging.INFO)
    
    print("=== ErrorRecoveryManager Test ===\n")
    
    manager = ErrorRecoveryManager()
    
    # テスト用関数
    attempt_count = 0
    def flaky_function():
        global attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ConnectionError("Simulated connection error")
        return "Success!"
    
    def fallback_function():
        return "Fallback result"
    
    # リトライ成功テスト
    print("1. Retry Success Test:")
    attempt_count = 0
    result = manager.handle_error(
        ConnectionError("Test error"),
        "test_file.wav",
        retry_func=flaky_function,
        max_retries=3
    )
    print(f"   Result: {result}")
    
    # フォールバックテスト
    print("\n2. Fallback Test:")
    result = manager.handle_error(
        MemoryError("Out of memory"),
        "large_file.wav",
        fallback_func=fallback_function
    )
    print(f"   Result: {result}")
    
    # サマリーテスト
    print("\n3. Error Summary:")
    summary = manager.get_error_summary()
    print(f"   Total errors: {summary['total_errors']}")
    print(f"   Recovery rate: {summary['recovery_rate']:.1%}")
    
    # デコレータテスト
    print("\n4. Decorator Test:")
    
    @Resilient(max_retries=2, fallback_value="Default")
    def decorated_function(file_path: str):
        raise TimeoutError("Simulated timeout")
    
    result = decorated_function("test.wav")
    print(f"   Decorated result: {result}")
    
    print("\nTest completed!")
