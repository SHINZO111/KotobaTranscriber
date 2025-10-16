# テスト

このディレクトリには、KotobaTranscriberのテストコードが含まれます。

## テストフレームワーク

- **pytest**: 単体テスト・統合テスト
- **pytest-qt**: PyQt5 GUIテスト
- **pytest-cov**: カバレッジ測定

## テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジ付きで実行
pytest --cov=src --cov-report=html

# 特定のテストファイルを実行
pytest tests/test_transcription_engine.py

# 詳細出力で実行
pytest -v
```

## テスト構造

```
tests/
├── test_app_settings.py          # AppSettings クラスの単体テスト (pytest)
├── run_app_settings_tests.py     # AppSettings 簡易テストランナー
├── test_integration.py           # 統合テスト
├── test_type_hints.py            # 型ヒントのテスト
├── test_memory_leak.py           # メモリリーク検証テスト
├── TEST_SUMMARY.md               # AppSettings テスト結果サマリ
├── MEMORY_TEST_README.md         # メモリテスト詳細ガイド
├── QUICKSTART_MEMORY_TEST.md     # メモリテストクイックスタート
└── README.md                     # このファイル
```

## AppSettings 単体テスト

AppSettingsクラスの包括的な単体テストが用意されています。

### クイックスタート

```bash
# 簡易テストランナー（推奨 - 依存関係不要）
python tests/run_app_settings_tests.py

# または、pytestで実行
pytest tests/test_app_settings.py -v
```

### テスト内容
- ✓ 基本機能（初期化、get/set、ネストされたキー）
- ✓ 永続化（保存/読み込み、JSON処理、エラーハンドリング）
- ✓ スレッドセーフティ（並行アクセス、RLock）
- ✓ セキュリティ（パストラバーサル対策）
- ✓ アトミック保存（データ整合性）
- ✓ ディープコピー保護（状態分離）
- ✓ 入力検証（型、範囲、フォーマット）

### テスト結果
最新実行: **18/18 テスト成功** (成功率: 100%)

詳細は [TEST_SUMMARY.md](TEST_SUMMARY.md) を参照してください。

## メモリリーク検証テスト

長時間動作テストでメモリリークを検証するための専用スクリプトが用意されています。

### クイックスタート

```bash
# Windowsの場合（簡単実行）
run_memory_test.bat quick

# または、Pythonスクリプトを直接実行
python tests/test_memory_leak.py --quick-test
```

### 詳細情報

- [メモリテスト詳細ガイド](MEMORY_TEST_README.md)
- [クイックスタートガイド](QUICKSTART_MEMORY_TEST.md)

## 今後の実装予定

- [x] 統合テスト
- [x] 型ヒントのテスト
- [x] メモリリーク検証テスト
- [x] AppSettings 単体テスト（包括的な検証付き）
- [ ] 文字起こしエンジンの単体テスト
- [ ] テキスト整形の単体テスト
- [ ] 話者分離の単体テスト
- [ ] GUI統合テスト
- [ ] エンドツーエンドテスト
- [ ] パフォーマンステスト
