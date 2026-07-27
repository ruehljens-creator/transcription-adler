# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für Transcription Adler (macOS / Apple Silicon).
Erzeugt dist/TranscriptionAdler.app; das DMG baut build_macos.sh daraus.

Gegenstück zu TranscriptionAdler.spec (Windows) – bewusst getrennt, weil
Binärnamen (ffmpeg vs. ffmpeg.exe), die VLC-Laufzeit (dylib statt dll) und
das .app-Bundle plattformspezifisch sind.
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = Path(os.path.abspath(SPECPATH))

# ----------------------------------------------------------------
# Assets (Frontend, Icons, Whisper-Modelle)
# ----------------------------------------------------------------
datas = [
    (str(ROOT / 'index.html'),     '.'),
    (str(ROOT / 'style.css'),      '.'),
    (str(ROOT / 'app.js'),         '.'),
    (str(ROOT / 'eagle_icon.png'), '.'),
]

for model_file in ('tiny.pt', 'base.pt', 'small.pt'):
    p = ROOT / model_file
    if p.exists():
        datas.append((str(p), '.'))
    else:
        print(f'[spec] WARNUNG: {model_file} nicht gefunden – wird nicht eingebunden.')

# Whisper-Assets (mel_filters.npz, Tokenizer)
try:
    import whisper
    whisper_assets_dir = Path(whisper.__file__).parent / 'assets'
    if whisper_assets_dir.exists():
        datas.append((str(whisper_assets_dir), 'whisper/assets'))
except ImportError:
    print('[spec] WARNUNG: whisper-Paket nicht importierbar.')

# Resemblyzer (d-Vektor-Gewichte) + librosa für die Sprecher-Diarisierung
try:
    datas += collect_data_files('resemblyzer')
    datas += collect_data_files('librosa')
    print('[spec] Resemblyzer/librosa-Daten eingebunden.')
except Exception as _e:
    print(f'[spec] WARNUNG: Resemblyzer/librosa-Daten nicht einbindbar: {_e}')

# ----------------------------------------------------------------
# Native Binaries: ffmpeg/ffprobe (Homebrew, Apple Silicon)
# ----------------------------------------------------------------
binaries = []
_ff_dirs = ['/opt/homebrew/bin', '/usr/local/bin']
for tool in ('ffmpeg', 'ffprobe'):
    src = next((os.path.join(d, tool) for d in _ff_dirs
                if os.path.exists(os.path.join(d, tool))), None)
    if src:
        binaries.append((src, '.'))
        print(f'[spec] {tool} eingebunden aus: {src}')
    else:
        print(f'[spec] WARNUNG: {tool} nicht gefunden (brew install ffmpeg).')

# ----------------------------------------------------------------
# VLC-Laufzeit bündeln (autarkes DMG): libvlc + libvlccore + Plugins.
# Die Original-Struktur bleibt erhalten – vlc/lib und vlc/plugins sind
# Geschwister, damit die Plugins libvlccore über ihre relativen
# @loader_path-Referenzen finden (siehe _ensure_vlc() in main.py).
# ----------------------------------------------------------------
_vlc_macos = next(
    (d for d in ('/Applications/VLC.app/Contents/MacOS',
                 os.path.expanduser('~/Applications/VLC.app/Contents/MacOS'))
     if os.path.exists(os.path.join(d, 'lib', 'libvlc.dylib'))),
    None
)
if _vlc_macos:
    # libvlc/libvlccore MÜSSEN unter ihrem unversionierten Namen direkt in
    # Contents/Frameworks liegen: PyInstaller setzt den Plugins den RPATH
    # "@loader_path/../.." – von vlc/plugins/ aus ist das genau Frameworks/.
    # Dort suchen sie ihr "@rpath/libvlccore.dylib". Deshalb den Symlink-Pfad
    # (nicht realpath) verwenden, damit der Dateiname erhalten bleibt.
    _lib_dir = os.path.join(_vlc_macos, 'lib')
    for _name in ('libvlc.dylib', 'libvlccore.dylib'):
        _src = os.path.join(_lib_dir, _name)
        if os.path.exists(_src):
            binaries.append((_src, '.'))
        else:
            print(f'[spec] WARNUNG: {_name} nicht gefunden in {_lib_dir}')

    _plugins_dir = os.path.join(_vlc_macos, 'plugins')
    _n_plugins = 0
    if os.path.isdir(_plugins_dir):
        for _root, _dirs, _files in os.walk(_plugins_dir):
            for _f in _files:
                if not _f.endswith('.dylib'):
                    continue
                _full = os.path.join(_root, _f)
                _rel = os.path.relpath(_root, _plugins_dir)
                _dest = 'vlc/plugins' if _rel == '.' else os.path.join('vlc/plugins', _rel)
                binaries.append((_full, _dest))
                _n_plugins += 1
    print(f'[spec] VLC eingebunden aus {_vlc_macos} ({_n_plugins} Plugins).')
else:
    print('[spec] WARNUNG: VLC.app nicht gefunden – das DMG wäre NICHT autark '
          '(Wiedergabe bräuchte lokal installiertes VLC). '
          'Abhilfe: brew install --cask vlc')

# ----------------------------------------------------------------
# Hidden Imports
# ----------------------------------------------------------------
hiddenimports = [
    'whisper', 'whisper.audio', 'whisper.decoding', 'whisper.model',
    'whisper.tokenizer', 'whisper.transcribe', 'whisper.utils',
    'torch', 'numpy', 'tiktoken', 'tiktoken_ext', 'tiktoken_ext.openai_public',
    'regex', 'ftfy', 'more_itertools',
    'webview', 'webview.platforms.cocoa',
    'docx', 'deep_translator', 'geopy', 'geopy.geocoders.nominatim',
    'PIL', 'PIL.Image', 'vlc',
    # Dock-Icon / Cocoa-Anbindung
    'objc', 'AppKit', 'Foundation', 'WebKit',
    # Sprecher-Diarisierung
    'resemblyzer', 'librosa', 'soundfile', 'audioread', 'webrtcvad',
    'scipy', 'scipy.signal', 'scipy.ndimage',
]
hiddenimports += collect_submodules('librosa')
hiddenimports += collect_submodules('resemblyzer')

# ----------------------------------------------------------------
# Analyse
# ----------------------------------------------------------------
a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / 'hooks')],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'pandas', 'IPython', 'jupyter', 'notebook',
        'pytest', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'torchvision', 'torchaudio', 'cv2', 'sklearn',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TranscriptionAdler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,          # nativ bauen (arm64 auf Apple Silicon)
    codesign_identity=None,    # Ad-hoc-Signierung übernimmt build_macos.sh
    entitlements_file=None,
)

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

# ----------------------------------------------------------------
# macOS-App-Bundle
# ----------------------------------------------------------------
app = BUNDLE(
    coll,
    name='TranscriptionAdler.app',
    icon=str(ROOT / 'eagle_icon.icns') if (ROOT / 'eagle_icon.icns').exists() else None,
    bundle_identifier='de.ruehljens.transcriptionadler',
    version='1.1.0',
    info_plist={
        'CFBundleName': 'Transcription Adler',
        'CFBundleDisplayName': 'Transcription Adler',
        'CFBundleShortVersionString': '1.1.0',
        'CFBundleVersion': '1.1.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
        'NSHumanReadableCopyright': 'MIT-Lizenz – Jens Rühl',
    },
)
