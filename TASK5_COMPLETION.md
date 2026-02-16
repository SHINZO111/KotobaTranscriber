# Task 5: システムトレイの統合 - 完了報告

## 実装概要

unified_app.py のシステムトレイ機能を強化し、各タブとの連携を実装しました。

## 実装内容

### 1. メニュー項目の拡張

**実装箇所**: `F:\KotobaTranscriber\src\unified_app.py` (lines 141-187)

- **追加メニュー**:
  - 「フォルダ監視開始」/「フォルダ監視停止」（動的に切り替え）
  - セパレータでグループ化

**変更点**:
```python
# トレイメニュー作成
self.tray_menu = QMenu()

show_action = QAction("表示", self)
hide_action = QAction("非表示", self)
self.tray_menu.addSeparator()

# 新規: フォルダ監視トグルアクション
self.monitor_toggle_action = QAction("フォルダ監視開始", self)
self.monitor_toggle_action.triggered.connect(self.toggle_folder_monitor_from_tray)
self.tray_menu.addAction(self.monitor_toggle_action)

self.tray_menu.addSeparator()
quit_action = QAction("終了", self)
```

### 2. 通知機能の実装

**実装箇所**: `F:\KotobaTranscriber\src\unified_app.py` (lines 241-267)

**新規メソッド**:
- `show_tray_notification(title, message, icon_type)` - 汎用通知メソッド
- `on_file_transcription_completed()` - ファイル処理完了時の通知
- `on_monitor_started()` - フォルダ監視開始時の通知
- `on_monitor_stopped()` - フォルダ監視停止時の通知

**通知タイプ**:
- ファイル処理完了: `QSystemTrayIcon.Information`
- 監視開始: `QSystemTrayIcon.Information` (フォルダ名付き)
- 監視停止: `QSystemTrayIcon.Information`
- エラー: `QSystemTrayIcon.Critical` (将来の拡張用)

### 3. 各タブとの連携

#### file_tab (ファイル処理タブ)

**変更箇所**: `F:\KotobaTranscriber\src\tabs\file_tab.py`

1. **新規シグナル追加** (line 57):
```python
transcription_completed = Signal()
```

2. **完了時にシグナル発火** (line 399):
```python
def _finalize_transcription(self, formatted_text):
    # ... 既存の処理 ...

    # 完了シグナルを送信（トレイ通知用）
    self.transcription_completed.emit()

    QMessageBox.information(self, "完了", "文字起こしが完了しました")
```

#### monitor_tab (フォルダ監視タブ)

**変更箇所**: `F:\KotobaTranscriber\src\tabs\monitor_tab.py`

1. **新規シグナル追加** (lines 56-58):
```python
monitoring_started = Signal()
monitoring_stopped = Signal()
```

2. **監視開始時にシグナル発火** (line 315):
```python
def toggle_folder_monitor(self):
    # ... 監視開始処理 ...

    # 開始シグナルを送信（トレイ通知用）
    self.monitoring_started.emit()
```

3. **監視停止時にシグナル発火** (line 285):
```python
def toggle_folder_monitor(self):
    # ... 監視停止処理 ...

    # 停止シグナルを送信（トレイ通知用）
    self.monitoring_stopped.emit()
```

#### unified_app (統合アプリ)

**変更箇所**: `F:\KotobaTranscriber\src\unified_app.py` (lines 208-229)

1. **シグナル接続** (lines 208-221):
```python
def connect_tab_signals(self):
    """タブのシグナルをトレイ通知に接続"""
    # file_tab: 文字起こし完了通知
    if hasattr(self, "file_tab"):
        self.file_tab.transcription_completed.connect(self.on_file_transcription_completed)

    # monitor_tab: 監視開始/停止通知
    if hasattr(self, "monitor_tab"):
        self.monitor_tab.monitoring_started.connect(self.on_monitor_started)
        self.monitor_tab.monitoring_stopped.connect(self.on_monitor_stopped)
```

2. **トレイからのフォルダ監視制御** (lines 223-239):
```python
def toggle_folder_monitor_from_tray(self):
    """トレイメニューからフォルダ監視をトグル"""
    if hasattr(self, "monitor_tab"):
        self.monitor_tab.toggle_folder_monitor()
        self.update_monitor_tray_menu()

def update_monitor_tray_menu(self):
    """フォルダ監視メニュー項目を更新"""
    if hasattr(self, "monitor_tab"):
        is_monitoring = self.monitor_tab.folder_monitor and self.monitor_tab.folder_monitor.isRunning()
        if is_monitoring:
            self.monitor_toggle_action.setText("フォルダ監視停止")
        else:
            self.monitor_toggle_action.setText("フォルダ監視開始")
```

## 動作検証

### テストスクリプト

**ファイル**: `F:\KotobaTranscriber\test_tray_integration.py`

**検証内容**:
1. ✓ トレイメニュー項目の存在確認
2. ✓ シグナルの存在確認
3. ✓ トレイアイコンメソッドの存在確認
4. ✓ トレイ通知の送信テスト
5. ✓ 各シグナルの発火テスト

**実行結果**:
```
=== システムトレイ統合テスト開始 ===
✓ トレイメニュー項目OK
✓ シグナル存在OK
✓ トレイアイコンメソッドOK
✓ トレイ通知送信OK
✓ 文字起こし完了シグナルOK
✓ 監視開始シグナルOK
✓ 監視停止シグナルOK
=== システムトレイ統合テスト完了 ===
```

すべてのテストが成功しました。

## ファイル変更まとめ

| ファイル | 変更内容 | 行数変更 |
|---------|---------|---------|
| `src/unified_app.py` | トレイメニュー拡張、通知機能追加、シグナル接続 | +80行 |
| `src/tabs/file_tab.py` | transcription_completed シグナル追加 | +3行 |
| `src/tabs/monitor_tab.py` | monitoring_started/stopped シグナル追加 | +6行 |
| `test_tray_integration.py` | 動作検証テストスクリプト作成 | +80行 (新規) |

## 完了基準のチェック

- [x] トレイメニューにフォルダ監視開始/停止追加
- [x] 通知機能実装
  - [x] ファイル処理完了通知
  - [x] フォルダ監視開始通知
  - [x] フォルダ監視停止通知
- [x] 各タブとの連携
  - [x] file_tab: transcription_completed Signal 実装
  - [x] monitor_tab: monitoring_started/stopped Signal 実装
  - [x] unified_app: シグナル接続とハンドラ実装
- [x] 動作確認
  - [x] テストスクリプトで全機能検証済み
  - [x] トレイ通知が正常に表示されることを確認

## 技術的ポイント

### シグナル・スロット パターン

PySide6 のシグナル・スロット機構を活用し、疎結合な設計を実現:
- タブは親ウィンドウの実装を知らない
- 親ウィンドウがシグナルを受信してトレイ通知を表示
- 将来的な機能拡張が容易

### 動的メニュー更新

フォルダ監視の状態に応じてトレイメニュー項目を動的に変更:
```python
if is_monitoring:
    self.monitor_toggle_action.setText("フォルダ監視停止")
else:
    self.monitor_toggle_action.setText("フォルダ監視開始")
```

### トレイアイコン初期化タイミング

`init_tray_icon()` 後に `connect_tab_signals()` を呼び出すことで、タブのシグナルをトレイアイコンのメソッドに確実に接続。

## 次のステップ

Task 6: 設定管理の統合 に進みます。
- 各タブの設定を unified_settings.json に統合
- 設定タブでの一元管理
- 設定変更の即時反映
