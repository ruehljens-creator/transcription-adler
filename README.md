# Transcription Adler

**Offline-Transkription und -Übersetzung von Audio- und Videodateien mit OpenAI Whisper.** Läuft vollständig lokal – keine Daten verlassen den Rechner.

*🇬🇧 [English version](README.en.md)*

> 📖 **[Bedienungsanleitung (mit Screenshots)](BEDIENUNGSANLEITUNG.md)** – Schritt-für-Schritt-Erklärung aller Funktionen und Einstellungen.

## Funktionen

- **Transkription in über 90 Sprachen** – vollständig offline (Whisper: tiny / base / small)
- **Sprecher-Erkennung (Diarisierung)** über vortrainierte Stimm-Embeddings (Resemblyzer) – ebenfalls offline
- **Optionale Übersetzung** in eine Zielsprache
- **Word-Bericht (.docx)** mit Zeitstempeln, Sprechern und Metadaten
- **Video-Player** mit synchron mitlaufendem Transkript – Klick auf einen Satz springt an die Stelle
- **Schnittmarken (IN/OUT)** und Export als **EDL** (Premiere, Avid, DaVinci Resolve) oder **FCPXML** (Final Cut Pro)
- **Broadcast-tauglich:** MXF und andere Profi-Formate, Original-Timecode der Datei wird berücksichtigt
- Metadaten-Auslesung (Dauer, Erstellungsdatum, GPS-Ort)
- Projektdateien (`.adler`) sichern Transkript, Schnitte und Video-Verknüpfung
- Barrierefreie Benutzeroberfläche (Tastaturbedienung, Screenreader, hohe Kontraste)
- Läuft auf **Windows** und **macOS (Apple Silicon)**

## Download

Fertige Pakete gibt es unter [Releases](../../releases/latest):

| Datei | Plattform |
|---|---|
| `TranscriptionAdler_Setup.exe` | Windows 10/11 (64 Bit) |
| `TranscriptionAdler.dmg` | macOS 11+ auf Apple Silicon (arm64) |
| `BEDIENUNGSANLEITUNG.pdf` | Anleitung mit Screenshots |

Beide Pakete sind **vollständig autark** – FFmpeg, VLC und die Whisper-Modelle sind enthalten, es ist keine weitere Installation nötig.

> **macOS:** Die App ist ad-hoc signiert (kein Apple-Entwicklerzertifikat). Beim ersten Start deshalb **Rechtsklick → „Öffnen"** und im Dialog nochmals „Öffnen".
> Die Wiedergabe läuft dort in einem eigenen VLC-Fenster; die unter Windows mögliche Einbettung des Videobildes gibt es auf macOS nicht.

## Unterstützte Dateiformate

Für die Transkription wird ausschließlich die **Audiospur** ausgewertet – der Video-Codec spielt dabei **keine Rolle**. Verarbeitet werden kann alles, was das mitgelieferte FFmpeg dekodiert:

**Video-Container**

| Format | Endungen |
|---|---|
| QuickTime / MPEG-4 | `.mp4` `.mov` `.m4v` `.3gp` |
| Matroska / WebM | `.mkv` `.webm` |
| **MXF** (Broadcast) | `.mxf` |
| MPEG Transport Stream | `.ts` `.m2ts` `.mts` |
| AVI | `.avi` |
| Windows Media | `.wmv` `.asf` |
| Flash Video | `.flv` |
| GXF / LXF (Broadcast) | `.gxf` `.lxf` |

**Audio-Formate**

`.wav` `.mp3` `.m4a` `.aac` `.flac` `.aiff` `.ogg` `.opus` `.wma` `.caf` `.ac3`

**Enthaltene Video-Codecs** (für die Wiedergabe im Player): H.264/AVC, H.265/HEVC, AV1, MPEG-2, **Apple ProRes** (inkl. RAW), **DNxHD/VC-3**, DV

**Enthaltene Audio-Codecs:** AAC, MP3, AC-3, ALAC, FLAC, Opus, Vorbis, WMA sowie sämtliche PCM-Varianten (16/24/32 Bit) – auch mehrkanalige Broadcast-Tonspuren.

> Der Dateidialog schlägt die gängigsten Endungen vor; über **„Alle Dateien"** oder per **Drag & Drop** lässt sich jedes weitere von FFmpeg unterstützte Format laden.
> Projektdateien der App tragen die Endung `.adler`.

## Datenschutz

Transkription, Sprechererkennung und Berichtserstellung laufen **vollständig offline** auf dem eigenen Rechner. Einzig die optionale **Übersetzung** nutzt einen Online-Dienst und überträgt dabei den erkannten *Text*. Bleibt die Übersetzung deaktiviert, verlässt nichts den Rechner. (Die Übersetzung *ins Englische* übernimmt Whisper selbst und bleibt offline.)

## Portable EXE für Windows 11 bauen

### Voraussetzungen

- Windows 10/11, 64 Bit
- **Python 3.10 oder 3.11** ([python.org](https://www.python.org/downloads/)) – beim Setup unbedingt **„Add python.exe to PATH"** anhaken
- Etwa **8 GB freier Speicher** während des Builds (das fertige Bundle liegt bei ca. 2,5 GB)
- Eine stabile Internetverbindung für FFmpeg- und Modell-Download

### Build starten

In der Eingabeaufforderung im Projektordner einfach:

```cmd
build_windows.bat
```

Das Skript erledigt alles automatisch:

1. Legt eine virtuelle Python-Umgebung an
2. Installiert alle Abhängigkeiten
3. Lädt FFmpeg und FFprobe (ca. 80 MB)
4. Lädt Whisper-Modelle **tiny**, **base** und **small** (ca. 670 MB zusammen)
5. Räumt alte Builds auf
6. Erzeugt die portable Anwendung mit PyInstaller

Je nach Hardware und Internetverbindung dauert der Build **15–30 Minuten**.

### Ergebnis

```
dist\TranscriptionAdler\TranscriptionAdler.exe
```

Den **gesamten Ordner** `dist\TranscriptionAdler\` kannst du:

- direkt starten (Doppelklick auf `TranscriptionAdler.exe`)
- auf einen USB-Stick kopieren
- als ZIP weitergeben

Der Ordner enthält alles, was zum Betrieb nötig ist – keine zusätzliche Installation, keine Administratorrechte.

> **Wichtig:** Die EXE kann nicht einzeln aus dem Ordner kopiert werden. PyInstaller verteilt die DLLs und Daten daneben – sie müssen zusammenbleiben.

## Optionaler Installer (statt portable)

Wenn [Inno Setup](https://jrsoftware.org/isdl.php) installiert ist, baut `build_windows.bat` automatisch zusätzlich `TranscriptionAdler_Setup.exe`. Andernfalls einfach den portablen Ordner verteilen.

## App und DMG für macOS bauen (Apple Silicon)

### Voraussetzungen

- macOS 11 oder neuer auf Apple Silicon (arm64)
- **Python 3.10 oder 3.11** – z. B. `brew install python@3.11`
  (System-Python 3.9 und aktuelle 3.13/3.14 funktionieren **nicht**: für sie gibt es keine PyTorch-/Whisper-Pakete)
- **Homebrew** mit `ffmpeg`: `brew install ffmpeg`
- **VLC**: `brew install --cask vlc` – wird ins Bundle kopiert, damit das DMG autark ist
- Xcode Command Line Tools: `xcode-select --install`
- Etwa **10 GB** freier Speicher während des Builds

### Build starten

```bash
./build_macos.sh
```

Das Skript legt eine virtuelle Umgebung an, installiert alle Abhängigkeiten
(inklusive Resemblyzer für die Sprechererkennung), lädt die Whisper-Modelle,
erzeugt aus `eagle_icon.png` ein `.icns`, baut das App-Bundle über
`TranscriptionAdler-macOS.spec`, signiert es ad-hoc und packt ein DMG.

### Ergebnis

```
dist/TranscriptionAdler.app
TranscriptionAdler.dmg
```

Das Bundle enthält FFmpeg, die VLC-Laufzeit (libVLC + Plugins) und die
Whisper-Modelle – auf dem Zielrechner muss nichts nachinstalliert werden.

## Barrierefreiheit

Die Oberfläche ist nach WCAG 2.1 AA gestaltet:

- Vollständige Tastaturbedienung (Skip-Link, sichtbare Fokus-Indikatoren)
- ARIA-Labels und Live-Regionen für Screenreader (NVDA, JAWS, Narrator)
- Kontrastverhältnisse aller Textfarben ≥ 4,5:1, meist > 7:1
- Unterstützung für `prefers-reduced-motion` und Windows-Hochkontrast-Modus
- Mindestgröße aller Bedienelemente 44×44 px (Touch-tauglich)
- Korrekte semantische HTML-Struktur

## Lizenz

Siehe LICENSE-Datei (sofern vorhanden).
