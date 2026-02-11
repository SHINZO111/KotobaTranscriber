#!/usr/bin/env python3
"""
KotobaTranscriber Release Builder
配布用パッケージを自動作成するスクリプト
"""

import os
import sys
import subprocess
import json
import hashlib
import zipfile
from pathlib import Path
from datetime import datetime


class ReleaseBuilder:
    def __init__(self, version: str = "2.2.0", mode: str = "tauri"):
        """
        Args:
            version: リリースバージョン
            mode: "tauri" (新しい Tauri + FastAPI ビルド) or "legacy" (PySide6 ビルド)
        """
        self.version = version
        self.mode = mode
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / "dist"
        self.release_dir = self.project_root / "releases"
        self.build_dir = self.project_root / "build"

    def log(self, message: str, level: str = "INFO"):
        """ログ出力"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        colors = {
            "INFO": "\033[94m",
            "SUCCESS": "\033[92m",
            "WARNING": "\033[93m",
            "ERROR": "\033[91m",
            "RESET": "\033[0m"
        }
        color = colors.get(level, colors["INFO"])
        print(f"{color}[{timestamp}] [{level}] {message}{colors['RESET']}")

    def run_command(self, command: list, description: str = "", cwd: Path = None):
        """コマンドを実行"""
        if description:
            self.log(f"実行中: {description}")
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
            )
            if result.stdout:
                self.log(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            self.log(f"エラー: {e.stderr}", "ERROR")
            return False

    def cleanup(self):
        """前回のビルドを削除"""
        self.log("前回のビルドをクリア中...")

        for target_dir in [self.dist_dir, self.build_dir]:
            if target_dir.exists():
                import shutil
                try:
                    shutil.rmtree(target_dir)
                    self.log(f"削除: {target_dir}")
                except Exception as e:
                    self.log(f"削除エラー ({target_dir}): {e}", "WARNING")
                    return False

        try:
            self.dist_dir.mkdir(exist_ok=True)
            return True
        except Exception as e:
            self.log(f"ディレクトリ作成エラー: {e}", "ERROR")
            return False

    def build_pyinstaller(self):
        """PyInstallerでビルド"""
        if self.mode == "tauri":
            return self.build_backend_pyinstaller()

        self.log("PyInstallerでビルド中 (レガシーモード)...", "INFO")
        self.log("(これには数分～数十分かかる場合があります)", "WARNING")

        spec_file = self.project_root / "build.spec"
        if not spec_file.exists():
            self.log(f"build.spec が見つかりません: {spec_file}", "ERROR")
            return False

        if not self.run_command(
            ["python", "-m", "PyInstaller", str(spec_file)],
            "PyInstaller ビルド"
        ):
            return False

        self.log("PyInstallerビルド完了", "SUCCESS")
        return True

    def build_backend_pyinstaller(self):
        """PyInstallerで API バックエンドをビルド（Tauri sidecar 用）"""
        self.log("PyInstallerでバックエンドをビルド中 (Tauri sidecar)...", "INFO")
        self.log("(これには数分～数十分かかる場合があります)", "WARNING")

        spec_file = self.project_root / "build_backend.spec"
        if not spec_file.exists():
            self.log(f"build_backend.spec が見つかりません: {spec_file}", "ERROR")
            return False

        if not self.run_command(
            ["python", "-m", "PyInstaller", str(spec_file)],
            "PyInstaller バックエンドビルド"
        ):
            return False

        # sidecar を Tauri のバイナリディレクトリにコピー（onefile モード: 単一 exe）
        import shutil
        src_exe = self.dist_dir / "kotoba_backend.exe"
        tauri_binaries = self.project_root / "src-tauri" / "binaries"
        tauri_binaries.mkdir(parents=True, exist_ok=True)

        if src_exe.exists():
            # Tauri sidecar 命名規則: {name}-{target_triple}.exe
            dst = tauri_binaries / "kotoba_backend-x86_64-pc-windows-msvc.exe"
            shutil.copy2(src_exe, dst)
            self.log(f"バックエンドをコピー: {dst}", "SUCCESS")
        else:
            self.log(f"バックエンドが見つかりません: {src_exe}", "ERROR")
            return False

        self.log("バックエンドビルド完了", "SUCCESS")
        return True

    def build_tauri(self):
        """Tauriアプリをビルド"""
        self.log("Tauriアプリをビルド中...", "INFO")

        frontend_dir = self.project_root / "frontend"
        if not frontend_dir.exists():
            self.log(f"frontend/ が見つかりません: {frontend_dir}", "ERROR")
            return False

        # npm install (frontend ディレクトリで実行)
        if not self.run_command(
            ["npm", "install"],
            "npm install (frontend)",
            cwd=frontend_dir,
        ):
            self.log("npm install failed", "WARNING")

        # npm run tauri build (frontend ディレクトリで実行)
        if not self.run_command(
            ["npm", "run", "tauri", "build"],
            "Tauri ビルド",
            cwd=frontend_dir,
        ):
            return False

        self.log("Tauriビルド完了", "SUCCESS")
        return True

    def build_nsis_installer(self):
        """NSISでインストーラーを作成"""
        self.log("NSISインストーラーを作成中...", "INFO")

        nsi_file = self.project_root / "installer.nsi"
        if not nsi_file.exists():
            self.log(f"installer.nsi が見つかりません: {nsi_file}", "ERROR")
            return False

        # makensis が利用可能か確認
        try:
            subprocess.run(
                ["makensis", "-VERSION"],
                check=True,
                capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("makensis が見つかりません。NSIS をインストールしてください。", "WARNING")
            self.log("ダウンロード: https://nsis.sourceforge.io", "INFO")
            return False

        if not self.run_command(
            ["makensis", f"/DPRODUCT_VERSION={self.version}", str(nsi_file)],
            "NSIS インストーラー作成"
        ):
            return False

        self.log("NSISインストーラー作成完了", "SUCCESS")
        return True

    def copy_resources(self):
        """リソースファイルをコピー"""
        self.log("リソースファイルをコピー中...")

        resources = [
            ("icon.ico", self.dist_dir / "icon.ico"),
            ("LICENSE", self.dist_dir / "KotobaTranscriber" / "LICENSE"),
        ]

        for src_name, dst_path in resources:
            src_path = self.project_root / src_name
            if src_path.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(src_path, dst_path)
                self.log(f"コピー: {src_name} → {dst_path}")
            else:
                self.log(f"見つかりません: {src_path}", "WARNING")

    def calculate_hash(self, file_path: Path) -> str:
        """ファイルのSHA256ハッシュを計算"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def create_release_package(self):
        """リリースパッケージを作成"""
        self.log("リリースパッケージを作成中...")

        self.release_dir.mkdir(exist_ok=True)

        # インストーラーが存在するか確認
        installer_path = self.dist_dir / "KotobaTranscriber-installer.exe"
        if not installer_path.exists():
            self.log("インストーラーが見つかりません", "WARNING")
            return False

        # リリースフォルダ名
        release_name = f"KotobaTranscriber-v{self.version}"
        release_folder = self.release_dir / release_name
        release_folder.mkdir(exist_ok=True)

        # ファイルをコピー
        import shutil

        files_to_copy = [
            (installer_path, release_folder / "KotobaTranscriber-installer.exe"),
            (self.project_root / "LICENSE", release_folder / "LICENSE"),
            (self.project_root / "README.md", release_folder / "README.md"),
            (self.project_root / "INSTALLATION.md", release_folder / "INSTALLATION.md"),
            (self.project_root / "DISTRIBUTION.md", release_folder / "DISTRIBUTION.md"),
        ]

        for src, dst in files_to_copy:
            if src.exists():
                shutil.copy2(src, dst)
                self.log(f"コピー: {src.name}")
            else:
                self.log(f"見つかりません: {src}", "WARNING")

        # ハッシュファイルを作成
        hash_info = {
            "version": self.version,
            "build_date": datetime.now().isoformat(),
            "files": {}
        }

        for file_path in release_folder.glob("*"):
            if file_path.is_file():
                file_hash = self.calculate_hash(file_path)
                hash_info["files"][file_path.name] = {
                    "sha256": file_hash,
                    "size": file_path.stat().st_size
                }
                self.log(f"ハッシュ: {file_path.name}")
                self.log(f"  SHA256: {file_hash}")

        # ハッシュ情報を保存
        hash_file = release_folder / "HASHES.json"
        with open(hash_file, "w", encoding="utf-8") as f:
            json.dump(hash_info, f, indent=2, ensure_ascii=False)

        self.log(f"リリースパッケージ作成完了: {release_folder}", "SUCCESS")
        return True

    def create_changelog(self):
        """チェンジログを作成（テンプレート）"""
        self.log("チェンジログテンプレートを作成中...")

        changelog_path = self.project_root / "CHANGELOG.md"

        if not changelog_path.exists():
            changelog_content = f"""# KotobaTranscriber Changelog

## [Unreleased]

## [{self.version}] - {datetime.now().strftime('%Y-%m-%d')}

### Added
- New features here

### Changed
- Changes here

### Fixed
- Bug fixes here

### Removed
- Removed features here

### Security
- Security fixes here

---

### Installation
Download `KotobaTranscriber-installer.exe` and run it.

### System Requirements
- Windows 10/11 (64-bit)
- 8GB RAM minimum
- 5GB free disk space
"""
            with open(changelog_path, "w", encoding="utf-8") as f:
                f.write(changelog_content)
            self.log(f"チェンジログ作成: {changelog_path}", "SUCCESS")
        else:
            self.log("チェンジログは既に存在します", "INFO")

    def generate_report(self):
        """ビルドレポートを生成"""
        self.log("ビルドレポートを生成中...")

        report_path = self.project_root / "BUILD_REPORT.md"

        installer_path = self.dist_dir / "KotobaTranscriber-installer.exe"
        exe_path = self.dist_dir / "KotobaTranscriber" / "KotobaTranscriber.exe"

        report_content = f"""# KotobaTranscriber Build Report

**Build Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Version**: {self.version}

## Build Artifacts

### インストーラー
- **ファイル名**: KotobaTranscriber-installer.exe
- **パス**: {installer_path}
- **サイズ**: {installer_path.stat().st_size / (1024**2):.2f} MB
- **SHA256**: {self.calculate_hash(installer_path)}

### ポータブル実行ファイル
- **ファイル名**: KotobaTranscriber.exe
- **パス**: {exe_path}
- **サイズ**: {exe_path.stat().st_size / (1024**2):.2f} MB
- **SHA256**: {self.calculate_hash(exe_path)}

## リリースディレクトリ
- **パス**: {self.release_dir}

## インストール方法

1. `KotobaTranscriber-installer.exe` を実行
2. インストールウィザードに従う
3. アプリケーションが起動

## テストチェックリスト

- [ ] インストーラーが正常に実行される
- [ ] アプリケーションが起動する
- [ ] アンインストーラーが正常に動作する
- [ ] ショートカットが作成されている
- [ ] レジストリにエントリが追加されている

## 次のステップ

1. テスト環境でテスト実行
2. GitHub Releases にアップロード
3. Web サイトで配布開始

---

このレポートは自動生成されました。
"""

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        self.log(f"ビルドレポート生成: {report_path}", "SUCCESS")

    def build(self):
        """ビルド実行"""
        self.log("=" * 50)
        self.log(f"KotobaTranscriber Release Builder v{self.version} ({self.mode} mode)")
        self.log("=" * 50, "INFO")
        self.log("")

        if self.mode == "tauri":
            steps = [
                ("クリーンアップ", self.cleanup),
                ("バックエンドビルド (PyInstaller)", self.build_backend_pyinstaller),
                ("Tauriビルド", self.build_tauri),
                ("チェンジログ作成", self.create_changelog),
            ]
        else:
            steps = [
                ("クリーンアップ", self.cleanup),
                ("PyInstallerビルド", self.build_pyinstaller),
                ("リソースコピー", self.copy_resources),
                ("NSISインストーラー作成", self.build_nsis_installer),
                ("リリースパッケージ作成", self.create_release_package),
                ("チェンジログ作成", self.create_changelog),
                ("レポート生成", self.generate_report),
            ]

        for step_name, step_func in steps:
            self.log(f"\n{step_name}...", "INFO")
            if not step_func():
                self.log(f"{step_name} に失敗しました", "ERROR")
                return False

        self.log("\n" + "=" * 50)
        self.log("ビルド完了！", "SUCCESS")
        self.log("=" * 50, "SUCCESS")

        print(f"\nリリースパッケージ: {self.release_dir}")
        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KotobaTranscriber Release Builder")
    parser.add_argument("--version", default="2.2.0", help="リリースバージョン")
    parser.add_argument("--mode", default="tauri", choices=["tauri", "legacy"],
                        help="ビルドモード: tauri (新) or legacy (PySide6)")
    args = parser.parse_args()

    builder = ReleaseBuilder(version=args.version, mode=args.mode)

    if builder.build():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
