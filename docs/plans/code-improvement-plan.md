# KotobaTranscriber コード改善実装計画

**作成日**: 2026-02-12
**目的**: 包括的コードレビューで発見された Critical/High 優先度の問題を修正

---

## 概要

包括的なレビュー（セキュリティ、並行性、コード品質、アーキテクチャ）の結果、48件の問題を発見。
このプランでは、Critical (P0) と High (P1) の16件を優先的に修正します。

---

## Phase 1: Critical セキュリティ修正 (P0)

### Task 1.1: WebSocket認証のトークンURL露出修正

**現状の問題**:
```python
# src/api/auth.py:52-55
def verify_websocket_token(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token", "")  # ❌ URL履歴に記録される
    return secrets.compare_digest(token, API_TOKEN)
```

**セキュリティリスク**:
- トークンがクエリパラメータ `?token=xxx` として URL に含まれる
- ブラウザ履歴、プロキシログ、サーバーログに平文で記録
- HTTPS/WSS 使用時もログには残る
- トークン漏洩時にセッション乗っ取りが容易

**要件**:
1. WebSocket ハンドシェイク時に `Authorization: Bearer <token>` ヘッダを使用
2. Starlette の WebSocket は初期 HTTP リクエストでヘッダアクセス可能
3. 既存の `verify_websocket_token()` 関数を修正
4. `src/api/websocket.py` の `ConnectionManager.connect()` でヘッダベース認証を使用
5. エラーメッセージは汎用的（トークン値を露出しない）

**実装**:
```python
# src/api/auth.py に追加
def verify_websocket_token_from_header(websocket: WebSocket) -> bool:
    """WebSocket接続時のトークン検証（Authorizationヘッダ）"""
    auth_header = websocket.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header[7:].strip()
    if not token or len(token) < 20:
        return False
    return secrets.compare_digest(token, API_TOKEN)
```

**テスト要件**:
- `tests/test_api/test_websocket_auth.py` を更新
- Authorization ヘッダなしで接続拒否
- 正しいトークンで接続成功
- 不正なトークンで接続拒否
- クエリパラメータでの接続は拒否（後方互換性なし）

**影響範囲**:
- `src/api/auth.py` - 関数追加/修正
- `src/api/websocket.py` - 認証呼び出し変更
- `tests/test_api/test_websocket_auth.py` - テスト更新
- フロントエンド（今後の Tauri 実装で対応）

**完了条件**:
- WebSocket 接続が Authorization ヘッダのみで認証
- クエリパラメータ方式が削除
- テスト全パス（既存 + 新規）
- git commit

---

### Task 1.2: Token生成とローテーション機構追加

**現状の問題**:
```python
# src/api/auth.py:16
API_TOKEN: str = secrets.token_urlsafe(32)  # モジュール読み込み時に一度だけ生成
```

**セキュリティリスク**:
- トークンがプロセス起動時に一度だけ生成
- 再生成メカニズムなし
- 長時間運用で同一トークンの使用期間が長い
- トークン漏洩時にプロセス再起動まで有効

**要件**:
1. トークンローテーション機構を実装
2. TTL（Time-To-Live）ベースで自動更新（デフォルト: 1時間）
3. 古いトークンは猶予期間（5分）で無効化
4. Tauri ↔ API 間の安全なトークン交換プロトコル
5. 環境変数 `KOTOBA_TOKEN_TTL_MINUTES` で TTL 設定可能

**実装**:
```python
# src/api/auth.py に追加
import time
from typing import Tuple

class TokenManager:
    """トークンのライフサイクル管理"""

    def __init__(self, ttl_minutes: int = 60, grace_period_minutes: int = 5):
        self._current_token: str = secrets.token_urlsafe(32)
        self._previous_token: Optional[str] = None
        self._token_created_at: float = time.time()
        self._ttl_seconds = ttl_minutes * 60
        self._grace_period_seconds = grace_period_minutes * 60
        self._lock = threading.RLock()

    def get_current_token(self) -> str:
        """現在有効なトークンを取得"""
        with self._lock:
            self._rotate_if_needed()
            return self._current_token

    def verify_token(self, token: str) -> bool:
        """トークンの有効性を検証（現在 + 猶予期間内の旧トークン）"""
        with self._lock:
            self._rotate_if_needed()
            if secrets.compare_digest(token, self._current_token):
                return True
            if self._previous_token and secrets.compare_digest(token, self._previous_token):
                # 猶予期間内かチェック
                elapsed = time.time() - self._token_created_at
                if elapsed <= self._grace_period_seconds:
                    return True
            return False

    def _rotate_if_needed(self):
        """TTL経過時にトークンをローテーション"""
        elapsed = time.time() - self._token_created_at
        if elapsed >= self._ttl_seconds:
            self._previous_token = self._current_token
            self._current_token = secrets.token_urlsafe(32)
            self._token_created_at = time.time()
            logger.info("Token rotated (TTL expired)")

# グローバルインスタンス
_token_manager: Optional[TokenManager] = None

def get_token_manager() -> TokenManager:
    global _token_manager
    if _token_manager is None:
        ttl = int(os.environ.get("KOTOBA_TOKEN_TTL_MINUTES", "60"))
        _token_manager = TokenManager(ttl_minutes=ttl)
    return _token_manager
```

**テスト要件**:
- `tests/test_api/test_auth_token_rotation.py` を新規作成
- トークンローテーション（TTL 経過）
- 猶予期間内の旧トークン有効性
- 猶予期間外の旧トークン無効化
- 並行アクセスでの競合なし

**影響範囲**:
- `src/api/auth.py` - TokenManager クラス追加
- `src/api/main.py` - lifespan で TokenManager 初期化
- `tests/test_api/test_auth_token_rotation.py` - 新規テスト

**完了条件**:
- TokenManager 実装完了
- TTL ベースローテーション動作
- 猶予期間が正しく機能
- テスト全パス
- git commit

---

## Phase 2: Critical 並行性修正 (P0)

### Task 2.1: EventBus asyncio.Queue のスレッド安全性強化

**現状の問題**:
```python
# src/api/event_bus.py:79-90
if self._loop and self._loop.is_running():
    try:
        self._loop.call_soon_threadsafe(
            self._put_nowait, queue, event, sub_id
        )
    except RuntimeError:
        logger.debug(f"Event loop closing...")
else:
    # ループ未設定時は直接追加（テスト環境等）
    self._put_nowait(queue, event, sub_id)
```

**並行性リスク**:
- `asyncio.Queue` はスレッドセーフではない（公式ドキュメント）
- 複数ワーカースレッドから同時に `emit()` 呼び出し時に競合
- イベントループ停止直後のレースコンディション

**要件**:
1. すべてのイベント発行を `call_soon_threadsafe()` 経由に統一
2. ループ未設定時は `threading.Queue` にフォールバック
3. テスト環境でもイベントループを使用
4. 既存の CoW スナップショットパターンは維持

**実装**:
```python
# src/api/event_bus.py 修正
class EventBus:
    def __init__(self):
        self._subscribers: Dict[int, asyncio.Queue] = {}
        self._counter = 0
        self._lock = threading.RLock()
        self._snapshot: Optional[list] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._fallback_queues: Dict[int, queue.Queue] = {}  # 新規追加

    def emit(self, event_type: str, data: dict):
        snapshot = self._get_snapshot()
        for sub_id, q in snapshot:
            event = {"type": event_type, "data": data}
            try:
                if self._loop and self._loop.is_running():
                    # asyncio.Queue への追加
                    self._loop.call_soon_threadsafe(
                        self._put_nowait, q, event, sub_id
                    )
                else:
                    # フォールバック: threading.Queue を使用
                    fallback_q = self._fallback_queues.get(sub_id)
                    if fallback_q:
                        fallback_q.put_nowait(event)
            except Exception as e:
                logger.error("Failed to emit event (generic error)")
```

**テスト要件**:
- `tests/test_api/test_event_bus_thread_safety.py` を新規作成
- 複数スレッドからの同時 emit()
- イベントループなし環境でのフォールバック
- イベント順序の保証（FIFO）

**影響範囲**:
- `src/api/event_bus.py` - emit() ロジック修正、フォールバック追加
- `tests/test_api/test_event_bus_thread_safety.py` - 新規テスト

**完了条件**:
- すべての emit() がスレッドセーフ
- フォールバック機構動作
- 既存テスト全パス + 新規テスト
- git commit

---

### Task 2.2: BatchTranscriptionWorker._executor TOCTOU修正

**現状の問題**:
```python
# src/api/workers.py:179-195
def cancel(self):
    logger.info("Batch processing cancellation requested")
    self._cancel_event.set()
    executor = self._executor  # 単一読み取り
    if executor:
        executor.shutdown(wait=False)
```

**並行性リスク**:
- `_executor` は `run()` で動的に割り当て/解放
- キャンセルと実行の間で競合が発生
- executor のスレッドがゾンビ化の可能性

**要件**:
1. `_executor` へのアクセスを `_executor_lock` で保護
2. `run()` メソッドでも同じロックを使用
3. キャンセル時に確実に executor を shutdown
4. デッドロックを避けるためロック順序を統一

**実装**:
```python
# src/api/workers.py 修正
class BatchTranscriptionWorker(threading.Thread):
    def __init__(self, ...):
        ...
        self._executor_lock = threading.RLock()  # 新規追加
        self._executor: Optional[ThreadPoolExecutor] = None

    def cancel(self):
        logger.info("Batch processing cancellation requested")
        self._cancel_event.set()
        with self._executor_lock:
            executor = self._executor
            if executor:
                executor.shutdown(wait=False)

    def run(self):
        try:
            with self._executor_lock:
                self._executor = ThreadPoolExecutor(max_workers=1)

            # 処理ループ
            for file_path in self.file_paths:
                if self._cancel_event.is_set():
                    break
                self._process_single_file(file_path)
        finally:
            with self._executor_lock:
                if self._executor:
                    self._executor.shutdown(wait=True)
                    self._executor = None
```

**テスト要件**:
- `tests/test_api/test_batch_worker_cancel.py` を新規作成
- バッチ処理開始直後のキャンセル
- 処理中のキャンセル
- 複数回のキャンセル呼び出し

**影響範囲**:
- `src/api/workers.py` - BatchTranscriptionWorker に _executor_lock 追加
- `tests/test_api/test_batch_worker_cancel.py` - 新規テスト

**完了条件**:
- cancel() がスレッドセーフ
- リソースリークなし
- テスト全パス
- git commit

---

### Task 2.3: TranscriptionEngine モデル推論の排他制御強化

**現状の問題**:
```python
# src/transcription_engine.py:443-567
with self._model_lock:
    if self.model is None:
        self.load_model()

# 推論（別の場所）
with self._model_lock:
    result = self.model(...)
```

**並行性リスク**:
- `load_model()` と推論の間でロックが解放される
- `is_loaded` フラグが RLock 保護外
- 複数スレッドが同じモデルに推論実行 → PyTorch 内部状態破損

**要件**:
1. モデルロードから推論までをアトミックに実行
2. `is_loaded` フラグチェックもロック内で実施
3. CUDA cache clear は lock 外で実行（性能）
4. 既存の RLock を維持（再入可能性）

**実装**:
```python
# src/transcription_engine.py:443-567 修正
def transcribe(self, audio_path, ...):
    # ... バリデーション処理 ...

    # アトミックなモデルロード + 推論
    with self._model_lock:
        # モデル未ロードなら load_model() 呼び出し
        if self.model is None:
            self.load_model()  # RLock なので再入可能

        # 推論実行（lock 保持したまま）
        result = self.model(
            validated_audio_path,
            batch_size=self.config.get("model.whisper.batch_size", 16),
            ...
        )

    # lock 外で CUDA キャッシュクリア
    if self.device == "cuda":
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

    return result
```

**テスト要件**:
- `tests/test_api/test_transcription_thread_safety.py` を新規作成
- 複数スレッドからの同時 transcribe() 呼び出し
- モデル未ロード状態からの並行呼び出し
- CUDA メモリリークなし（可能なら）

**影響範囲**:
- `src/transcription_engine.py` - transcribe() メソッド修正
- `tests/test_api/test_transcription_thread_safety.py` - 新規テスト

**完了条件**:
- モデル推論がスレッドセーフ
- PyTorch 内部状態破損なし
- テスト全パス
- git commit

---

### Task 2.4: WorkerState.is_alive() 競合修正

**現状の問題**:
```python
# src/api/dependencies.py:109-132
def try_set_batch_worker(self, worker) -> bool:
    with self._lock:
        if self.batch_worker and self.batch_worker.is_alive():
            return False  # ワーカーが動作中
        self.batch_worker = worker
        return True
```

**並行性リスク**:
- `is_alive()` の戻り値の信頼性が不確定
- 終了直前のワーカーで複数リクエストが通過
- 複数バッチが同時実行される可能性

**要件**:
1. `batch_worker` が None でない場合は `is_alive()` をチェック
2. ワーカー終了後は明示的に None に設定
3. try_set の戻り値を caller 側で確認
4. API ルーターで 409 Conflict を正しく返す

**実装**:
```python
# src/api/dependencies.py 修正
def try_set_batch_worker(self, worker) -> bool:
    """バッチワーカーを設定（既存ワーカーが alive なら失敗）"""
    with self._lock:
        # 既存ワーカーが存在し、かつまだ生きている場合は拒否
        if self.batch_worker is not None and self.batch_worker.is_alive():
            return False
        # 古いワーカーを明示的にクリア
        self.batch_worker = worker
        return True

def clear_batch_worker(self):
    """バッチワーカーをクリア（終了後に呼び出す）"""
    with self._lock:
        self.batch_worker = None
```

```python
# src/api/routers/transcription.py 修正
@router.post("/batch", response_model=BatchTranscriptionResponse)
async def start_batch_transcription(...):
    worker_state = get_worker_state()

    # ワーカー作成
    worker = BatchTranscriptionWorker(...)

    # ワーカー設定試行
    if not worker_state.try_set_batch_worker(worker):
        raise HTTPException(
            status_code=409,
            detail="バッチ処理が既に実行中です"
        )

    worker.start()

    # 終了後のクリーンアップを登録
    def cleanup():
        worker.join(timeout=1)
        worker_state.clear_batch_worker()

    threading.Thread(target=cleanup, daemon=True).start()

    return BatchTranscriptionResponse(...)
```

**テスト要件**:
- `tests/test_api/test_worker_state_concurrency.py` を新規作成
- 同時バッチリクエスト → 2つ目が 409
- ワーカー終了直前の競合
- clear_batch_worker() の動作確認

**影響範囲**:
- `src/api/dependencies.py` - clear_batch_worker() 追加
- `src/api/routers/transcription.py` - クリーンアップロジック追加
- `tests/test_api/test_worker_state_concurrency.py` - 新規テスト

**完了条件**:
- 複数バッチの同時実行が防止される
- 409 エラーが正しく返る
- テスト全パス
- git commit

---

## Phase 3: High Priority 実装改善 (P1)

### Task 3.1: ワーカーコード重複の解消 - 共通基底クラス抽出

**現状の問題**:
- `src/workers.py` (528行) と `src/api/workers.py` (353行) で重複
- `TranscriptionWorker.run()` と `BatchTranscriptionWorker.process_single_file()` が類似
- エラーハンドリング体系が重複
- 保守コスト高（バグ修正が2箇所必要）

**要件**:
1. 共通モジュール `src/transcription_worker_base.py` を作成
2. `TranscriptionLogic` クラスで共通処理を抽出
3. Qt版（`src/workers.py`）と API版（`src/api/workers.py`）から継承
4. シグナル/EventBus の通知部分は各実装に残す
5. 既存の動作を完全に維持

**実装**:
```python
# src/transcription_worker_base.py 新規作成
"""TranscriptionWorker の共通ロジック"""

from pathlib import Path
from typing import Optional, Callable, Dict, Any
import logging

from transcription_engine import TranscriptionEngine
from exceptions import *
from validator import Validator

logger = logging.getLogger(__name__)

class TranscriptionLogic:
    """文字起こし処理の共通ロジック（Qt/API 非依存）"""

    def __init__(self,
                 audio_path: str,
                 enable_diarization: bool = False,
                 enable_llm_correction: bool = False,
                 llm_provider: Optional[str] = None,
                 progress_callback: Optional[Callable[[int], None]] = None,
                 error_callback: Optional[Callable[[str], None]] = None):
        """
        Args:
            audio_path: 音声ファイルパス
            enable_diarization: 話者分離を有効化
            enable_llm_correction: LLM補正を有効化
            llm_provider: LLMプロバイダ ("local", "claude", "openai")
            progress_callback: 進捗通知コールバック progress_callback(percentage)
            error_callback: エラー通知コールバック error_callback(message)
        """
        self.audio_path = audio_path
        self.enable_diarization = enable_diarization
        self.enable_llm_correction = enable_llm_correction
        self.llm_provider = llm_provider
        self._progress_callback = progress_callback
        self._error_callback = error_callback

    def process(self) -> Optional[str]:
        """
        文字起こし処理を実行

        Returns:
            成功時: 文字起こし結果テキスト
            失敗時: None
        """
        try:
            # バリデーション
            self._notify_progress(5)
            validated_path = Validator.validate_file_path(
                self.audio_path,
                must_exist=True
            )

            # エンジン初期化
            self._notify_progress(10)
            engine = TranscriptionEngine()

            # モデルロード
            self._notify_progress(20)
            if not engine.is_loaded:
                engine.load_model()

            # 文字起こし実行
            self._notify_progress(40)
            result = engine.transcribe(
                validated_path,
                enable_diarization=self.enable_diarization
            )

            text = result.get("text", "")
            self._notify_progress(70)

            # テキスト整形（オプション）
            if self.enable_llm_correction and text:
                self._notify_progress(80)
                text = self._apply_llm_correction(text)

            self._notify_progress(100)
            return text

        except ValidationError as e:
            error_msg = f"ファイルパスが不正です"
            logger.error(f"Validation error: {e}")
            self._notify_error(error_msg)
            return None
        except ModelLoadError as e:
            error_msg = "モデルのロードに失敗しました"
            logger.error(f"Model load error: {e}")
            self._notify_error(error_msg)
            return None
        except TranscriptionError as e:
            error_msg = "文字起こし処理中にエラーが発生しました"
            logger.error(f"Transcription error: {e}")
            self._notify_error(error_msg)
            return None
        except Exception as e:
            error_msg = "予期しないエラーが発生しました"
            logger.error(f"Unexpected error: {e}", exc_info=True)
            self._notify_error(error_msg)
            return None

    def _notify_progress(self, percentage: int):
        """進捗を通知"""
        if self._progress_callback:
            self._progress_callback(percentage)

    def _notify_error(self, message: str):
        """エラーを通知"""
        if self._error_callback:
            self._error_callback(message)

    def _apply_llm_correction(self, text: str) -> str:
        """LLM補正を適用（実装は各サブクラスで）"""
        # TODO: LLM補正ロジックを実装
        return text
```

```python
# src/workers.py 修正（Qt版）
from transcription_worker_base import TranscriptionLogic

class TranscriptionWorker(QThread):
    """Qt Signal版ワーカー"""
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, audio_path: str, ...):
        QThread.__init__(self)
        self.audio_path = audio_path
        # ... オプション設定 ...

    def run(self):
        # 共通ロジックを使用
        logic = TranscriptionLogic(
            audio_path=self.audio_path,
            enable_diarization=self.enable_diarization,
            progress_callback=self._on_progress,
            error_callback=self._on_error
        )

        result = logic.process()

        if result is not None:
            self.finished.emit(result)

    def _on_progress(self, percentage: int):
        self.progress.emit(percentage)

    def _on_error(self, message: str):
        self.error.emit(message)
```

```python
# src/api/workers.py 修正（API版）
from transcription_worker_base import TranscriptionLogic

class TranscriptionWorker(threading.Thread):
    """EventBus版ワーカー"""

    def __init__(self, audio_path: str, event_bus=None, ...):
        threading.Thread.__init__(self)
        self.audio_path = audio_path
        self._bus = event_bus or get_event_bus()
        # ... オプション設定 ...

    def run(self):
        # 共通ロジックを使用
        logic = TranscriptionLogic(
            audio_path=self.audio_path,
            enable_diarization=self.enable_diarization,
            progress_callback=self._on_progress,
            error_callback=self._on_error
        )

        result = logic.process()

        if result is not None:
            self._bus.emit("transcription.finished", {"text": result})

    def _on_progress(self, percentage: int):
        self._bus.emit("transcription.progress", {"value": percentage})

    def _on_error(self, message: str):
        self._bus.emit("transcription.error", {"message": message})
```

**テスト要件**:
- 既存テスト全パス（動作保証）
- `tests/test_transcription_worker_base.py` を新規作成
- TranscriptionLogic 単体テスト
- Qt版/API版で同じ動作確認

**影響範囲**:
- `src/transcription_worker_base.py` - 新規作成（約200行）
- `src/workers.py` - TranscriptionWorker/BatchTranscriptionWorker 簡略化
- `src/api/workers.py` - 同上
- `tests/test_transcription_worker_base.py` - 新規テスト

**完了条件**:
- 共通基底クラス実装完了
- Qt版/API版が基底クラスを使用
- 既存テスト全パス
- コード削減量: 約150-200行
- git commit

---

### Task 3.2: モジュール依存の整理 - folder_monitor.py → constants.py 直接参照

**現状の問題**:
```python
# src/folder_monitor.py:14
from workers import SharedConstants  # ❌ Qt版 workers 経由

# src/enhanced_folder_monitor.py:15
from workers import SharedConstants  # ❌ 同上
```

**アーキテクチャリスク**:
- `folder_monitor.py` は Qt非依存のはずだが、Qt版 `workers.py` に依存
- `SharedConstants` は `src/constants.py` で定義（Qt非依存）
- 不要な結合が発生

**要件**:
1. `folder_monitor.py` を `constants.py` から直接インポート
2. `enhanced_folder_monitor.py` も同様に修正
3. `workers.py` の再エクスポートは維持（後方互換性）
4. 既存の動作を完全に維持

**実装**:
```python
# src/folder_monitor.py:14 修正
- from workers import SharedConstants
+ from constants import SharedConstants

# src/enhanced_folder_monitor.py:15 修正
- from workers import SharedConstants
+ from constants import SharedConstants
```

**テスト要件**:
- 既存テスト全パス
- インポートエラーなし

**影響範囲**:
- `src/folder_monitor.py` - インポート1行変更
- `src/enhanced_folder_monitor.py` - インポート1行変更

**完了条件**:
- フォルダ監視が constants.py を直接参照
- 既存テスト全パス
- git commit

---

## 実装順序

```
Phase 1 (Critical セキュリティ)
├─ Task 1.1: WebSocket認証修正          (2-3時間)
└─ Task 1.2: Token ローテーション        (3-4時間)
    └─ Phase 1 完了: git commit "security: Critical セキュリティ修正完了"

Phase 2 (Critical 並行性)
├─ Task 2.1: EventBus スレッド安全性     (2-3時間)
├─ Task 2.2: BatchWorker TOCTOU修正      (1-2時間)
├─ Task 2.3: TranscriptionEngine 排他制御 (2-3時間)
└─ Task 2.4: WorkerState 競合修正         (1-2時間)
    └─ Phase 2 完了: git commit "concurrency: Critical 並行性修正完了"

Phase 3 (High Priority 実装改善)
├─ Task 3.1: ワーカーコード重複解消      (4-5時間)
└─ Task 3.2: モジュール依存整理          (30分)
    └─ Phase 3 完了: git commit "refactor: High Priority 実装改善完了"
```

**総見積もり時間**: 18-25時間

---

## 検証基準

各 Phase 完了時に以下を確認：

### 1. テスト
```bash
pytest tests/ -v --cov=src --cov-report=term
# カバレッジ >= 77% (現行維持)
# 全テストパス
```

### 2. コード品質
```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/
```

### 3. セキュリティ
```bash
bandit -r src/
# Critical/High の新規問題なし
```

### 4. git 履歴
- 各 Phase で1つの論理的コミット
- コミットメッセージは日本語
- Co-Authored-By: Claude を含む

---

## 成功条件

1. ✅ 全 Critical (P0) 問題が修正される
2. ✅ 全 High (P1) 主要問題が修正される
3. ✅ テストカバレッジが維持される (≥77%)
4. ✅ 既存機能が完全に動作する
5. ✅ 新規テストが追加される (約7ファイル)
6. ✅ コード削減量: 約150-200行

---

## 除外事項（今回対応しない）

以下は Medium (P2) / Low (P3) 問題として別計画で対応：

- エクスポーター重複解消
- broad except ハンドラの詳細化
- dark_theme.py の超長関数分割
- テストカバレッジ拡張（transcription_engine.py など）
- mypy 型チェック改善
- MEMORY.md ドキュメント更新
