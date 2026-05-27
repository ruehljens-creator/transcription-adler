#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Säubere alte Build-Artefakte ==="
rm -rf build dist TranscriptionAdler.spec
rm -rf /tmp/build_adler /tmp/dist_adler

# Find python interpreter
PYTHON="../venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

echo "=== Downloade Whisper-Modelle (tiny & base) für 100% Offline-Betrieb ==="
# Download tiny model weights if not present
if [ ! -f "tiny.pt" ]; then
    echo "Lade tiny.pt herunter..."
    "$PYTHON" -c "import whisper, urllib.request; urllib.request.urlretrieve(whisper._MODELS['tiny'], 'tiny.pt')"
fi

# Download base model weights if not present
if [ ! -f "base.pt" ]; then
    echo "Lade base.pt herunter..."
    "$PYTHON" -c "import whisper, urllib.request; urllib.request.urlretrieve(whisper._MODELS['base'], 'base.pt')"
fi

echo "=== Erstelle Standalone-App-Bundle mit PyInstaller ==="
# We bundle:
# - index.html, style.css, app.js
# - eagle_icon.png
# - ffmpeg and ffprobe binaries
# - Whisper model files (tiny.pt, base.pt)
"$PYTHON" -m PyInstaller \
  --name="TranscriptionAdler" \
  --windowed \
  --noconfirm \
  --workpath="/tmp/build_adler" \
  --distpath="/tmp/dist_adler" \
  --icon="eagle_icon.png" \
  --add-data="index.html:." \
  --add-data="style.css:." \
  --add-data="app.js:." \
  --add-data="eagle_icon.png:." \
  --add-data="tiny.pt:." \
  --add-data="base.pt:." \
  --add-binary="/opt/homebrew/bin/ffmpeg:." \
  --add-binary="/opt/homebrew/bin/ffprobe:." \
  --hidden-import=webview \
  --hidden-import=whisper \
  --hidden-import=geopy \
  --hidden-import=deep_translator \
  --hidden-import=docx \
  --hidden-import=torch \
  --hidden-import=numpy \
  main.py

echo "=== Führe Ad-hoc Code-Signierung durch ==="
codesign --force --deep --sign - /tmp/dist_adler/TranscriptionAdler.app

echo "=== Bereite DMG Staging-Ordner vor ==="
DMG_STAGE="/tmp/dist_adler/dmg_stage"
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"
cp -r /tmp/dist_adler/TranscriptionAdler.app "$DMG_STAGE/"

# Link to Applications folder for easy drag and drop installer
ln -s /Applications "$DMG_STAGE/Programme (Applications)"

echo "=== Erzeuge komprimiertes DMG-Image ==="
rm -f "/tmp/TranscriptionAdler_raw.dmg"
rm -f "$SCRIPT_DIR/TranscriptionAdler.dmg"

# 1. Create a hybrid raw image (hfs+)
hdiutil makehybrid -hfs -o "/tmp/TranscriptionAdler_raw.dmg" "$DMG_STAGE"

# 2. Compress the image to UDZO format
hdiutil convert -format UDZO -o "$SCRIPT_DIR/TranscriptionAdler.dmg" "/tmp/TranscriptionAdler_raw.dmg"

# 3. Sign the DMG file itself
echo "=== Führe Ad-hoc Signierung des DMG-Images durch ==="
codesign --force --sign - "$SCRIPT_DIR/TranscriptionAdler.dmg"

# Cleanup staging and raw image
rm -f "/tmp/TranscriptionAdler_raw.dmg"
rm -rf "$DMG_STAGE"

echo "✅ DMG erfolgreich erstellt und signiert: transcriber-app/TranscriptionAdler.dmg"
