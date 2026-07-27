#!/bin/bash
# ============================================================
#  Transcription Adler – macOS-Build (Apple Silicon & Intel)
#  Erzeugt dist/TranscriptionAdler.app und TranscriptionAdler.dmg
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "===================================================="
echo "  Transcription Adler – Build für macOS"
echo "===================================================="
echo

# ---------- Plattform prüfen ----------
if [ "$(uname -s)" != "Darwin" ]; then
    echo "[FEHLER] Dieses Skript läuft nur auf macOS."
    exit 1
fi
echo "[OK] macOS $(sw_vers -productVersion) auf $(uname -m)"

# ---------- Python 3.10/3.11 suchen ----------
PY=""
for cand in python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        if "$cand" -c 'import sys; sys.exit(0 if sys.version_info[:2] in ((3,10),(3,11)) else 1)' 2>/dev/null; then
            PY="$cand"; break
        fi
    fi
done
if [ -z "$PY" ]; then
    echo "[FEHLER] Kein Python 3.10/3.11 gefunden."
    echo "  PyTorch und Whisper bieten dafür fertige Pakete an."
    echo "  Installation z. B. mit:  brew install python@3.11"
    exit 1
fi
echo "[OK] Python: $($PY --version) ($(command -v $PY))"

# ---------- ffmpeg/ffprobe ----------
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    echo "[Info] ffmpeg/ffprobe fehlen – installiere via Homebrew..."
    if ! command -v brew >/dev/null 2>&1; then
        echo "[FEHLER] Homebrew nicht gefunden. Bitte ffmpeg manuell installieren."
        exit 1
    fi
    brew install ffmpeg
fi
echo "[OK] ffmpeg: $(command -v ffmpeg)"

# ---------- virtuelle Umgebung ----------
if [ ! -d ".venv" ]; then
    echo
    echo "[Schritt 1/6] Virtuelle Umgebung wird erstellt..."
    "$PY" -m venv .venv
else
    echo "[Schritt 1/6] Virtuelle Umgebung vorhanden."
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# ---------- Abhängigkeiten ----------
echo
echo "[Schritt 2/6] Installiere Abhängigkeiten..."
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt
python -m pip install pyinstaller pillow
# Dock-Icon/Cocoa-Anbindung für pywebview
python -m pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit

# ---------- Sprecher-Diarisierung (Resemblyzer) ----------
echo
echo "[Schritt 3/6] Installiere Sprecher-Erkennung (Resemblyzer)..."
# Vorgebautes webrtcvad-Wheel bevorzugen; fällt auf Quellbau zurück
# (dafür reichen die Xcode Command Line Tools).
python -m pip install webrtcvad-wheels || python -m pip install webrtcvad
python -m pip install --no-deps resemblyzer

# ---------- Whisper-Modelle ----------
echo
echo "[Schritt 4/6] Lade Whisper-Modelle (tiny, base, small)..."
python download_models.py

# ---------- Icon (.icns) aus PNG erzeugen ----------
if [ ! -f "eagle_icon.icns" ] && [ -f "eagle_icon.png" ]; then
    echo "[Info] Erzeuge eagle_icon.icns aus eagle_icon.png..."
    ICONSET="$(mktemp -d)/icon.iconset"
    mkdir -p "$ICONSET"
    for size in 16 32 64 128 256 512; do
        sips -z $size $size eagle_icon.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
        sips -z $((size*2)) $((size*2)) eagle_icon.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o eagle_icon.icns || echo "[Warnung] .icns-Erzeugung fehlgeschlagen – Build läuft ohne eigenes Icon."
    rm -rf "$(dirname "$ICONSET")"
fi

# ---------- alte Build-Reste ----------
echo
echo "[Schritt 5/6] Räume alte Builds auf..."
rm -rf build dist          # NICHT die .spec-Dateien löschen – die sind eingecheckt!

# ---------- PyInstaller ----------
echo
echo "[Schritt 6/6] Erstelle App-Bundle mit PyInstaller..."
pyinstaller --noconfirm --clean TranscriptionAdler-macOS.spec

APP="dist/TranscriptionAdler.app"
if [ ! -d "$APP" ]; then
    echo "[FEHLER] App-Bundle wurde nicht erzeugt."
    exit 1
fi

# ---------- Ad-hoc-Signierung ----------
echo
echo "=== Ad-hoc-Signierung des App-Bundles ==="
codesign --force --deep --sign - "$APP"
codesign --verify --verbose=2 "$APP" 2>&1 | tail -3 || true

# ---------- DMG ----------
echo
echo "=== Erzeuge DMG ==="
DMG_STAGE="$(mktemp -d)/stage"
mkdir -p "$DMG_STAGE"
cp -R "$APP" "$DMG_STAGE/"
ln -s /Applications "$DMG_STAGE/Programme (Applications)"

RAW_DMG="$(mktemp -d)/TranscriptionAdler_raw.dmg"
rm -f "$SCRIPT_DIR/TranscriptionAdler.dmg"
hdiutil makehybrid -hfs -hfs-volume-name "Transcription Adler" -o "$RAW_DMG" "$DMG_STAGE" -quiet
hdiutil convert -format UDZO -o "$SCRIPT_DIR/TranscriptionAdler.dmg" "$RAW_DMG" -quiet
codesign --force --sign - "$SCRIPT_DIR/TranscriptionAdler.dmg"
rm -rf "$(dirname "$DMG_STAGE")" "$(dirname "$RAW_DMG")"

echo
echo "===================================================="
echo "  FERTIG!"
echo "===================================================="
echo "App:  $SCRIPT_DIR/dist/TranscriptionAdler.app"
echo "DMG:  $SCRIPT_DIR/TranscriptionAdler.dmg"
echo
echo "Hinweis: Für die Videowiedergabe muss VLC installiert sein"
echo "         (brew install --cask vlc oder videolan.org)."
echo "Die App ist ad-hoc signiert; beim ersten Start ggf."
echo "Rechtsklick → Öffnen (Gatekeeper)."
