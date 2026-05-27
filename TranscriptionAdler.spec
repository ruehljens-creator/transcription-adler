# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für Transcription Adler (Windows-Build).
Erzeugt einen portablen Ordner unter dist/TranscriptionAdler/.
"""

import os
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(os.path.abspath(SPECPATH))

# ----------------------------------------------------------------
# Assets, die ins Bundle wandern (Frontend, Icons, Whisper-Modelle)
# ----------------------------------------------------------------
datas = [
    (str(ROOT / 'index.html'),       '.'),
    (str(ROOT / 'style.css'),        '.'),
    (str(ROOT / 'app.js'),           '.'),
    (str(ROOT / 'eagle_icon.png'),   '.'),
    (str(ROOT / 'eagle_icon.ico'),   '.'),
]

# Whisper-Modelle (tiny, base, small) – nur einbinden, wenn vorhanden
for model_file in ('tiny.pt', 'base.pt', 'small.pt'):
    p = ROOT / model_file
    if p.exists():
        datas.append((str(p), '.'))
    else:
        print(f'[spec] WARNUNG: {model_file} nicht gefunden – wird nicht eingebunden.')

# Whisper-Assets (mel_filters.npz, multilingual.tiktoken, gpt2.tiktoken)
try:
    import whisper
    whisper_pkg_dir = Path(whisper.__file__).parent
    whisper_assets_dir = whisper_pkg_dir / 'assets'
    if whisper_assets_dir.exists():
        datas.append((str(whisper_assets_dir), 'whisper/assets'))
except ImportError:
    print('[spec] WARNUNG: whisper-Paket nicht importierbar.')

# ----------------------------------------------------------------
# Native Binaries (FFmpeg/FFprobe für Windows)
# ----------------------------------------------------------------
binaries = []
for binary_file in ('ffmpeg.exe', 'ffprobe.exe'):
    p = ROOT / binary_file
    if p.exists():
        binaries.append((str(p), '.'))
    else:
        print(f'[spec] WARNUNG: {binary_file} nicht gefunden.')

# ----------------------------------------------------------------
# Hidden Imports (Module, die PyInstaller sonst nicht erkennt)
# ----------------------------------------------------------------
hiddenimports = [
    'whisper',
    'whisper.audio',
    'whisper.decoding',
    'whisper.model',
    'whisper.tokenizer',
    'whisper.transcribe',
    'whisper.utils',
    'torch',
    'numpy',
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
    'regex',
    'ftfy',
    'more_itertools',
    'webview',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
    'docx',
    'deep_translator',
    'geopy',
    'geopy.geocoders.nominatim',
    'PIL',
    'PIL.Image',
]

# ----------------------------------------------------------------
# Analyse
# ----------------------------------------------------------------
a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI-Toolkits, die wir nicht brauchen → spart Platz
        'tkinter',
        'matplotlib',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ----------------------------------------------------------------
# EXE
# ----------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TranscriptionAdler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX kann Antiviren-Falschmeldungen verursachen
    console=False,       # GUI-App – kein Konsolenfenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'eagle_icon.ico'),
)

# ----------------------------------------------------------------
# Collect → portabler Ordner unter dist/TranscriptionAdler/
# ----------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TranscriptionAdler',
)
