# KotobaTranscriber 配布ガイド

このドキュメントは、KotobaTranscriberをエンドユーザーに配布するための手順を説明します。

## ファイル構成

配布パッケージに含めるべきファイル：

```
配布フォルダ/
├── KotobaTranscriber-installer.exe    ← メインインストーラー
├── README.md                          ← ユーザー向けドキュメント
├── INSTALLATION.md                    ← インストール手順
├── LICENSE                            ← ライセンス
└── THIRD_PARTY_LICENSES.md            ← 第三者ライセンス
```

## 配布前チェックリスト

- [ ] インストーラーをテスト環境でテスト
- [ ] アンインストーラーが正常に動作することを確認
- [ ] Windows Defender/ウイルス対策がスキャンを完了
- [ ] バージョン番号が正しいことを確認
- [ ] ライセンスファイルが含まれていることを確認
- [ ] README が最新版であることを確認
- [ ] ハッシュ値を計算（オプション）

## ハッシュ値の計算

配布パッケージの整合性確認用：

```powershell
# PowerShell
Get-FileHash "KotobaTranscriber-installer.exe" -Algorithm SHA256
```

```bash
# コマンドプロンプト
certutil -hashfile "KotobaTranscriber-installer.exe" SHA256
```

## インストーラー配布チャネル

### 1. GitHub Releases

```bash
# GitHubのReleasesタブから新規リリースを作成
# バイナリをアップロード
```

### 2. 公式Webサイト

1. ダウンロードページを作成
2. インストーラーをホスト
3. インストール手順と必要な情報を提供

### 3. コマンドラインインストール

```bash
# Scoop（オプション）
# scoop create-manifest https://example.com/KotobaTranscriber-installer.exe

# Chocolatey（オプション）
# choco install kotobtranscriber
```

## インストーラーの署名（オプション）

本番環境では、実行ファイルに署名することを推奨：

```powershell
# 自己署名証明書を作成（テスト用）
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=KotobaTranscriber"

# 実行ファイルに署名
Set-AuthenticodeSignature -FilePath "KotobaTranscriber-installer.exe" -Certificate $cert
```

## 必要システム情報

ユーザーに提供すべき情報：

| 項目 | 要件 |
|------|------|
| OS | Windows 10/11 (64-bit) |
| ディスク容量 | 5GB以上の空き領域 |
| メモリ | 8GB以上推奨 |
| .NET Framework | 4.5以上（Windows 10では自動） |
| Visual C++ 再頒布可能パッケージ | 最新版推奨 |

## ユーザーサポート向け情報

### インストーラーが起動しない場合

1. 管理者権限で実行
   ```
   インストーラーを右クリック → 「管理者として実行」
   ```

2. Visual C++再頒布可能パッケージをインストール
   ```
   https://support.microsoft.com/ja-jp/help/2977003
   ```

3. Windows Defender で除外に追加
   ```
   設定 → ウイルスと脅威の防止 → 設定の管理 → 除外の追加
   ```

### インストール後にアプリが起動しない場合

1. アプリケーションログを確認
   ```
   C:\Users\<ユーザー名>\AppData\Local\KotobaTranscriber\logs
   ```

2. Python環境を確認
   ```
   Python 3.8以上がインストールされていることを確認
   ```

3. 依存パッケージを確認
   ```
   PyAudio、Torch等がインストールされているか確認
   ```

## トラブルシューティング

### よくある質問

**Q: インストール中に「アクセスが拒否されました」と表示される**
- A: インストーラーを管理者権限で実行してください

**Q: アンインストール後にフォルダが残っている**
- A: 手動でフォルダを削除してください：
  ```
  C:\Program Files\KotobaTranscriber
  C:\Users\<ユーザー名>\AppData\Local\KotobaTranscriber
  ```

**Q: GPUが認識されない**
- A: CUDA対応NVIDIAドライバのインストール後、再起動してください

## バージョン管理

### リリース命名規則

```
KotobaTranscriber-v<major>.<minor>.<patch>-installer.exe

例：
- KotobaTranscriber-v2.1.0-installer.exe
- KotobaTranscriber-v2.0.1-installer.exe
```

### バージョン番号の意味

- **Major**: 大規模な機能追加や大きな改変
- **Minor**: 新機能の追加
- **Patch**: バグ修正やセキュリティパッチ

## セキュリティ

### 推奨事項

1. **署名**：実行ファイルにコード署名を追加
2. **スキャン**：配布前にVirusTotal等でスキャン
3. **HTTPS**：配布サーバーはHTTPSを使用
4. **チェックサム**：ハッシュ値をWebサイトに公開

### ウイルス検出への対応

PyInstallerで作成された実行ファイルが誤検出される場合：

1. VirusTotal で報告
2. セキュリティベンダーに申告
3. ホワイトリスト登録をリクエスト

## 統計とフィードバック

### ユーザーテレメトリ（オプション）

アプリ内にテレメトリ機能を追加することで以下を収集可能：

- インストール数
- バージョン分布
- 機能使用統計
- クラッシュレポート

**プライバシーに注意**：ユーザーの同意を取得し、収集データは最小限に

## リリースノート例

```markdown
# KotobaTranscriber v2.1.0 リリース

## 新機能
- 話者分離機能の改善
- LLM補正の精度向上
- ダークモード対応

## バグ修正
- GPU使用時のクラッシュを修正
- ファイルフォーマット認識の改善

## 既知の問題
- 長時間の連続処理でメモリ使用量が増加することがあります

## システム要件
- Windows 10/11 (64-bit)
- Python 3.8以上
- メモリ 8GB以上推奨

## インストール方法
1. `KotobaTranscriber-installer.exe`をダウンロード
2. ダブルクリックして実行
3. インストールウィザードに従う

## アンインストール方法
1. コントロールパネル → プログラムと機能
2. 「KotobaTranscriber」を選択 → アンインストール
```

## ダウンロードリンク配置例

```html
<!-- Webサイト用HTML -->
<a href="/downloads/KotobaTranscriber-v2.1.0-installer.exe"
   class="btn btn-primary">
   KotobaTranscriberをダウンロード
</a>

<!-- ファイルサイズと説明 -->
<p>
  <small>
    ファイルサイズ: 850MB<br>
    SHA256: abc123def456...<br>
    最終更新: 2024年10月19日
  </small>
</p>
```

## ローカライゼーション

将来的なサポート言語：

- [ ] 日本語（現在サポート）
- [ ] 英語（計画中）
- [ ] 中国語簡体字（検討中）

## 今後の改善予定

- [ ] アップデーター機能の追加
- [ ] ポータブル版の提供
- [ ] Microsoft Store への登録
- [ ] コード署名の実装

---

**最終更新日**: 2024年10月19日
**バージョン**: 2.1.0
