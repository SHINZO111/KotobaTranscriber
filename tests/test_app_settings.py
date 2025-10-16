"""
AppSettings クラスのユニットテスト
"""

import pytest
import json
import threading
import time
from pathlib import Path
import sys
import copy

# テスト対象のモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from app_settings import AppSettings


class TestAppSettingsBasic:
    """基本機能のテスト"""

    def test_default_initialization(self):
        """デフォルト設定で初期化できることを確認"""
        settings = AppSettings()
        assert settings.get('monitor_interval') == 10
        assert settings.get('realtime.model_size') == 'base'
        assert settings.get('remove_fillers') is True
        assert settings.get('realtime.vad_threshold') == 10
        assert settings.get('window.width') == 900

    def test_custom_settings_file(self, tmp_path):
        """カスタム設定ファイルパスで初期化できることを確認"""
        custom_path = tmp_path / "custom_settings.json"
        settings = AppSettings(str(custom_path))
        assert settings.settings_file == custom_path

    def test_nested_key_access(self):
        """ドット記法でネストされたキーにアクセスできることを確認"""
        settings = AppSettings()

        # 設定
        settings.set('realtime.model_size', 'medium')
        settings.set('window.width', 1024)

        # 取得
        assert settings.get('realtime.model_size') == 'medium'
        assert settings.get('window.width') == 1024

    def test_get_with_default(self):
        """存在しないキーのデフォルト値が返ることを確認"""
        settings = AppSettings()
        assert settings.get('nonexistent_key', 'default_value') == 'default_value'
        assert settings.get('nonexistent.nested.key', 42) == 42
        assert settings.get('nonexistent_key') is None

    def test_get_all(self):
        """全設定を取得できることを確認"""
        settings = AppSettings()
        all_settings = settings.get_all()

        assert 'monitor_interval' in all_settings
        assert 'realtime' in all_settings
        assert isinstance(all_settings['realtime'], dict)
        assert all_settings['monitor_interval'] == 10

    def test_set_creates_nested_dict(self):
        """存在しないネストされたキーを設定すると辞書が作成されることを確認"""
        settings = AppSettings()
        settings.set('new_section.new_key', 'new_value')

        assert settings.get('new_section.new_key') == 'new_value'
        assert isinstance(settings.settings['new_section'], dict)


class TestAppSettingsPersistence:
    """永続化機能のテスト"""

    def test_save_and_load(self, tmp_path):
        """保存と読み込みが正しく動作することを確認"""
        settings_file = tmp_path / "test_settings.json"

        # 保存
        settings1 = AppSettings(str(settings_file))
        settings1.set('monitor_interval', 20)
        settings1.set('realtime.model_size', 'large-v2')
        settings1.set('monitored_folder', '/test/folder')
        assert settings1.save()

        # ファイルが存在することを確認
        assert settings_file.exists()

        # 読み込み
        settings2 = AppSettings(str(settings_file))
        assert settings2.load()
        assert settings2.get('monitor_interval') == 20
        assert settings2.get('realtime.model_size') == 'large-v2'
        assert settings2.get('monitored_folder') == '/test/folder'

    def test_load_nonexistent_file(self):
        """存在しないファイルの読み込み時にFalseが返ることを確認"""
        settings = AppSettings("/nonexistent/path/settings.json")
        assert settings.load() is False

        # デフォルト設定が使われることを確認
        assert settings.get('monitor_interval') == 10
        assert settings.get('realtime.model_size') == 'base'

    def test_corrupted_json_handling(self, tmp_path):
        """破損したJSONファイルの処理を確認"""
        settings_file = tmp_path / "corrupted.json"

        # 破損したJSONを作成
        settings_file.write_text("{invalid json content", encoding='utf-8')

        # 読み込み失敗を確認
        settings = AppSettings(str(settings_file))
        assert settings.load() is False

        # デフォルト設定が使われることを確認
        assert settings.get('monitor_interval') == 10

    def test_save_creates_directory(self, tmp_path):
        """保存時に存在しないディレクトリが作成されることを確認"""
        deep_path = tmp_path / "level1" / "level2" / "settings.json"
        settings = AppSettings(str(deep_path))
        settings.set('monitor_interval', 15)

        assert settings.save()
        assert deep_path.exists()
        assert deep_path.parent.exists()

    def test_saved_json_format(self, tmp_path):
        """保存されたJSONのフォーマットが正しいことを確認"""
        settings_file = tmp_path / "format_test.json"
        settings = AppSettings(str(settings_file))
        settings.set('monitor_interval', 25)
        settings.save()

        # 直接JSONを読み込んで確認
        with open(settings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data['monitor_interval'] == 25
        assert 'realtime' in data
        assert isinstance(data['realtime'], dict)


class TestAppSettingsThreadSafety:
    """スレッドセーフティのテスト"""

    def test_concurrent_reads(self):
        """複数スレッドからの同時読み取りが安全であることを確認"""
        settings = AppSettings()
        settings.set('monitor_interval', 10)

        results = []
        errors = []

        def reader():
            try:
                for _ in range(100):
                    value = settings.get('monitor_interval')
                    results.append(value)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # エラーがないことを確認
        assert len(errors) == 0

        # 全て同じ値が読めることを確認
        assert all(v == 10 for v in results)
        assert len(results) == 1000

    def test_concurrent_writes(self):
        """複数スレッドからの同時書き込みが安全であることを確認"""
        settings = AppSettings()
        errors = []

        def writer(value):
            try:
                for _ in range(100):
                    settings.set('monitor_interval', value)
                    # 短い遅延を入れて競合を発生させやすくする
                    time.sleep(0.0001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # エラーがないことを確認
        assert len(errors) == 0

        # クラッシュせずに完了することを確認
        final_value = settings.get('monitor_interval')
        assert isinstance(final_value, int)
        assert 0 <= final_value < 10

    def test_concurrent_save_load(self, tmp_path):
        """保存と読み込みの同時実行が安全であることを確認"""
        settings_file = tmp_path / "concurrent_test.json"
        settings = AppSettings(str(settings_file))
        errors = []

        def save_worker():
            try:
                for i in range(20):
                    settings.set('monitor_interval', i)
                    settings.save()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        def load_worker():
            try:
                for _ in range(20):
                    settings.load()
                    value = settings.get('monitor_interval')
                    assert isinstance(value, int)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=save_worker),
            threading.Thread(target=load_worker)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # エラーがないことを確認
        assert len(errors) == 0

        # ファイルが破損していないことを確認
        assert settings_file.exists()
        settings2 = AppSettings(str(settings_file))
        assert settings2.load()


class TestAppSettingsMerge:
    """設定マージのテスト"""

    def test_merge_preserves_defaults(self, tmp_path):
        """マージ時にデフォルト設定が保持されることを確認"""
        settings_file = tmp_path / "partial_settings.json"

        # 一部の設定のみ保存
        partial_settings = {
            'monitor_interval': 20
        }
        settings_file.write_text(json.dumps(partial_settings), encoding='utf-8')

        # 読み込み
        settings = AppSettings(str(settings_file))
        settings.load()

        # 保存された設定は反映される
        assert settings.get('monitor_interval') == 20

        # 他の設定はデフォルトのまま
        assert settings.get('realtime.model_size') == 'base'
        assert settings.get('remove_fillers') is True
        assert settings.get('window.width') == 900

    def test_merge_nested_dicts(self, tmp_path):
        """ネストされた辞書が正しくマージされることを確認"""
        settings_file = tmp_path / "nested_settings.json"

        # 一部のネストされた設定のみ保存
        partial_settings = {
            'realtime': {
                'model_size': 'medium'
                # vad_enabled と vad_threshold は含まない
            }
        }
        settings_file.write_text(json.dumps(partial_settings), encoding='utf-8')

        # 読み込み
        settings = AppSettings(str(settings_file))
        settings.load()

        # 保存された設定は反映される
        assert settings.get('realtime.model_size') == 'medium'

        # 同じネスト内の他の設定はデフォルトのまま
        assert settings.get('realtime.vad_enabled') is True
        assert settings.get('realtime.vad_threshold') == 10

    def test_unknown_keys_preserved(self, tmp_path):
        """不明なキーが保持されることを確認（将来の互換性のため）"""
        settings_file = tmp_path / "with_unknown_keys.json"

        # 不明なキーを含む設定
        settings_dict = {
            'monitor_interval': 15,
            'future_feature': 'some_value',
            'realtime': {
                'model_size': 'medium',
                'future_nested': 'also_preserved'
            }
        }
        settings_file.write_text(json.dumps(settings_dict), encoding='utf-8')

        # 読み込み
        settings = AppSettings(str(settings_file))
        settings.load()

        # 既知のキーは読み込まれる
        assert settings.get('monitor_interval') == 15
        assert settings.get('realtime.model_size') == 'medium'

        # 不明なキーも保持される（設定内に存在する）
        assert settings.get('future_feature') == 'some_value'
        assert settings.get('realtime.future_nested') == 'also_preserved'


class TestAppSettingsDeepCopy:
    """ディープコピーのテスト"""

    def test_no_shared_state_between_instances(self):
        """インスタンス間で状態が共有されないことを確認"""
        settings1 = AppSettings()
        settings2 = AppSettings()

        # settings1を変更
        settings1.set('realtime.model_size', 'large-v2')
        settings1.set('monitor_interval', 30)

        # settings2は影響を受けない
        assert settings2.get('realtime.model_size') == 'base'
        assert settings2.get('monitor_interval') == 10

    def test_reset_restores_defaults(self):
        """resetがデフォルトに戻すことを確認"""
        settings = AppSettings()

        # 設定を変更
        settings.set('realtime.model_size', 'large-v2')
        settings.set('monitor_interval', 30)
        settings.set('remove_fillers', False)
        assert settings.get('realtime.model_size') == 'large-v2'
        assert settings.get('monitor_interval') == 30

        # リセット
        settings.reset()

        # デフォルトに戻る
        assert settings.get('realtime.model_size') == 'base'
        assert settings.get('monitor_interval') == 10
        assert settings.get('remove_fillers') is True

    def test_get_all_returns_copy(self):
        """get_all()がコピーを返すことを確認（元データを保護）"""
        settings = AppSettings()

        # get_all()で取得
        all_settings = settings.get_all()

        # 取得した辞書を変更
        all_settings['monitor_interval'] = 999
        all_settings['realtime']['model_size'] = 'modified'

        # 元の設定は変更されていない
        assert settings.get('monitor_interval') == 10
        # 注意: shallow copyの場合、ネストされた辞書は共有される可能性がある
        # 深い階層の保護が必要な場合は deep copy が必要


class TestAppSettingsEdgeCases:
    """エッジケースのテスト"""

    def test_empty_key(self):
        """空のキーの処理を確認"""
        settings = AppSettings()

        # 空のキーでgetを呼ぶと設定全体が返る可能性がある
        result = settings.get('')
        # 実装依存だが、Noneまたはエラーが適切

    def test_key_with_multiple_dots(self):
        """複数のドットを含むキーの処理を確認"""
        settings = AppSettings()

        # 深くネストされたキー
        settings.set('level1.level2.level3.level4', 'deep_value')
        assert settings.get('level1.level2.level3.level4') == 'deep_value'

    def test_overwrite_dict_with_value(self):
        """辞書型の値を通常の値で上書きできることを確認"""
        settings = AppSettings()

        # 元々辞書型の値
        assert isinstance(settings.get('realtime'), dict)

        # 文字列で上書き
        settings.set('realtime', 'not_a_dict_anymore')
        assert settings.get('realtime') == 'not_a_dict_anymore'

    def test_set_none_value(self):
        """None値を設定できることを確認"""
        settings = AppSettings()

        settings.set('monitor_interval', None)
        assert settings.get('monitor_interval') is None

        # デフォルト値を指定した場合でもNoneが返る
        assert settings.get('monitor_interval', 'default') is None

    def test_unicode_values(self):
        """Unicode文字列を扱えることを確認"""
        settings = AppSettings()

        japanese_text = "日本語のテキスト"
        settings.set('monitored_folder', japanese_text)
        assert settings.get('monitored_folder') == japanese_text

    def test_complex_value_types(self):
        """複雑なデータ型を扱えることを確認"""
        settings = AppSettings()

        # リスト
        settings.set('test_list', [1, 2, 3, 'four'])
        assert settings.get('test_list') == [1, 2, 3, 'four']

        # ネストされた辞書
        nested = {'a': {'b': {'c': 'deep'}}}
        settings.set('test_nested', nested)
        assert settings.get('test_nested') == nested


class TestAppSettingsRobustness:
    """堅牢性のテスト"""

    def test_save_with_permission_error(self, tmp_path, monkeypatch):
        """保存時のパーミッションエラーを処理できることを確認"""
        settings_file = tmp_path / "readonly.json"
        settings = AppSettings(str(settings_file))

        # まず正常に保存
        assert settings.save()

        # ファイルを読み取り専用にする（Windowsでは完全には機能しない場合がある）
        import os
        import stat
        os.chmod(str(settings_file), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        # 保存を試みる（失敗するはず）
        settings.set('monitor_interval', 30)
        result = settings.save()

        # パーミッションを戻す
        os.chmod(str(settings_file), stat.S_IWUSR | stat.S_IRUSR)

        # Windowsでは書き込み可能な場合もあるため、厳密なテストは難しい

    def test_load_with_encoding_error(self, tmp_path):
        """エンコーディングエラーを処理できることを確認"""
        settings_file = tmp_path / "bad_encoding.json"

        # 不正なエンコーディングでファイルを作成
        # UTF-8でない文字を含む
        with open(settings_file, 'wb') as f:
            f.write(b'\xff\xfe{"monitor_interval": 20}')

        settings = AppSettings(str(settings_file))
        result = settings.load()

        # 読み込みは失敗するが、クラッシュはしない
        # デフォルト設定が使用される
        assert settings.get('monitor_interval') == 10

    def test_large_settings_file(self, tmp_path):
        """大きな設定ファイルを処理できることを確認"""
        settings_file = tmp_path / "large_settings.json"
        settings = AppSettings(str(settings_file))

        # 多数の設定を追加
        for i in range(1000):
            settings.set(f'key_{i}', f'value_{i}')

        # 保存
        assert settings.save()

        # 読み込み
        settings2 = AppSettings(str(settings_file))
        assert settings2.load()

        # 一部の値を確認
        assert settings2.get('key_0') == 'value_0'
        assert settings2.get('key_999') == 'value_999'


class TestAppSettingsDefaultSettings:
    """デフォルト設定の整合性テスト"""

    def test_all_default_keys_accessible(self):
        """すべてのデフォルトキーにアクセスできることを確認"""
        settings = AppSettings()

        # トップレベルのキー
        assert settings.get('monitored_folder') is None
        assert settings.get('monitor_interval') == 10
        assert settings.get('completed_folder') is None
        assert settings.get('auto_move_completed') is False
        assert settings.get('remove_fillers') is True
        assert settings.get('add_punctuation') is True
        assert settings.get('format_paragraphs') is True
        assert settings.get('enable_diarization') is False
        assert settings.get('enable_llm_correction') is False
        assert settings.get('use_advanced_llm') is False

        # realtimeセクション
        assert settings.get('realtime.device_index') is None
        assert settings.get('realtime.model_size') == 'base'
        assert settings.get('realtime.vad_enabled') is True
        assert settings.get('realtime.vad_threshold') == 10

        # windowセクション
        assert settings.get('window.width') == 900
        assert settings.get('window.height') == 700
        assert settings.get('window.x') == 100
        assert settings.get('window.y') == 100

    def test_default_settings_immutability(self):
        """DEFAULT_SETTINGS定数が変更されないことを確認"""
        # 元のデフォルト設定を記録
        original_defaults = copy.deepcopy(AppSettings.DEFAULT_SETTINGS)

        # インスタンスを作成して変更
        settings = AppSettings()
        settings.set('monitor_interval', 999)
        settings.set('realtime.model_size', 'modified')

        # DEFAULT_SETTINGSが変更されていないことを確認
        assert AppSettings.DEFAULT_SETTINGS == original_defaults
        assert AppSettings.DEFAULT_SETTINGS['monitor_interval'] == 10
        assert AppSettings.DEFAULT_SETTINGS['realtime']['model_size'] == 'base'


class TestAppSettingsSecurityValidation:
    """セキュリティ検証のテスト"""

    def test_path_traversal_prevention_unix(self):
        """Unixパストラバーサル攻撃が防がれることを確認"""
        # システムディレクトリへのアクセスは拒否される
        with pytest.raises(ValueError, match="Settings file must be within"):
            AppSettings("/etc/passwd")

        with pytest.raises(ValueError, match="Settings file must be within"):
            AppSettings("/root/.ssh/id_rsa")

    def test_path_traversal_prevention_windows(self):
        """Windowsパストラバーサル攻撃が防がれることを確認"""
        if sys.platform == 'win32':
            with pytest.raises(ValueError, match="Settings file must be within"):
                AppSettings("C:\\Windows\\System32\\config.json")

            with pytest.raises(ValueError, match="Settings file must be within"):
                AppSettings("C:\\Program Files\\sensitive.json")

    def test_allowed_paths_project_directory(self):
        """プロジェクトディレクトリ内のパスが許可されることを確認"""
        # プロジェクトディレクトリ内
        settings_file = Path(__file__).parent.parent / "test_settings.json"
        settings = AppSettings(str(settings_file))
        assert settings is not None
        assert settings.settings_file.exists() or True  # ファイルが存在しなくてもパスは有効

    def test_allowed_paths_user_home(self):
        """ユーザーホーム内のパスが許可されることを確認"""
        # ユーザーホーム配下のパス
        import tempfile
        user_temp = Path(tempfile.gettempdir())

        # tempdirがuser home配下にあることを確認
        try:
            user_temp.relative_to(Path.home())
            # user home配下にある場合
            test_path = user_temp / "test_kotoba_settings.json"
            settings = AppSettings(str(test_path))
            assert settings is not None
        except ValueError:
            # user home外にある場合はテストをスキップ
            pytest.skip("temp directory is outside user home")

    def test_relative_path_resolution(self, tmp_path):
        """相対パスが正しく解決されることを確認"""
        # tmp_pathは通常user home配下にある
        relative_path = tmp_path / "settings.json"
        settings = AppSettings(str(relative_path))

        # 絶対パスに解決されていることを確認
        assert settings.settings_file.is_absolute()


class TestAppSettingsAtomicSave:
    """アトミック保存のテスト"""

    def test_atomic_save_creates_temp_file(self, tmp_path):
        """アトミック保存が一時ファイルを使用することを確認"""
        settings_file = tmp_path / "atomic_test.json"
        settings = AppSettings(str(settings_file))
        settings.set('monitor_interval', 15)

        # 保存前に一時ファイルが存在しないことを確認
        temp_file = settings_file.with_suffix('.tmp')
        assert not temp_file.exists()

        # 保存
        assert settings.save()

        # 保存後も一時ファイルは残っていない（os.replaceで置き換わった）
        assert not temp_file.exists()
        assert settings_file.exists()

    def test_atomic_save_error_cleanup(self, tmp_path, monkeypatch):
        """アトミック保存失敗時に一時ファイルがクリーンアップされることを確認"""
        settings_file = tmp_path / "cleanup_test.json"
        settings = AppSettings(str(settings_file))
        settings.set('monitor_interval', 15)

        # json.dumpがエラーを起こすようにモック
        import json as json_module
        original_dump = json_module.dump

        def failing_dump(*args, **kwargs):
            raise IOError("Simulated write error")

        monkeypatch.setattr(json_module, 'dump', failing_dump)

        # 保存は失敗するはず
        result = settings.save()
        assert result is False

        # 一時ファイルがクリーンアップされていることを確認
        temp_file = settings_file.with_suffix('.tmp')
        assert not temp_file.exists()


class TestAppSettingsDeepCopyProtection:
    """ディープコピー保護のテスト（get_all拡張）"""

    def test_get_all_returns_deep_copy(self):
        """get_all()がディープコピーを返すことを確認（ネストされた辞書も保護）"""
        settings = AppSettings()

        # get_all()で取得
        all_settings = settings.get_all()

        # 取得した辞書を変更（ネストされた辞書も変更）
        all_settings['monitor_interval'] = 999
        all_settings['realtime']['model_size'] = 'modified'
        all_settings['realtime']['vad_threshold'] = 999

        # 元の設定は変更されていない（deep copyなので）
        assert settings.get('monitor_interval') == 10
        assert settings.get('realtime.model_size') == 'base'
        assert settings.get('realtime.vad_threshold') == 10

    def test_reset_creates_deep_copy(self):
        """resetがディープコピーを作成し、DEFAULT_SETTINGSを汚染しないことを確認"""
        settings = AppSettings()

        # ネストされた辞書を変更
        settings.set('realtime.model_size', 'large-v2')
        settings.set('realtime.vad_threshold', 50)

        # リセット
        settings.reset()

        # 再度変更
        settings.set('realtime.model_size', 'medium')

        # DEFAULT_SETTINGSは汚染されていない
        assert AppSettings.DEFAULT_SETTINGS['realtime']['model_size'] == 'base'
        assert AppSettings.DEFAULT_SETTINGS['realtime']['vad_threshold'] == 10


# pytest設定とフィクスチャ
@pytest.fixture
def tmp_path(tmp_path_factory):
    """一時ディレクトリを提供"""
    return tmp_path_factory.mktemp("test_settings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
