# KotobaTranscriber アイコン仕様

## デザインコンセプト

KotobaTranscriberのアプリケーションアイコンは、音声文字起こしの本質を視覚的に表現しています。

### デザイン要素

1. **グラデーション背景**
   - 青 (RGB: 70, 130, 255) から紫 (RGB: 138, 43, 226) への滑らかなグラデーション
   - モダンで親しみやすい印象を与える配色

2. **音声波形バー**
   - 3本の白いバー（左・中・右）
   - 異なる高さで音声の動きを表現
   - 角丸処理による柔らかな印象

3. **日本語テキスト「文」**
   - 文字起こしを象徴する日本語の文字
   - 白色（不透明度 255）で視認性を確保
   - 影付き（立体感）

4. **円形ボーダー**
   - 白い円形の枠線
   - アイコン全体を引き締める効果

## 技術仕様

### ファイル形式

- **メインアイコン**: `icon.ico` (Windows ICO形式)
- **プレビュー**: `icon_preview.png` (PNG形式、256x256px)

### 含まれるサイズ

ICOファイルには以下の6つのサイズが含まれています：

- 16x16px - タスクバー、小アイコン
- 32x32px - ウィンドウタイトルバー
- 48x48px - フォルダ表示
- 64x64px - 大アイコン表示
- 128x128px - 高解像度ディスプレイ
- 256x256px - 最高品質プレビュー

## 使用箇所

### アプリケーション内

1. **メインウィンドウ** (`src/main.py`)
   ```python
   icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
   self.setWindowIcon(QIcon(icon_path))
   ```

2. **監視アプリウィンドウ** (`src/monitor_app.py`)
   ```python
   icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.ico')
   self.setWindowIcon(QIcon(icon_path))
   ```

3. **システムトレイアイコン** (`src/monitor_app.py`)
   ```python
   self.tray_icon.setIcon(QIcon(icon_path))
   ```

### ビルド設定

- `build.spec`: PyInstallerメインビルド
- `build_backend.spec`: バックエンドビルド
- `build_v2.2_pyqt5.spec`: レガシービルド

すべてのビルド設定で `icon='icon.ico'` として参照されています。

## アイコンの再生成

アイコンを再生成する場合は、`create_icon.py` スクリプトを使用します：

```bash
python create_icon.py
```

### 依存パッケージ

- Pillow (PIL) - 画像生成ライブラリ

### カスタマイズ

`create_icon.py` の以下のパラメータを変更することで、デザインをカスタマイズできます：

- **グラデーション色**: `r`, `g`, `b` の計算式を変更
- **波形バーの高さ**: `bars` リストの値を調整
- **テキスト**: `text = "文"` を変更（他の漢字も可能）
- **フォント**: `font_paths` リストにフォントパスを追加

## デザインガイドライン

アイコンを変更する際は、以下の原則を維持してください：

1. **視認性**: 小サイズ（16x16）でも識別可能
2. **ブランド一貫性**: 青紫系のカラースキームを維持
3. **シンプルさ**: 詳細すぎるデザインを避ける
4. **用途の明確さ**: 音声文字起こしを連想させるデザイン

## ライセンス

このアイコンは KotobaTranscriber プロジェクトの一部であり、プロジェクトと同じライセンスが適用されます。
