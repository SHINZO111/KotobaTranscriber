# KotobaTranscriber 包括的コードレビューレポート

**レビュー日**: 2025-10-19
**レビュー対象**: KotobaTranscriberアプリケーション全体
**レビュー観点**: セキュリティ、パフォーマンス、コード品質、エラーハンドリング、スレッド安全性、リソース管理

---

## 📊 総合評価

### 全体スコア: **85/100** (Good)

| カテゴリ | スコア | 評価 |
|---------|--------|------|
| セキュリティ | 90/100 | Excellent |
| パフォーマンス | 80/100 | Good |
| コード品質 | 85/100 | Good |
| エラーハンドリング | 88/100 | Very Good |
| スレッド安全性 | 78/100 | Good |
| リソース管理 | 82/100 | Good |

---

## 🔴 Critical Issues (即座に修正が必要)

### 1. main.py: PyQt5とPySide6の混在

**ファイル**: `F:\KotobaTranscriber\src\main.py:1712`
**問題**: PyQt5のQApplicationをインポートしているが、他の箇所ではPySide6を使用している

```python
# Line 1712
from PyQt5.QtWidgets import QApplication  # ❌ WRONG
desktop = QApplication.desktop()
```

**影響範囲**:
- アプリケーションクラッシュの可能性
- ライブラリの競合による予期しない動作

**修正方法**:
```python
# PySide6に統一
from PySide6.QtWidgets import QApplication
desktop = QApplication.primaryScreen().availableGeometry()
```

**優先度**: 🔴 Critical

---

### 2. main.py: logger使用前のインポートエラー処理

**ファイル**: `F:\KotobaTranscriber\src\main.py:48-50`
**問題**: loggerが未初期化の状態でwarningを呼び出す可能性

```python
try:
    from vocabulary_dialog import VocabularyDialog
    VOCABULARY_DIALOG_AVAILABLE = True
except ImportError:
    VOCABULARY_DIALOG_AVAILABLE = False
    logger.warning("vocabulary_dialog not available")  # ❌ logger未初期化の可能性
```

**影響範囲**:
- 起動時のエラー
- デバッグ困難

**修正方法**:
```python
# オプション1: logging.basicConfigを先に実行
# オプション2: 条件付きロギング
except ImportError:
    VOCABULARY_DIALOG_AVAILABLE = False
    if 'logger' in locals():
        logger.warning("vocabulary_dialog not available")
```

**優先度**: 🔴 Critical

---

### 3. folder_monitor.py: is_file_ready() の競合状態（TOCTOU脆弱性）

**ファイル**: `F:\KotobaTranscriber\src\folder_monitor.py:122-145`
**問題**: ファイルサイズチェック後に1秒sleep、その後再チェックする間にファイルが変更される可能性

```python
def is_file_ready(self, file_path: str) -> bool:
    # ファイルサイズチェック
    size1 = os.path.getsize(file_path)  # ⚠️ TOCTOU: Time-of-check
    time.sleep(1)
    size2 = os.path.getsize(file_path)  # ⚠️ Time-of-use
    return size1 == size2
```

**影響範囲**:
- 競合状態による不完全なファイル処理
- データ破損の可能性

**修正方法**:
```python
def is_file_ready(self, file_path: str, timeout: int = 5) -> bool:
    """
    ファイルが読み取り可能かチェック（ファイルロック確認を含む）
    """
    start_time = time.time()
    previous_size = -1

    while time.time() - start_time < timeout:
        try:
            # 排他的読み取りを試みる
            with open(file_path, 'rb') as f:
                current_size = os.fstat(f.fileno()).st_size

                if current_size == 0:
                    return False

                if current_size == previous_size:
                    # サイズが安定している
                    f.seek(0)
                    f.read(min(1024, current_size))  # 一部読み取りテスト
                    return True

                previous_size = current_size

        except (OSError, IOError, PermissionError):
            pass

        time.sleep(0.5)

    return False
```

**優先度**: 🔴 Critical

---

### 4. transcription_engine.py: FFmpegパス検証の不十分なチェック

**ファイル**: `F:\KotobaTranscriber\src\transcription_engine.py:56-69`
**問題**: 許可リストのチェックがstartswith()のみで、シンボリックリンク悪用の可能性

```python
# パスが許可リストのいずれかで始まるか確認
if not any(real_path.startswith(allowed) for allowed in allowed_paths):  # ⚠️ 不十分
    logger.error(f"ffmpeg path not in allowed list: {real_path}")
    return False
```

**影響範囲**:
- パストラバーサル攻撃の可能性
- 任意コード実行のリスク

**修正方法**:
```python
# 許可されたディレクトリのいずれかの子孫であることを確認
is_allowed = False
for allowed in allowed_paths:
    try:
        allowed_resolved = Path(allowed).resolve()
        real_path_obj = Path(real_path).resolve()

        # 相対パスを計算してディレクトリトラバーサルをチェック
        real_path_obj.relative_to(allowed_resolved)
        is_allowed = True
        break
    except ValueError:
        continue

if not is_allowed:
    logger.error(f"ffmpeg path not in allowed list: {real_path}")
    return False
```

**優先度**: 🔴 Critical

---

## 🟡 Warnings (改善推奨)

### 5. main.py: BatchTranscriptionWorker - ThreadPoolExecutor のタイムアウト固定

**ファイル**: `F:\KotobaTranscriber\src\main.py:316`
**問題**: 10分のハードコードされたタイムアウトは大きなファイルに対して不十分

```python
audio_path, result_text, success = future.result(timeout=600)  # ⚠️ 10分固定
```

**影響範囲**:
- 長時間の音声ファイル処理時のタイムアウト
- ユーザー体験の低下

**修正方法**:
```python
# ファイルサイズに基づいた動的タイムアウト
def calculate_timeout(audio_path: str) -> int:
    """ファイルサイズに基づいてタイムアウトを計算"""
    try:
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        # 1MBあたり30秒、最小5分、最大30分
        timeout = max(300, min(1800, int(file_size_mb * 30)))
        return timeout
    except:
        return 600  # デフォルト10分

# 使用例
timeout = calculate_timeout(audio_path)
audio_path, result_text, success = future.result(timeout=timeout)
```

**優先度**: 🟡 Warning

---

### 6. main.py: 処理中ファイルの重複検出のメモリ効率

**ファイル**: `F:\KotobaTranscriber\src\main.py:1344-1355`
**問題**: 処理中ファイルのセットが無限に成長する可能性

```python
# 重複処理防止: 既に処理中のファイルをフィルタ（スレッドセーフ）
with self.processing_files_lock:
    new_files = [f for f in files if f not in self.processing_files]  # ⚠️ メモリリーク

    # 処理中リストに追加
    for f in new_files:
        self.processing_files.add(f)  # ⚠️ 削除されない場合メモリ増加
```

**影響範囲**:
- 長期間実行時のメモリリーク
- パフォーマンス低下

**修正方法**:
```python
# TTL（Time-To-Live）付き処理中ファイル管理
from collections import defaultdict
import time

class ProcessingFilesTracker:
    """TTL付き処理中ファイル追跡クラス"""

    def __init__(self, ttl: int = 3600):  # 1時間のTTL
        self.processing_files: Dict[str, float] = {}  # {file_path: start_time}
        self.lock = threading.RLock()
        self.ttl = ttl

    def add(self, file_path: str) -> None:
        """処理中としてマーク"""
        with self.lock:
            self.processing_files[file_path] = time.time()

    def remove(self, file_path: str) -> None:
        """処理済みとしてマーク"""
        with self.lock:
            self.processing_files.pop(file_path, None)

    def is_processing(self, file_path: str) -> bool:
        """処理中かチェック（期限切れファイルは自動削除）"""
        with self.lock:
            if file_path not in self.processing_files:
                return False

            start_time = self.processing_files[file_path]
            if time.time() - start_time > self.ttl:
                # TTL期限切れ、削除
                del self.processing_files[file_path]
                return False

            return True

    def cleanup_expired(self) -> None:
        """期限切れエントリをクリーンアップ"""
        with self.lock:
            current_time = time.time()
            expired = [
                path for path, start_time in self.processing_files.items()
                if current_time - start_time > self.ttl
            ]
            for path in expired:
                del self.processing_files[path]

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired processing entries")
```

**優先度**: 🟡 Warning

---

### 7. text_formatter.py: 正規表現パターンのプリコンパイル（パフォーマンス）

**ファイル**: `F:\KotobaTranscriber\src\text_formatter.py:48-147`
**問題**: 一部の正規表現パターンは既にプリコンパイルされているが、動的パターンのキャッシュ管理が不完全

```python
# 現在の実装は良好だが、キャッシュサイズ制限がない
_pattern_cache: Dict[str, Pattern] = {}  # ⚠️ 無制限のキャッシュ

@classmethod
def get_filler_pattern(cls, filler: str) -> Pattern:
    key = f"filler_{filler}"
    if key not in cls._pattern_cache:
        pattern = r'\b' + re.escape(filler) + r'\b[、。]?\s*'
        cls._pattern_cache[key] = re.compile(pattern, re.IGNORECASE)  # ⚠️ 上限なし
    return cls._pattern_cache[key]
```

**影響範囲**:
- 長時間実行時のメモリ使用量増加（軽微）
- パフォーマンス低下の可能性

**修正方法**:
```python
from functools import lru_cache

class RegexPatterns:
    """Precompiled regex patterns with LRU cache"""

    # 固定パターンはそのまま
    CONSECUTIVE_COMMAS = re.compile(r'[、]{2,}')
    # ... 他のパターン ...

    @classmethod
    @lru_cache(maxsize=128)  # ✅ LRUキャッシュで自動管理
    def get_filler_pattern(cls, filler: str) -> Pattern:
        """フィラー語パターンを取得（LRUキャッシュ付き）"""
        pattern = r'\b' + re.escape(filler) + r'\b[、。]?\s*'
        return re.compile(pattern, re.IGNORECASE)
```

**優先度**: 🟡 Warning

---

### 8. transcription_engine.py: 一時ファイルのクリーンアップタイミング

**ファイル**: `F:\KotobaTranscriber\src\transcription_engine.py:179-182`
**問題**: atexitによるクリーンアップはプロセス終了時のみで、長時間実行時に一時ファイルが蓄積

```python
# 一時ファイル追跡（リソースリーク対策）
self._temp_files: List[str] = []
atexit.register(self._cleanup_temp_files)  # ⚠️ プロセス終了時のみ
```

**影響範囲**:
- ディスク容量の浪費
- 一時ディレクトリの肥大化

**修正方法**:
```python
import tempfile
import weakref

class TempFileManager:
    """一時ファイル管理クラス（自動クリーンアップ付き）"""

    def __init__(self):
        self._temp_files: List[str] = []
        self._lock = threading.Lock()
        # weakrefを使用して自動クリーンアップ
        weakref.finalize(self, self._cleanup_all_temp_files, self._temp_files[:])

    def create_temp_file(self, suffix: str = "", prefix: str = "transcribe_") -> str:
        """一時ファイルを作成して追跡"""
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)  # ファイルハンドルをすぐに閉じる

        with self._lock:
            self._temp_files.append(path)

        return path

    def register_temp_file(self, path: str) -> None:
        """既存ファイルを一時ファイルとして追跡"""
        with self._lock:
            self._temp_files.append(path)

    def cleanup_temp_file(self, path: str) -> None:
        """個別の一時ファイルを削除"""
        try:
            if os.path.exists(path):
                os.unlink(path)

            with self._lock:
                if path in self._temp_files:
                    self._temp_files.remove(path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {path}: {e}")

    @staticmethod
    def _cleanup_all_temp_files(temp_files: List[str]) -> None:
        """すべての一時ファイルをクリーンアップ（静的メソッド）"""
        for path in temp_files:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {path}: {e}")
```

**優先度**: 🟡 Warning

---

### 9. main.py: quit_application() のスレッド終了待機の改善

**ファイル**: `F:\KotobaTranscriber\src\main.py:1181-1212`
**問題**: 各スレッドを順次待機するため、終了が遅い。並列終了が望ましい。

```python
def quit_application(self):
    # 通常の文字起こしワーカー停止
    if self.worker and self.worker.isRunning():
        self.worker.quit()
        if not self.worker.wait(10000):  # ⚠️ 順次待機
            self.worker.terminate()

    # バッチ処理ワーカー停止
    if self.batch_worker and self.batch_worker.isRunning():
        self.batch_worker.cancel()
        if not self.batch_worker.wait(30000):  # ⚠️ 順次待機
            self.batch_worker.terminate()

    # フォルダ監視停止
    if self.folder_monitor and self.folder_monitor.isRunning():
        self.folder_monitor.stop()
        if not self.folder_monitor.wait(5000):  # ⚠️ 順次待機
            self.folder_monitor.terminate()
```

**影響範囲**:
- アプリケーション終了の遅延
- ユーザー体験の低下

**修正方法**:
```python
def quit_application(self):
    """アプリケーション終了（並列スレッド終了）"""
    self.save_ui_settings()

    # すべてのスレッドに停止要求を送信（並列）
    threads_to_stop = []

    if self.worker and self.worker.isRunning():
        logger.info("Stopping transcription worker...")
        self.worker.quit()
        threads_to_stop.append(('worker', self.worker, 10000))

    if self.batch_worker and self.batch_worker.isRunning():
        logger.info("Stopping batch worker...")
        self.batch_worker.cancel()
        threads_to_stop.append(('batch_worker', self.batch_worker, 30000))

    if self.folder_monitor and self.folder_monitor.isRunning():
        logger.info("Stopping folder monitor...")
        self.folder_monitor.stop()
        threads_to_stop.append(('folder_monitor', self.folder_monitor, 5000))

    # 並列に待機
    import time
    start_time = time.time()
    max_timeout = max((timeout for _, _, timeout in threads_to_stop), default=0)

    for name, thread, timeout in threads_to_stop:
        remaining_time = max(0, timeout - int((time.time() - start_time) * 1000))

        if not thread.wait(remaining_time):
            logger.warning(f"{name} did not finish within timeout, terminating...")
            thread.terminate()
            thread.wait()
        else:
            logger.info(f"{name} stopped successfully")

    self.tray_icon.hide()
    logger.info("Application quitting - all worker threads cleaned up")

    QApplication.quit()
    sys.exit(0)
```

**優先度**: 🟡 Warning

---

### 10. folder_monitor.py: ファイル名のみで処理済み判定（衝突の可能性）

**ファイル**: `F:\KotobaTranscriber\src\folder_monitor.py:82-86`
**問題**: ベース名のみで処理済みチェック、フルパスでないため異なるディレクトリで衝突

```python
def is_processed(self, file_path: str) -> bool:
    """処理済みかチェック"""
    # ファイル名（ベース名のみ）で比較  # ⚠️ 衝突の可能性
    filename = os.path.basename(file_path)
    return os.path.exists(transcription_file) or filename in self.processed_files
```

**影響範囲**:
- 異なるフォルダの同名ファイルが誤って処理済みと判定される
- ファイル処理の漏れ

**修正方法**:
```python
def is_processed(self, file_path: str) -> bool:
    """処理済みかチェック（フルパスベース）"""
    # 絶対パスに正規化
    abs_path = os.path.abspath(file_path)

    # 文字起こしファイルが存在するかチェック
    base_name = os.path.splitext(abs_path)[0]
    transcription_file = f"{base_name}_文字起こし.txt"

    # フルパスで処理済みリストをチェック
    return os.path.exists(transcription_file) or abs_path in self.processed_files

def mark_as_processed(self, file_path: str):
    """ファイルを処理済みとしてマーク（フルパスベース）"""
    abs_path = os.path.abspath(file_path)
    self.processed_files.add(abs_path)
    self.save_processed_files()
    logger.info(f"Marked as processed: {abs_path}")
```

**優先度**: 🟡 Warning

---

## 🟢 Suggestions (より良くするための提案)

### 11. main.py: TranscriptionWorker - 重複したエラーハンドリングコード

**ファイル**: `F:\KotobaTranscriber\src\main.py:373-442`
**問題**: 各例外タイプで同様のエラーハンドリングが繰り返されている

```python
# 重複したパターン
except ModelLoadError as e:
    error_msg = f"モデルのロードに失敗しました: {e}"
    logger.error(error_msg, exc_info=True)
    self.error.emit(error_msg)
    return
except (IOError, OSError) as e:
    error_msg = f"モデルファイルの読み込みエラー: {e}"
    logger.error(error_msg, exc_info=True)
    self.error.emit(error_msg)
    return
# ... 以下同様
```

**修正方法**:
```python
def run(self):
    """文字起こし実行"""
    try:
        self._run_transcription()
    except Exception as e:
        self._handle_error(e)

def _run_transcription(self):
    """文字起こし処理（内部）"""
    self.progress.emit(UIConstants.PROGRESS_MODEL_LOAD)
    logger.info(f"Starting transcription for: {self.audio_path}")

    self.engine.load_model()
    self.progress.emit(UIConstants.PROGRESS_BEFORE_TRANSCRIBE)

    result = self.engine.transcribe(self.audio_path, return_timestamps=True)
    self.progress.emit(UIConstants.PROGRESS_AFTER_TRANSCRIBE)

    # ... 残りの処理

def _handle_error(self, error: Exception):
    """エラーハンドリング（統一）"""
    error_messages = {
        ModelLoadError: "モデルのロードに失敗しました",
        TranscriptionFailedError: "文字起こしに失敗しました",
        FileNotFoundError: "ファイルが見つかりません",
        PermissionError: "ファイルへのアクセス権限がありません",
        MemoryError: "メモリ不足です。ファイルサイズが大きすぎる可能性があります",
        ValueError: "音声フォーマットエラー",
    }

    error_type = type(error)
    base_message = error_messages.get(error_type, "予期しないエラーが発生しました")
    error_msg = f"{base_message}: {error}"

    logger.error(error_msg, exc_info=True)
    self.error.emit(error_msg)
```

**優先度**: 🟢 Suggestion

---

### 12. batch_processor.py: psutilのオプショナル依存性の明示化

**ファイル**: `F:\KotobaTranscriber\src\batch_processor.py:227-246`
**問題**: psutilの有無で動作が変わるが、明示的なログがない

```python
try:
    import psutil  # ⚠️ オプショナル、利用不可時は静かに失敗
    process = psutil.Process()
    # ...
except ImportError:
    pass  # ⚠️ ログなし
```

**修正方法**:
```python
class BatchProcessor:
    def __init__(self, ...):
        # ...
        self._psutil_available = self._check_psutil_availability()
        if self.auto_adjust_batch_size and not self._psutil_available:
            logger.warning(
                "psutil not available, batch size auto-adjustment disabled. "
                "Install with: pip install psutil"
            )

    @staticmethod
    def _check_psutil_availability() -> bool:
        """psutilの利用可能性をチェック"""
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _adjust_batch_size(self) -> None:
        """メモリ使用量に応じてバッチサイズを自動調整"""
        if not self._psutil_available:
            return

        import psutil
        # ... 既存のロジック
```

**優先度**: 🟢 Suggestion

---

### 13. faster_whisper_engine.py: TransformersWhisperEngineのコンテキストマネージャ実装

**ファイル**: `F:\KotobaTranscriber\src\faster_whisper_engine.py:240-353`
**問題**: TransformersWhisperEngineにコンテキストマネージャが実装されていない（FasterWhisperEngineには実装済み）

**修正方法**:
```python
class TransformersWhisperEngine(BaseTranscriptionEngine):
    """
    transformersベースのWhisperエンジン（フォールバック用）

    コンテキストマネージャとして使用可能（BaseEngineから継承）:
        with TransformersWhisperEngine() as engine:
            result = engine.transcribe(audio_data)
            # ... 処理 ...
        # 自動的にモデルがアンロードされる
    """
    # BaseTranscriptionEngineが__enter__と__exit__を実装しているため、
    # 既にコンテキストマネージャとして使用可能
    # ドキュメントに明記するのみ
```

**優先度**: 🟢 Suggestion

---

### 14. main.py: UIConstants の設定値の集約

**ファイル**: `F:\KotobaTranscriber\src\main.py:61-93`
**問題**: UI定数が定義されているが、一部の値はハードコードされている

**修正方法**:
```python
class UIConstants:
    """UI関連の定数を管理（完全版）"""

    # 進捗値
    PROGRESS_MODEL_LOAD = 20
    PROGRESS_BEFORE_TRANSCRIBE = 40
    PROGRESS_AFTER_TRANSCRIBE = 70
    PROGRESS_DIARIZATION_START = 75
    PROGRESS_DIARIZATION_END = 85
    PROGRESS_COMPLETE = 100

    # スライダー範囲
    VAD_SLIDER_MIN = 5
    VAD_SLIDER_MAX = 50
    VAD_SLIDER_DEFAULT = 10

    # 監視間隔範囲
    MONITOR_INTERVAL_MIN = 5
    MONITOR_INTERVAL_MAX = 60
    MONITOR_INTERVAL_DEFAULT = 10

    # 並列処理数
    BATCH_WORKERS_DEFAULT = 3
    MONITOR_BATCH_WORKERS = 2

    # ウィンドウサイズ制限
    WINDOW_MIN_WIDTH = 280  # ✅ 統一
    WINDOW_MIN_HEIGHT = 450  # ✅ 統一
    WINDOW_MAX_WIDTH = 3840
    WINDOW_MAX_HEIGHT = 2160

    # 段落整形デフォルト
    SENTENCES_PER_PARAGRAPH = 4

    # トレイ通知表示時間（ミリ秒）
    TRAY_NOTIFICATION_DURATION_SHORT = 2000
    TRAY_NOTIFICATION_DURATION_MEDIUM = 3000
    TRAY_NOTIFICATION_DURATION_LONG = 5000

# 使用例（Line 561をUIConstantsに置き換え）
self.setGeometry(100, 100, UIConstants.WINDOW_MIN_WIDTH, UIConstants.WINDOW_MIN_HEIGHT)
```

**優先度**: 🟢 Suggestion

---

### 15. app_settings.py: 設定ファイルのバックアップ機能

**ファイル**: `F:\KotobaTranscriber\src\app_settings.py:235-277`
**問題**: 設定ファイルの保存時にバックアップを作成していない

**修正方法**:
```python
def save(self, create_backup: bool = True) -> bool:
    """
    設定ファイルに保存（アトミック書き込み、バックアップ付き）

    Args:
        create_backup: 既存ファイルのバックアップを作成するか

    Returns:
        保存成功ならTrue
    """
    with self._lock:
        temp_file = None
        backup_file = None

        try:
            # ディレクトリが存在しない場合は作成
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)

            # 既存ファイルのバックアップを作成
            if create_backup and self.settings_file.exists():
                backup_file = self.settings_file.with_suffix('.bak')
                import shutil
                shutil.copy2(self.settings_file, backup_file)
                logger.debug(f"Created backup: {backup_file}")

            # 一時ファイルに書き込み
            temp_file = self.settings_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)

            # アトミックにリネーム（既存ファイルを上書き）
            os.replace(temp_file, self.settings_file)

            logger.info(f"Settings saved successfully to: {self.settings_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save settings: {e}", exc_info=True)

            # エラー時は一時ファイルを削除
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass

            # バックアップから復元
            if backup_file and backup_file.exists():
                try:
                    import shutil
                    shutil.copy2(backup_file, self.settings_file)
                    logger.info("Restored from backup")
                except:
                    pass

            return False
```

**優先度**: 🟢 Suggestion

---

## ✅ Good Practices (良い実装例)

### 1. exceptions.py: 包括的なカスタム例外階層

**ファイル**: `F:\KotobaTranscriber\src\exceptions.py`
**評価**: ✅ Excellent

**良い点**:
- 明確な例外階層（11レベル）
- 各例外に詳細なドキュメント
- 型ヒント付きの属性
- ユーティリティ関数（`is_kotoba_error`, `get_error_category`）
- 包括的なテストコード

**例**:
```python
class InvalidVADThresholdError(VADError):
    """VAD閾値が無効"""

    def __init__(self, threshold: float, valid_range: tuple):
        self.threshold = threshold
        self.valid_range = valid_range
        super().__init__(
            f"Invalid VAD threshold: {threshold} "
            f"(valid range: {valid_range[0]} ~ {valid_range[1]})"
        )
```

---

### 2. text_formatter.py: 正規表現パターンのプリコンパイル

**ファイル**: `F:\KotobaTranscriber\src\text_formatter.py:48-147`
**評価**: ✅ Very Good

**良い点**:
- 静的パターンをクラス変数としてプリコンパイル
- 動的パターンをLRUキャッシュで管理（推奨改善で更に向上可能）
- パフォーマンス最適化

**例**:
```python
class RegexPatterns:
    """Precompiled regex patterns for text formatting"""

    # 静的パターン
    CONSECUTIVE_COMMAS = re.compile(r'[、]{2,}')
    CONSECUTIVE_PERIODS = re.compile(r'[。]{2,}')

    # 動的パターン（キャッシュ付き）
    @classmethod
    def get_filler_pattern(cls, filler: str) -> Pattern:
        if key not in cls._pattern_cache:
            cls._pattern_cache[key] = re.compile(pattern, re.IGNORECASE)
        return cls._pattern_cache[key]
```

---

### 3. app_settings.py: スレッドセーフな設定管理

**ファイル**: `F:\KotobaTranscriber\src\app_settings.py`
**評価**: ✅ Very Good

**良い点**:
- RLock（再入可能ロック）を使用
- デバウンス機能付き保存
- アトミック書き込み（一時ファイル + os.replace）
- 包括的な入力検証（型、範囲、キーフォーマット）
- パストラバーサル対策

**例**:
```python
def save_debounced(self) -> None:
    """デバウンス付きで保存"""
    with self._lock:
        if self._save_timer is not None:
            self._save_timer.cancel()

        self._save_timer = threading.Timer(
            self._save_debounce_delay,
            self._execute_debounced_save
        )
        self._save_timer.daemon = True
        self._save_timer.start()
```

---

### 4. transcription_engine.py: リソース管理とクリーンアップ

**ファイル**: `F:\KotobaTranscriber\src\transcription_engine.py:179-432`
**評価**: ✅ Good

**良い点**:
- 一時ファイルの追跡とクリーンアップ
- CUDAメモリのクリーンアップ
- finally ブロックでの確実なリソース解放
- atexit によるフォールバック

**例**:
```python
finally:
    # CUDAメモリキャッシュをクリア（メモリリーク防止）
    if self.device == "cuda" and torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("CUDA cache cleared")

    # 一時ファイルの削除
    if processed_audio_path != validated_path:
        try:
            Path(processed_audio_path).unlink(missing_ok=True)
            self._temp_files.remove(str(processed_audio_path))
        except Exception as e:
            logger.warning(f"Failed to delete temporary file: {e}")
```

---

### 5. main.py: Validatorを使用したパストラバーサル対策

**ファイル**: `F:\KotobaTranscriber\src\main.py:932-947`
**評価**: ✅ Excellent

**良い点**:
- 入力パスの検証
- 実パスの正規化
- ディレクトリトラバーサルチェック
- 拡張子の制限

**例**:
```python
# パストラバーサル脆弱性対策: パスを検証
try:
    validated_path = Validator.validate_file_path(
        output_file,
        allowed_extensions=[".txt"],
        must_exist=False
    )

    # 実パスが元ファイルの親ディレクトリ内にあるか確認
    original_dir = os.path.realpath(os.path.dirname(self.selected_file))
    real_save_path = os.path.realpath(str(validated_path))
    real_save_dir = os.path.dirname(real_save_path)

    if not real_save_dir.startswith(original_dir):
        raise ValidationError(f"Path traversal detected: {output_file}")
```

---

## 📈 パフォーマンス分析

### メモリ使用量

| コンポーネント | 推定メモリ使用量 | 最適化の余地 |
|--------------|--------------|------------|
| TranscriptionEngine（モデル） | 1-4 GB | 低 |
| BatchWorker（並列処理） | 100-500 MB/ワーカー | 中 |
| 一時ファイル | 0-2 GB | 高（改善推奨） |
| processing_files セット | 数KB-数MB | 中（TTL推奨） |
| RegexPatterns キャッシュ | 数KB | 低 |

### ボトルネック

1. **ファイルI/O**: 一時ファイルの作成・削除（特に非ASCIIパス対応）
2. **スレッド待機**: 順次終了による遅延（並列終了推奨）
3. **正規表現**: 大量テキスト処理時（既に最適化済み）

---

## 🔒 セキュリティ評価

### セキュリティスコア: 90/100

#### 実装済みの対策

✅ **パストラバーサル対策**:
- `Validator.validate_file_path()` による検証
- `os.path.realpath()` による正規化
- ディレクトリトラバーサルチェック

✅ **入力検証**:
- AppSettings の型・範囲検証
- モデル名のホワイトリスト検証
- FFmpegパスの許可リスト検証（改善の余地あり）

✅ **リソース制限**:
- タイムアウト設定
- メモリ使用量監視（psutil）

#### 改善が必要な領域

⚠️ **FFmpegパス検証**: startswith() による不完全なチェック（Critical #4）

⚠️ **TOCTOU脆弱性**: is_file_ready() の競合状態（Critical #3）

---

## 🧵 スレッド安全性評価

### スレッド安全性スコア: 78/100

#### スレッドセーフな実装

✅ **AppSettings**: RLock使用、アトミック操作

✅ **BatchTranscriptionWorker**: threading.Lock使用、_engine_lock

✅ **MainWindow.processing_files**: processing_files_lock使用

#### 改善が必要な領域

⚠️ **FolderMonitor.processed_files**: ロックなし（複数スレッドからアクセスされる可能性）

⚠️ **TranscriptionEngine._temp_files**: ロックなし（複数スレッドから呼ばれる可能性は低いが念のため）

---

## 📋 推奨アクションプラン

### Phase 1: Critical Fixes (1-2日)

1. ✅ PyQt5/PySide6混在の修正（#1）
2. ✅ logger未初期化の修正（#2）
3. ✅ TOCTOU脆弱性の修正（#3）
4. ✅ FFmpegパス検証の強化（#4）

### Phase 2: Warnings (3-5日)

5. ⚠️ タイムアウトの動的調整（#5）
6. ⚠️ 処理中ファイルのTTL実装（#6）
7. ⚠️ 正規表現パターンのLRUキャッシュ（#7）
8. ⚠️ 一時ファイルの積極的クリーンアップ（#8）
9. ⚠️ スレッド終了の並列化（#9）
10. ⚠️ フルパスベースの処理済み判定（#10）

### Phase 3: Improvements (1週間)

11. 🟢 エラーハンドリングコードの統一（#11）
12. 🟢 psutilの明示的なログ（#12）
13. 🟢 TransformersEngineのドキュメント改善（#13）
14. 🟢 UI定数の完全集約（#14）
15. 🟢 設定ファイルのバックアップ（#15）

---

## 🎯 総括

KotobaTranscriberは全体的に**高品質なコードベース**を持ち、特に以下の点で優れています:

### 優れている点
- ✅ 包括的なカスタム例外階層
- ✅ パストラバーサル対策の実装
- ✅ スレッドセーフな設定管理
- ✅ リソースクリーンアップの意識
- ✅ 正規表現パターンの最適化

### 改善が必要な点
- 🔴 PyQt5/PySide6の混在（クラッシュリスク）
- 🔴 TOCTOU脆弱性（ファイル処理）
- 🟡 メモリリークの可能性（処理中ファイル管理）
- 🟡 スレッド終了の最適化

### 推奨事項
1. **即座にCritical Issuesを修正** - 安定性とセキュリティに直結
2. **Warningsを段階的に改善** - パフォーマンスと長期安定性向上
3. **Suggestionsは優先度に応じて実装** - コード保守性の向上
4. **継続的なコードレビュー** - 新機能追加時の品質維持

---

**レビュー完了日**: 2025-10-19
**次回レビュー推奨日**: Critical修正後、1週間以内
