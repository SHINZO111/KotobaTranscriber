"""
pytest conftest.py - テスト設定

src/ ディレクトリをsys.pathに追加して、モジュールインポートとカバレッジ計測を両立させる。
"""

import sys
from pathlib import Path

# src/ を sys.path の先頭に追加（テストとカバレッジの両方で使用）
src_dir = str(Path(__file__).parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
