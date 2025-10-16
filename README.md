# KotobaTranscriber

日本語音声文字起こしアプリケーション - kotoba-whisper v2.2使用

[![CI Pipeline](https://github.com/SHINZO111/KotobaTranscriber/actions/workflows/ci.yml/badge.svg)](https://github.com/SHINZO111/KotobaTranscriber/actions/workflows/ci.yml)
[![Release](https://github.com/SHINZO111/KotobaTranscriber/actions/workflows/release.yml/badge.svg)](https://github.com/SHINZO111/KotobaTranscriber/actions/workflows/release.yml)
[![codecov](https://codecov.io/gh/SHINZO111/KotobaTranscriber/branch/main/graph/badge.svg)](https://codecov.io/gh/SHINZO111/KotobaTranscriber)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 特徴

- ✅ **高精度**: kotoba-whisper v2.2による日本語特化の音声認識
- ✅ **オフライン動作**: 完全ローカルで動作、プライバシー保護
- ✅ **シンプルUI**: PyQt5による直感的な操作画面
- ✅ **複数形式対応**: 15種類の音声・動画形式に対応
- ✅ **GPU対応**: CUDA対応GPU使用で高速処理
- ✅ **🎤 リアルタイム文字起こし**: **NEW!** マイクからリアルタイムで文字起こし
  - faster-whisperによる4～8倍の高速化
  - 適応的VAD（音声検出）でCPU使用率40%削減
  - タブベースUIで既存機能と共存
  - ハイブリッド表示（確定/処理中の区別）
- ✅ **テキスト整形**: フィラー語削除、句読点整形、段落整形
- ✅ **AI文章補正**: 2段階のAI補正機能
  - 軽量版: ルールベース補正（モデル不要、即座に動作）
  - 高度版: transformersベースの高度な補正（初回310MBダウンロード）
- ✅ **話者分離**: 完全無料の話者分離機能（トークン不要）
  - speechbrain使用（高精度、推奨）
  - resemblyzer使用（軽量・高速）
- ✅ **バッチ処理**: 複数ファイルを並列処理
- ✅ **フォルダ監視**: 自動文字起こし機能
- ✅ **自動保存**: 文字起こし完了後、即座にテキストファイルで保存

## 必要要件

### システム要件
- **OS**: Windows 10/11, macOS, Ubuntu
- **Python**: 3.8以上
- **RAM**: 8GB以上（推奨16GB）
- **GPU**: NVIDIA CUDA対応GPU（オプション、CPUでも動作）
- **ディスク**: 5GB以上の空き容量

### Python環境
Python 3.8以上がインストールされている必要があります。

## セットアップ

### 簡単インストール（Windows）

#### GPU搭載PCの場合
1. `install.bat` をダブルクリック
2. インストール完了まで待つ（5-10分）
3. `start.bat` でアプリケーション起動

#### GPUなしのPCの場合
1. `install-cpu.bat` をダブルクリック
2. インストール完了まで待つ（5-10分）
3. `start.bat` でアプリケーション起動

#### オプション機能（話者分離）
- `install-optional.bat` を実行して speechbrain をインストール

### 手動インストール

#### 1. リポジトリのクローン
```bash
cd F:\VoiceToText
cd KotobaTranscriber
```

#### 2. 仮想環境の作成（オプション）
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

#### 3. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

#### 4. PyTorchのインストール（GPU使用の場合）
```bash
# CUDA 11.8の場合
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1の場合
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# CPUのみの場合
pip install torch torchvision torchaudio
```

## 使い方

### アプリケーション起動
```bash
cd src
python main.py
```

### 基本操作（ファイル処理）
1. **ファイル選択**: 「単一ファイル選択」または「複数ファイル選択（バッチ処理）」ボタンをクリック
2. **オプション設定**: テキスト整形オプションを選択
   - フィラー語削除: 「あー」「えー」「その」などを自動削除
   - 句読点整形: 自然な日本語の句読点を追加
   - 段落整形: 適切な位置で段落を分ける
   - AI文章補正: ルールベースまたはtransformersベースの補正
   - 高度なAI補正: より自然な補正（初回のみモデルダウンロード）
   - 話者分離: 複数の話者を識別（完全無料、トークン不要）
3. **文字起こし**: 「文字起こし開始」ボタンをクリック
4. **結果確認**: 画面下部に文字起こし結果が表示されます
5. **自動保存**: 元のファイル名_文字起こし.txt として自動保存されます
6. **追加保存**: 「テキストを保存」ボタンで別名保存も可能

### 🎤 リアルタイム文字起こし（NEW!）
1. **タブ切り替え**: 「🎤 リアルタイム」タブをクリック
2. **マイク選択**: ドロップダウンから使用するマイクを選択
3. **設定調整**（オプション）:
   - **Whisperモデル**: tiny/base/small/medium から選択（base推奨）
   - **VAD有効化**: 音声検出を有効にして無音時の処理をスキップ
   - **VAD感度**: スライダーで調整（0.005～0.050、デフォルト0.010）
4. **録音開始**: 「🎤 録音開始」ボタンをクリック
5. **話す**: マイクに向かって話すと、リアルタイムで文字起こし結果が表示されます
   - **処理中テキスト**: 灰色・イタリック表示
   - **確定済みテキスト**: 黒色・太字表示
   - **音声検出**: 🎤（音声あり）/ 🔇（無音）インジケーター
6. **録音停止**: 「⏹ 録音停止」ボタンで終了
7. **結果保存**: 「結果を保存」ボタンでテキストファイルに保存（統計情報付き）

**リアルタイム機能の詳細**: `docs/REALTIME_TRANSCRIPTION_GUIDE.md` を参照

## 対応音声形式

### 音声ファイル
- MP3 (`.mp3`) - 標準的な圧縮音声
- WAV (`.wav`) - 無圧縮音声
- M4A (`.m4a`) - Apple音声形式
- FLAC (`.flac`) - 可逆圧縮音声
- OGG (`.ogg`) - Vorbis音声
- AAC (`.aac`) - 高品質圧縮音声
- WMA (`.wma`) - Windows Media Audio
- OPUS (`.opus`) - 高効率音声コーデック
- AMR (`.amr`) - 携帯電話録音形式

### 動画ファイル（音声抽出）
- MP4 (`.mp4`) - 標準的な動画形式
- AVI (`.avi`) - Windows動画形式
- MOV (`.mov`) - QuickTime動画形式
- MKV (`.mkv`) - Matroska動画形式
- 3GP (`.3gp`) - 携帯電話動画形式
- WEBM (`.webm`) - Web動画形式

## AI文章補正の使い方

### 軽量AI補正（デフォルト）
- チェックボックスをONにするだけで使用可能
- モデルダウンロード不要
- ルールベースで以下を補正：
  - よくある音声認識の間違い（「わ」→「は」など）
  - 重複表現の削除（「ですです」→「です」）
  - 連続する句読点の整理
  - スペースの正規化

### 高度なAI補正（オプション）
- 「高度なAI補正を使用」にもチェックを入れる
- 初回のみrinna/japanese-gpt2-medium（310MB）を自動ダウンロード
- transformersベースでより自然な日本語に補正
- GPU使用可能（CPU でも動作）

補正例：
```
【元のテキスト】
えーとですね今日わ会議がありましてですです

【軽量補正後】
えーとですね今日は会議がありましてです

【高度補正後】
今日は会議がありました
```

## 話者分離の使い方（完全無料）

### セットアップ
話者分離機能は完全無料で、Hugging Faceトークンは不要です！

#### 推奨: speechbrain（高精度）
```bash
pip install speechbrain
```

#### 軽量版: resemblyzer（軽量・高速）
```bash
pip install resemblyzer
```

どちらか一方をインストールすれば使用できます。自動的に利用可能な方を使用します。

### 使い方
1. 「話者分離を有効化（完全無料）」にチェック
2. 初回のみモデルを自動ダウンロード（数分）
3. 文字起こし実行

### 出力例
話者分離を有効にすると、出力テキストに話者情報が追加されます：
```
[SPEAKER_00] (0.5秒 - 3.2秒)
こんにちは、今日はいい天気ですね。

[SPEAKER_01] (3.5秒 - 6.1秒)
本当ですね。散歩日和です。

[SPEAKER_00] (6.3秒 - 8.9秒)
週末はどこか行きますか？
```

## トラブルシューティング

### モデルのダウンロードが遅い
初回起動時、kotoba-whisper v2.2モデル（約1.5GB）が自動ダウンロードされます。
時間がかかる場合がありますので、しばらくお待ちください。

### GPU が認識されない
```bash
python -c "import torch; print(torch.cuda.is_available())"
```
`False`の場合、CUDA対応PyTorchを再インストールしてください。

### メモリ不足エラー
- 音声ファイルを短く分割してください
- GPUメモリが不足している場合、CPU モードで実行してください

### 話者分離が動作しない
- speechbrainまたはresemblyzerがインストールされているか確認:
  ```bash
  pip install speechbrain
  # または
  pip install resemblyzer
  ```
- scikit-learnがインストールされているか確認: `pip install scikit-learn`
- 初回使用時はモデルのダウンロードに時間がかかります（数分）
- GPU使用時はCUDA対応PyTorchが必要です

## ライセンス

このプロジェクトは要件定義書に基づいて開発されています。

### 使用ライブラリとライセンス
- **kotoba-whisper v2.2**: Apache-2.0
- **PyQt5**: GPL v3 / 商用ライセンス
- **Transformers**: Apache-2.0
- **PyTorch**: BSD-style

## 開発者向け

### プロジェクト構造
```
KotobaTranscriber/
├── .github/
│   └── workflows/
│       ├── ci.yml                     # CI パイプライン
│       └── release.yml                # リリース自動化
├── src/
│   ├── main.py                        # メインアプリケーション（タブベースUI）
│   ├── transcription_engine.py        # 文字起こしエンジン
│   ├── text_formatter.py              # テキスト整形
│   ├── speaker_diarization_free.py    # 話者分離
│   ├── llm_corrector_standalone.py    # AI補正
│   ├── folder_monitor.py              # フォルダ監視
│   ├── realtime_audio_capture.py      # 🆕 リアルタイム音声キャプチャ
│   ├── simple_vad.py                  # 🆕 適応的VAD
│   ├── faster_whisper_engine.py       # 🆕 高速文字起こしエンジン
│   ├── realtime_transcriber.py        # 🆕 リアルタイム統合
│   └── __init__.py
├── tests/                             # テストコード
├── docs/                              # ドキュメント
│   ├── CI_CD_GUIDE.md                        # CI/CD ガイド
│   ├── REALTIME_TRANSCRIPTION_GUIDE.md      # 🆕 リアルタイム機能ガイド
│   ├── REALTIME_TECHNICAL_DETAILS.md        # 🆕 技術詳細
│   └── REALTIME_IMPLEMENTATION_SUMMARY.md   # 🆕 実装サマリー
├── models/                            # モデルファイル（自動ダウンロード）
├── pytest.ini                         # pytest 設定
├── .coveragerc                        # カバレッジ設定
├── .pre-commit-config.yaml            # pre-commit フック設定
├── requirements.txt                   # 依存パッケージ
├── requirements-dev.txt               # 開発依存パッケージ
└── README.md                          # このファイル
```

### 開発環境セットアップ

```bash
# 依存パッケージのインストール
pip install -r requirements.txt
pip install -r requirements-dev.txt

# pre-commit フックのインストール
pre-commit install
```

### テスト実行
```bash
# 全テストを実行
pytest

# カバレッジレポート付き
pytest --cov=src --cov-report=html --cov-report=term-missing

# ユニットテストのみ
pytest -m unit

# 統合テストのみ
pytest -m integration

# 並列実行（高速化）
pytest -n auto
```

### コード品質チェック
```bash
# コードフォーマット
black src/ tests/
isort src/ tests/

# リント
ruff check src/ tests/ --fix

# 型チェック
mypy src/

# セキュリティスキャン
bandit -r src/
```

### CI/CD
このプロジェクトは包括的なCI/CDパイプラインを実装しています。詳細は [CI/CD Guide](docs/CI_CD_GUIDE.md) を参照してください。

**ワークフロー:**
- **CI Pipeline**: コミット毎に自動テスト、リント、セキュリティスキャン
- **Release Pipeline**: タグプッシュで自動ビルド、GitHub リリース作成

## 参考リンク

- [kotoba-whisper v2.2 - Hugging Face](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.2)
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [Transformers Documentation](https://huggingface.co/docs/transformers)

## サポート

問題が発生した場合は、GitHubのIssuesに報告してください。
