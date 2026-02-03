# KotobaTranscriber v2.1 改善コード導入ガイド

## 概要

このドキュメントでは、KotobaTranscriber v2.1の改善コードの導入方法を説明します。

## 新規ファイル一覧

### 1. device_manager.py
**機能**: マルチデバイス管理（GPU/CPU/MPS自動選択）

**導入方法**:
```python
# transcription_engine.py の置き換え例
from device_manager import DeviceContext

class TranscriptionEngine:
    def load_model(self):
        with DeviceContext(required_memory_mb=4096) as ctx:
            # モデルロード処理
            self.device = ctx.device
            self.dtype = ctx.dtype
```

**依存関係**: `torch`

### 2. memory_optimizer.py
**機能**: メモリ最適化・リーク防止

**導入方法**:
```python
from memory_optimizer import MemoryOptimizer

optimizer = MemoryOptimizer()

with optimizer.optimized_inference("cuda"):
    result = model(input_data)

# メモリ状態チェック
status = optimizer.check_memory()
print(f"Memory usage: {status.rss_mb:.1f}MB")
```

**依存関係**: `torch`, `psutil`

### 3. error_recovery.py
**機能**: エラー自動回復（リトライ・フォールバック）

**導入方法**:
```python
from error_recovery import ErrorRecoveryManager

manager = ErrorRecoveryManager()

def process_with_recovery(file_path):
    def retry_fn():
        return transcribe(file_path)
    
    def fallback_fn():
        return "[文字起こし失敗]"
    
    try:
        return transcribe(file_path)
    except Exception as e:
        result = manager.handle_error(
            e, file_path, retry_fn, fallback_fn
        )
        return result.get('result')
```

**依存関係**: なし

### 4. ui_responsive.py
**機能**: UI応答性改善・非同期処理キュー

**導入方法**:
```python
from ui_responsive import ProcessingQueue, ResponsiveWorker

# 処理キュー使用例
queue = ProcessingQueue(max_workers=2)
queue.add_task("task1", process_file, "file1.wav")
queue.task_finished.connect(on_task_finished)

# ResponsiveWorker使用例
class MyWorker(ResponsiveWorker):
    def run(self):
        for i in range(100):
            if self.check_cancelled():
                return
            self.update_progress(i, f"Processing {i}%")
            time.sleep(0.1)
```

**依存関係**: `PySide6`

### 5. enhanced_folder_monitor.py
**機能**: watchdogベースのイベント駆動監視

**導入方法**:
```python
from enhanced_folder_monitor import AsyncFolderMonitor

monitor = AsyncFolderMonitor(["/path/to/watch"])
monitor.new_files_detected.connect(on_new_files)
monitor.start()

# 処理完了後にマーク
monitor.mark_as_processed(file_path, success=True)
```

**依存関係**: `watchdog`, `PySide6`

### 6. enhanced_subtitle_exporter.py
**機能**: 拡張字幕エクスポート（SRT/VTT/JSON/DOCX）

**導入方法**:
```python
from enhanced_subtitle_exporter import EnhancedSubtitleExporter

exporter = EnhancedSubtitleExporter()

# 単一フォーマット
exporter.export(segments, "output.srt", "srt")

# 複数フォーマット一括
results = exporter.export_auto(
    segments,
    "base_path",
    formats=['srt', 'vtt', 'json', 'docx']
)
```

**依存関係**: `python-docx`（DOCX出力時）

## 依存関係のインストール

```bash
# 必須
pip install torch psutil PySide6

# 推奨
pip install watchdog python-docx

# 完全版
pip install torch psutil PySide6 watchdog python-docx
```

## 統合例

### main_window.py への統合

```python
# 既存のインポートに追加
from device_manager import MultiDeviceManager
from memory_optimizer import MemoryOptimizer
from error_recovery import ErrorRecoveryManager, resilient
from ui_responsive import ProcessingQueue
from enhanced_folder_monitor import AsyncFolderMonitor
from enhanced_subtitle_exporter import EnhancedSubtitleExporter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 新機能の初期化
        self.device_manager = MultiDeviceManager()
        self.memory_optimizer = MemoryOptimizer()
        self.error_recovery = ErrorRecoveryManager()
        self.processing_queue = ProcessingQueue(max_workers=4)
        self.subtitle_exporter = EnhancedSubtitleExporter()
        
        # フォルダ監視の置き換え
        self.folder_monitor = AsyncFolderMonitor()
        
    @resilient(max_retries=3)
    def process_file(self, file_path):
        """エラー回復付きファイル処理"""
        with self.memory_optimizer.optimized_inference("cuda"):
            # 処理実行
            return self.engine.transcribe(file_path)
```

## 設定ファイルの更新

### config.yaml

```yaml
# デバイス設定
device:
  preference: "auto"  # auto, cuda, cpu, mps
  required_memory_mb: 4096
  fallback_to_cpu: true

# メモリ設定
memory:
  warning_threshold_mb: 6144
  critical_threshold_mb: 8192
  enable_gc: true
  gc_interval: 50  # 50ファイルごとにGC

# エラー回復設定
error_recovery:
  max_retries: 3
  retry_delay_base: 2  # 秒
  enable_fallback: true

# UI設定
ui:
  update_interval_ms: 100
  max_queue_workers: 4

# フォルダ監視設定
folder_monitor:
  use_watchdog: true  # falseでポーリング
  check_interval: 1.0  # 秒
  recursive: false

# エクスポート設定
export:
  default_formats: ["srt", "txt"]
  merge_short_segments: true
  min_segment_duration: 1.0
```

## 既存コードとの互換性

| ファイル | 互換性 | 備考 |
|----------|--------|------|
| device_manager.py | ○ | 新規機能、既存コードに影響なし |
| memory_optimizer.py | ○ | コンテキストマネージャとして使用 |
| error_recovery.py | ○ | デコレータとして使用 |
| ui_responsive.py | △ | QThread使用箇所の一部置き換え |
| enhanced_folder_monitor.py | △ | FolderMonitorの置き換え |
| enhanced_subtitle_exporter.py | ○ | SubtitleExporterの拡張 |

## 移行チェックリスト

- [ ] 依存関係のインストール確認
- [ ] 新規ファイルの配置確認
- [ ] 既存コードのバックアップ
- [ ] 段階的な統合テスト
- [ ] エラー回復機能の動作確認
- [ ] メモリ使用量の監視
- [ ] UI応答性の確認

## トラブルシューティング

### watchdogが動作しない
```bash
# ポーリングモードに切り替え
monitor = AsyncFolderMonitor(use_polling=True)
```

### メモリ不足エラー
```python
# バッチサイズ縮小
processor = BatchProcessor(batch_size=1)

# メモリ閾値調整
optimizer = MemoryOptimizer(
    warning_threshold_mb=4096,
    critical_threshold_mb=6144
)
```

### GPU認識されない
```python
# デバイスマネージャで確認
manager = MultiDeviceManager()
print(manager.get_device_list())
```

---

**作成日**: 2026年2月3日
**対象バージョン**: KotobaTranscriber v2.1
