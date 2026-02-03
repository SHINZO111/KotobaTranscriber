# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for KotobaTranscriber v2.2 (PyQt5版)
ビルド設定の最適化とエクスポート機能の完全対応
"""

import sys
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE

# ブロック暗号化（オプション）
block_cipher = None

# アプリケーション情報
APP_NAME = "KotobaTranscriber"
APP_VERSION = "2.2.0"
APP_ICON = "icon.ico"

# パス設定
base_path = os.path.abspath(os.path.dirname(SPECFILE) if 'SPECFILE' in dir() else '.')
src_path = os.path.join(base_path, 'src')

# 隠しインポート - PyQt5版
hiddenimports = [
    # Core
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    
    # AI/ML
    'torch',
    'torchaudio',
    'torchvision',
    'transformers',
    'transformers.pipelines',
    
    # Whisper variants
    'faster_whisper',
    'faster_whisper.transcribe',
    
    # Speaker diarization
    'speechbrain',
    'speechbrain.pretrained',
    'sklearn',
    'sklearn.cluster',
    'sklearn.metrics',
    'resemblyzer',
    
    # Audio processing
    'librosa',
    'librosa.core',
    'soundfile',
    'soundfile_compat',
    'pydub',
    'pyaudio',
    'webrtcvad',
    
    # Export formats
    'docx',
    'docx.shared',
    'docx.enum',
    'openpyxl',
    'openpyxl.styles',
    'pandas',
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.timedeltas',
    'csv',
    
    # Utils
    'numpy',
    'numpy.core._dtype_ctypes',
    'yaml',
    'tqdm',
    'psutil',
    'validators',
    
    # API correctors (optional)
    'anthropic',
    'openai',
    
    # SSL/Certificates
    'certifi',
    'ssl',
    
    # Windows specific
    'win32event',
    'win32api',
    'winerror',
]

# バイナリ設定
binaries = [
    # FFmpeg (バンドルする場合)
    # ('C:/ffmpeg/ffmpeg-8.0-essentials_build/bin/ffmpeg.exe', 'ffmpeg'),
    # ('C:/ffmpeg/ffmpeg-8.0-essentials_build/bin/ffprobe.exe', 'ffmpeg'),
]

# データファイル
datas = [
    # 設定ファイル
    ('config/config.yaml', 'config'),
    ('config/logging.yaml', 'config'),
    
    # アイコン
    ('icon.ico', '.'),
    
    # カスタム語彙
    ('custom_vocabulary.json', '.'),
    
    # LICENSEファイル
    ('LICENSE', '.'),
    ('THIRD_PARTY_LICENSES.md', '.'),
    
    # PyQt5用スタイル
    ('src/qt_compat.py', 'src'),
    ('src/ui_enhancements.py', 'src'),
    ('src/enhanced_error_handling.py', 'src'),
    ('src/optimized_pipeline.py', 'src'),
]

# 除外モジュール（サイズ削減）
excludedimports = [
    'matplotlib',
    'matplotlib.pyplot',
    'PIL',
    'PIL.Image',
    'tkinter',
    'tkinter.filedialog',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'sphinx',
    'alabaster',
    'babel',
    'django',
    'flask',
    'bottle',
    'tornado',
    'zmq',
    'scipy',
    'sklearn.datasets',
    'sklearn.ensemble',
    'sklearn.linear_model',
    'sklearn.neural_network',
    'sklearn.svm',
    'sklearn.tree',
    'pandas.plotting',
    'pandas.io.clipboard',
    'pandas.io.sql',
    'sqlalchemy',
    'pymysql',
    'psycopg2',
    'lxml',
    'html5lib',
    'BeautifulSoup4',
    'PIL',
    'Cython',
    'cython',
    'tensorflow',
    'tensorboard',
]

# アナリシス
a = Analysis(
    ['src/main.py'],
    pathex=[src_path, base_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludedimports,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Pythonファイルを圧縮
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 単一EXEまたはフォルダ形式
# 単一EXE（配布簡単、起動遅め）
exe_single = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'python*.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
    version=os.path.join(base_path, 'version_info.txt') if os.path.exists(os.path.join(base_path, 'version_info.txt')) else None,
)

# フォルダ形式（起動高速、ファイル数多め） - オプション
# coll = COLLECT(
#     exe_single,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name=APP_NAME
# )
