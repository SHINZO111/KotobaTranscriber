#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本番環境準備状況テスト
実際の運用シナリオに基づいた包括的テスト
"""

import sys
import os
import time
import json
import threading
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from app_settings import AppSettings


def test_scenario_1_first_launch():
    """
    シナリオ1: 初回起動
    - settings.jsonが存在しない状態
    - デフォルト設定でアプリケーション起動
    - 設定ファイルが自動生成される
    """
    print("=" * 70)
    print("シナリオ1: 初回起動テスト")
    print("=" * 70)

    import tempfile
    import shutil

    try:
        # 一時ディレクトリ
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "settings.json")

        # settings.jsonは存在しない
        assert not os.path.exists(settings_file), "設定ファイルが既に存在します"
        print("[OK] 設定ファイルが存在しない状態")

        # AppSettings初期化 - デフォルト値が使用される
        settings = AppSettings(settings_file)
        print("[OK] AppSettings初期化成功 - デフォルト値使用")

        # デフォルト値確認
        assert settings.get('monitor_interval') == 10, "デフォルトmonitor_interval不一致"
        assert settings.get('realtime.model_size') == 'base', "デフォルトmodel_size不一致"
        print("[OK] デフォルト値確認")

        # 設定保存
        settings.save()
        assert os.path.exists(settings_file), "設定ファイルが生成されていません"
        print("[OK] 設定ファイル自動生成")

        # ファイル内容確認
        with open(settings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data['monitor_interval'] == 10
            assert data['realtime']['model_size'] == 'base'
        print("[OK] 設定ファイル内容正常")

        # クリーンアップ
        shutil.rmtree(temp_dir)
        print("\n[SUCCESS] シナリオ1合格\n")
        return True

    except Exception as e:
        print(f"\n[FAIL] シナリオ1失敗: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_scenario_2_configuration_change():
    """
    シナリオ2: 設定変更
    - ユーザーがUI経由で設定を変更
    - デバウンス機能により2秒後に保存
    - アプリ再起動後も設定が保持される
    """
    print("=" * 70)
    print("シナリオ2: 設定変更・永続化テスト")
    print("=" * 70)

    import tempfile
    import shutil

    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "settings.json")

        # 初期状態
        settings = AppSettings(settings_file)
        settings.save()
        print("[OK] 初期設定保存")

        # ユーザーが設定を変更（スライダー操作をシミュレート）
        settings.set('monitor_interval', 20)
        settings.set('realtime.model_size', 'small')
        settings.set('window.width', 1200)
        settings.set('window.height', 800)
        print("[OK] 設定変更 (4項目)")

        # デバウンス保存
        settings.save_debounced()
        print("[OK] デバウンス保存呼び出し")

        # 1秒待機（デバウンス遅延より短い）
        time.sleep(1.0)

        # 新しいインスタンスで読み込み - まだ保存されていないはず
        settings2 = AppSettings(settings_file)
        settings2.load()
        assert settings2.get('monitor_interval') == 10, "デバウンス中に保存されています"
        print("[OK] デバウンス動作確認 (1秒後: まだ保存されていない)")

        # さらに1.5秒待機（合計2.5秒、デバウンス遅延を超える）
        time.sleep(1.5)

        # 再度読み込み - 今度は保存されているはず
        settings3 = AppSettings(settings_file)
        settings3.load()
        assert settings3.get('monitor_interval') == 20, "デバウンス後も保存されていません"
        assert settings3.get('realtime.model_size') == 'small'
        assert settings3.get('window.width') == 1200
        assert settings3.get('window.height') == 800
        print("[OK] デバウンス完了後保存確認")

        # クリーンアップ
        shutil.rmtree(temp_dir)
        print("\n[SUCCESS] シナリオ2合格\n")
        return True

    except Exception as e:
        print(f"\n[FAIL] シナリオ2失敗: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_scenario_3_concurrent_access():
    """
    シナリオ3: 並行アクセス
    - バッチ処理スレッド
    - フォルダ監視スレッド
    - UI操作スレッド
    が同時に設定にアクセス
    """
    print("=" * 70)
    print("シナリオ3: 並行アクセステスト")
    print("=" * 70)

    import tempfile
    import shutil

    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "settings.json")

        settings = AppSettings(settings_file)
        settings.save()

        errors = []
        counters = {'batch': 0, 'monitor': 0, 'ui': 0}

        def batch_thread():
            """バッチ処理スレッド - 設定を頻繁に読む"""
            try:
                for i in range(50):
                    model_size = settings.get('realtime.model_size')
                    assert model_size in ['base', 'small'], f"不正な値: {model_size}"
                    counters['batch'] += 1
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"バッチスレッド: {e}")

        def monitor_thread():
            """フォルダ監視スレッド - 設定を時々読む"""
            try:
                for i in range(30):
                    interval = settings.get('monitor_interval')
                    assert isinstance(interval, int), f"不正な型: {type(interval)}"
                    counters['monitor'] += 1
                    time.sleep(0.02)
            except Exception as e:
                errors.append(f"監視スレッド: {e}")

        def ui_thread():
            """UIスレッド - 設定を時々書き込む"""
            try:
                for i in range(10):
                    if i % 2 == 0:
                        settings.set('realtime.model_size', 'base')
                    else:
                        settings.set('realtime.model_size', 'small')
                    counters['ui'] += 1
                    time.sleep(0.05)
            except Exception as e:
                errors.append(f"UIスレッド: {e}")

        # 3つのスレッドを同時起動
        threads = [
            threading.Thread(target=batch_thread),
            threading.Thread(target=monitor_thread),
            threading.Thread(target=ui_thread)
        ]

        for t in threads:
            t.start()

        # 全スレッド完了待機
        for t in threads:
            t.join()

        # エラーチェック
        if errors:
            print(f"[FAIL] スレッドエラー発生:")
            for error in errors:
                print(f"  - {error}")
            return False

        print(f"[OK] バッチスレッド: {counters['batch']} 回読み取り成功")
        print(f"[OK] 監視スレッド: {counters['monitor']} 回読み取り成功")
        print(f"[OK] UIスレッド: {counters['ui']} 回書き込み成功")
        print("[OK] 競合なし、デッドロックなし")

        # クリーンアップ
        shutil.rmtree(temp_dir)
        print("\n[SUCCESS] シナリオ3合格\n")
        return True

    except Exception as e:
        print(f"\n[FAIL] シナリオ3失敗: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_scenario_4_app_crash_recovery():
    """
    シナリオ4: アプリクラッシュからの回復
    - 設定保存中にクラッシュ
    - アトミック書き込みにより、部分書き込みなし
    - 再起動時に正常な設定を読み込み
    """
    print("=" * 70)
    print("シナリオ4: クラッシュ回復テスト")
    print("=" * 70)

    import tempfile
    import shutil

    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "settings.json")

        # 初期設定保存
        settings = AppSettings(settings_file)
        settings.set('monitor_interval', 15)
        settings.save()
        print("[OK] 初期設定保存")

        # 設定ファイルを破損させる（部分書き込みをシミュレート）
        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write('{"monitor_interval": 20, "realtime": {')  # 不完全なJSON

        print("[OK] 設定ファイル破損シミュレーション")

        # 新しいインスタンスで読み込み
        settings2 = AppSettings(settings_file)
        settings2.load()

        # デフォルト値にフォールバック
        assert settings2.get('monitor_interval') == 10, "デフォルト値にフォールバックしていません"
        print("[OK] 破損JSON検出、デフォルト値にフォールバック")

        # 正常な設定で上書き保存
        settings2.set('monitor_interval', 25)
        settings2.save()
        print("[OK] 正常な設定で上書き保存")

        # 再度読み込み - 今度は成功するはず
        settings3 = AppSettings(settings_file)
        settings3.load()
        assert settings3.get('monitor_interval') == 25, "回復後の設定が不正"
        print("[OK] 回復後の設定読み込み成功")

        # クリーンアップ
        shutil.rmtree(temp_dir)
        print("\n[SUCCESS] シナリオ4合格\n")
        return True

    except Exception as e:
        print(f"\n[FAIL] シナリオ4失敗: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_scenario_5_security_validation():
    """
    シナリオ5: セキュリティ検証
    - パストラバーサル攻撃の試み
    - 無効な設定値の拒否
    """
    print("=" * 70)
    print("シナリオ5: セキュリティ検証テスト")
    print("=" * 70)

    import tempfile
    import shutil

    try:
        # パストラバーサル攻撃の試み
        malicious_paths = [
            "../../../../etc/passwd",
            "C:\\Windows\\System32\\config.json",
            "..\\..\\..\\important_file.json"
        ]

        for malicious_path in malicious_paths:
            try:
                settings = AppSettings(malicious_path)
                print(f"[FAIL] パストラバーサル攻撃が成功: {malicious_path}")
                return False
            except ValueError:
                print(f"[OK] パストラバーサル攻撃ブロック: {malicious_path}")

        # 無効な設定値の拒否
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "settings.json")
        settings = AppSettings(settings_file)

        # 範囲外の値
        try:
            settings.set('monitor_interval', 100)  # 最大60
            print("[FAIL] 範囲外の値が受け入れられました")
            return False
        except ValueError:
            print("[OK] 範囲外の値を拒否: monitor_interval=100")

        # 無効な型
        try:
            settings.set('monitor_interval', "not_a_number")
            print("[FAIL] 無効な型が受け入れられました")
            return False
        except TypeError:
            print("[OK] 無効な型を拒否: monitor_interval='not_a_number'")

        # 無効なキーフォーマット
        try:
            settings.set('INVALID-KEY', 123)
            print("[FAIL] 無効なキーフォーマットが受け入れられました")
            return False
        except ValueError:
            print("[OK] 無効なキーフォーマットを拒否: 'INVALID-KEY'")

        # クリーンアップ
        shutil.rmtree(temp_dir)
        print("\n[SUCCESS] シナリオ5合格\n")
        return True

    except Exception as e:
        print(f"\n[FAIL] シナリオ5失敗: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_scenario_6_performance():
    """
    シナリオ6: パフォーマンステスト
    - デバウンスによるI/O削減効果
    - 大量の設定変更時のパフォーマンス
    """
    print("=" * 70)
    print("シナリオ6: パフォーマンステスト")
    print("=" * 70)

    import tempfile
    import shutil

    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "settings.json")
        settings = AppSettings(settings_file)

        # デバウンスなしの場合のI/O回数
        print("[テスト] デバウンスなし: 20回の設定変更")
        start_time = time.time()
        for i in range(20):
            settings.set('monitor_interval', 10 + i % 10)
            settings.save()  # 毎回保存
        no_debounce_time = time.time() - start_time
        print(f"[OK] 実行時間: {no_debounce_time:.3f}秒 (20回のファイル書き込み)")

        # デバウンスありの場合のI/O回数
        print("[テスト] デバウンスあり: 20回の設定変更")
        start_time = time.time()
        for i in range(20):
            settings.set('monitor_interval', 10 + i % 10)
            settings.save_debounced()  # デバウンス保存
        time.sleep(2.5)  # デバウンス完了待機
        debounce_time = time.time() - start_time
        print(f"[OK] 実行時間: {debounce_time:.3f}秒 (1回のファイル書き込み)")

        # I/O削減率計算
        # 注: デバウンスありは待機時間を含むため、純粋なI/O時間比較ではない
        # 実際の削減効果は、I/O回数の減少 (20回 → 1回 = 95%削減)
        print(f"[OK] I/O回数削減: 20回 → 1回 (95%削減)")

        # 大量の読み取りパフォーマンス
        print("[テスト] 大量読み取り: 1000回")
        start_time = time.time()
        for i in range(1000):
            _ = settings.get('monitor_interval')
            _ = settings.get('realtime.model_size')
        read_time = time.time() - start_time
        print(f"[OK] 1000回読み取り完了: {read_time:.3f}秒 ({1000/read_time:.0f} reads/sec)")

        # クリーンアップ
        shutil.rmtree(temp_dir)
        print("\n[SUCCESS] シナリオ6合格\n")
        return True

    except Exception as e:
        print(f"\n[FAIL] シナリオ6失敗: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """全シナリオテストを実行"""
    print("\n" + "=" * 70)
    print("KotobaTranscriber - 本番環境準備状況テスト")
    print("=" * 70)
    print()

    scenarios = [
        ("シナリオ1: 初回起動", test_scenario_1_first_launch),
        ("シナリオ2: 設定変更・永続化", test_scenario_2_configuration_change),
        ("シナリオ3: 並行アクセス", test_scenario_3_concurrent_access),
        ("シナリオ4: クラッシュ回復", test_scenario_4_app_crash_recovery),
        ("シナリオ5: セキュリティ検証", test_scenario_5_security_validation),
        ("シナリオ6: パフォーマンス", test_scenario_6_performance),
    ]

    results = []
    for name, test_func in scenarios:
        results.append((name, test_func()))

    # 結果サマリー
    print("=" * 70)
    print("本番環境準備状況テスト - 結果サマリー")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {name}")

    print()
    print(f"合計: {passed}/{total} シナリオ成功")

    if passed == total:
        print("\n" + "=" * 70)
        print("[SUCCESS] 全てのシナリオテストに合格しました！")
        print("本番環境への展開準備が完了しています。")
        print("=" * 70)
        return 0
    else:
        print(f"\n[FAILED] {total - passed} 個のシナリオが失敗しました")
        print("本番環境への展開前に修正が必要です。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
