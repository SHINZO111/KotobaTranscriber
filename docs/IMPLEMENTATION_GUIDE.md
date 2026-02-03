# KotobaTranscriber v2.2.0 改善実装ガイド

## 新機能概要

### 1. 字幕エクスポート機能 (subtitle_exporter.py)
SRT/VTT形式の字幕ファイルを出力可能に。

**使用方法:**
```python
from subtitle_exporter import SubtitleExporter

exporter = SubtitleExporter()
exporter.export_srt(segments, "output.srt")
exporter.export_vtt(segments, "output.vtt")
```

**機能:**
- SRT形式エクスポート
- VTT形式エクスポート
- 話者分離情報の埋め込み
- セグメントの自動マージ/分割

---

### 2. リアルタイム文字起こし (realtime_tab.py)
マイク入力によるライブ文字起こし機能。

**要件:**
```bash
pip install faster-whisper pyaudio webrtcvad
```

**使用方法:**
リアルタイムタブを開いて「開始」ボタンをクリック。

**設定項目:**
- モデルサイズ選択（tiny〜large-v3）
- デバイス選択（CPU/CUDA）
- バッファ時間調整
- VAD（音声検出）有効/無効

---

### 3. API補正機能 (api_corrector.py)
Claude 3.5 Sonnet / OpenAI GPT-4 APIによる高度な文章補正。

**環境変数設定:**
```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY="your-api-key"
$env:OPENAI_API_KEY="your-api-key"

# または .env ファイル
ANTHROPIC_API_KEY=your-api-key
OPENAI_API_KEY=your-api-key
```

**使用方法:**
```python
from api_corrector import create_corrector

corrector = create_corrector("claude", api_key="your-key")
corrected_text = corrector.correct_text(text)
```

---

### 4. 強化バッチ処理 (enhanced_batch_processor.py)
100ファイル以上対応・チェックポイント機能付き。

**特徴:**
- チェックポイントによる処理再開
- 動的ワーカー数調整
- メモリ使用量監視
- 進捗永続化

**使用方法:**
```python
from enhanced_batch_processor import EnhancedBatchProcessor

processor = EnhancedBatchProcessor(
    max_workers=4,
    enable_checkpoint=True,
    memory_limit_mb=4096
)

result = processor.process_files(
    file_paths,
    processor_func,
    progress_callback
)
```

---

### 5. ダークモード (dark_theme.py)
目に優しいダークテーマ。

**使用方法:**
```python
from dark_theme import set_theme
from PySide6.QtWidgets import QApplication

app = QApplication([])
set_theme(app, dark_mode=True)  # ダークモード
set_theme(app, dark_mode=False)  # ライトモード
```

---

## インストール手順

### 1. 必要パッケージのインストール

```bash
# 基本機能
cd F:\KotobaTranscriber
pip install -r requirements.txt

# リアルタイム機能（オプション）
pip install faster-whisper pyaudio webrtcvad

# API補正機能（オプション）
pip install anthropic openai

# 強化バッチ処理（オプション）
pip install psutil
```

### 2. 設定ファイル更新

`config/config.yaml` に以下を追加:

```yaml
# 字幕エクスポート設定
export:
  default_formats: ["txt", "srt"]
  merge_short_segments: true
  min_segment_duration: 1.0

# API設定
api:
  anthropic:
    enabled: false
    model: "claude-3-5-sonnet-20241022"
  openai:
    enabled: false
    model: "gpt-4"

# リアルタイム設定
realtime:
  default_model: "base"
  default_device: "auto"
  vad_enabled: true
  buffer_duration: 3.0

# UI設定
ui:
  dark_mode: false
  theme_color: "blue"
```

### 3. 環境変数設定

`.env` ファイルを作成:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...
```

---

## 使用方法

### 起動

```bash
cd F:\KotobaTranscriber
python src/main.py
```

### 字幕エクスポート

1. ファイルを文字起こし
2. 「字幕エクスポート」ボタンをクリック
3. SRTまたはVTT形式を選択
4. 保存先を指定

### リアルタイム文字起こし

1. 「リアルタイム」タブを選択
2. モデルサイズを選択
3. 「開始」ボタンをクリック
4. マイクに向かって話す

### バッチ処理再開

1. 100ファイル以上を選択して処理開始
2. 処理中にアプリを閉じてもOK
3. 再起動時に「再開しますか？」と表示
4. 「はい」を選択して続きから処理

---

## テスト実行

```bash
cd F:\KotobaTranscriber
python tests/test_enhancements.py
```

---

## トラブルシューティング

### PyAudioがインストールできない

**Windows:**
```bash
pip install pipwin
pipwin install pyaudio
```

**または:**
```bash
# 対応するPythonバージョンのwhlをダウンロード
pip install https://example.com/PyAudio-0.2.11-cp311-cp311-win_amd64.whl
```

### faster-whisperのエラー

```bash
# CPU版を使用
pip install --force-reinstall faster-whisper
```

### CUDAメモリ不足

```python
# config.yaml で小さいモデルを使用
model:
  faster_whisper:
    model_size: "base"  # または "tiny"
```

---

## 今後の展望

### v2.3.0 予定
- Whisper v3 Turbo対応
- クラウドストレージ連携（Google Drive, Dropbox）
- 自動要約機能

### v3.0.0 予定
- Webインターフェース
- クラウド文字起こしサービス統合
- モバイルアプリ連携

---

**作成日**: 2026年2月3日
