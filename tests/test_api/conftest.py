"""API テスト共通フィクスチャ"""

import sys
import os
import pytest

# src/ を sys.path に追加
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# API認証トークン（テスト用）
try:
    from api.auth import API_TOKEN
except ImportError:
    API_TOKEN = ""


def auth_headers():
    """テスト用認証ヘッダーを返すヘルパー"""
    return {"Authorization": f"Bearer {API_TOKEN}"}


@pytest.fixture
def api_auth_headers():
    """テスト用認証ヘッダーフィクスチャ"""
    return auth_headers()


@pytest.fixture
def anyio_backend():
    return "asyncio"
