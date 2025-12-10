"""
Safe file I/O utilities.

- atomic_write_text / atomic_write_bytes: write to a temp file and
  atomically replace target.
- is_within_directory: prevent path traversal by ensuring target is
  inside base.
- safe_makedirs: create directories with exist_ok semantics and basic
  race handling.
- validate_executable: check that a given path is an executable file.
"""

import os
import tempfile


def is_within_directory(base_dir: str, target_path: str) -> bool:
    base = os.path.abspath(base_dir)
    target = os.path.abspath(target_path)
    try:
        return os.path.commonpath([base, target]) == base
    except ValueError:
        return False


def safe_makedirs(path: str, mode: int = 0o755) -> None:
    os.makedirs(path, mode=mode, exist_ok=True)


def atomic_write_text(
    path: str, text: str, encoding: str = 'utf-8'
) -> None:
    dirpath = os.path.dirname(path) or '.'
    safe_makedirs(dirpath)
    with tempfile.NamedTemporaryFile(
        mode='w', encoding=encoding, dir=dirpath, delete=False
    ) as tmp:
        tmp.write(text)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def atomic_write_bytes(path: str, data: bytes) -> None:
    dirpath = os.path.dirname(path) or '.'
    safe_makedirs(dirpath)
    with tempfile.NamedTemporaryFile(
        mode='wb', dir=dirpath, delete=False
    ) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def validate_executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)
