# CUDA 12.x セットアップガイド

KotobaTranscriberでGPU加速を使用するには、CUDA 12.xランタイムのインストールが必要です。

## 現在の問題

以下のエラーが発生している場合、CUDA 12.xライブラリが不足しています：

```
Library cublas64_12.dll is not found or cannot be loaded
Cannot copy out of meta tensor; no data!
```

## CUDA 12.xランタイムのインストール手順

### 方法1: NVIDIA公式サイトからダウンロード（推奨）

1. **CUDA Toolkitをダウンロード**
   - URLにアクセス: https://developer.nvidia.com/cuda-downloads
   - Windows x86_64を選択
   - CUDA Toolkit 12.x（最新版）をダウンロード

2. **インストール**
   - ダウンロードしたインストーラーを実行
   - **Express Installation**（高速インストール）を選択
   - インストール完了まで待機（5-10分）

3. **インストール確認**
   ```cmd
   nvcc --version
   ```
   CUDA Version 12.xと表示されればOK

### 方法2: cuDNNとセットでインストール

PyTorchを使用する場合、cuDNNも必要です：

```cmd
# PyTorch公式の推奨コマンド（CUDA 12.1対応）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 方法3: CUDA Runtimeのみインストール（軽量）

完全なCUDA Toolkitが不要な場合、Runtimeのみインストール：

1. URLにアクセス: https://developer.nvidia.com/cuda-toolkit-archive
2. CUDA Toolkit 12.1（またはそれ以降）を選択
3. **Runtime Installer**を選択してダウンロード
4. インストール実行

## インストール後の確認

### 1. CUDA DLLの確認

PowerShellで以下を実行：

```powershell
where cublas64_12.dll
```

以下のようなパスが表示されればOK：
```
C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin\cublas64_12.dll
```

### 2. PyTorchでCUDAを確認

```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"Device count: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"Device name: {torch.cuda.get_device_name(0)}")
```

期待される出力：
```
CUDA available: True
CUDA version: 12.1
Device count: 1
Device name: NVIDIA GeForce RTX 3060
```

## トラブルシューティング

### エラー: "CUDA driver version is insufficient"

**原因**: NVIDIAグラフィックドライバーが古い

**解決策**:
1. GeForce Experienceを起動
2. ドライバー更新を確認
3. 最新ドライバーをインストール

### エラー: "cublas64_12.dll not found"

**原因**: CUDA Toolkitのbinフォルダがパスに含まれていない

**解決策**:
1. 環境変数を確認:
   ```cmd
   echo %PATH%
   ```

2. 以下のパスが含まれているか確認:
   ```
   C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin
   ```

3. 含まれていない場合、手動で追加:
   - Windowsキー → 「環境変数」で検索
   - システム環境変数 → Path → 編集
   - 新規 → CUDA binフォルダのパスを追加

### CPUモードで動作させたい場合

CUDA 12.xのインストールが不要な場合、CPUモードで動作します：

1. `config/config.yaml`を編集:
   ```yaml
   model:
     whisper:
       device: "cpu"  # autoからcpuに変更
   ```

2. 音声前処理を無効化（すでに実施済み）:
   ```yaml
   audio:
     preprocessing:
       enabled: false
   ```

## パフォーマンス比較

| モード | 処理速度 | 推奨用途 |
|--------|---------|---------|
| **CUDA GPU** | 5-10倍高速 | リアルタイム文字起こし、大量ファイル処理 |
| **CPU** | 標準速度 | 短いファイル、CUDA環境がない場合 |

## 参考リンク

- [NVIDIA CUDA Toolkit Documentation](https://docs.nvidia.com/cuda/)
- [PyTorch CUDA Installation](https://pytorch.org/get-started/locally/)
- [CUDA Compatibility Guide](https://docs.nvidia.com/deploy/cuda-compatibility/)
