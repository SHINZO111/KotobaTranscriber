# メモリリーク検証テスト - 実装サマリー

## 概要

KotobaTranscriberのリアルタイム文字起こし機能を長時間動作させ、メモリリークを検証するための包括的なテストスクリプトを実装しました。

**実装日**: 2025-10-16
**担当**: Claude Code (QA Specialist)

## 実装内容

### 1. メインテストスクリプト

**ファイル**: `tests/test_memory_leak.py` (24KB)

#### 主要機能

1. **MemoryMonitor クラス**
   - psutilを使用したメモリ使用量の測定
   - 物理メモリ（RSS）と仮想メモリ（VMS）の追跡
   - CPU使用率、スレッド数の監視
   - メモリリーク検出アルゴリズム（50MB閾値）
   - matplotlibによるグラフ生成

2. **AudioCaptureStressTest クラス**
   - `RealtimeAudioCapture` の繰り返し start/stop
   - コンテキストマネージャによる自動クリーンアップ検証
   - ガベージコレクションの強制実行

3. **WhisperEngineStressTest クラス**
   - `FasterWhisperEngine` の繰り返し load/unload
   - モデルのロードとアンロードでのメモリ解放検証
   - CUDAメモリキャッシュのクリア確認

4. **IntegratedStressTest クラス**
   - AudioCapture + WhisperEngine + VAD の統合動作
   - 実際のリアルタイム文字起こしシナリオの再現
   - すべてのコンポーネントの連携動作検証

#### テストサイクル

各テストサイクルで以下を実行:
- サイクル開始前のメモリ測定
- コンポーネントの初期化と動作
- サイクル終了後のメモリ測定
- ガベージコレクションの実行
- 次のサイクルへの待機

#### 出力ファイル

1. **詳細ログ**: `logs/memory_test/memory_test_YYYYMMDD_HHMMSS.log`
2. **サマリーレポート**: `logs/memory_test/memory_test_report_YYYYMMDD_HHMMSS.txt`
3. **メモリ使用量グラフ**: `logs/memory_test/memory_usage_plot_YYYYMMDD_HHMMSS.png`

### 2. ドキュメント

#### MEMORY_TEST_README.md (9.2KB)

包括的な使用ガイド:
- テスト内容の詳細説明
- 前提条件とライブラリのインストール
- コマンドラインオプションの説明
- 出力ファイルの解説
- 結果の解釈方法
- トラブルシューティング
- ベストプラクティス

#### QUICKSTART_MEMORY_TEST.md (7.1KB)

クイックスタートガイド:
- 5分で始められる手順
- 実行例とコマンド
- 出力例の表示
- よくある質問と回答
- レポートとグラフの見方
- CI/CD統合の例

### 3. 実行スクリプト

**ファイル**: `run_memory_test.bat` (2.3KB)

Windows用の簡単実行スクリプト:
- 仮想環境の自動アクティベート
- 必須ライブラリの自動チェックとインストール
- クイックテスト、標準テスト、カスタムテストのモード選択
- 結果ファイルの場所を表示

#### 使用方法

```batch
# クイックテスト（5分）
run_memory_test.bat quick

# 標準テスト（1時間）
run_memory_test.bat

# カスタムテスト（30分）
run_memory_test.bat 30
```

### 4. tests/README.md の更新

テストディレクトリのREADMEに以下を追加:
- メモリリーク検証テストのセクション
- クイックスタート手順
- ドキュメントへのリンク
- 実装済みテストの一覧更新

## 技術的な特徴

### 1. コンテキストマネージャの活用

すべてのコンポーネントをコンテキストマネージャとして使用:

```python
with RealtimeAudioCapture() as capture, \
     FasterWhisperEngine(model_size="tiny") as engine:
    # テスト処理
    pass
# 自動的にクリーンアップされる
```

### 2. メモリリーク検出アルゴリズム

物理メモリ（RSS）の増加量で判定:
- **50MB未満**: 正常
- **50MB以上**: メモリリークの兆候あり

### 3. ガベージコレクションの明示的実行

各サイクル後にガベージコレクションを強制実行:

```python
gc.collect()

# CUDA使用時は追加のクリーンアップ
if torch.cuda.is_available():
    torch.cuda.empty_cache()
```

### 4. スレッドセーフな測定

メモリ測定とテスト実行を分離:
- 測定はメインスレッドで実行
- テストはサブコンポーネントで実行
- psutilによる正確なプロセス監視

### 5. グラフによる可視化

matplotlibで2段グラフを生成:
- 上段: 物理メモリ（RSS）と仮想メモリ（VMS）の推移
- 下段: CPU使用率の推移
- 時系列で見やすいフォーマット

## テストケース

### 1. AudioCapture ストレステスト

**目的**: マイク入力の繰り返しキャプチャでメモリリークがないことを確認

**手順**:
1. RealtimeAudioCaptureをコンテキストマネージャで作成
2. start_capture()で録音開始
3. 指定時間（3-5秒）録音
4. stop_capture()で録音停止
5. コンテキストマネージャを抜ける（自動クリーンアップ）
6. メモリ測定
7. ガベージコレクション
8. 1-7を繰り返し

**期待結果**: メモリ使用量が一定範囲内で推移

### 2. WhisperEngine ストレステスト

**目的**: モデルのロードとアンロードでメモリリークがないことを確認

**手順**:
1. FasterWhisperEngineをコンテキストマネージャで作成
2. モデルが自動ロードされる
3. テスト用音声（3秒の無音）を文字起こし
4. RTFを測定
5. コンテキストマネージャを抜ける（自動アンロード）
6. メモリ測定
7. ガベージコレクション
8. CUDAキャッシュクリア
9. 1-8を繰り返し

**期待結果**: モデルアンロード後にメモリが解放される

### 3. 統合ストレステスト

**目的**: 実際のリアルタイム文字起こしシナリオでメモリリークがないことを確認

**手順**:
1. AudioCapture、WhisperEngine、VADをすべて作成
2. 音声キャプチャ開始
3. VADで音声検出
4. 検出された音声を文字起こし
5. 指定時間（5-10秒）実行
6. 停止とクリーンアップ
7. メモリ測定
8. 1-7を繰り返し

**期待結果**: 複数コンポーネント連携でもメモリが安定

## メモリリーク判定基準

### 正常なパターン

```
RSS増加量: 24.87 MB
判定: OK - メモリリークの兆候は検出されませんでした
```

- 物理メモリの増加が50MB未満
- グラフで鋸波パターン（上下を繰り返す）
- ガベージコレクション後にメモリが元のレベルに戻る

### 異常なパターン（メモリリーク）

```
RSS増加量: 130.33 MB
判定: 警告 - メモリリークの兆候が検出されました！
```

- 物理メモリの増加が50MB以上
- グラフで右肩上がりのトレンド
- ガベージコレクション後もメモリが高い状態を維持

## 実行時間の目安

| テストモード | 時間 | 用途 |
|------------|------|------|
| クイックテスト | 5分 | 開発中の動作確認 |
| 標準テスト | 1時間 | 本格的なメモリリーク検証 |
| カスタムテスト | 任意 | 特定の条件でのテスト |

## システム要件

### 必須

- Python 3.8+
- psutil (メモリ測定)
- プロジェクトの依存関係（requirements.txt）

### 推奨

- matplotlib (グラフ生成)
- faster-whisper (Whisperエンジン)
- マイクデバイス（AudioCaptureテスト用）

### リソース

- メモリ: 4GB以上推奨
- CPU: マルチコア推奨
- ディスク: ログ保存用に100MB以上

## CI/CD統合

GitHub Actionsの例:

```yaml
name: Memory Leak Test

on:
  schedule:
    - cron: '0 2 * * 0'  # 毎週日曜2時

jobs:
  memory-test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install psutil matplotlib
      - name: Run memory test
        run: python tests/test_memory_leak.py --duration 10
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: memory-test-results
          path: logs/memory_test/
```

## 今後の拡張案

### 1. 詳細なメトリクス

- ヒープメモリのプロファイリング
- オブジェクト数の追跡
- メモリアロケーションのトレース

### 2. 自動アラート

- メモリリーク検出時のSlack/Email通知
- しきい値のカスタマイズ
- 異常パターンの自動検出

### 3. 比較レポート

- 過去のテスト結果との比較
- 回帰の検出
- パフォーマンス推移の可視化

### 4. マルチプラットフォーム対応

- Linux/macOS向けの実行スクリプト
- Docker環境でのテスト
- クロスプラットフォームのCI/CD

## まとめ

この実装により、以下が実現されました:

1. **包括的なメモリリーク検証**: 3種類のストレステストで多角的に検証
2. **自動化された測定**: psutilによる正確なメモリ測定
3. **可視化とレポート**: グラフとテキストレポートで結果を明確に
4. **簡単な実行**: バッチファイルとPythonスクリプトの両方で実行可能
5. **詳細なドキュメント**: 使用方法からトラブルシューティングまで完備

このテストスクリプトを定期的に実行することで、メモリリークのない安定したアプリケーションを維持できます。

---

**実装ファイル一覧**:
- `tests/test_memory_leak.py` (24KB)
- `tests/MEMORY_TEST_README.md` (9.2KB)
- `tests/QUICKSTART_MEMORY_TEST.md` (7.1KB)
- `run_memory_test.bat` (2.3KB)
- `tests/README.md` (更新)
- `MEMORY_TEST_IMPLEMENTATION_SUMMARY.md` (このファイル)

**合計**: 6ファイル、約45KB
