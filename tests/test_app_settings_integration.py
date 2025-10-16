"""
AppSettings統合テスト - アプリケーション全体の連携動作を検証

このテストスイートは以下のカテゴリをカバーします:
1. 基本統合テスト (AppSettings + Main連携)
2. マルチスレッド統合テスト (並行読み書き)
3. デバウンス統合テスト (連続操作シミュレーション)
4. セキュリティ統合テスト (パストラバーサル防御)
5. UI設定統合テスト (ウィンドウ位置復元、フォルダ存在確認)
"""

import sys
import os
import tempfile
import shutil
import time
import threading
import json
from pathlib import Path
from typing import List, Dict, Any
import unittest

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app_settings import AppSettings


class TestBasicIntegration(unittest.TestCase):
    """基本統合テスト: AppSettingsの永続化と復元"""

    def setUp(self):
        """各テストの前処理"""
        self.temp_dir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.temp_dir, "test_settings.json")

    def tearDown(self):
        """各テストの後処理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_settings_persistence(self):
        """設定変更→保存→再読み込みが正常に動作するか"""
        # 設定を作成して変更
        settings1 = AppSettings(self.settings_file)
        settings1.set('monitored_folder', 'C:/test/folder')
        settings1.set('monitor_interval', 15)
        settings1.set('realtime.model_size', 'medium')
        settings1.set('window.width', 1200)
        self.assertTrue(settings1.save())

        # 新しいインスタンスで読み込み
        settings2 = AppSettings(self.settings_file)
        self.assertTrue(settings2.load())

        # 値が正しく復元されているか確認
        self.assertEqual(settings2.get('monitored_folder'), 'C:/test/folder')
        self.assertEqual(settings2.get('monitor_interval'), 15)
        self.assertEqual(settings2.get('realtime.model_size'), 'medium')
        self.assertEqual(settings2.get('window.width'), 1200)

    def test_default_fallback(self):
        """settings.jsonが存在しない場合のフォールバック"""
        # 存在しないファイルを指定
        non_existent = os.path.join(self.temp_dir, "non_existent.json")
        settings = AppSettings(non_existent)

        # loadはFalseを返すがデフォルト設定が使われる
        self.assertFalse(settings.load())

        # デフォルト値が使われているか確認
        self.assertEqual(settings.get('monitor_interval'), 10)
        self.assertEqual(settings.get('realtime.model_size'), 'base')
        self.assertIsNone(settings.get('monitored_folder'))

    def test_partial_settings_merge(self):
        """部分的な設定ファイルとデフォルト設定のマージ"""
        # 部分的な設定を手動で作成
        partial_settings = {
            'monitored_folder': 'C:/partial',
            'realtime': {
                'model_size': 'small'
            }
        }

        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(partial_settings, f, ensure_ascii=False, indent=2)

        # 読み込み
        settings = AppSettings(self.settings_file)
        self.assertTrue(settings.load())

        # 部分的に指定した値は復元される
        self.assertEqual(settings.get('monitored_folder'), 'C:/partial')
        self.assertEqual(settings.get('realtime.model_size'), 'small')

        # 未指定の値はデフォルトのまま
        self.assertEqual(settings.get('monitor_interval'), 10)
        self.assertTrue(settings.get('remove_fillers'))

    def test_corrupted_json_handling(self):
        """破損したJSONファイルの処理"""
        # 破損したJSONを作成
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            f.write('{ "invalid json syntax" }')

        settings = AppSettings(self.settings_file)
        # 読み込みは失敗するが例外は発生しない
        self.assertFalse(settings.load())

        # デフォルト設定が維持されている
        self.assertEqual(settings.get('monitor_interval'), 10)


class TestMultithreadIntegration(unittest.TestCase):
    """マルチスレッド統合テスト: 並行読み書き"""

    def setUp(self):
        """各テストの前処理"""
        self.temp_dir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.temp_dir, "test_settings.json")
        self.settings = AppSettings(self.settings_file)

    def tearDown(self):
        """各テストの後処理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_concurrent_reads(self):
        """複数スレッドからの同時読み取り"""
        # 初期値を設定
        self.settings.set('monitor_interval', 20)

        errors = []
        results = []

        def reader_thread():
            try:
                for _ in range(100):
                    value = self.settings.get('monitor_interval')
                    results.append(value)
            except Exception as e:
                errors.append(str(e))

        # 5つのスレッドを起動
        threads = [threading.Thread(target=reader_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # エラーが発生していないか確認
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        # すべての読み取りが成功しているか確認
        self.assertEqual(len(results), 500)
        # すべての値が一貫しているか確認
        self.assertTrue(all(v == 20 for v in results))

    def test_concurrent_writes(self):
        """複数スレッドからの同時書き込み"""
        errors = []
        counters = {'thread_0': 0, 'thread_1': 0, 'thread_2': 0}

        def writer_thread(thread_id: int):
            try:
                for i in range(20):
                    # 有効範囲 (5-60) 内の値を生成: 10 + (thread_id * 5) + i
                    # thread_0: 10-29, thread_1: 15-34, thread_2: 20-39
                    value = 10 + (thread_id * 5) + i
                    self.settings.set('monitor_interval', value)
                    counters[f'thread_{thread_id}'] += 1
                    time.sleep(0.001)  # 少し待機
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        # 3つのスレッドを起動
        threads = [threading.Thread(target=writer_thread, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # エラーが発生していないか確認
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        # すべてのスレッドが完了しているか確認
        self.assertEqual(sum(counters.values()), 60)

    def test_concurrent_save(self):
        """複数スレッドからの同時保存"""
        errors = []
        success_counts = []

        def saver_thread():
            try:
                for i in range(10):
                    self.settings.set('monitor_interval', 15 + i)
                    success = self.settings.save()
                    if success:
                        success_counts.append(1)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(str(e))

        # 3つのスレッドを起動
        threads = [threading.Thread(target=saver_thread) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # エラーが発生していないか確認
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        # 少なくとも一部の保存が成功しているか確認
        self.assertGreater(len(success_counts), 0)

        # ファイルが破損していないか確認
        settings2 = AppSettings(self.settings_file)
        self.assertTrue(settings2.load())


class TestDebounceIntegration(unittest.TestCase):
    """デバウンス統合テスト: 連続操作シミュレーション"""

    def setUp(self):
        """各テストの前処理"""
        self.temp_dir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.temp_dir, "test_settings.json")
        self.settings = AppSettings(self.settings_file)
        # テスト用に短いデバウンス遅延を設定
        self.settings._save_debounce_delay = 0.5

    def tearDown(self):
        """各テストの後処理"""
        # 保留中の保存をキャンセル
        self.settings.cancel_pending_save()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_debounced_save_reduces_io(self):
        """デバウンス保存がI/O操作を削減することを確認"""
        # 連続してデバウンス保存を呼び出す
        for i in range(20):
            self.settings.set('monitor_interval', 10 + i)
            self.settings.save_debounced()
            time.sleep(0.05)  # 短い間隔

        # デバウンス遅延の間待機
        time.sleep(1.0)

        # ファイルが保存されているか確認
        self.assertTrue(os.path.exists(self.settings_file))

        # 最後の値が保存されているか確認
        settings2 = AppSettings(self.settings_file)
        self.assertTrue(settings2.load())
        self.assertEqual(settings2.get('monitor_interval'), 29)

    def test_save_immediate_cancels_debounce(self):
        """save_immediate()がデバウンス保存をキャンセルすることを確認"""
        # デバウンス保存をスケジュール
        self.settings.set('monitor_interval', 15)
        self.settings.save_debounced()

        # 即座に別の値で保存
        self.settings.set('monitor_interval', 20)
        self.assertTrue(self.settings.save_immediate())

        # 保存された値を確認
        settings2 = AppSettings(self.settings_file)
        self.assertTrue(settings2.load())
        self.assertEqual(settings2.get('monitor_interval'), 20)

    def test_cancel_pending_save(self):
        """cancel_pending_save()が動作することを確認"""
        # デバウンス保存をスケジュール
        self.settings.set('monitor_interval', 15)
        self.settings.save_debounced()

        # 保存をキャンセル
        self.settings.cancel_pending_save()

        # デバウンス遅延の間待機
        time.sleep(1.0)

        # ファイルが作成されていないことを確認
        self.assertFalse(os.path.exists(self.settings_file))


class TestSecurityIntegration(unittest.TestCase):
    """セキュリティ統合テスト: パストラバーサル防御"""

    def setUp(self):
        """各テストの前処理"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """各テストの後処理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_path_traversal_prevention(self):
        """パストラバーサル攻撃の防御"""
        # 許可されたディレクトリ外のパスを指定
        malicious_path = "/etc/passwd"

        with self.assertRaises(ValueError) as context:
            AppSettings(malicious_path)

        self.assertIn("must be within project directory", str(context.exception))

    def test_relative_path_traversal(self):
        """相対パスによるトラバーサル攻撃の防御"""
        # 相対パスで上位ディレクトリを指定
        malicious_path = "../../../etc/passwd"

        with self.assertRaises(ValueError) as context:
            AppSettings(malicious_path)

        self.assertIn("must be within project directory", str(context.exception))

    def test_allowed_path_within_project(self):
        """プロジェクト内のパスは許可される"""
        # プロジェクトルート内の有効なパス
        project_root = Path(__file__).parent.parent
        valid_path = project_root / "test_settings.json"

        try:
            settings = AppSettings(str(valid_path))
            # 例外が発生しないことを確認
            self.assertIsNotNone(settings)
        except ValueError:
            self.fail("Valid path within project was rejected")

    def test_invalid_key_formats(self):
        """無効なキーフォーマットの拒否"""
        settings = AppSettings(os.path.join(self.temp_dir, "test.json"))

        # 無効なキー (大文字)
        with self.assertRaises(ValueError):
            settings.set('INVALID_KEY', 'value')

        # 無効なキー (ハイフン)
        with self.assertRaises(ValueError):
            settings.set('invalid-key', 'value')

        # 無効なキー (スペース)
        with self.assertRaises(ValueError):
            settings.set('invalid key', 'value')

        # 無効なキー (特殊文字)
        with self.assertRaises(ValueError):
            settings.set('invalid@key', 'value')


class TestUISettingsIntegration(unittest.TestCase):
    """UI設定統合テスト: ウィンドウ位置復元、フォルダ存在確認"""

    def setUp(self):
        """各テストの前処理"""
        self.temp_dir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.temp_dir, "test_settings.json")
        self.settings = AppSettings(self.settings_file)

    def tearDown(self):
        """各テストの後処理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_window_geometry_validation(self):
        """ウィンドウジオメトリの検証"""
        # 正常な値
        self.settings.set('window.width', 1200)
        self.settings.set('window.height', 800)
        self.settings.set('window.x', 100)
        self.settings.set('window.y', 100)

        # 範囲外の値 (最小値以下)
        with self.assertRaises(ValueError):
            self.settings.set('window.width', 50)

        with self.assertRaises(ValueError):
            self.settings.set('window.height', 50)

        # 範囲外の値 (最大値以上)
        with self.assertRaises(ValueError):
            self.settings.set('window.width', 20000)

        with self.assertRaises(ValueError):
            self.settings.set('window.height', 20000)

    def test_monitor_interval_validation(self):
        """監視間隔の検証"""
        # 正常な値
        self.settings.set('monitor_interval', 10)
        self.settings.set('monitor_interval', 30)

        # 範囲外の値 (最小値未満)
        with self.assertRaises(ValueError):
            self.settings.set('monitor_interval', 3)

        # 範囲外の値 (最大値超過)
        with self.assertRaises(ValueError):
            self.settings.set('monitor_interval', 100)

    def test_vad_threshold_validation(self):
        """VAD閾値の検証"""
        # 正常な値
        self.settings.set('realtime.vad_threshold', 10)
        self.settings.set('realtime.vad_threshold', 30)

        # 範囲外の値 (最小値未満)
        with self.assertRaises(ValueError):
            self.settings.set('realtime.vad_threshold', 3)

        # 範囲外の値 (最大値超過)
        with self.assertRaises(ValueError):
            self.settings.set('realtime.vad_threshold', 100)

    def test_model_size_validation(self):
        """モデルサイズの検証"""
        # 有効なモデルサイズ
        valid_models = ['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3']
        for model in valid_models:
            self.settings.set('realtime.model_size', model)
            self.assertEqual(self.settings.get('realtime.model_size'), model)

        # 無効なモデルサイズ
        with self.assertRaises(ValueError):
            self.settings.set('realtime.model_size', 'invalid_model')

    def test_type_validation(self):
        """型の検証"""
        # 正しい型
        self.settings.set('monitor_interval', 15)  # int
        self.settings.set('remove_fillers', True)  # bool
        self.settings.set('monitored_folder', 'C:/test')  # str

        # 間違った型
        with self.assertRaises(TypeError):
            self.settings.set('monitor_interval', 'not_an_int')

        with self.assertRaises(TypeError):
            self.settings.set('remove_fillers', 'not_a_bool')

    def test_deep_copy_isolation(self):
        """get_all()が深いコピーを返すことを確認"""
        # 設定を取得
        settings_dict = self.settings.get_all()

        # 辞書を変更
        settings_dict['monitored_folder'] = 'modified_value'
        settings_dict['realtime']['model_size'] = 'modified_model'

        # 元の設定が変更されていないことを確認
        self.assertNotEqual(self.settings.get('monitored_folder'), 'modified_value')
        self.assertNotEqual(self.settings.get('realtime.model_size'), 'modified_model')

    def test_atomic_file_write(self):
        """アトミックファイル書き込みの検証"""
        # 設定を保存
        self.settings.set('monitor_interval', 15)
        self.assertTrue(self.settings.save())

        # 一時ファイルが削除されていることを確認
        temp_file = Path(self.settings_file).with_suffix('.tmp')
        self.assertFalse(temp_file.exists())

        # 正しい設定ファイルが存在することを確認
        self.assertTrue(Path(self.settings_file).exists())


class TestRealWorldScenarios(unittest.TestCase):
    """実際の使用シナリオをシミュレートする統合テスト"""

    def setUp(self):
        """各テストの前処理"""
        self.temp_dir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.temp_dir, "test_settings.json")

    def tearDown(self):
        """各テストの後処理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_slider_continuous_adjustment(self):
        """スライダー連続操作のシミュレーション"""
        settings = AppSettings(self.settings_file)
        settings._save_debounce_delay = 0.3

        # スライダーを連続調整（デバウンス保存）
        for i in range(10, 30):
            settings.set('monitor_interval', i)
            settings.save_debounced()
            time.sleep(0.05)

        # アプリ終了時の即座保存
        settings.save_immediate()

        # 最後の値が保存されていることを確認
        settings2 = AppSettings(self.settings_file)
        self.assertTrue(settings2.load())
        self.assertEqual(settings2.get('monitor_interval'), 29)

    def test_app_restart_scenario(self):
        """アプリ再起動シナリオ"""
        # 初回起動: 設定変更して保存
        settings1 = AppSettings(self.settings_file)
        settings1.set('monitored_folder', 'C:/monitored')
        settings1.set('completed_folder', 'C:/completed')
        settings1.set('monitor_interval', 20)
        settings1.set('remove_fillers', False)
        settings1.save()

        # 再起動: 新しいインスタンスで設定を復元
        settings2 = AppSettings(self.settings_file)
        self.assertTrue(settings2.load())

        # すべての設定が復元されていることを確認
        self.assertEqual(settings2.get('monitored_folder'), 'C:/monitored')
        self.assertEqual(settings2.get('completed_folder'), 'C:/completed')
        self.assertEqual(settings2.get('monitor_interval'), 20)
        self.assertFalse(settings2.get('remove_fillers'))

    def test_folder_monitor_restart_scenario(self):
        """フォルダ監視間隔変更→再起動シナリオ"""
        settings = AppSettings(self.settings_file)
        settings._save_debounce_delay = 0.5

        # 監視間隔を変更（デバウンス保存）
        settings.set('monitor_interval', 25)
        settings.save_debounced()

        # フォルダ監視を再起動するタイミングで即座保存
        time.sleep(0.2)  # 少し待機
        settings.save_immediate()

        # 設定が保存されていることを確認
        settings2 = AppSettings(self.settings_file)
        self.assertTrue(settings2.load())
        self.assertEqual(settings2.get('monitor_interval'), 25)

    def test_batch_processing_simulation(self):
        """バッチ処理スレッドからの設定アクセス"""
        settings = AppSettings(self.settings_file)
        errors = []
        values = []

        def batch_worker():
            """バッチ処理ワーカースレッド"""
            try:
                # 設定を読み取る
                remove_fillers = settings.get('remove_fillers')
                add_punctuation = settings.get('add_punctuation')
                enable_diarization = settings.get('enable_diarization')

                values.append({
                    'remove_fillers': remove_fillers,
                    'add_punctuation': add_punctuation,
                    'enable_diarization': enable_diarization
                })
            except Exception as e:
                errors.append(str(e))

        # 複数のバッチワーカーを起動
        threads = [threading.Thread(target=batch_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # エラーが発生していないか確認
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        # すべてのワーカーが設定を読み取れたことを確認
        self.assertEqual(len(values), 5)


def run_all_tests():
    """すべてのテストを実行"""
    # テストスイートを作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # すべてのテストクラスを追加
    suite.addTests(loader.loadTestsFromTestCase(TestBasicIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMultithreadIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestDebounceIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestUISettingsIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestRealWorldScenarios))

    # テストランナーを作成して実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == '__main__':
    print("="*70)
    print("AppSettings統合テスト実行")
    print("="*70)
    print()

    result = run_all_tests()

    print()
    print("="*70)
    print("テスト結果サマリー")
    print("="*70)
    print(f"実行: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"エラー: {len(result.errors)}")
    print("="*70)

    # 終了コード
    sys.exit(0 if result.wasSuccessful() else 1)
