"""
KotobaTranscriber - 統一ロギングモジュール
構造化ログ（JSON形式）による一貫したロギング、分析・監視の容易化
"""

import logging
import logging.handlers
import json
import sys
import traceback
import yaml
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """
    JSON形式のログフォーマッター

    構造化ログとして出力し、ログ分析・監視ツールとの統合を容易にする
    """

    def __init__(
        self,
        timestamp_format: str = "%Y-%m-%dT%H:%M:%S.%fZ",
        include_context: bool = True,
        include_traceback: bool = True,
        mask_sensitive: bool = True,
        sensitive_keywords: Optional[list] = None
    ):
        """
        初期化

        Args:
            timestamp_format: タイムスタンプフォーマット（ISO 8601推奨）
            include_context: コンテキスト情報を含めるか
            include_traceback: スタックトレースを含めるか
            mask_sensitive: センシティブ情報をマスクするか
            sensitive_keywords: マスク対象キーワードリスト
        """
        super().__init__()
        self.timestamp_format = timestamp_format
        self.include_context = include_context
        self.include_traceback = include_traceback
        self.mask_sensitive = mask_sensitive
        self.sensitive_keywords = sensitive_keywords or [
            'password', 'token', 'secret', 'api_key', 'auth', 'credential'
        ]

    def format(self, record: logging.LogRecord) -> str:
        """
        ログレコードをJSON形式にフォーマット

        Args:
            record: ログレコード

        Returns:
            JSON形式の文字列
        """
        # 基本情報
        log_data = {
            'timestamp': self._format_timestamp(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
            'process': record.process,
        }

        # コンテキスト情報を追加
        if self.include_context and hasattr(record, 'context'):
            context = record.context
            if self.mask_sensitive:
                context = self._mask_sensitive_data(context)
            log_data['context'] = context

        # 例外情報を追加
        if record.exc_info and self.include_traceback:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }

        # スタックトレース（例外以外）
        if record.stack_info and self.include_traceback:
            log_data['stack_info'] = self.formatStack(record.stack_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)

    def _format_timestamp(self) -> str:
        """
        タイムスタンプをフォーマット（UTC）

        Returns:
            フォーマット済みタイムスタンプ文字列
        """
        return datetime.now(timezone.utc).strftime(self.timestamp_format)

    def _mask_sensitive_data(self, data: Any) -> Any:
        """
        センシティブ情報をマスク

        Args:
            data: マスク対象データ

        Returns:
            マスク済みデータ
        """
        if isinstance(data, dict):
            return {
                key: '***MASKED***' if any(
                    keyword.lower() in key.lower()
                    for keyword in self.sensitive_keywords
                ) else self._mask_sensitive_data(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        else:
            return data


class TextFormatter(logging.Formatter):
    """
    テキスト形式のログフォーマッター（コンソール出力用）

    人間が読みやすい形式で出力
    """

    # カラーコード（ANSI escape sequences）
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }

    def __init__(self, colorize: bool = True):
        """
        初期化

        Args:
            colorize: カラー出力を有効化するか
        """
        super().__init__(
            fmt='%(asctime)s - [%(levelname)s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.colorize = colorize and sys.stdout.isatty()  # TTYの場合のみカラー化

    def format(self, record: logging.LogRecord) -> str:
        """
        ログレコードをテキスト形式にフォーマット

        Args:
            record: ログレコード

        Returns:
            フォーマット済み文字列
        """
        formatted = super().format(record)

        # カラー化
        if self.colorize:
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            formatted = f"{color}{formatted}{reset}"

        # コンテキスト情報を追加（存在する場合）
        if hasattr(record, 'context') and record.context:
            context_str = json.dumps(record.context, ensure_ascii=False, indent=2)
            formatted += f"\n  Context: {context_str}"

        return formatted


class StructuredLogger:
    """
    構造化ロガー

    アプリケーション全体で統一されたロギングインターフェースを提供
    """

    _instances: Dict[str, 'StructuredLogger'] = {}
    _config: Optional[Dict[str, Any]] = None

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        初期化

        Args:
            name: ロガー名（通常は __name__）
            config: ロギング設定（未指定の場合はデフォルト設定）
        """
        self.name = name
        self.logger = logging.getLogger(name)

        # 設定を読み込み（初回のみ）
        if config is None and StructuredLogger._config is None:
            StructuredLogger._config = self._load_default_config()

        if config is not None:
            StructuredLogger._config = config

        # ロガーを設定
        self._setup_logging(StructuredLogger._config)

    @classmethod
    def get_logger(cls, name: str) -> 'StructuredLogger':
        """
        ロガーインスタンスを取得（シングルトンパターン）

        Args:
            name: ロガー名

        Returns:
            StructuredLoggerインスタンス
        """
        if name not in cls._instances:
            cls._instances[name] = cls(name)
        return cls._instances[name]

    @classmethod
    def load_config_from_file(cls, config_path: str) -> None:
        """
        設定ファイルから設定を読み込み

        Args:
            config_path: 設定ファイルパス（YAML）
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                cls._config = config

                # 既存のロガーを再設定
                for instance in cls._instances.values():
                    instance._setup_logging(config)

        except Exception as e:
            print(f"Failed to load logging config from {config_path}: {e}", file=sys.stderr)
            cls._config = cls._load_default_config()

    @staticmethod
    def _load_default_config() -> Dict[str, Any]:
        """
        デフォルト設定を読み込み

        Returns:
            デフォルト設定辞書
        """
        return {
            'default_level': 'INFO',
            'file': {
                'path': 'logs/app.log',
                'level': 'INFO',
                'max_size': 10485760,  # 10MB
                'backup_count': 5
            },
            'console': {
                'enabled': True,
                'level': 'INFO',
                'colorize': True
            },
            'format': {
                'structured': True,
                'timestamp_format': '%Y-%m-%dT%H:%M:%S.%fZ',
                'include_context': True,
                'include_traceback': True
            },
            'security': {
                'mask_sensitive': True,
                'sensitive_keywords': [
                    'password', 'token', 'secret', 'api_key', 'auth', 'credential'
                ]
            }
        }

    def _setup_logging(self, config: Dict[str, Any]) -> None:
        """
        ロギングを設定

        Args:
            config: ロギング設定辞書
        """
        # ハンドラーをクリア（重複防止）
        self.logger.handlers.clear()

        # ロガーレベル設定
        default_level = config.get('default_level', 'INFO')

        # モジュール別設定をチェック
        loggers_config = config.get('loggers', {})
        module_level = loggers_config.get(self.name, {}).get('level', default_level)

        self.logger.setLevel(getattr(logging, module_level))

        # 親ロガーへの伝播を無効化（重複ログ防止）
        self.logger.propagate = False

        # ファイルハンドラー設定
        file_config = config.get('file', {})
        if file_config:
            self._add_file_handler(file_config, config)

        # コンソールハンドラー設定
        console_config = config.get('console', {})
        if console_config.get('enabled', True):
            self._add_console_handler(console_config, config)

        # 外部ライブラリのログレベル設定
        self._configure_external_loggers(config)

    def _add_file_handler(
        self,
        file_config: Dict[str, Any],
        global_config: Dict[str, Any]
    ) -> None:
        """
        ファイルハンドラーを追加

        Args:
            file_config: ファイル設定
            global_config: グローバル設定
        """
        log_file = Path(file_config.get('path', 'logs/app.log'))
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # ローテーティングファイルハンドラー
        max_size = file_config.get('max_size', 10485760)  # 10MB
        backup_count = file_config.get('backup_count', 5)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_size,
            backupCount=backup_count,
            encoding='utf-8'
        )

        # レベル設定
        file_level = file_config.get('level', 'INFO')
        file_handler.setLevel(getattr(logging, file_level))

        # JSON フォーマッター設定
        format_config = global_config.get('format', {})
        security_config = global_config.get('security', {})

        file_handler.setFormatter(
            JSONFormatter(
                timestamp_format=format_config.get('timestamp_format', '%Y-%m-%dT%H:%M:%S.%fZ'),
                include_context=format_config.get('include_context', True),
                include_traceback=format_config.get('include_traceback', True),
                mask_sensitive=security_config.get('mask_sensitive', True),
                sensitive_keywords=security_config.get('sensitive_keywords', [])
            )
        )

        self.logger.addHandler(file_handler)

    def _add_console_handler(
        self,
        console_config: Dict[str, Any],
        global_config: Dict[str, Any]
    ) -> None:
        """
        コンソールハンドラーを追加

        Args:
            console_config: コンソール設定
            global_config: グローバル設定
        """
        console_handler = logging.StreamHandler(sys.stdout)

        # レベル設定
        console_level = console_config.get('level', 'INFO')
        console_handler.setLevel(getattr(logging, console_level))

        # テキストフォーマッター設定
        colorize = console_config.get('colorize', True)
        console_handler.setFormatter(TextFormatter(colorize=colorize))

        self.logger.addHandler(console_handler)

    def _configure_external_loggers(self, config: Dict[str, Any]) -> None:
        """
        外部ライブラリのロガー設定

        Args:
            config: ロギング設定
        """
        external_loggers = config.get('external_loggers', {})

        for logger_name, logger_config in external_loggers.items():
            external_logger = logging.getLogger(logger_name)
            level = logger_config.get('level', 'WARNING')
            external_logger.setLevel(getattr(logging, level))

    # ロギングメソッド
    def debug(self, message: str, **context) -> None:
        """DEBUGレベルのログ"""
        self._log('debug', message, **context)

    def info(self, message: str, **context) -> None:
        """INFOレベルのログ"""
        self._log('info', message, **context)

    def warning(self, message: str, **context) -> None:
        """WARNINGレベルのログ"""
        self._log('warning', message, **context)

    def error(self, message: str, **context) -> None:
        """ERRORレベルのログ"""
        self._log('error', message, **context)

    def critical(self, message: str, **context) -> None:
        """CRITICALレベルのログ"""
        self._log('critical', message, **context)

    def exception(self, message: str, **context) -> None:
        """例外情報付きERRORログ"""
        self._log('error', message, exc_info=True, **context)

    def _log(self, level: str, message: str, exc_info: bool = False, **context) -> None:
        """
        ログ出力（内部メソッド）

        Args:
            level: ログレベル
            message: メッセージ
            exc_info: 例外情報を含めるか
            **context: コンテキスト情報
        """
        extra = {'context': context} if context else {}

        log_method = getattr(self.logger, level)
        log_method(message, extra=extra, exc_info=exc_info)


# グローバル関数（既存コードとの互換性のため）
def get_logger(name: str) -> StructuredLogger:
    """
    ロガーを取得

    Args:
        name: ロガー名（通常は __name__）

    Returns:
        StructuredLoggerインスタンス
    """
    return StructuredLogger.get_logger(name)


def load_config_from_file(config_path: str) -> None:
    """
    設定ファイルから設定を読み込み

    Args:
        config_path: 設定ファイルパス（YAML）
    """
    StructuredLogger.load_config_from_file(config_path)


# 初期化: デフォルトで config/logging.yaml を読み込む
def initialize_logging() -> None:
    """
    ロギングシステムを初期化

    プロジェクトルートの config/logging.yaml から設定を読み込む
    """
    # プロジェクトルートを取得
    project_root = Path(__file__).parent.parent
    config_path = project_root / 'config' / 'logging.yaml'

    if config_path.exists():
        load_config_from_file(str(config_path))
    else:
        # 設定ファイルが存在しない場合はデフォルト設定を使用
        print(
            f"Logging config not found at {config_path}, using default configuration",
            file=sys.stderr
        )


# モジュールインポート時に初期化
initialize_logging()


# 使用例（モジュール内テスト）
if __name__ == "__main__":
    # ロガー取得
    logger = get_logger(__name__)

    # 基本ログ
    logger.info("アプリケーション起動")
    logger.debug("デバッグ情報")
    logger.warning("警告メッセージ")

    # コンテキスト付きログ
    logger.info(
        "ユーザーログイン成功",
        user_id=12345,
        ip_address="192.168.1.100",
        session_id="abc123"
    )

    # エラーログ
    logger.error(
        "データベース接続エラー",
        database="main_db",
        host="localhost",
        port=5432
    )

    # 例外ログ
    try:
        result = 1 / 0
    except ZeroDivisionError:
        logger.exception(
            "計算エラーが発生しました",
            operation="division",
            numerator=1,
            denominator=0
        )

    # センシティブ情報のマスク
    logger.info(
        "API認証成功",
        api_key="secret_key_12345",  # マスクされる
        token="bearer_token_xyz",    # マスクされる
        username="test_user"         # マスクされない
    )

    print("\n--- ログファイルを確認してください ---")
    print("場所: logs/app.log")
