# GitHub Official Release 作成ガイド

KotobaTranscriber v2.1.0 の公式 GitHub Release を作成するための完全ガイドです。

## クイックスタート

### 方法 1: Webブラウザで作成（最も簡単）

1. GitHub Releases ページにアクセス
   ```
   https://github.com/SHINZO111/KotobaTranscriber/releases
   ```

2. 「Create a new release」をクリック

3. 以下の情報を入力：

   **Tag version:**
   ```
   v2.1.0
   ```

   **Release title:**
   ```
   KotobaTranscriber v2.1.0 - Official Release
   ```

   **Release notes:**
   下の「Release Notes Template」を参照

4. 「Publish release」をクリック

---

## Release Notes Template

以下をコピーして Release notes に貼り付けてください：

```markdown
## KotobaTranscriber v2.1.0 - Official Release

### Release Contents
- **KotobaTranscriber-Source-v2.1.0.zip** - Complete source code
- **README.md** - Project documentation
- **INSTALLATION.md** - Installation and setup guide
- **DISTRIBUTION.md** - Distribution guidelines
- **LICENSE** - Open source license
- **HASHES.json** - SHA256 checksums for file verification

### System Requirements
- Windows 10/11 (64-bit)
- 8GB RAM minimum
- 5GB free disk space
- Python 3.8 or higher

### Quick Start
1. Download KotobaTranscriber-Source-v2.1.0.zip
2. Extract the file
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python src/main.py`

See INSTALLATION.md for detailed instructions.

### File Verification
Verify downloaded files using SHA256 checksums:
```bash
sha256sum -c HASHES.json
```

### What's New in v2.1.0
- First official public release
- Complete source code distribution
- Automated deployment and packaging
- Comprehensive documentation
- Release automation scripts

### Build Information
- **Build Date**: 2025-10-20
- **Version**: 2.1.0
- **Python**: 3.13.7
- **PyInstaller**: 6.16.0

### Support
For issues and feature requests: https://github.com/SHINZO111/KotobaTranscriber/issues
```

---

## 方法 2: PowerShell スクリプトで自動作成

### 前提条件
- GitHub Personal Access Token が必要（repo スコープ）
- Token 作成: https://github.com/settings/tokens

### 実行手順

1. GitHub Token を設定：
   ```powershell
   $env:GITHUB_TOKEN = "your_github_token_here"
   ```

2. リリース作成スクリプトを実行：
   ```powershell
   powershell -File create_release.ps1
   ```

3. スクリプトが成功すると Release URL が表示されます

---

## 方法 3: Python スクリプトで自動作成

### 前提条件
- Python 3.8 以上
- `requests` ライブラリ: `pip install requests`
- GitHub Personal Access Token

### 実行手順

1. GitHub Token を設定：
   ```bash
   set GITHUB_TOKEN=your_github_token_here
   ```

2. Python スクリプトを実行：
   ```bash
   python create_release.py
   ```

---

## Release 作成後の確認

### 1. Release ページの確認
- URL: https://github.com/SHINZO111/KotobaTranscriber/releases/tag/v2.1.0
- Tag が表示されているか確認
- リリース説明が正しく表示されているか確認

### 2. ダウンロードリンクの確認
- ファイルがダウンロード可能か確認

### 3. 公開ステータスの確認
- Draft ではなく公開されているか確認

---

## GitHub Personal Access Token の作成方法

1. GitHub にログイン
2. Settings → Developer settings → Personal access tokens
3. 「Generate new token (classic)」をクリック
4. Token name: `KotobaTranscriber Release`
5. Expiration: `90 days` (推奨)
6. Select scopes:
   - ☑️ `repo` (全て)
7. 「Generate token」をクリック
8. Token をコピーして安全に保存

**⚠️ 注意:** Token は二度と表示されません。安全に保管してください。

---

## トラブルシューティング

### エラー: "Tag 'v2.1.0' already exists"
- Tag は既に存在します
- 既存の Release を削除するか、別のバージョンを作成してください

### エラー: "GITHUB_TOKEN not set"
- 環境変数が設定されていません
- 方法 1 (Web UI) をお試しください

### エラー: "401 Unauthorized"
- GitHub Token が無効またはスコープが足りません
- Token を再生成して、正しいスコープを選択してください

---

## Release 公開後

### 通知
- GitHub ユーザーに自動的に通知されます
- リポジトリをウォッチしている人に通知されます

### 配布
- Release ページで直接ダウンロード可能
- GitHub API で自動取得可能

### アナウンス
- SNS で共有してください
- ドキュメントを更新してください

---

## 次のリリースの自動化

今後は以下のコマンドで自動化可能：

```bash
# PowerShell
$env:GITHUB_TOKEN = "your_token"
powershell -File create_release.ps1

# Python
set GITHUB_TOKEN=your_token
python create_release.py
```

---

**Repository:** https://github.com/SHINZO111/KotobaTranscriber
**Release Tag:** v2.1.0
**Build Date:** 2025-10-20
