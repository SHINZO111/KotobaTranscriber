# メモリリーク検証テスト - クイックスタート

## 5分で始める

### ステップ1: 必須ライブラリのインストール

```bash
# プロジェクトルートで実行
pip install psutil matplotlib
```

### ステップ2: クイックテストの実行

```bash
# Windowsの場合（バッチファイル使用）
run_memory_test.bat quick

# または、Pythonスクリプトを直接実行
python tests\test_memory_leak.py --quick-test
```

### ステップ3: 結果の確認

テスト完了後、以下のファイルを確認:

```
logs/memory_test/
├── memory_test_YYYYMMDD_HHMMSS.log          (詳細ログ)
├── memory_test_report_YYYYMMDD_HHMMSS.txt   (サマリーレポート)
└── memory_usage_plot_YYYYMMDD_HHMMSS.png    (グラフ)
```

## 実行例

### クイックテスト（5分）

開発中や動作確認に最適:

```bash
# Windowsバッチファイル
run_memory_test.bat quick

# Python直接実行
python tests/test_memory_leak.py --quick-test
```

**出力例:**
```
================================================================================
KotobaTranscriber メモリリーク検証テスト
================================================================================
テスト時間: 5 分
測定間隔: 15 秒
出力ディレクトリ: F:\KotobaTranscriber\logs\memory_test
================================================================================

================================================================================
Test Cycle 1
================================================================================

[1/3] AudioCapture Stress Test
Cycle 1/3 - Processing...
Cycle 2/3 - Processing...
Cycle 3/3 - Processing...

[2/3] WhisperEngine Stress Test
Cycle 1/2 - Processing...
Cycle 2/2 - Processing...

[3/3] Integrated Stress Test
Cycle 1/2 - Processing...
Cycle 2/2 - Processing...

Elapsed: 0.52 min, Remaining: 4.48 min
Memory - RSS: 285.34 MB, VMS: 458.12 MB, CPU: 15.2%

...（繰り返し）...

================================================================================
テスト完了
================================================================================
実行時間: 300.45 秒 (5.01 分)

OK: メモリリークの兆候は検出されませんでした

グラフ保存: logs\memory_test\memory_usage_plot_20251016_120530.png
レポートファイル: logs\memory_test\memory_test_report_20251016_120530.txt
```

### 標準テスト（1時間）

本格的な検証用:

```bash
# Windowsバッチファイル
run_memory_test.bat

# Python直接実行
python tests/test_memory_leak.py
```

### カスタムテスト（30分）

```bash
# Windowsバッチファイル
run_memory_test.bat 30

# Python直接実行
python tests/test_memory_leak.py --duration 30
```

## トラブルシューティング

### Q: psutil not available エラー

**A:** psutilをインストール:

```bash
pip install psutil
```

### Q: matplotlib not available エラー

**A:** グラフ生成はスキップされますが、テストは実行可能。グラフが必要な場合:

```bash
pip install matplotlib
```

### Q: faster-whisper not available エラー

**A:** faster-whisperをインストール:

```bash
pip install faster-whisper
```

### Q: マイクデバイスが見つからない

**A:** 以下を確認:
1. マイクが物理的に接続されているか
2. Windowsのプライバシー設定でマイクアクセスが許可されているか
3. 他のアプリケーションがマイクを使用していないか

### Q: テストが途中で止まった

**A:** `Ctrl+C` で安全に中断可能。結果ファイルは正常に生成されます。

## レポートの見方

### レポートファイルの例

```
================================================================================
メモリリーク検証テスト - レポート
================================================================================

テスト日時: 2025-10-16 12:05:30
テスト時間: 300.45 秒 (5.01 分)
測定回数: 21

================================================================================
テスト実行回数
================================================================================
AudioCapture サイクル: 12
WhisperEngine サイクル: 8
統合テスト サイクル: 8

================================================================================
メモリ使用量サマリー (RSS - 物理メモリ)
================================================================================
初期値:   250.45 MB
最終値:   275.32 MB
最小値:   248.12 MB
最大値:   290.45 MB
平均値:   268.78 MB
増加量:   24.87 MB

================================================================================
メモリリーク検出結果
================================================================================
OK: メモリリークの兆候は検出されませんでした

================================================================================
```

### グラフの見方

グラフは2段構成:

**上段: メモリ使用量**
- 青線（RSS）: 物理メモリ使用量
- オレンジ線（VMS）: 仮想メモリ使用量
- 理想的なパターン: 一定範囲内で推移（鋸波パターン）

**下段: CPU使用率**
- 緑線: CPU使用率の推移
- 処理中にピークが出るのは正常

## 次のステップ

### 定期的なテスト実行

週1回程度、メモリリーク検証を実施:

```bash
# 週次テスト（結果を日付別に保存）
python tests/test_memory_leak.py --output-dir logs/memory_test/weekly/2025-10-16
```

### CI/CDへの組み込み

継続的インテグレーションパイプラインに追加:

```yaml
# .github/workflows/memory-test.yml
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

### 結果の長期追跡

複数回のテスト結果を比較して傾向を把握:

```bash
# 日付ごとに整理
logs/memory_test/
├── 2025-10-16/
│   ├── memory_test_report.txt
│   └── memory_usage_plot.png
├── 2025-10-17/
│   ├── memory_test_report.txt
│   └── memory_usage_plot.png
└── 2025-10-18/
    ├── memory_test_report.txt
    └── memory_usage_plot.png
```

## まとめ

1. **クイックテスト（5分）** で動作確認
2. **標準テスト（1時間）** で本格検証
3. **レポートとグラフ** でメモリリークを可視化
4. **定期的な実行** で継続的な品質維持

これで、KotobaTranscriberのメモリリーク検証が簡単に実行できます！
