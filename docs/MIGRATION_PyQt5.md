# KotobaTranscriber v2.2 PyQt5版 移行ガイド

## 概要

このドキュメントでは、KotobaTranscriberをPySide6からPyQt5に移行する手順を説明します。

## 主な変更点

### 1. インポート変更

**変更前 (PySide6):**
```python
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Signal, Slot
```

**変更後 (PyQt5):**
```python
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
```

### 2. 互換性モジュールの使用

`qt_compat.py`を使用して自動的に適切なバインディングを選択:

```python
from qt_compat import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QPushButton, QLabel,
    Signal, Slot, exec_app
)
```

### 3. exec() → exec_() 変更

**変更前:**
```python
dialog.exec()
app.exec()
```

**変更後:**
```python
dialog.exec_()
app.exec_()
```

または互換性関数を使用:
```python
from qt_compat import exec_dialog, exec_app

exec_dialog(dialog)
exit_code = exec_app(app)
```

## 移行手順

### ステップ1: 依存関係の更新

```bash
# requirements.txt更新
# PySide6>=6.5.0  →  PyQt5>=5.15.0

pip uninstall PySide6
pip install PyQt5>=5.15.0
```

### ステップ2: ソースコード変換

```bash
# 自動変換スクリプト実行
python -c "
from qt_compat import migrate_file
import glob

for file in glob.glob('src/*.py'):
    migrate_file(file)
    print(f'Migrated: {file}')
"
```

### ステップ3: 手動修正

自動変換で対応できない部分を手動修正:

1. **Signal定義の変更**
   ```python
   # 変更前
   progress = Signal(int)
   
   # 変更後
   progress = pyqtSignal(int)
   ```

2. **Slotデコレータの変更**
   ```python
   # 変更前
   @Slot(str)
   def on_message(self, msg):
       pass
   
   # 変更後
   @pyqtSlot(str)
   def on_message(self, msg):
       pass
   ```

### ステップ4: ビルド設定更新

```python
# build.spec
hiddenimports = [
    'PyQt5',           # ← PySide6から変更
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    # ...
]
```

## ライセンス注意事項

### PyQt5ライセンス

- **GPL v3**: オープンソースプロジェクト用
- **商用ライセンス**: 商用利用時は別途購入必要

### ソースコード公開義務

GPL v3準拠の場合:
- ソースコードを公開する必要あり
- 同じライセンス(GPL v3)で配布

### 商用利用の場合

1. PyQt5商用ライセンスを購入
2. またはPySide6に戻す（LGPL v3 - より緩やか）

## トラブルシューティング

### 問題1: Signalが動作しない

**症状:**
```
TypeError: connect() failed
```

**解決:**
```python
# pyqtSignalを使用
from PyQt5.QtCore import pyqtSignal

class Worker(QObject):
    finished = pyqtSignal(str)  # SignalではなくpyqtSignal
```

### 問題2: exec()が見つからない

**症状:**
```
AttributeError: 'QDialog' object has no attribute 'exec'
```

**解決:**
```python
# exec_()を使用
dialog.exec_()  # dialog.exec() ではない
```

### 問題3: インポートエラー

**症状:**
```
ModuleNotFoundError: No module named 'PySide6'
```

**解決:**
```bash
pip uninstall PySide6
pip install PyQt5
```

## 自動移行スクリプト

```python
#!/usr/bin/env python3
"""
PySide6 → PyQt5 自動移行スクリプト
"""

import os
import re
import sys

def migrate_directory(directory: str):
    """ディレクトリ内の全Pythonファイルを移行"""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                migrate_file(filepath)

def migrate_file(filepath: str):
    """単一ファイルを移行"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # インポート置換
    replacements = [
        (r'from PySide6\.', 'from PyQt5.'),
        (r'import PySide6', 'import PyQt5'),
        (r'from PyQt5\.QtCore import Signal', 'from PyQt5.QtCore import pyqtSignal as Signal'),
        (r'from PyQt5\.QtCore import Slot', 'from PyQt5.QtCore import pyqtSlot as Slot'),
        (r'(?<!\w)\.exec\(\)', '.exec_()'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Migrated: {filepath}")
    else:
        print(f"Skipped: {filepath}")

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "src"
    migrate_directory(target_dir)
    print("Migration completed!")
```

## 検証手順

### 1. インポートテスト

```python
python -c "from qt_compat import QApplication, Signal, Slot; print('OK')"
```

### 2. 基本UIテスト

```python
python -c "
from qt_compat import QApplication, QLabel
app = QApplication([])
label = QLabel('Test')
label.show()
print('UI OK')
"
```

### 3. Signal/Slotテスト

```python
python -c "
from qt_compat import QObject, Signal, Slot

class Test(QObject):
    sig = Signal(str)
    
    @Slot(str)
    def on_sig(self, msg):
        print(f'Received: {msg}')

t = Test()
t.sig.connect(t.on_sig)
t.sig.emit('Hello')
print('Signal/Slot OK')
"
```

## まとめ

PySide6からPyQt5への移行は主に以下の変更が必要:

1. インポートパスの変更
2. Signal/Slotの名称変更
3. exec() → exec_() の変更
4. ライセンスの確認

`qt_compat.py`を使用することで、両方のバインディングで動作するコードを書くことができます。
