# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for KotobaTranscriber API Backend (kotoba_backend)
Builds a standalone Windows executable for the FastAPI sidecar.
PySide6 は除外（Tauri シェルが UI を担当）。
"""

block_cipher = None

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

# torch関連の隠しインポート
torch_hiddenimports = collect_submodules('torch') + collect_submodules('torchaudio')

# faster_whisper関連
whisper_hiddenimports = collect_submodules('faster_whisper') + collect_submodules('whisper')

# transformers関連
transformers_hiddenimports = collect_submodules('transformers')

# speechbrain関連
speechbrain_hiddenimports = collect_submodules('speechbrain')

# sklearn関連
sklearn_hiddenimports = collect_submodules('sklearn')

a = Analysis(
    ['src/api/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('custom_vocabulary.json', '.'),
        ('data/construction_dictionary.json', 'data'),
    ],
    hiddenimports=[
        'torch',
        'torchaudio',
        'transformers',
        'faster_whisper',
        'speechbrain',
        'librosa',
        'soundfile',
        'pydub',
        'pyaudio',
        'webrtcvad',
        'numpy',
        'pandas',
        'sklearn',
        'docx',
        'openpyxl',
        'tqdm',
        'ctranslate2',
        'scipy',
        'yaml',
        'uvicorn',
        'fastapi',
        'pydantic',
        'websockets',
        'starlette',
        'anyio',
        'httptools',
    ] + torch_hiddenimports + whisper_hiddenimports + transformers_hiddenimports + speechbrain_hiddenimports + sklearn_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludedimports=[
        'PySide6',
        'shiboken6',
        'PyQt5',
        'PyQt6',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# フィルタリング: 不要な大きなファイルを除外
excluded_patterns = [
    'torch/test',
    'torch/testing',
    'torch/distributed',
    'torch/include',
    'torch/lib/test',
    'torch/lib/include',
]

a.datas = [x for x in a.datas if not any(pattern in x[0] for pattern in excluded_patterns)]
a.binaries = [x for x in a.binaries if not any(pattern in x[0] for pattern in excluded_patterns)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='kotoba_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # ML バイナリに UPX を使うと起動が遅くなる
    console=True,  # stdout を Tauri が読み取るため console=True
    icon='icon.ico',
)

# 注: COLLECT 不要 — onefile モード（Tauri sidecar は単一 exe を要求する）
