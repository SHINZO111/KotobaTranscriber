"""
シンプル統合テストランナー - コアシナリオのみをテスト

pytest不要で実行できるシンプルなテストランナー
"""

import sys
import os
import tempfile
import shutil
import time
import threading
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app_settings import AppSettings


class TestResult:
    """テスト結果を保持するクラス"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"  [OK] PASS: {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  [FAIL] {test_name}")
        print(f"    Error: {error}")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "="*70)
        print(f"テスト結果: {self.passed}/{total} 成功")
        print("="*70)
        if self.failed > 0:
            print(f"\n失敗したテスト ({self.failed}):")
            for test_name, error in self.errors:
                print(f"  - {test_name}")
                print(f"    {error[:200]}")
        return self.failed == 0


def test_basic_persistence(result: TestResult):
    """基本テスト: 設定の永続化と復元"""
    test_name = "設定の永続化と復元"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")

        # 設定を作成して保存
        settings1 = AppSettings(settings_file)
        settings1.set('monitored_folder', 'C:/test/folder')
        settings1.set('monitor_interval', 20)
        settings1.save()

        # 新しいインスタンスで復元
        settings2 = AppSettings(settings_file)
        settings2.load()

        # 検証
        assert settings2.get('monitored_folder') == 'C:/test/folder'
        assert settings2.get('monitor_interval') == 20

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_default_fallback(result: TestResult):
    """基本テスト: デフォルト設定へのフォールバック"""
    test_name = "デフォルト設定へのフォールバック"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        non_existent = os.path.join(temp_dir, "non_existent.json")

        settings = AppSettings(non_existent)
        settings.load()  # ファイルが存在しなくてもエラーにならない

        # デフォルト値が使われているか確認
        assert settings.get('monitor_interval') == 10
        assert settings.get('realtime.model_size') == 'base'

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_concurrent_reads(result: TestResult):
    """マルチスレッドテスト: 並行読み取り"""
    test_name = "並行読み取り"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")

        settings = AppSettings(settings_file)
        settings.set('monitor_interval', 25)

        errors = []
        values = []

        def reader_thread():
            try:
                for _ in range(50):
                    value = settings.get('monitor_interval')
                    values.append(value)
            except Exception as e:
                errors.append(str(e))

        # 3つのスレッドを起動
        threads = [threading.Thread(target=reader_thread) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # 検証
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(values) == 150
        assert all(v == 25 for v in values)

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_concurrent_writes(result: TestResult):
    """マルチスレッドテスト: 並行書き込み"""
    test_name = "並行書き込み"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")

        settings = AppSettings(settings_file)

        errors = []
        counters = {'thread_0': 0, 'thread_1': 0}

        def writer_thread(thread_id: int):
            try:
                for i in range(20):
                    value = 10 + thread_id * 10 + i
                    settings.set('monitor_interval', value)
                    counters[f'thread_{thread_id}'] += 1
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        # 2つのスレッドを起動
        threads = [threading.Thread(target=writer_thread, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # 検証
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert sum(counters.values()) == 40

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_debounced_save(result: TestResult):
    """デバウンステスト: 連続操作シミュレーション"""
    test_name = "デバウンス保存"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")

        settings = AppSettings(settings_file)
        settings._save_debounce_delay = 0.5

        # 連続してデバウンス保存
        for i in range(10):
            settings.set('monitor_interval', 10 + i)
            settings.save_debounced()
            time.sleep(0.05)

        # デバウンス遅延の間待機
        time.sleep(1.0)

        # 検証
        assert os.path.exists(settings_file)
        settings2 = AppSettings(settings_file)
        settings2.load()
        assert settings2.get('monitor_interval') == 19

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_save_immediate(result: TestResult):
    """デバウンステスト: 即座保存"""
    test_name = "即座保存がデバウンスをキャンセル"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")

        settings = AppSettings(settings_file)
        settings._save_debounce_delay = 1.0

        # デバウンス保存をスケジュール
        settings.set('monitor_interval', 15)
        settings.save_debounced()

        # 即座に別の値で保存
        settings.set('monitor_interval', 25)
        settings.save_immediate()

        # 検証
        settings2 = AppSettings(settings_file)
        settings2.load()
        assert settings2.get('monitor_interval') == 25

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_path_traversal_prevention(result: TestResult):
    """セキュリティテスト: パストラバーサル防御"""
    test_name = "パストラバーサル防御"
    try:
        # 許可されたディレクトリ外のパスを指定
        malicious_path = "/etc/passwd"

        try:
            AppSettings(malicious_path)
            result.add_fail(test_name, "Path traversal attack was not prevented")
        except ValueError as e:
            if "must be within project directory" in str(e):
                result.add_pass(test_name)
            else:
                result.add_fail(test_name, f"Unexpected error: {e}")
    except Exception as e:
        result.add_fail(test_name, str(e))


def test_invalid_key_formats(result: TestResult):
    """セキュリティテスト: 無効なキーフォーマットの拒否"""
    test_name = "無効なキーフォーマットの拒否"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")
        settings = AppSettings(settings_file)

        invalid_keys = ['INVALID_KEY', 'invalid-key', 'invalid key', 'invalid@key']

        for invalid_key in invalid_keys:
            try:
                settings.set(invalid_key, 'value')
                result.add_fail(test_name, f"Invalid key '{invalid_key}' was accepted")
                return
            except ValueError:
                pass  # 期待通り

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_window_geometry_validation(result: TestResult):
    """UI設定テスト: ウィンドウジオメトリの検証"""
    test_name = "ウィンドウジオメトリの検証"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")
        settings = AppSettings(settings_file)

        # 正常な値
        settings.set('window.width', 1200)
        settings.set('window.height', 800)

        # 範囲外の値（最小値以下）
        try:
            settings.set('window.width', 50)
            result.add_fail(test_name, "Invalid window width was accepted")
            return
        except ValueError:
            pass

        # 範囲外の値（最大値以上）
        try:
            settings.set('window.width', 20000)
            result.add_fail(test_name, "Invalid window width was accepted")
            return
        except ValueError:
            pass

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_monitor_interval_validation(result: TestResult):
    """UI設定テスト: 監視間隔の検証"""
    test_name = "監視間隔の検証"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")
        settings = AppSettings(settings_file)

        # 正常な値
        settings.set('monitor_interval', 15)
        settings.set('monitor_interval', 30)

        # 範囲外の値（最小値未満）
        try:
            settings.set('monitor_interval', 3)
            result.add_fail(test_name, "Invalid monitor_interval was accepted")
            return
        except ValueError:
            pass

        # 範囲外の値（最大値超過）
        try:
            settings.set('monitor_interval', 100)
            result.add_fail(test_name, "Invalid monitor_interval was accepted")
            return
        except ValueError:
            pass

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_deep_copy_isolation(result: TestResult):
    """UI設定テスト: 深いコピーの検証"""
    test_name = "深いコピーの隔離"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")
        settings = AppSettings(settings_file)

        # 設定を取得
        settings_dict = settings.get_all()

        # 辞書を変更
        settings_dict['monitored_folder'] = 'modified_value'
        settings_dict['realtime']['model_size'] = 'modified_model'

        # 元の設定が変更されていないことを確認
        assert settings.get('monitored_folder') != 'modified_value'
        assert settings.get('realtime.model_size') != 'modified_model'

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_slider_simulation(result: TestResult):
    """実シナリオテスト: スライダー連続操作"""
    test_name = "スライダー連続操作シミュレーション"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")

        settings = AppSettings(settings_file)
        settings._save_debounce_delay = 0.3

        # スライダーを連続調整
        for i in range(10, 20):
            settings.set('monitor_interval', i)
            settings.save_debounced()
            time.sleep(0.05)

        # アプリ終了時の即座保存
        settings.save_immediate()

        # 検証
        settings2 = AppSettings(settings_file)
        settings2.load()
        assert settings2.get('monitor_interval') == 19

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_app_restart(result: TestResult):
    """実シナリオテスト: アプリ再起動シミュレーション"""
    test_name = "アプリ再起動シミュレーション"
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        settings_file = os.path.join(temp_dir, "test.json")

        # 初回起動
        settings1 = AppSettings(settings_file)
        settings1.set('monitored_folder', 'C:/monitored')
        settings1.set('monitor_interval', 20)
        settings1.set('remove_fillers', False)
        settings1.save()

        # 再起動
        settings2 = AppSettings(settings_file)
        settings2.load()

        # 検証
        assert settings2.get('monitored_folder') == 'C:/monitored'
        assert settings2.get('monitor_interval') == 20
        assert settings2.get('remove_fillers') == False

        result.add_pass(test_name)
    except Exception as e:
        result.add_fail(test_name, str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def run_all_tests():
    """すべてのコアテストを実行"""
    result = TestResult()

    print("="*70)
    print("AppSettings統合テスト - コアシナリオ")
    print("="*70)
    print()

    # カテゴリ1: 基本統合テスト
    print("[1/5] 基本統合テスト")
    test_basic_persistence(result)
    test_default_fallback(result)
    print()

    # カテゴリ2: マルチスレッド統合テスト
    print("[2/5] マルチスレッド統合テスト")
    test_concurrent_reads(result)
    test_concurrent_writes(result)
    print()

    # カテゴリ3: デバウンス統合テスト
    print("[3/5] デバウンス統合テスト")
    test_debounced_save(result)
    test_save_immediate(result)
    print()

    # カテゴリ4: セキュリティ統合テスト
    print("[4/5] セキュリティ統合テスト")
    test_path_traversal_prevention(result)
    test_invalid_key_formats(result)
    print()

    # カテゴリ5: UI設定 + 実シナリオ統合テスト
    print("[5/5] UI設定 + 実シナリオ統合テスト")
    test_window_geometry_validation(result)
    test_monitor_interval_validation(result)
    test_deep_copy_isolation(result)
    test_slider_simulation(result)
    test_app_restart(result)
    print()

    # サマリー
    success = result.summary()

    return 0 if success else 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
