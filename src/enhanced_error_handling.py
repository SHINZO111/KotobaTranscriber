"""
エラーハンドリング強化モジュール
KotobaTranscriber v2.2 - 堅牢性向上
"""

import os
import sys
import time
import logging
import traceback
from typing import Optional, Dict, Any, List, Callable, Type, Tuple
from enum import Enum, auto
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """エラーの重要度"""
    DEBUG = auto()      # デバッグ情報
    INFO = auto()       # 情報
    WARNING = auto()    # 警告（処理継続可能）
    ERROR = auto()      # エラー（処理中断）
    CRITICAL = auto()   # 致命的（アプリケーション終了）


@dataclass
class ErrorRecord:
    """エラーレコード"""
    timestamp: float
    error_type: str
    message: str
    severity: ErrorSeverity
    traceback: str
    context: Dict[str, Any]
    recovered: bool = False
    recovery_attempts: int = 0


class ErrorHandler:
    """エラーハンドラー"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._error_history: List[ErrorRecord] = []
        self._handlers: Dict[ErrorSeverity, List[Callable[[ErrorRecord], None]]] = {
            severity: [] for severity in ErrorSeverity
        }
        self._recovery_strategies: Dict[str, Callable[[Exception], bool]] = {}
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5
    
    def register_handler(self, 
                        severity: ErrorSeverity, 
                        handler: Callable[[ErrorRecord], None]):
        """エラーハンドラーを登録"""
        self._handlers[severity].append(handler)
    
    def register_recovery_strategy(self, 
                                   error_type: Type[Exception],
                                   strategy: Callable[[Exception], bool]):
        """回復戦略を登録"""
        self._recovery_strategies[error_type.__name__] = strategy
    
    def handle(self, 
               error: Exception, 
               severity: ErrorSeverity = ErrorSeverity.ERROR,
               context: Dict[str, Any] = None) -> bool:
        """
        エラーを処理
        
        Args:
            error: 発生した例外
            severity: エラーの重要度
            context: 追加コンテキスト情報
            
        Returns:
            回復成功時True
        """
        # エラーレコード作成
        record = ErrorRecord(
            timestamp=time.time(),
            error_type=type(error).__name__,
            message=str(error),
            severity=severity,
            traceback=traceback.format_exc(),
            context=context or {}
        )
        
        # 履歴に追加
        self._error_history.append(record)
        if len(self._error_history) > self.max_history:
            self._error_history.pop(0)
        
        # 連続エラーカウント
        self._consecutive_errors += 1
        
        # ログ出力
        self._log_error(record)
        
        # ハンドラー実行
        for handler in self._handlers[severity]:
            try:
                handler(record)
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
        
        # 回復を試行
        if self._consecutive_errors <= self._max_consecutive_errors:
            recovered = self._try_recovery(error)
            record.recovered = recovered
            
            if recovered:
                self._consecutive_errors = 0
                logger.info(f"Successfully recovered from {record.error_type}")
                return True
        else:
            logger.critical(f"Too many consecutive errors ({self._consecutive_errors})")
            record.severity = ErrorSeverity.CRITICAL
        
        return False
    
    def _log_error(self, record: ErrorRecord):
        """エラーをログ出力"""
        log_message = f"[{record.error_type}] {record.message}"
        
        if record.severity == ErrorSeverity.DEBUG:
            logger.debug(log_message)
        elif record.severity == ErrorSeverity.INFO:
            logger.info(log_message)
        elif record.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif record.severity == ErrorSeverity.ERROR:
            logger.error(log_message)
            logger.debug(record.traceback)
        elif record.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
            logger.critical(record.traceback)
    
    def _try_recovery(self, error: Exception) -> bool:
        """回復を試行"""
        error_type = type(error).__name__
        
        if error_type in self._recovery_strategies:
            try:
                return self._recovery_strategies[error_type](error)
            except Exception as e:
                logger.error(f"Recovery strategy failed: {e}")
        
        return False
    
    def reset_error_count(self):
        """連続エラーカウントをリセット"""
        self._consecutive_errors = 0
    
    def get_error_history(self, severity: ErrorSeverity = None) -> List[ErrorRecord]:
        """エラー履歴を取得"""
        if severity is None:
            return self._error_history.copy()
        return [r for r in self._error_history if r.severity == severity]
    
    def get_error_summary(self) -> Dict[str, int]:
        """エラーサマリーを取得"""
        summary = {severity.name: 0 for severity in ErrorSeverity}
        for record in self._error_history:
            summary[record.severity.name] += 1
        return summary


# グローバルエラーハンドラー
_global_error_handler = ErrorHandler()

def get_error_handler() -> ErrorHandler:
    """グローバルエラーハンドラーを取得"""
    return _global_error_handler


def safe_execute(func: Callable, 
                 default_return: Any = None,
                 error_message: str = None,
                 severity: ErrorSeverity = ErrorSeverity.ERROR):
    """
    安全に関数を実行
    
    Args:
        func: 実行する関数
        default_return: エラー時のデフォルト戻り値
        error_message: カスタムエラーメッセージ
        severity: エラーの重要度
        
    Returns:
        関数の戻り値、またはデフォルト値
    """
    try:
        return func()
    except Exception as e:
        handler = get_error_handler()
        context = {"function": func.__name__} if hasattr(func, '__name__') else {}
        handler.handle(e, severity=severity, context=context)
        return default_return


def retry_on_error(max_retries: int = 3, 
                   delay: float = 1.0,
                   exceptions: Tuple[Type[Exception], ...] = (Exception,)):
    """
    デコレータ: エラー時にリトライ
    
    Args:
        max_retries: 最大リトライ回数
        delay: リトライ間隔（秒）
        exceptions: リトライ対象の例外型
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        time.sleep(delay * (attempt + 1))  # バックオフ
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts")
            
            # 最後のエラーを再発生
            raise last_error
        
        return wrapper
    return decorator


def with_error_handling(error_message: str = None,
                        severity: ErrorSeverity = ErrorSeverity.ERROR,
                        reraise: bool = False):
    """
    デコレータ: エラーハンドリングを追加
    
    Args:
        error_message: カスタムエラーメッセージ
        severity: エラーの重要度
        reraise: エラーを再発生させるか
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = get_error_handler()
                msg = error_message or str(e)
                context = {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
                handler.handle(e, severity=severity, context=context)
                
                if reraise:
                    raise
                
                return None
        
        return wrapper
    return decorator


class FileOperationGuard:
    """ファイル操作ガード"""
    
    @staticmethod
    def safe_read(file_path: str, 
                  encoding: str = 'utf-8',
                  default: str = None) -> Optional[str]:
        """安全にファイルを読み込み"""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"File not found: {file_path}")
            return default
        except PermissionError:
            logger.error(f"Permission denied: {file_path}")
            return default
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return default
    
    @staticmethod
    def safe_write(file_path: str, 
                   content: str,
                   encoding: str = 'utf-8',
                   backup: bool = True) -> bool:
        """安全にファイルを書き込み"""
        try:
            # バックアップ作成
            if backup and os.path.exists(file_path):
                backup_path = f"{file_path}.backup"
                import shutil
                shutil.copy2(file_path, backup_path)
            
            # ディレクトリ作成
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # 書き込み
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            
            return True
        
        except PermissionError:
            logger.error(f"Permission denied: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to write {file_path}: {e}")
            return False
    
    @staticmethod
    def safe_delete(file_path: str, 
                    move_to_trash: bool = False) -> bool:
        """安全にファイルを削除"""
        try:
            if not os.path.exists(file_path):
                return True
            
            if move_to_trash:
                # ゴミ箱に移動（Send2Trash必要）
                try:
                    import send2trash
                    send2trash.send2trash(file_path)
                    return True
                except ImportError:
                    pass
            
            os.remove(file_path)
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return False


class ResourceGuard:
    """リソース管理ガード"""
    
    def __init__(self, cleanup_callback: Callable = None):
        self._resources: List[Any] = []
        self._cleanup_callback = cleanup_callback
    
    def register(self, resource: Any):
        """リソースを登録"""
        self._resources.append(resource)
    
    def cleanup(self):
        """すべてのリソースをクリーンアップ"""
        for resource in reversed(self._resources):
            try:
                if hasattr(resource, 'close'):
                    resource.close()
                elif hasattr(resource, 'cleanup'):
                    resource.cleanup()
                elif hasattr(resource, 'release'):
                    resource.release()
            except Exception as e:
                logger.warning(f"Resource cleanup failed: {e}")
        
        self._resources.clear()
        
        if self._cleanup_callback:
            try:
                self._cleanup_callback()
            except Exception as e:
                logger.warning(f"Cleanup callback failed: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


def setup_global_error_handling():
    """グローバルエラーハンドリングを設定"""
    handler = get_error_handler()
    
    # デフォルトハンドラー
    def console_handler(record: ErrorRecord):
        """コンソール出力ハンドラー"""
        if record.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL):
            print(f"\n[ERROR] {record.error_type}: {record.message}", file=sys.stderr)
    
    handler.register_handler(ErrorSeverity.ERROR, console_handler)
    handler.register_handler(ErrorSeverity.CRITICAL, console_handler)
    
    # 回復戦略
    def handle_memory_error(e: Exception) -> bool:
        """メモリエラーの回復戦略"""
        import gc
        gc.collect()
        return True
    
    def handle_file_not_found(e: Exception) -> bool:
        """ファイル未検出の回復戦略"""
        # ファイル選択ダイアログを表示等
        return False
    
    handler.register_recovery_strategy(MemoryError, handle_memory_error)
    handler.register_recovery_strategy(FileNotFoundError, handle_file_not_found)
    
    logger.info("Global error handling configured")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("=== Enhanced Error Handling Test ===\n")
    
    # エラーハンドラーテスト
    handler = get_error_handler()
    
    # テスト用エラー
    try:
        raise ValueError("Test error")
    except Exception as e:
        handler.handle(e, severity=ErrorSeverity.WARNING, context={"test": True})
    
    print(f"Error history count: {len(handler.get_error_history())}")
    print(f"Error summary: {handler.get_error_summary()}")
    
    # リトライデコレータテスト
    @retry_on_error(max_retries=2, delay=0.1)
    def flaky_operation():
        if not hasattr(flaky_operation, 'attempts'):
            flaky_operation.attempts = 0
        flaky_operation.attempts += 1
        
        if flaky_operation.attempts < 3:
            raise RuntimeError("Temporary failure")
        return "Success!"
    
    result = flaky_operation()
    print(f"\nRetry test result: {result}")
    
    print("\nTest completed!")
