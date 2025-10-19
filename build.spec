# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for KotobaTranscriber
Builds a standalone Windows executable
"""

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('icon.ico', '.'),
        ('custom_vocabulary.json', '.'),
    ],
    hiddenimports=[
        'torch',
        'torchaudio',
        'transformers',
        'faster_whisper',
        'speechbrain',
        'PyQt5',
        'librosa',
        'soundfile',
        'pydub',
        'pyaudio',
        'numpy',
        'pandas',
        'sklearn',
        'docx',
        'openpyxl',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KotobaTranscriber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
