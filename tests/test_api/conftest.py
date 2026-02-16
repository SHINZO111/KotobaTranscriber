"""API テスト共通フィクスチャ"""

import os
import sys

import pytest

# src/ を sys.path に追加
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# API認証トークン（テスト用）
try:
    from api.auth import _reset_token_manager_for_test, get_token_manager

    TOKEN_MANAGER_AVAILABLE = True
except ImportError:
    TOKEN_MANAGER_AVAILABLE = False


def auth_headers():
    """テスト用認証ヘッダーを返すヘルパー"""
    if TOKEN_MANAGER_AVAILABLE:
        token_manager = get_token_manager()
        token = token_manager.get_current_token()
        return {"Authorization": f"Bearer {token}"}
    return {"Authorization": "Bearer invalid_token"}


@pytest.fixture(autouse=True)
def reset_token_manager():
    """各テスト前にTokenManagerをリセット（autouse=Trueで全テストに適用）"""
    if TOKEN_MANAGER_AVAILABLE:
        _reset_token_manager_for_test()
    yield


@pytest.fixture
def api_auth_headers():
    """テスト用認証ヘッダーフィクスチャ"""
    return auth_headers()


@pytest.fixture
def anyio_backend():
    return "asyncio"
