#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main.py起動テスト - 軽量版
実際のGUIを起動せずに、基本的な初期化のみテスト
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def test_imports():
    """必要なモジュールがインポート可能かテスト"""
    print("=" * 60)
    print("Test 1: モジュールインポートテスト")
    print("=" * 60)

    try:
        from app_settings import AppSettings
        print("[OK] AppSettings インポート成功")
    except Exception as e:
        print(f"[FAIL] AppSettings インポート失敗: {e}")
        return False

    try:
        from PyQt5.QtWidgets import QApplication, QMainWindow
        print("[OK] PyQt5 インポート成功")
    except Exception as e:
        print(f"[FAIL] PyQt5 インポート失敗: {e}")
        return False

    try:
        import main
        print("[OK] main モジュール インポート成功")
    except Exception as e:
        print(f"[FAIL] main モジュール インポート失敗: {e}")
        return False

    print()
    return True


def test_app_settings_initialization():
    """AppSettingsが正常に初期化できるかテスト"""
    print("=" * 60)
    print("Test 2: AppSettings初期化テスト")
    print("=" * 60)

    try:
        from app_settings import AppSettings
        import tempfile

        # 一時ディレクトリで設定ファイルを作成
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test_settings.json")

        settings = AppSettings(settings_file)
        print(f"[OK] AppSettings初期化成功")
        print(f"     設定ファイル: {settings.settings_file}")
        print(f"     設定数: {len(settings.get_all())} 個")

        # いくつかの設定を取得
        monitor_interval = settings.get('monitor_interval')
        model_size = settings.get('realtime.model_size')
        print(f"[OK] monitor_interval: {monitor_interval}")
        print(f"[OK] realtime.model_size: {model_size}")

        # クリーンアップ
        import shutil
        shutil.rmtree(temp_dir)

        print()
        return True

    except Exception as e:
        print(f"[FAIL] AppSettings初期化失敗: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_main_class_definition():
    """MainWindowクラスが定義されているかテスト"""
    print("=" * 60)
    print("Test 3: MainWindowクラス定義テスト")
    print("=" * 60)

    try:
        import main

        # MainWindowクラスが存在するか確認
        assert hasattr(main, 'MainWindow'), "MainWindowクラスが見つかりません"
        print("[OK] MainWindowクラス定義確認")

        # 重要なメソッドが存在するか確認
        MainWindow = main.MainWindow
        methods = [
            'load_ui_settings',
            'save_ui_settings',
            'on_monitor_interval_changed'
        ]

        for method in methods:
            # メソッドの存在確認（実際のインスタンスではなくクラスレベル）
            if hasattr(MainWindow, method):
                print(f"[OK] メソッド '{method}' 定義確認")
            else:
                print(f"[FAIL] メソッド '{method}' が見つかりません")
                return False

        print()
        return True

    except Exception as e:
        print(f"[FAIL] MainWindowクラステスト失敗: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_main_settings_integration():
    """main.pyでAppSettingsが使用可能かテスト"""
    print("=" * 60)
    print("Test 4: main.py + AppSettings統合テスト")
    print("=" * 60)

    try:
        import tempfile
        import shutil
        from app_settings import AppSettings

        # 一時ディレクトリで設定ファイルを作成
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "integration_test_settings.json")

        # AppSettingsを初期化
        settings = AppSettings(settings_file)

        # いくつかの設定を変更
        settings.set('monitor_interval', 15)
        settings.set('realtime.model_size', 'small')
        settings.set('window.width', 1024)
        settings.set('window.height', 768)

        # 保存
        assert settings.save(), "設定保存失敗"
        print("[OK] 設定保存成功")

        # 新しいインスタンスで読み込み
        settings2 = AppSettings(settings_file)
        settings2.load()

        # 値を検証
        assert settings2.get('monitor_interval') == 15, "monitor_interval不一致"
        assert settings2.get('realtime.model_size') == 'small', "model_size不一致"
        assert settings2.get('window.width') == 1024, "window.width不一致"
        assert settings2.get('window.height') == 768, "window.height不一致"

        print("[OK] 設定読み込み成功")
        print("[OK] 設定値検証成功")

        # クリーンアップ
        shutil.rmtree(temp_dir)

        print()
        return True

    except Exception as e:
        print(f"[FAIL] 統合テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_debounce_functionality():
    """デバウンス機能のテスト"""
    print("=" * 60)
    print("Test 5: デバウンス機能テスト")
    print("=" * 60)

    try:
        import tempfile
        import shutil
        import time
        from app_settings import AppSettings

        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "debounce_test_settings.json")

        settings = AppSettings(settings_file)

        # デバウンス保存を複数回呼び出し
        for i in range(5):
            settings.set('monitor_interval', 10 + i)
            settings.save_debounced()

        print("[OK] デバウンス保存 5回呼び出し完了")

        # 少し待機（デバウンス遅延より短い）
        time.sleep(1.0)

        # まだ保存されていないはず
        if not os.path.exists(settings_file):
            print("[OK] デバウンス中 - まだ保存されていない")

        # デバウンス遅延を超えて待機
        time.sleep(1.5)

        # 保存されているはず
        if os.path.exists(settings_file):
            print("[OK] デバウンス完了 - 設定ファイル保存確認")
        else:
            print("[FAIL] 設定ファイルが保存されていません")
            return False

        # 即座保存のテスト
        settings.set('monitor_interval', 25)
        settings.save_immediate()

        # 即座に保存されているはず
        settings2 = AppSettings(settings_file)
        settings2.load()
        assert settings2.get('monitor_interval') == 25, "即座保存が反映されていません"
        print("[OK] 即座保存機能正常動作")

        # クリーンアップ
        shutil.rmtree(temp_dir)

        print()
        return True

    except Exception as e:
        print(f"[FAIL] デバウンステスト失敗: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def main():
    """全テストを実行"""
    print("\n" + "=" * 60)
    print("KotobaTranscriber - Main.py起動テスト")
    print("=" * 60)
    print()

    results = []

    # Test 1: インポートテスト
    results.append(("モジュールインポート", test_imports()))

    # Test 2: AppSettings初期化
    results.append(("AppSettings初期化", test_app_settings_initialization()))

    # Test 3: MainWindowクラス定義
    results.append(("MainWindowクラス定義", test_main_class_definition()))

    # Test 4: 統合テスト
    results.append(("main.py + AppSettings統合", test_main_settings_integration()))

    # Test 5: デバウンス機能
    results.append(("デバウンス機能", test_debounce_functionality()))

    # 結果サマリー
    print("=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {name}")

    print()
    print(f"合計: {passed}/{total} テスト成功")

    if passed == total:
        print("\n[SUCCESS] 全てのテストに合格しました！")
        return 0
    else:
        print(f"\n[FAILED] {total - passed} 個のテストが失敗しました")
        return 1


if __name__ == "__main__":
    sys.exit(main())
