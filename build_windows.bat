@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

REM ============================================================
REM   Transcription Adler – Windows Build Script
REM   Erzeugt eine portable Version unter dist\TranscriptionAdler\
REM ============================================================

echo.
echo ====================================================
echo   Transcription Adler – Build fuer Windows 11
echo ====================================================
echo.

REM ---------- Python pruefen ----------
where python >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python wurde nicht gefunden.
    echo Bitte Python 3.10 oder 3.11 von https://www.python.org/downloads/ installieren
    echo und beim Setup "Add python.exe to PATH" anhaken.
    pause
    exit /b 1
)
echo [OK] Python gefunden:
python --version

REM ---------- Optional: virtuelle Umgebung ----------
if not exist ".venv\" (
    echo.
    echo [Schritt 1/6] Virtuelle Umgebung wird erstellt...
    python -m venv .venv
    if errorlevel 1 (
        echo [FEHLER] venv konnte nicht erstellt werden.
        pause
        exit /b 1
    )
) else (
    echo [Schritt 1/6] Virtuelle Umgebung vorhanden.
)
call .venv\Scripts\activate.bat

REM ---------- Abhaengigkeiten ----------
echo.
echo [Schritt 2/6] Installiere Abhaengigkeiten...
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt
python -m pip install pyinstaller pillow
if errorlevel 1 (
    echo [FEHLER] Installation der Abhaengigkeiten fehlgeschlagen.
    pause
    exit /b 1
)

REM ---------- FFmpeg + FFprobe ----------
echo.
echo [Schritt 3/6] Pruefe FFmpeg / FFprobe...
if exist "ffmpeg.exe" if exist "ffprobe.exe" (
    echo [OK] FFmpeg und FFprobe sind bereits vorhanden.
    goto :models
)

echo [Info] FFmpeg / FFprobe nicht gefunden – Download startet...
python download_ffmpeg.py
if errorlevel 1 (
    echo [FEHLER] FFmpeg-Download fehlgeschlagen.
    echo Bitte ffmpeg.exe und ffprobe.exe manuell ins Projektverzeichnis legen.
    pause
    exit /b 1
)

:models
REM ---------- Whisper-Modelle ----------
echo.
echo [Schritt 4/6] Lade Whisper-Modelle (tiny, base, small)...
python download_models.py
if errorlevel 1 (
    echo [FEHLER] Modell-Download fehlgeschlagen.
    pause
    exit /b 1
)

REM ---------- Alte Build-Reste loeschen ----------
echo.
echo [Schritt 5/6] Raeume alte Builds auf...
if exist "build\"  rmdir /s /q build
if exist "dist\"   rmdir /s /q dist

REM ---------- PyInstaller ----------
echo.
echo [Schritt 6/6] Erstelle portable Anwendung mit PyInstaller...
pyinstaller --noconfirm --clean TranscriptionAdler.spec
if errorlevel 1 (
    echo [FEHLER] PyInstaller-Build fehlgeschlagen.
    pause
    exit /b 1
)

REM ---------- Erfolg ----------
echo.
echo ====================================================
echo   FERTIG!
echo ====================================================
echo.
echo Portable Anwendung:  dist\TranscriptionAdler\TranscriptionAdler.exe
echo.
echo Den gesamten Ordner "dist\TranscriptionAdler" kannst du auf
echo einen USB-Stick kopieren oder als ZIP weitergeben – die EXE
echo laeuft ohne weitere Installation auf Windows 10/11 (64 Bit).
echo.

REM ---------- Optionaler Inno-Setup-Schritt ----------
REM ISCC.exe an den ueblichen Orten suchen (auch Pro-Benutzer-Installation).
set "ISCC="
for %%P in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) do (
    if not defined ISCC if exist "%%~P" set "ISCC=%%~P"
)

if defined ISCC (
    echo Inno Setup gefunden: !ISCC!
    echo Erstelle Installer...
    "!ISCC!" installer.iss
    if not errorlevel 1 (
        echo Setup-Datei erstellt: TranscriptionAdler_Setup.exe
    )
) else (
    echo [Info] Inno Setup nicht installiert – portable Version reicht voellig aus.
    echo        ^(Falls Setup gewuenscht: https://jrsoftware.org/isdl.php^)
)

echo.
pause
endlocal
