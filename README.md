# Transcription Adler

Offline-Transkription und -Übersetzung von Audio- und Videodateien mit OpenAI Whisper. Läuft vollständig lokal – keine Daten verlassen den Rechner.

## Funktionen

- Transkription in mehreren Sprachen (Whisper: tiny / base / small)
- Optionale Übersetzung in eine Zielsprache
- Metadaten-Auslesung (Dauer, Erstellungsdatum, GPS-Ort)
- Word-Bericht (.docx) als Ergebnis
- Barrierefreie Benutzeroberfläche (Tastaturbedienung, Screenreader, hohe Kontraste)

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
