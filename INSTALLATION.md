# KotobaTranscriber インストール手順

このドキュメントでは、KotobaTranscriberをインストールする方法を説明します。

## 対応OS

- Windows 10 (22H2 以降推奨)
- Windows 11

**注意**: Mac、Linux、その他のOSはサポートしていません

## 必須要件

### ハードウェア

| 項目 | 最小要件 | 推奨要件 |
|------|---------|---------|
| CPU | Intel i5以上 | Intel i7/i9以上 |
| メモリ(RAM) | 8GB | 16GB以上 |
| ストレージ | 10GB以上の空き | 20GB以上の空き |
| GPU(オプション) | 不要 | NVIDIA CUDA対応GPU(6GB VRAM以上) |

### ソフトウェア

- Windows 10/11（最新のアップデート推奨）
- .NET Framework 4.5以上（Windows 10/11に標準搭載）

## インストール手順

### ステップ1: インストーラーのダウンロード

1. [公式Webサイト](https://example.com/download)から`KotobaTranscriber-installer.exe`をダウンロード
2. ファイルをデスクトップなど分かりやすい場所に保存

### ステップ2: インストーラーを実行

1. `KotobaTranscriber-installer.exe`をダブルクリック
2. 「ユーザーアカウント制御」ダイアログが表示されたら「はい」をクリック

   ![UAC](images/uac-prompt.png)

3. インストールウィザードが起動

### ステップ3: セットアップウィザード

#### ウェルカム画面

![Welcome](images/installer-welcome.png)

- 「Next」をクリック

#### ライセンス確認

![License](images/installer-license.png)

- ライセンス条項を確認
- 同意する場合は「I Agree」をクリック

#### インストール先の選択

![Destination](images/installer-destination.png)

- デフォルト: `C:\Program Files\KotobaTranscriber`
- 別の場所にインストールする場合は「Browse」をクリック
- 「Next」をクリック

#### インストール実行

![Installing](images/installer-progress.png)

- インストール処理が実行されます（数秒～数分）
- 進捗バーで確認できます

#### 完了

![Finish](images/installer-finish.png)

- 「Finish」をクリック
- アプリケーションが起動します（初回のみ初期化処理あり）

## アプリケーションの起動

### 方法1: デスクトップショートカット

- デスクトップの「KotobaTranscriber」アイコンをダブルクリック

### 方法2: スタートメニューから

1. スタートボタンをクリック
2. 「KotobaTranscriber」と入力
3. 「KotobaTranscriber」をクリック

### 方法3: 管理者権限で起動

一部の機能を使用する場合、管理者権限が必要な場合があります：

1. スタートメニュー → KotobaTranscriber
2. 右クリック → 「管理者として実行」

## 初回起動時の設定

### ステップ1: 言語設定

アプリケーション起動時に言語選択画面が表示されます：

- 日本語を選択（推奨）
- その他の言語も対応予定

### ステップ2: 出力フォルダの設定

1. 「Settings」ボタンをクリック
2. 「Output Folder」で出力先フォルダを選択
3. 「Save」をクリック

### ステップ3: 初期化処理

- 初回起動時は内部ファイルの初期化が実行されます
- 処理完了まで待機してください（1～5分）

## オプション設定

### GPU加速（NVIDIA CUDA）

GPUで高速化する場合：

1. NVIDIA GeForce Experienceをインストール
2. CUDA Toolkit 11.8以上をインストール
3. cuDNNをインストール
4. 環境変数を設定（自動）

#### 確認方法

```bash
# コマンドプロンプトで確認
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

### カスタム語彙の追加

1. KotobaTranscriber フォルダ内の `custom_vocabulary.json` を編集
2. 以下の形式で単語を追加：

```json
{
  "専門用語": {
    "reading": "せんもんようご",
    "weight": 2.0
  },
  "固有名詞": {
    "reading": "こゆうめいし",
    "weight": 1.5
  }
}
```

## アンインストール方法

### 方法1: コントロールパネル

1. 設定アプリを開く
2. 「アプリ」→「インストール済みアプリ」
3. 「KotobaTranscriber」を検索
4. 「アンインストール」をクリック
5. 確認ダイアログで「アンインストール」をクリック

### 方法2: スタートメニューから

1. スタートメニュー → KotobaTranscriber フォルダ
2. 「Uninstall」をクリック
3. アンインストールウィザードに従う

### 方法3: プログラムの追加と削除

1. コントロールパネル → プログラムと機能
2. 「KotobaTranscriber」を選択
3. 「アンインストール」をクリック

## トラブルシューティング

### インストールが進まない

**症状**: インストーラーが起動しない、または途中で止まる

**解決策**:

1. 管理者権限で実行
   - インストーラーを右クリック → 「管理者として実行」

2. Windows Defender を一時的に無効化
   - Windows セキュリティ → ウイルスと脅威の防止 → 設定の管理

3. インストーラーを再ダウンロード
   - 別のブラウザでダウンロード

### インストール後にアプリが起動しない

**症状**: インストールは成功したがアプリが起動しない

**解決策**:

1. ログファイルを確認
   ```
   C:\Users\<ユーザー名>\AppData\Local\KotobaTranscriber\logs
   ```

2. .NET Framework を更新
   ```
   https://dotnet.microsoft.com/download/dotnet-framework
   ```

3. Visual C++ 再頒布可能パッケージをインストール
   ```
   https://support.microsoft.com/ja-jp/help/2977003
   ```

4. 管理者権限で起動
   - アプリを右クリック → 「管理者として実行」

### 「アクセスが拒否されました」エラー

**症状**: インストール中にアクセス拒否エラーが表示される

**解決策**:

1. ウイルス対策ソフトを一時的に無効化
2. インストーラーを管理者権限で実行
3. Program Files 以外のフォルダにインストール
   ```
   例: C:\Apps\KotobaTranscriber
   ```

### GPU が認識されない

**症状**: GPU（CUDA）が認識されない、または「CUDA available: False」

**解決策**:

1. NVIDIA ドライバを最新に更新
   ```
   https://www.nvidia.com/Download/index.aspx
   ```

2. CUDA Toolkit をインストール
   ```
   https://developer.nvidia.com/cuda-toolkit
   ```

3. 環境変数を設定
   ```
   CUDA_PATH: C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8
   Path に %CUDA_PATH%\bin を追加
   ```

4. PC を再起動

### ファイアウォール警告

**症状**: Windows ファイアウォールが警告を表示

**解決策**:

- 「アクセスを許可」をクリック
- または、手動で例外に追加：
  ```
  Windows Defender ファイアウォール → 許可されたアプリ → アプリを追加
  C:\Program Files\KotobaTranscriber\KotobaTranscriber.exe を選択
  ```

## システムリソースの確認

### メモリ使用量の監視

1. タスクマネージャーを開く（Ctrl+Shift+Esc）
2. 「パフォーマンス」タブ
3. 「メモリ」の使用率を確認

### ディスク空き容量の確認

```bash
# コマンドプロンプトで確認
fsutil volume diskfree C:
```

## 起動オプション

### コマンドラインからの起動

```bash
# 標準起動
"C:\Program Files\KotobaTranscriber\KotobaTranscriber.exe"

# デバッグモード
"C:\Program Files\KotobaTranscriber\KotobaTranscriber.exe" --debug

# 設定リセット
"C:\Program Files\KotobaTranscriber\KotobaTranscriber.exe" --reset
```

## 自動起動設定

Windows 起動時に KotobaTranscriber を自動起動する：

1. KotobaTranscriber を起動
2. Settings → 「起動時に自動実行」 をON
3. 次回 Windows 起動時から自動起動します

## アップデート

新しいバージョンがリリースされた場合：

1. [公式サイト](https://example.com/download)で確認
2. 新しいインストーラーをダウンロード
3. インストーラーを実行
4. 既存のバージョンを置き換えて「Upgrade」を選択

## サポート

### よくある質問

**Q: ポータブル版はありますか？**
- A: 現在はインストーラー版のみの提供です。ポータブル版の提供を検討中です。

**Q: Mac版、Linux版はありますか？**
- A: 現在のところ Windows 版のみです。今後の対応を検討中です。

**Q: ファイアウォール/セキュリティソフトとの相性は？**
- A: ほぼのソフトウェアと互換性があります。問題が発生した場合は、例外リストに追加してください。

### サポート連絡先

- 📧 メール: support@example.com
- 🌐 Web: https://example.com/support
- 💬 Discord: https://discord.gg/example

---

**最終更新日**: 2024年10月19日
**バージョン**: 2.1.0
