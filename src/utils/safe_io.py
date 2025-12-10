"""
Safe file I/O utilities.

- atomic_write_text / atomic_write_bytes: write to a temp file and atomically replace target.
- is_within_directory: prevent path traversal by ensuring target is inside base.
- safe_makedirs: create directories with exist_ok semantics and basic race handling.
- validate_executable: check that a given path is an executable file.
"""

import os
import tempfile


def is_within_directory(base_dir: str, target_path: str) -> bool:
    """
    Return True if target_path is inside base_dir (no path traversal).
    Both paths are resolved to absolute normalized paths.
    """
    base = os.path.abspath(base_dir)
    target = os.path.abspath(target_path)
    try:
        return os.path.commonpath([base, target]) == base
    except ValueError:
        # On different drives (Windows) commonpath can raise
        return False


def safe_makedirs(path: str, mode: int = 0o755) -> None:
    """
    Create directories, handling races where another process may create it concurrently.
    """
    os.makedirs(path, mode=mode, exist_ok=True)


def atomic_write_text(path: str, text: str, encoding: str = 'utf-8') -> None:
    """
    Atomically write text to path. Ensures data is flushed and file replaced atomically.
    """
    dirpath = os.path.dirname(path) or '.'
    safe_makedirs(dirpath)
    # Use NamedTemporaryFile in same directory to ensure os.replace stays atomic
    with tempfile.NamedTemporaryFile(mode='w', encoding=encoding, dir=dirpath, delete=False) as tmp:
        tmp.write(text)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    # atomic replace
    os.replace(tmp_name, path)


def atomic_write_bytes(path: str, data: bytes) -> None:
    """
    Atomically write bytes to path.
    """
    dirpath = os.path.dirname(path) or '.'
    safe_makedirs(dirpath)
    with tempfile.NamedTemporaryFile(mode='wb', dir=dirpath, delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def validate_executable(path: str) -> bool:
    """
    Return True if path exists, is a regular file, and is executable.
    This is a lightweight check (does not verify content/hash).
    """
    return os.path.isfile(path) and os.access(path, os.X_OK)
