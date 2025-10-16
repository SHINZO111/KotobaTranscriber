# CI/CD Guide - KotobaTranscriber

このドキュメントでは、KotobaTranscriberプロジェクトのCI/CDパイプラインについて説明します。

## 目次

- [概要](#概要)
- [CI/CDパイプライン構成](#cicdパイプライン構成)
- [ローカルでのテスト実行](#ローカルでのテスト実行)
- [pre-commitフックの使用](#pre-commitフックの使用)
- [GitHub Actionsワークフロー](#github-actionsワークフロー)
- [トラブルシューティング](#トラブルシューティング)
- [ベストプラクティス](#ベストプラクティス)

---

## 概要

KotobaTranscriberのCI/CDパイプラインは、以下の目標を達成するために設計されています：

- **品質保証**: コード品質、テストカバレッジ、セキュリティの維持
- **自動化**: 手動プロセスの最小化、エラーの削減
- **迅速なフィードバック**: 問題の早期発見と修正
- **クロスプラットフォーム対応**: Windows、macOS、Linux での動作確認
- **ドキュメンテーション**: 明確な手順とベストプラクティスの提供

### CI/CDパイプラインの構成要素

1. **Lint & Format Check**: コード品質とスタイルの検証
2. **Unit Tests**: 単体テストの実行とカバレッジ測定
3. **Integration Tests**: 統合テストの実行
4. **Main Startup Test**: アプリケーション起動テスト
5. **Production Readiness Test**: 本番環境シナリオテスト
6. **Security Scan**: セキュリティ脆弱性スキャン
7. **Build Test**: PyInstallerによるビルドテスト

---

## CI/CDパイプライン構成

### GitHub Actions ワークフロー

#### 1. CI Pipeline (`.github/workflows/ci.yml`)

**トリガー条件:**
- `push` イベント（全ブランチ）
- `pull_request` イベント（mainブランチへのPR）
- 手動トリガー（`workflow_dispatch`）

**実行環境:**
- OS: Ubuntu, Windows, macOS
- Python: 3.8, 3.9, 3.10, 3.11, 3.12

**ジョブ構成:**

```yaml
lint → unit-tests → integration-tests → main-startup-test → production-readiness-test → security-scan → build-test → test-summary
```

#### 2. Release Pipeline (`.github/workflows/release.yml`)

**トリガー条件:**
- タグプッシュ（`v*.*.*` パターン）
- 手動トリガー

**実行内容:**
- Windows実行ファイル生成
- GitHubリリース作成
- 成果物アップロード

---

## ローカルでのテスト実行

### 開発環境セットアップ

```bash
# 1. 仮想環境の作成
python -m venv venv

# 2. 仮想環境の有効化
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. 依存関係のインストール
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. PyTorch（CPU版）のインストール
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### テスト実行コマンド

#### 全テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジレポート付き
pytest --cov=src --cov-report=html --cov-report=term-missing
```

#### テストマーカー別の実行

```bash
# ユニットテストのみ
pytest -m unit

# 統合テストのみ
pytest -m integration

# 本番環境テストのみ
pytest -m production

# GUIテストを除外
pytest -m "not gui"
```

#### 並列実行（高速化）

```bash
# 自動的にCPUコア数に応じて並列実行
pytest -n auto

# 4プロセスで並列実行
pytest -n 4
```

#### 特定のテストファイル/関数の実行

```bash
# 特定のファイル
pytest tests/unit/test_text_formatter.py

# 特定のテストクラス
pytest tests/test_app_settings.py::TestAppSettings

# 特定のテスト関数
pytest tests/test_app_settings.py::TestAppSettings::test_default_settings
```

#### 詳細出力

```bash
# 詳細出力（-v）
pytest -v

# さらに詳細（-vv）
pytest -vv

# 標準出力を表示（-s）
pytest -s

# ログ出力を表示
pytest --log-cli-level=DEBUG
```

### カバレッジレポートの確認

```bash
# HTMLレポート生成
pytest --cov=src --cov-report=html

# ブラウザで確認（Windows）
start htmlcov/index.html

# ブラウザで確認（macOS）
open htmlcov/index.html

# ブラウザで確認（Linux）
xdg-open htmlcov/index.html
```

### コード品質チェック

#### Ruff（高速linter）

```bash
# コードチェック
ruff check src/ tests/

# 自動修正
ruff check src/ tests/ --fix
```

#### Black（フォーマッター）

```bash
# フォーマットチェック
black --check src/ tests/

# 自動フォーマット
black src/ tests/
```

#### isort（インポート整理）

```bash
# インポートチェック
isort --check-only src/ tests/

# 自動整理
isort src/ tests/
```

#### mypy（型チェック）

```bash
# 型チェック
mypy src/
```

#### Bandit（セキュリティチェック）

```bash
# セキュリティスキャン
bandit -r src/ -ll

# JSONレポート生成
bandit -r src/ -f json -o bandit-report.json
```

---

## pre-commitフックの使用

pre-commitフックを使用すると、コミット前に自動的にコード品質チェックが実行されます。

### セットアップ

```bash
# pre-commitのインストール（requirements-dev.txtに含まれています）
pip install pre-commit

# Gitフックのインストール
pre-commit install
```

### 使用方法

```bash
# 通常のコミット（自動的にフックが実行されます）
git commit -m "your commit message"

# 手動でフックを実行（全ファイル）
pre-commit run --all-files

# 特定のフックのみ実行
pre-commit run black --all-files
pre-commit run ruff --all-files
```

### フックの無効化（緊急時のみ）

```bash
# フックをスキップしてコミット
git commit -m "your message" --no-verify
```

### pre-commit設定の確認

```bash
# インストール済みフックの確認
pre-commit run --all-files --verbose

# 設定ファイルの検証
pre-commit validate-config
```

---

## GitHub Actionsワークフロー

### ワークフローの確認

GitHubリポジトリの「Actions」タブで、すべてのワークフローの実行状況を確認できます。

### ワークフローの手動実行

1. GitHub リポジトリの「Actions」タブを開く
2. 実行したいワークフロー（例: CI Pipeline）を選択
3. 「Run workflow」ボタンをクリック
4. ブランチを選択して「Run workflow」を実行

### ワークフローの成果物（Artifacts）

各ワークフロー実行後、以下の成果物がダウンロード可能です：

- **カバレッジレポート** (`coverage-report-*`): HTMLカバレッジレポート
- **テストレポート** (`integration-test-results-*`, `production-test-results-*`): テスト結果
- **セキュリティスキャン結果** (`security-scan-results`): セキュリティスキャンレポート
- **ビルド成果物** (`kotoba-transcriber-windows-build`): Windows実行ファイル

### ワークフローのステータスバッジ

README.mdにステータスバッジを追加することで、CI/CDの状態を可視化できます：

```markdown
[![CI Pipeline](https://github.com/YOUR_USERNAME/KotobaTranscriber/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/KotobaTranscriber/actions/workflows/ci.yml)
```

---

## トラブルシューティング

### 問題: テストがローカルでは成功するが、CIで失敗する

**原因:**
- 環境依存の問題（パス、OS固有の動作など）
- モックが不十分
- タイムゾーン、ロケールの違い

**解決策:**
```bash
# CI環境変数を設定してローカルでテスト
export CI=true
pytest

# Windowsの場合
set CI=true
pytest
```

### 問題: pre-commitフックが遅い

**原因:**
- 大量のファイルを一度にチェックしている
- 重いフック（mypy、banditなど）が含まれている

**解決策:**
```bash
# 変更されたファイルのみチェック
pre-commit run

# 特定のフックのみ実行
pre-commit run black
pre-commit run ruff
```

### 問題: カバレッジが目標値に達しない

**原因:**
- テストが不十分
- 除外設定が適切でない

**解決策:**
```bash
# カバーされていない行を確認
pytest --cov=src --cov-report=term-missing

# HTMLレポートで詳細確認
pytest --cov=src --cov-report=html
start htmlcov/index.html
```

### 問題: PyQt5関連のテストがCIで失敗する

**原因:**
- ヘッドレス環境でGUIテストが実行できない

**解決策:**
- CIワークフローで `xvfb-run` を使用（Linuxの場合）
- GUI テストに `@pytest.mark.gui` マーカーを付け、必要に応じてスキップ

```python
import pytest

@pytest.mark.gui
def test_gui_feature():
    # GUI関連のテスト
    pass
```

### 問題: 依存関係のインストールに失敗する

**原因:**
- バージョン競合
- プラットフォーム固有の依存関係

**解決策:**
```bash
# キャッシュをクリアして再インストール
pip cache purge
pip install -r requirements.txt --no-cache-dir

# 依存関係の競合をチェック
pip check
```

---

## ベストプラクティス

### 1. コミット前のチェックリスト

- [ ] ローカルでテストが成功している
- [ ] コードフォーマットが適用されている（black, isort）
- [ ] Lintエラーがない（ruff）
- [ ] 新しいコードにテストが追加されている
- [ ] ドキュメントが更新されている（必要に応じて）

### 2. テスト作成のガイドライン

- **AAA パターン**: Arrange（準備）、Act（実行）、Assert（検証）
- **独立性**: 各テストは独立して実行可能であること
- **再現性**: 同じ入力で常に同じ結果を返すこと
- **高速性**: ユニットテストは高速であること（目安: 1秒以内）
- **明確性**: テスト名から何をテストしているか明確であること

```python
def test_remove_fillers_removes_common_filler_words():
    """フィラー語削除機能が一般的なフィラー語を削除することをテスト"""
    # Arrange
    formatter = TextFormatter()
    text = "えーと、あのー、今日はいい天気ですね"

    # Act
    result = formatter.remove_fillers(text)

    # Assert
    assert "えーと" not in result
    assert "あのー" not in result
    assert "今日はいい天気ですね" in result
```

### 3. マーカーの使用

テストにマーカーを付けて、実行を制御します：

```python
import pytest

@pytest.mark.unit
def test_unit_feature():
    pass

@pytest.mark.integration
def test_integration_feature():
    pass

@pytest.mark.slow
@pytest.mark.gpu
def test_slow_gpu_feature():
    pass
```

### 4. フィクスチャの活用

共通のセットアップ処理はフィクスチャとして定義します：

```python
import pytest

@pytest.fixture
def text_formatter():
    """TextFormatterのインスタンスを提供するフィクスチャ"""
    return TextFormatter()

def test_remove_fillers(text_formatter):
    result = text_formatter.remove_fillers("えーと、こんにちは")
    assert "えーと" not in result
```

### 5. CI/CDパイプラインの最適化

- **並列実行**: pytest-xdistを使用してテストを並列実行
- **キャッシュ活用**: GitHub Actionsのキャッシュ機能を使用
- **早期失敗**: `--maxfail=5` で早期に失敗を検出
- **選択的実行**: 変更されたファイルに関連するテストのみ実行

### 6. セキュリティのベストプラクティス

- **シークレット管理**: GitHub Secretsを使用
- **依存関係の更新**: 定期的に依存関係を更新
- **脆弱性スキャン**: safety、banditを定期実行
- **最小権限原則**: 必要最小限の権限のみ付与

---

## リソース

### 公式ドキュメント

- [pytest Documentation](https://docs.pytest.org/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pre-commit Documentation](https://pre-commit.com/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

### プロジェクト関連ドキュメント

- [README.md](../README.md): プロジェクト概要
- [CLAUDE.md](../CLAUDE.md): プロジェクト技術詳細
- [tests/README.md](../tests/README.md): テスト概要

### コミュニティリソース

- [pytest Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
- [GitHub Actions Best Practices](https://docs.github.com/en/actions/learn-github-actions/best-practices-for-github-actions)

---

## サポート

問題が発生した場合は、以下の手順でサポートを受けることができます：

1. **ドキュメントを確認**: このガイドとプロジェクトドキュメントを確認
2. **既存のIssueを検索**: GitHubのIssuesで類似の問題を検索
3. **新しいIssueを作成**: 問題が解決しない場合、詳細な情報とともにIssueを作成

### Issueに含めるべき情報

- OS（Windows、macOS、Linux）
- Pythonバージョン
- エラーメッセージ（全文）
- 再現手順
- 期待する動作と実際の動作

---

## 変更履歴

- **2025-10-16**: 初版作成
  - CI/CDパイプライン構成の文書化
  - ローカルテスト実行手順の追加
  - pre-commitフック使用方法の追加
  - トラブルシューティングセクションの追加
