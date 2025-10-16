"""
Simple test runner for AppSettings without pytest dependency issues
"""

import sys
from pathlib import Path
import tempfile
import json
import threading
import time
import copy

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app_settings import AppSettings

# Test counters
total_tests = 0
passed_tests = 0
failed_tests = 0


def test(name):
    """Test decorator"""
    def decorator(func):
        def wrapper():
            global total_tests, passed_tests, failed_tests
            total_tests += 1
            try:
                func()
                passed_tests += 1
                print(f"[PASS] {name}")
                return True
            except AssertionError as e:
                failed_tests += 1
                print(f"[FAIL] {name}")
                print(f"  Error: {e}")
                return False
            except Exception as e:
                failed_tests += 1
                print(f"[FAIL] {name}")
                print(f"  Unexpected error: {e}")
                return False
        return wrapper
    return decorator


# Basic functionality tests
@test("デフォルト設定で初期化できることを確認")
def test_default_initialization():
    settings = AppSettings()
    assert settings.get('monitor_interval') == 10
    assert settings.get('realtime.model_size') == 'base'
    assert settings.get('remove_fillers') is True


@test("ネストされたキーにアクセスできることを確認")
def test_nested_key_access():
    settings = AppSettings()
    settings.set('realtime.model_size', 'medium')
    assert settings.get('realtime.model_size') == 'medium'


@test("存在しないキーのデフォルト値が返ることを確認")
def test_get_with_default():
    settings = AppSettings()
    assert settings.get('nonexistent_key', 'default_value') == 'default_value'
    assert settings.get('nonexistent_key') is None


@test("全設定を取得できることを確認")
def test_get_all():
    settings = AppSettings()
    all_settings = settings.get_all()
    assert 'monitor_interval' in all_settings
    assert 'realtime' in all_settings


# Persistence tests
@test("保存と読み込みが正しく動作することを確認")
def test_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_file = Path(tmpdir) / "test_settings.json"

        # Save
        settings1 = AppSettings(str(settings_file))
        settings1.set('monitor_interval', 20)
        settings1.set('realtime.model_size', 'large-v2')
        assert settings1.save()

        # Load
        settings2 = AppSettings(str(settings_file))
        assert settings2.load()
        assert settings2.get('monitor_interval') == 20
        assert settings2.get('realtime.model_size') == 'large-v2'


@test("存在しないファイルの読み込み時にFalseが返ることを確認")
def test_load_nonexistent_file():
    # Use a path within the project directory
    nonexistent_path = Path(__file__).parent.parent / "nonexistent_settings.json"
    settings = AppSettings(str(nonexistent_path))
    assert settings.load() is False
    assert settings.get('monitor_interval') == 10  # Default value


@test("破損したJSONファイルの処理を確認")
def test_corrupted_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_file = Path(tmpdir) / "corrupted.json"
        settings_file.write_text("{invalid json", encoding='utf-8')

        settings = AppSettings(str(settings_file))
        assert settings.load() is False
        assert settings.get('monitor_interval') == 10  # Default value


# Thread safety tests
@test("複数スレッドからの同時読み取りが安全であることを確認")
def test_concurrent_reads():
    settings = AppSettings()
    settings.set('monitor_interval', 10)

    results = []
    def reader():
        for _ in range(100):
            value = settings.get('monitor_interval')
            results.append(value)

    threads = [threading.Thread(target=reader) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(v == 10 for v in results)
    assert len(results) == 1000


@test("複数スレッドからの同時書き込みが安全であることを確認")
def test_concurrent_writes():
    settings = AppSettings()

    def writer(value):
        for _ in range(100):
            settings.set('monitor_interval', value)
            time.sleep(0.0001)

    # Use valid values (5-15) instead of (0-9)
    threads = [threading.Thread(target=writer, args=(i + 5,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should complete without crashing
    final_value = settings.get('monitor_interval')
    assert isinstance(final_value, int)
    assert 5 <= final_value <= 15  # Should be one of the valid values we set


# Merge tests
@test("マージ時にデフォルト設定が保持されることを確認")
def test_merge_preserves_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_file = Path(tmpdir) / "partial.json"

        partial_settings = {'monitor_interval': 20}
        settings_file.write_text(json.dumps(partial_settings), encoding='utf-8')

        settings = AppSettings(str(settings_file))
        settings.load()

        assert settings.get('monitor_interval') == 20
        assert settings.get('realtime.model_size') == 'base'  # Default preserved


@test("ネストされた辞書が正しくマージされることを確認")
def test_merge_nested_dicts():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_file = Path(tmpdir) / "nested.json"

        partial_settings = {
            'realtime': {
                'model_size': 'medium'
            }
        }
        settings_file.write_text(json.dumps(partial_settings), encoding='utf-8')

        settings = AppSettings(str(settings_file))
        settings.load()

        assert settings.get('realtime.model_size') == 'medium'
        assert settings.get('realtime.vad_enabled') is True  # Default preserved


# Deep copy tests
@test("インスタンス間で状態が共有されないことを確認")
def test_no_shared_state():
    settings1 = AppSettings()
    settings2 = AppSettings()

    settings1.set('realtime.model_size', 'large-v2')

    assert settings2.get('realtime.model_size') == 'base'


@test("resetがデフォルトに戻すことを確認")
def test_reset():
    settings = AppSettings()

    settings.set('realtime.model_size', 'large-v2')
    settings.set('monitor_interval', 30)

    settings.reset()

    assert settings.get('realtime.model_size') == 'base'
    assert settings.get('monitor_interval') == 10


@test("get_all()がディープコピーを返すことを確認")
def test_get_all_deep_copy():
    settings = AppSettings()

    all_settings = settings.get_all()
    all_settings['monitor_interval'] = 999
    all_settings['realtime']['model_size'] = 'modified'

    # Original should be unchanged
    assert settings.get('monitor_interval') == 10
    assert settings.get('realtime.model_size') == 'base'


# Security tests
@test("パストラバーサル攻撃が防がれることを確認")
def test_path_traversal_prevention():
    try:
        AppSettings("/etc/passwd")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Settings file must be within" in str(e)


@test("プロジェクトディレクトリ内のパスが許可されることを確認")
def test_allowed_project_path():
    settings_file = Path(__file__).parent.parent / "test_settings.json"
    settings = AppSettings(str(settings_file))
    assert settings is not None


# Atomic save tests
@test("アトミック保存が一時ファイルを使用することを確認")
def test_atomic_save():
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_file = Path(tmpdir) / "atomic_test.json"
        settings = AppSettings(str(settings_file))
        settings.set('monitor_interval', 15)

        assert settings.save()

        # Temp file should not exist after successful save
        temp_file = settings_file.with_suffix('.tmp')
        assert not temp_file.exists()
        assert settings_file.exists()


# DEFAULT_SETTINGS immutability tests
@test("DEFAULT_SETTINGS定数が変更されないことを確認")
def test_default_settings_immutability():
    original_defaults = copy.deepcopy(AppSettings.DEFAULT_SETTINGS)

    settings = AppSettings()
    settings.set('monitor_interval', 25)  # Use valid value (5-60)
    settings.set('realtime.model_size', 'medium')  # Use valid model size

    assert AppSettings.DEFAULT_SETTINGS == original_defaults


# Run all tests
def main():
    print("\n=== Running AppSettings Tests ===\n")

    # Get all test functions
    test_funcs = [
        obj for name, obj in globals().items()
        if callable(obj) and name.startswith('test_')
    ]

    # Run tests
    for test_func in test_funcs:
        test_func()

    # Print summary
    print(f"\n{'='*50}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"{'='*50}\n")

    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
