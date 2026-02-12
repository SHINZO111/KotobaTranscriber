# アイコン設定完了ガイド

## 🎨 新しいアイコンについて

KotobaTranscriberに、モダンでプロフェッショナルなアイコンを設定しました。

### デザイン特徴

- **配色**: 青 (RGB: 70, 130, 255) → 紫 (RGB: 138, 43, 226) の美しいグラデーション
- **音声波形**: 3本の白いバーで音声を視覚的に表現
- **日本語文字**: 「文」（もじ/ぶん）で文字起こしを象徴
- **スタイル**: ミニマル、モダン、視認性が高い

## ✅ アイコンが適用される箇所

### 1. メインアプリケーション (`main.py`)
- **ウィンドウタイトルバー**: アイコンが左上に表示
- **タスクバー**: アプリ実行中、タスクバーにアイコン表示
- **Alt+Tab切り替え**: ウィンドウ切り替え時にアイコン表示

**実装箇所**: `src/main.py:118`
```python
icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
if os.path.exists(icon_path):
    self.setWindowIcon(QIcon(icon_path))
```

### 2. 監視アプリケーション (`monitor_app.py`)
- **ウィンドウタイトルバー**: アイコンが左上に表示
- **タスクバー**: アプリ実行中、タスクバーにアイコン表示
- **システムトレイ**: 右下の通知領域にアイコン常駐

**実装箇所**:
- ウィンドウ: `src/monitor_app.py:94`
- システムトレイ: `src/monitor_app.py:249`

```python
# ウィンドウアイコン
icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
if os.path.exists(icon_path):
    self.setWindowIcon(QIcon(icon_path))

# システムトレイアイコン
self.tray_icon.setIcon(QIcon(icon_path))
```

### 3. PyInstallerビルド（実行ファイル）

すべてのビルド設定でアイコンが設定されています：

- **build.spec** (メインビルド): `icon='icon.ico'` (line 189)
- **build_backend.spec** (バックエンド): `icon='icon.ico'` (line 108)
- **build_v2.2_pyqt5.spec** (レガシー): `icon=APP_ICON` (line 207)

実行ファイル (`.exe`) を作成すると、以下で自動的にアイコンが表示されます：
- エクスプローラーでのファイルアイコン
- ショートカットアイコン
- プログラム一覧のアイコン

## 🧪 アイコン表示テスト

### テストスクリプトの実行

新しいアイコンが正しく表示されるかテストできます：

```bash
python test_icon.py
```

### 手動確認手順

1. **メインアプリを起動**
   ```bash
   python src/main.py
   ```
   - ウィンドウタイトルバーのアイコンを確認
   - タスクバーのアイコンを確認

2. **監視アプリを起動**
   ```bash
   python src/monitor_app.py
   ```
   - ウィンドウタイトルバーのアイコンを確認
   - タスクバーのアイコンを確認
   - システムトレイ（右下）のアイコンを確認

3. **ビルドした実行ファイル**
   ```bash
   python build_release.py
   ```
   - ビルド後、`dist/` フォルダ内の `.exe` ファイルのアイコンを確認
   - 実行時のウィンドウアイコンを確認

## 🔄 アイコンの再生成

デザインを変更したい場合は、`create_icon.py` を編集して再実行：

```bash
python create_icon.py
```

### カスタマイズ可能な要素

`create_icon.py` 内で以下を変更できます：

```python
# グラデーションの色
r = int(70 + (138 - 70) * ratio)      # 青 → 紫
g = int(130 + (43 - 130) * ratio)
b = int(255 + (226 - 255) * ratio)

# 波形バーの高さと配置
bars = [
    (0.4, 0.6),   # 左のバー
    (0.2, 1.0),   # 中央のバー（最も高い）
    (0.4, 0.7),   # 右のバー
]

# 表示する日本語文字
text = "文"  # 他の文字に変更可能（例: "話", "音", "声"）
```

## 📁 関連ファイル

- `icon.ico` - メインアイコンファイル（複数サイズ含む）
- `icon_preview.png` - プレビュー用PNG（256x256px）
- `create_icon.py` - アイコン生成スクリプト
- `test_icon.py` - アイコン表示テストスクリプト
- `docs/ICON.md` - アイコン仕様書
- `docs/ICON_SETUP.md` - このファイル（設定ガイド）

## 🎯 確認ポイント

新しいアイコンが正しく適用されているか、以下を確認してください：

- [ ] メインアプリのウィンドウタイトルバーにアイコン表示
- [ ] メインアプリのタスクバーにアイコン表示
- [ ] 監視アプリのウィンドウタイトルバーにアイコン表示
- [ ] 監視アプリのタスクバーにアイコン表示
- [ ] 監視アプリのシステムトレイにアイコン表示
- [ ] アイコンの配色が青→紫のグラデーション
- [ ] 音声波形（3本のバー）が表示
- [ ] 日本語文字「文」が表示
- [ ] 小サイズ（16x16）でも視認可能

## 💡 トラブルシューティング

### アイコンが表示されない

1. **ファイルパスの確認**
   ```python
   import os
   icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
   print(f"Icon path: {icon_path}")
   print(f"Exists: {os.path.exists(icon_path)}")
   ```

2. **アイコンファイルの再生成**
   ```bash
   python create_icon.py
   ```

3. **Windowsのアイコンキャッシュをクリア**
   - エクスプローラーを再起動
   - または、システムを再起動

### アイコンが古いまま

- アプリケーションを完全に終了して再起動
- ビルドした実行ファイルの場合は、再ビルドが必要

### システムトレイにアイコンが表示されない

- 監視アプリ (`monitor_app.py`) のみシステムトレイを使用
- メインアプリ (`main.py`) はシステムトレイ機能なし

## 📚 参考

- [Pillow ドキュメント](https://pillow.readthedocs.io/)
- [PySide6 QIcon](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QIcon.html)
- [PyInstaller Icon設定](https://pyinstaller.org/en/stable/usage.html#icon)
