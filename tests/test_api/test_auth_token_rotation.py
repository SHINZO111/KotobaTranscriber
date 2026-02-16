"""
TokenManager トークンローテーション機構のテスト
"""

import os
import threading
import time
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from api.auth import TokenManager, get_token_manager


class TestTokenManager:
    """TokenManager クラスのテスト"""

    def test_初回トークン生成(self):
        """TokenManager初期化時にトークンが生成される"""
        manager = TokenManager()
        token = manager.get_current_token()
        assert token
        assert len(token) >= 32  # token_urlsafe(32) は通常43文字程度

    def test_トークン検証_有効なトークン(self):
        """現在のトークンは検証に成功する"""
        manager = TokenManager()
        token = manager.get_current_token()
        assert manager.verify_token(token) is True

    def test_トークン検証_無効なトークン(self):
        """無効なトークンは検証に失敗する"""
        manager = TokenManager()
        assert manager.verify_token("invalid_token") is False

    def test_トークンローテーション_TTL経過(self):
        """TTL経過後にトークンがローテーションされる"""
        # TTL=0.1秒で設定（テスト用）
        manager = TokenManager(ttl_minutes=0.1 / 60)
        first_token = manager.get_current_token()

        # TTL経過まで待機
        time.sleep(0.15)

        # 新しいトークン取得（内部でローテーション）
        second_token = manager.get_current_token()

        assert first_token != second_token

    def test_猶予期間内の旧トークン有効性(self):
        """猶予期間内は旧トークンも有効"""
        # TTL=0.1秒、猶予期間=0.2秒
        manager = TokenManager(ttl_minutes=0.1 / 60, grace_period_minutes=0.2 / 60)
        first_token = manager.get_current_token()

        # TTL経過まで待機
        time.sleep(0.15)

        # 新しいトークン取得（ローテーション発生）
        second_token = manager.get_current_token()
        assert first_token != second_token

        # 旧トークンはまだ猶予期間内なので有効
        assert manager.verify_token(first_token) is True
        assert manager.verify_token(second_token) is True

    def test_猶予期間外の旧トークン無効化(self):
        """猶予期間経過後は旧トークンが無効化される"""
        # TTL=0.1秒、猶予期間=0.1秒
        manager = TokenManager(ttl_minutes=0.1 / 60, grace_period_minutes=0.1 / 60)
        first_token = manager.get_current_token()

        # TTL経過まで待機
        time.sleep(0.15)

        # 新しいトークン取得（ローテーション発生）
        second_token = manager.get_current_token()

        # 猶予期間経過まで待機
        time.sleep(0.15)

        # 旧トークンは無効、新トークンは有効
        assert manager.verify_token(first_token) is False
        assert manager.verify_token(second_token) is True

    def test_並行アクセスでの競合なし(self):
        """複数スレッドからの同時アクセスで競合しない"""
        manager = TokenManager()
        tokens = []

        def worker():
            for _ in range(10):
                token = manager.get_current_token()
                tokens.append(token)
                time.sleep(0.01)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 全トークンが有効であることを確認
        for token in tokens:
            assert manager.verify_token(token) is True

    def test_環境変数_TTL設定(self):
        """環境変数 KOTOBA_TOKEN_TTL_MINUTES でTTLが設定される"""
        with patch.dict(os.environ, {"KOTOBA_TOKEN_TTL_MINUTES": "30"}):
            manager = TokenManager(ttl_minutes=int(os.environ.get("KOTOBA_TOKEN_TTL_MINUTES", "60")))
            # TTL=30分 → 1800秒
            assert manager._ttl_seconds == 30 * 60


class TestGetTokenManager:
    """get_token_manager() シングルトンテスト"""

    def test_シングルトンインスタンス(self):
        """get_token_manager() は同一インスタンスを返す"""
        # 既存のシングルトンをリセット（テスト分離のため）
        from api.auth import _reset_token_manager_for_test

        _reset_token_manager_for_test()

        manager1 = get_token_manager()
        manager2 = get_token_manager()
        assert manager1 is manager2

    def test_環境変数からTTL読み取り(self):
        """環境変数 KOTOBA_TOKEN_TTL_MINUTES を読み取る"""
        from api.auth import _reset_token_manager_for_test

        _reset_token_manager_for_test()

        with patch.dict(os.environ, {"KOTOBA_TOKEN_TTL_MINUTES": "45"}):
            manager = get_token_manager()
            assert manager._ttl_seconds == 45 * 60


class TestBackwardCompatibility:
    """後方互換性テスト"""

    def test_API_TOKEN_グローバル変数が存在する(self):
        """API_TOKEN グローバル変数が後方互換性のため残っている"""
        from api.auth import API_TOKEN

        assert API_TOKEN
        assert isinstance(API_TOKEN, str)
