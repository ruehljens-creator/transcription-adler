@echo off
echo ===================================================
echo   Transcription Adler - Windows Build Script
echo ===================================================
echo.

echo 1. Installiere Python-Abhaengigkeiten...
pip install pyinstaller webview openai-whisper deep-translator python-docx geopy torch numpy Pillow

echo.
echo 2. Downloade ffmpeg und ffprobe fuer Windows...
python -c "import urllib.request, zipfile, io, os, shutil; print('Lade FFmpeg fuer Windows herunter...'); r = urllib.request.urlopen('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'); z = zipfile.ZipFile(io.BytesIO(r.read())); [shutil.copy(z.extract(f), '.') for f in z.namelist() if f.endswith('ffmpeg.exe') or f.endswith('ffprobe.exe')]; print('FFmpeg und FFprobe erfolgreich heruntergeladen.')"

echo.
echo 3. Downloade Whisper-Modelle (tiny & base) fuer Offline-Betrieb...
python -c "import whisper, urllib.request; print('Lade tiny.pt...'); urllib.request.urlretrieve(whisper._MODELS['tiny'], 'tiny.pt'); print('Lade base.pt...'); urllib.request.urlretrieve(whisper._MODELS['base'], 'base.pt')"

echo.
echo 4. Kompiliere Anwendung mit PyInstaller...
pyinstaller --name="TranscriptionAdler" --windowed --noconfirm --icon="eagle_icon.ico" --add-data="index.html;." --add-data="style.css;." --add-data="app.js;." --add-data="eagle_icon.png;." --add-data="tiny.pt;." --add-data="base.pt;." --add-binary="ffmpeg.exe;." --add-binary="ffprobe.exe;." main.py

echo.
echo 5. Erstelle Windows-Installer (Inno Setup)...
echo Falls Inno Setup nicht installiert ist, lade es von https://jrsoftware.org/isdl.php herunter.
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Inno Setup (ISCC) konnte nicht gefunden werden. 
    echo Die portable Version findest du unter: dist\TranscriptionAdler\TranscriptionAdler.exe
) else (
    echo.
    echo Setup-Datei erfolgreich erstellt: TranscriptionAdler_Setup.exe
)

echo.
echo === Fertig! ===
pause
