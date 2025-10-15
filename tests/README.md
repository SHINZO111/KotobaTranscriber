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
├── test_transcription_engine.py  # 文字起こしエンジンのテスト
├── test_text_formatter.py        # テキスト整形のテスト
├── test_speaker_diarization.py   # 話者分離のテスト
└── test_gui.py                   # GUI統合テスト
```

## 今後の実装予定

- [ ] 文字起こしエンジンの単体テスト
- [ ] テキスト整形の単体テスト
- [ ] 話者分離の単体テスト
- [ ] GUI統合テスト
- [ ] エンドツーエンドテスト
- [ ] パフォーマンステスト
