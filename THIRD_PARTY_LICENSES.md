# サードパーティライセンス

KotobaTranscriberは以下のオープンソースソフトウェアを使用しています。

---

## GUIフレームワーク

### PySide6
- **ライセンス**: LGPL v3
- **著作権**: Qt Company
- **用途**: アプリケーションのGUI
- **URL**: https://www.qt.io/qt-for-python
- **商用利用**: 可能（動的リンク使用時）

---

## AI/機械学習

### PyTorch
- **ライセンス**: BSD-3-Clause
- **著作権**: Facebook, Inc. and its affiliates
- **用途**: 深層学習フレームワーク
- **URL**: https://pytorch.org/
- **商用利用**: 可能

### Transformers (Hugging Face)
- **ライセンス**: Apache 2.0
- **著作権**: Hugging Face, Inc.
- **用途**: 事前学習モデルの利用
- **URL**: https://github.com/huggingface/transformers
- **商用利用**: 可能

### Kotoba-Whisper
- **ライセンス**: Apache 2.0
- **著作権**: Kotoba Technologies, Asahi Ushio
- **用途**: 日本語音声認識モデル
- **URL**: https://huggingface.co/kotoba-tech/kotoba-whisper-v2.2
- **商用利用**: 可能

### Faster-Whisper
- **ライセンス**: MIT
- **著作権**: Guillaume Klein
- **用途**: 高速音声認識エンジン
- **URL**: https://github.com/guillaumekln/faster-whisper
- **商用利用**: 可能

### SpeechBrain
- **ライセンス**: Apache 2.0
- **著作権**: SpeechBrain Team
- **用途**: 話者分離
- **URL**: https://speechbrain.github.io/
- **商用利用**: 可能

---

## 音声処理

### librosa
- **ライセンス**: ISC License
- **著作権**: Brian McFee
- **用途**: 音声分析
- **URL**: https://librosa.org/
- **商用利用**: 可能

### soundfile
- **ライセンス**: BSD-3-Clause
- **著作権**: Bastian Bechtold
- **用途**: 音声ファイルI/O
- **URL**: https://github.com/bastibe/python-soundfile
- **商用利用**: 可能

### pydub
- **ライセンス**: MIT
- **著作権**: James Robert
- **用途**: 音声ファイル変換
- **URL**: https://github.com/jiaaro/pydub
- **商用利用**: 可能

---

## 科学計算

### NumPy
- **ライセンス**: BSD-3-Clause
- **著作権**: NumPy Developers
- **用途**: 数値計算
- **URL**: https://numpy.org/
- **商用利用**: 可能

### pandas
- **ライセンス**: BSD-3-Clause
- **著作権**: pandas Development Team
- **用途**: データ処理
- **URL**: https://pandas.pydata.org/
- **商用利用**: 可能

### scikit-learn
- **ライセンス**: BSD-3-Clause
- **著作権**: scikit-learn developers
- **用途**: 機械学習（話者分離のクラスタリング）
- **URL**: https://scikit-learn.org/
- **商用利用**: 可能

---

## ドキュメント処理

### python-docx
- **ライセンス**: MIT
- **著作権**: Steve Canny
- **用途**: Word文書生成
- **URL**: https://github.com/python-openxml/python-docx
- **商用利用**: 可能

### openpyxl
- **ライセンス**: MIT
- **著作権**: Eric Gazoni, Charlie Clark
- **用途**: Excel文書処理
- **URL**: https://openpyxl.readthedocs.io/
- **商用利用**: 可能

---

## ユーティリティ

### tqdm
- **ライセンス**: MIT + MPL-2.0
- **著作権**: tqdm developers
- **用途**: プログレスバー
- **URL**: https://github.com/tqdm/tqdm
- **商用利用**: 可能

### pywin32
- **ライセンス**: PSF License (Python Software Foundation)
- **著作権**: Mark Hammond
- **用途**: Windows API連携
- **URL**: https://github.com/mhammond/pywin32
- **商用利用**: 可能

---

## 外部ツール

### FFmpeg
- **ライセンス**: LGPL v2.1+ または GPL v2+
- **著作権**: FFmpeg developers
- **用途**: 動画ファイルからの音声抽出
- **URL**: https://ffmpeg.org/
- **商用利用**: 可能（動的リンク使用時）
- **備考**: 本アプリケーションはFFmpegを外部プロセスとして実行しており、動的リンクを使用しています。

---

## ライセンス要約

すべての依存パッケージは以下の条件で商用利用可能です：

- ✅ **無償で商用利用可能**
- ✅ **ソースコード開示不要**（動的リンク使用時）
- ✅ **改変・再配布可能**

ただし、各ライセンスに基づく著作権表示とライセンス文書の同梱が必要です。

---

## クレジット

本アプリケーションのアイコンは自作です。

開発: Claude Code + Human Collaboration

最終更新: 2025-10-19
