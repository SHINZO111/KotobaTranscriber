# メモリリーク検証テスト - 使用ガイド

## 概要

`test_memory_leak.py` は、KotobaTranscriberのリアルタイム文字起こし機能を長時間動作させてメモリリークを検証するためのスクリプトです。

## テスト内容

このスクリプトは以下の3つのストレステストを実行します:

### 1. AudioCapture ストレステスト
- `RealtimeAudioCapture` の繰り返し start/stop
- コンテキストマネージャによる自動クリーンアップの検証
- マイク入力の連続キャプチャと停止

### 2. WhisperEngine ストレステスト
- `FasterWhisperEngine` の繰り返し load/unload
- モデルのロードとアンロードでのメモリ解放検証
- 文字起こし処理の繰り返し実行

### 3. 統合ストレステスト
- AudioCapture + WhisperEngine + VAD の統合動作
- 実際のリアルタイム文字起こしシナリオの再現
- すべてのコンポーネントの連携動作検証

## 前提条件

### 必須ライブラリ

```bash
# 基本機能
pip install psutil

# グラフ生成（オプション）
pip install matplotlib
```

### プロジェクト依存関係

通常のプロジェクトセットアップが完了していること:

```bash
# プロジェクトのルートディレクトリで
pip install -r requirements.txt
```

## 使用方法

### 基本的な実行

```bash
# testsディレクトリに移動
cd tests

# デフォルト設定（1時間テスト）
python test_memory_leak.py

# プロジェクトルートから実行する場合
python tests/test_memory_leak.py
```

### クイックテスト（5分）

開発中や動作確認用の短時間テスト:

```bash
python test_memory_leak.py --quick-test
```

### カスタム設定

```bash
# 30分間のテスト、測定間隔15秒
python test_memory_leak.py --duration 30 --interval 15

# 出力ディレクトリを指定
python test_memory_leak.py --output-dir my_test_results
```

## コマンドラインオプション

| オプション | 説明 | デフォルト値 |
|-----------|------|-------------|
| `--duration MINUTES` | テスト時間（分） | 60 |
| `--interval SECONDS` | 測定間隔（秒） | 30 |
| `--quick-test` | クイックテスト（5分） | - |
| `--output-dir DIR` | 出力ディレクトリ | logs/memory_test |

## 出力ファイル

テスト実行後、以下のファイルが生成されます:

### 1. ログファイル

```
logs/memory_test/memory_test_YYYYMMDD_HHMMSS.log
```

詳細な実行ログ（タイムスタンプ付き）

### 2. レポートファイル

```
logs/memory_test/memory_test_report_YYYYMMDD_HHMMSS.txt
```

テスト結果のサマリー:
- テスト実行時間と測定回数
- 各ストレステストのイテレーション数
- メモリ使用量の統計（初期値、最終値、最小/最大/平均）
- メモリリーク検出結果

### 3. グラフファイル

```
logs/memory_test/memory_usage_plot_YYYYMMDD_HHMMSS.png
```

メモリ使用量の推移グラフ（matplotlib が利用可能な場合）:
- 上段: 物理メモリ（RSS）と仮想メモリ（VMS）の推移
- 下段: CPU使用率の推移

## 結果の見方

### メモリリーク判定基準

テスト終了時に以下の基準でメモリリークを判定します:

- **物理メモリ（RSS）の増加量が50MB以上**: メモリリークの兆候あり
- **物理メモリ（RSS）の増加量が50MB未満**: 問題なし

### 正常なパターン

```
メモリ使用量サマリー (RSS - 物理メモリ)
初期値:   250.45 MB
最終値:   280.32 MB
増加量:   29.87 MB

メモリリーク検出結果
OK: メモリリークの兆候は検出されませんでした
```

### 異常なパターン（メモリリーク）

```
メモリ使用量サマリー (RSS - 物理メモリ)
初期値:   250.45 MB
最終値:   380.78 MB
増加量:   130.33 MB

メモリリーク検出結果
警告: メモリリークの兆候が検出されました！
      物理メモリが 50MB 以上増加しています
```

### グラフの見方

**理想的なグラフ**:
- メモリ使用量が一定範囲内で推移（鋸波パターン）
- ガベージコレクション後にメモリが元のレベルに戻る
- 全体的な上昇トレンドがない

**問題のあるグラフ**:
- 時間経過とともにメモリ使用量が右肩上がり
- ガベージコレクション後もメモリが高い状態を維持
- 明確な上昇トレンドが見られる

## テスト中の挙動

### コンソール出力例

```
2025-10-16 12:00:00 - INFO - KotobaTranscriber メモリリーク検証テスト
2025-10-16 12:00:00 - INFO - テスト時間: 60 分
2025-10-16 12:00:00 - INFO - 測定間隔: 30 秒
================================================================================
Test Cycle 1
================================================================================

[1/3] AudioCapture Stress Test
2025-10-16 12:00:05 - INFO - Cycle 1/3
2025-10-16 12:00:05 - INFO - AudioCapture Cycle 1 - Before
2025-10-16 12:00:10 - INFO - AudioCapture Cycle 1 - After
...

[2/3] WhisperEngine Stress Test
2025-10-16 12:00:15 - INFO - Cycle 1/2
...

[3/3] Integrated Stress Test
2025-10-16 12:00:25 - INFO - Cycle 1/2
...

Elapsed: 0.50 min, Remaining: 59.50 min
Total iterations - Audio: 3, Whisper: 2, Integrated: 2
Memory - RSS: 280.45 MB, VMS: 450.23 MB, CPU: 12.3%
```

### 途中で停止したい場合

`Ctrl+C` を押すことでテストを安全に中断できます:
- 現在のサイクルが完了してから停止
- 結果ファイルは正常に生成される
- メモリリーク判定も実行される

## トラブルシューティング

### エラー: psutil not available

```bash
pip install psutil
```

### エラー: matplotlib not available

グラフ生成がスキップされますが、テストは実行されます:

```bash
# グラフを生成したい場合
pip install matplotlib
```

### エラー: faster-whisper not available

```bash
pip install faster-whisper
```

### エラー: マイクデバイスが見つからない

- マイクが接続されているか確認
- 他のアプリケーションがマイクを使用していないか確認
- Windows の場合、プライバシー設定でマイクアクセスが許可されているか確認

### メモリ不足エラー

テストは大量のメモリを使用する可能性があります:
- 他のアプリケーションを閉じる
- `--quick-test` オプションで短時間テストを実行
- `--duration` を短く設定（例: 10分）

## ベストプラクティス

### 1. テスト前の準備

```bash
# 他のアプリケーションを閉じる
# システムモニターでメモリ使用状況を確認

# クリーンな状態でテスト開始
python test_memory_leak.py
```

### 2. 段階的なテスト

まずクイックテストで動作確認:

```bash
# 5分間のクイックテスト
python test_memory_leak.py --quick-test
```

問題なければ本番テスト:

```bash
# 1時間の本格テスト
python test_memory_leak.py
```

### 3. 定期的な実行

CI/CDパイプラインへの統合:

```yaml
# GitHub Actions の例
- name: Memory Leak Test
  run: |
    pip install psutil matplotlib
    python tests/test_memory_leak.py --duration 10 --output-dir artifacts/memory_test

- name: Upload Test Results
  uses: actions/upload-artifact@v2
  with:
    name: memory-test-results
    path: artifacts/memory_test/
```

### 4. 結果の比較

複数回のテストを実行して傾向を把握:

```bash
# 日付ごとにディレクトリを分ける
python test_memory_leak.py --output-dir logs/memory_test/2025-10-16
python test_memory_leak.py --output-dir logs/memory_test/2025-10-17
python test_memory_leak.py --output-dir logs/memory_test/2025-10-18
```

## テスト結果の解釈ガイド

### 許容範囲

| 項目 | 許容範囲 | 備考 |
|-----|---------|------|
| RSS増加量 | < 50 MB | 長時間実行でも50MB以内なら正常 |
| VMS増加量 | < 100 MB | 仮想メモリは物理メモリより余裕あり |
| CPU使用率 | < 50% | アイドル時、処理時のピークは除く |

### 各コンポーネントの期待動作

#### AudioCapture
- start/stop サイクル後、メモリが初期レベルに戻る
- PyAudio のストリームが確実にクローズされる
- スレッドが確実に終了する

#### WhisperEngine
- load/unload サイクル後、GPUメモリが解放される
- モデルオブジェクトが削除される
- ガベージコレクションで回収される

#### Integrated Test
- 複数コンポーネントの組み合わせでもメモリが安定
- VADとWhisperの連携でメモリリークがない
- 長時間動作でもパフォーマンスが維持される

## まとめ

このテストスクリプトを使用することで:

1. **メモリリークの早期発見**: 開発中にメモリリークを検出
2. **パフォーマンスの定量評価**: 数値とグラフで可視化
3. **リファクタリングの検証**: コード変更後の影響を確認
4. **本番環境の予測**: 長時間動作時の挙動を予測

定期的にテストを実行し、メモリリークのない安定したアプリケーションを維持しましょう。
