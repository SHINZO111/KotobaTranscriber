# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for KotobaTranscriber
Builds a standalone Windows executable
"""

block_cipher = None

# データファイルの収集
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

# PySide6のデータファイル
pyside6_datas = collect_data_files('PySide6')

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
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('icon.ico', '.'),
        ('custom_vocabulary.json', '.'),
        ('data/construction_dictionary.json', 'data'),
    ] + pyside6_datas,
    hiddenimports=[
        'torch',
        'torchaudio',
        'torchaudio._extension',
        'torchaudio.transforms',
        'transformers',
        'transformers.models.whisper',
        'faster_whisper',
        'faster_whisper.tokenizer',
        'faster_whisper.transcribe',
        'faster_whisper.utils',
        'faster_whisper.feature_extractor',
        'speechbrain',
        'speechbrain.pretrained',
        'speechbrain.pretrained.interfaces',
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'shiboken6',
        'librosa',
        'librosa.core',
        'librosa.feature',
        'soundfile',
        'soundfile._soundfile_data',
        'pydub',
        'pyaudio',
        'numpy',
        'numpy.core._dtype_ctypes',
        'pandas',
        'pandas._libs.tslibs',
        'pandas._libs.tslibs.np_datetime',
        'sklearn',
        'sklearn.cluster',
        'sklearn.metrics',
        'sklearn.utils',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors',
        'sklearn.neighbors._partition_nodes',
        'sklearn.tree',
        'sklearn.tree._utils',
        'docx',
        'docx.shared',
        'docx.enum',
        'docx.oxml',
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.styles',
        'openpyxl.utils',
        'tqdm',
        'tqdm.auto',
        'tqdm.std',
        'av',
        'tokenizers',
        'tokenizers.models',
        'tokenizers.trainers',
        'tokenizers.pre_tokenizers',
        'tokenizers.decoders',
        'ctranslate2',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        'scipy.linalg',
        'scipy.sparse',
        'scipy.special',
        'filelock',
        'huggingface_hub',
        'huggingface_hub.constants',
        'regex',
        'requests',
        'urllib3',
        'charset_normalizer',
        'certifi',
        'idna',
        'yaml',
        'packaging',
        'packaging.version',
        'packaging.specifiers',
        'packaging.requirements',
        'packaging.markers',
        'win32event',
        'win32api',
        'winerror',
        'pywintypes',
        '_socket',
        'socket',
        '_socket',
        'multiprocessing',
        'multiprocessing.context',
        'multiprocessing.reduction',
        'multiprocessing.pool',
        'multiprocessing.process',
        'multiprocessing.queues',
        'multiprocessing.synchronize',
        'multiprocessing.spawn',
        'multiprocessing.util',
    ] + torch_hiddenimports + whisper_hiddenimports + transformers_hiddenimports + speechbrain_hiddenimports + sklearn_hiddenimports,
    hookspath=[],
    hooksconfig={
        'pyinstaller-hooks-contrib': {
            'collect_all': ['PySide6', 'torch', 'torchaudio', 'transformers', 'multiprocessing', 'socket']
        }
    },
    runtime_hooks=[],
    excludedimports=[],
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
    'torch/cuda',
    'torch/backends/cuda',
    'torch/include',
    'torch/lib/test',
    'torch/lib/include',
]

# 大きなテストファイルを除外
a.datas = [x for x in a.datas if not any(pattern in x[0] for pattern in excluded_patterns)]
a.binaries = [x for x in a.binaries if not any(pattern in x[0] for pattern in excluded_patterns)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedirモードでビルド（起動速度と安定性のため）
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KotobaTranscriber'
)
