# Transcription Adler

**Offline transcription and translation of audio and video files, powered by OpenAI Whisper.** Everything runs locally — no data ever leaves your machine.

*🇩🇪 [Deutsche Version](README.md)*

> 📖 The illustrated user manual is currently available in German only: **[Bedienungsanleitung](BEDIENUNGSANLEITUNG.md)**.

## Features

- **Transcription in 90+ languages** — fully offline (Whisper: tiny / base / small)
- **Speaker diarization** using pre-trained voice embeddings (Resemblyzer) — also offline
- **Optional translation** into a target language
- **Word report (.docx)** with timestamps, speaker labels and file metadata
- **Video player** with a synchronized transcript — click a line to jump to that moment
- **Cut marks (IN/OUT)** exportable as **EDL** (Premiere, Avid, DaVinci Resolve) or **FCPXML** (Final Cut Pro)
- **Broadcast ready:** handles MXF and other professional formats, honours the file's original timecode
- Metadata extraction (duration, creation date, GPS location)
- Project files (`.adler`) preserve transcript, cuts and the video link
- Accessible user interface (full keyboard control, screen readers, high contrast)
- Runs on **Windows** and **macOS (Apple Silicon)**

## Download

Ready-made packages are available under [Releases](../../releases/latest):

| File | Platform |
|---|---|
| `TranscriptionAdler_Setup.exe` | Windows 10/11 (64-bit) |
| `TranscriptionAdler.dmg` | macOS 11+ on Apple Silicon (arm64) |
| `BEDIENUNGSANLEITUNG.pdf` | Illustrated manual (German) |

Both packages are **fully self-contained** — FFmpeg, VLC and the Whisper models are bundled, nothing else needs to be installed.

> **macOS:** The app is ad-hoc signed (no Apple Developer certificate). On first launch use **right-click → "Open"**, then confirm with "Open" in the dialog.
> Playback happens in a separate VLC window; the embedded video view available on Windows is not offered on macOS.

## Supported file formats

Transcription only ever reads the **audio track** — the video codec is **irrelevant** for it. Anything the bundled FFmpeg can decode will work:

**Video containers**

| Format | Extensions |
|---|---|
| QuickTime / MPEG-4 | `.mp4` `.mov` `.m4v` `.3gp` |
| Matroska / WebM | `.mkv` `.webm` |
| **MXF** (broadcast) | `.mxf` |
| MPEG transport stream | `.ts` `.m2ts` `.mts` |
| AVI | `.avi` |
| Windows Media | `.wmv` `.asf` |
| Flash Video | `.flv` |
| GXF / LXF (broadcast) | `.gxf` `.lxf` |

**Audio formats**

`.wav` `.mp3` `.m4a` `.aac` `.flac` `.aiff` `.ogg` `.opus` `.wma` `.caf` `.ac3`

**Bundled video codecs** (for playback): H.264/AVC, H.265/HEVC, AV1, MPEG-2, **Apple ProRes** (including RAW), **DNxHD/VC-3**, DV

**Bundled audio codecs:** AAC, MP3, AC-3, ALAC, FLAC, Opus, Vorbis, WMA and every PCM variant (16/24/32-bit), including multi-channel broadcast tracks.

> The file dialog suggests the most common extensions; use **"All files"** or **drag & drop** to load any other format FFmpeg supports.
> The app's own project files use the `.adler` extension.

## Privacy

Transcription, speaker recognition and report generation run **entirely offline** on your machine. The only feature that uses the internet is the optional **translation**, which sends the recognized *text* to an online translation service. Leave translation disabled to keep everything local. (Translation *into English* is handled by Whisper itself and stays offline.)

## Building a portable EXE for Windows

### Requirements

- Windows 10/11, 64-bit
- **Python 3.10 or 3.11** ([python.org](https://www.python.org/downloads/)) — make sure to tick **"Add python.exe to PATH"** during setup
- About **8 GB** of free space during the build (the finished bundle is roughly 2.5 GB)
- An internet connection for downloading FFmpeg and the models

### Running the build

From a command prompt in the project folder:

```cmd
build_windows.bat
```

The script creates a virtual environment, installs all dependencies, downloads
FFmpeg/FFprobe and the Whisper models (tiny, base, small), then builds the
application with PyInstaller. Expect **15–30 minutes** depending on hardware and
connection speed.

### Result

```
dist\TranscriptionAdler\TranscriptionAdler.exe
```

The **entire folder** `dist\TranscriptionAdler\` is portable: run it directly,
copy it to a USB stick, or pass it on as a ZIP. No installation and no
administrator rights required.

> **Important:** the EXE cannot be moved out of the folder on its own — PyInstaller places DLLs and data next to it, and they must stay together.

If [Inno Setup](https://jrsoftware.org/isdl.php) is installed, `build_windows.bat`
additionally produces `TranscriptionAdler_Setup.exe`.

## Building the app and DMG for macOS (Apple Silicon)

### Requirements

- macOS 11 or newer on Apple Silicon (arm64)
- **Python 3.10 or 3.11** — e.g. `brew install python@3.11`
  (system Python 3.9 and current 3.13/3.14 will **not** work: no PyTorch/Whisper wheels exist for them)
- **Homebrew** with `ffmpeg`: `brew install ffmpeg`
- **VLC**: `brew install --cask vlc` — it gets copied into the bundle so the DMG stays self-contained
- Xcode Command Line Tools: `xcode-select --install`
- About **10 GB** of free space during the build

### Running the build

```bash
./build_macos.sh
```

The script sets up a virtual environment, installs all dependencies (including
Resemblyzer for speaker recognition), downloads the Whisper models, generates an
`.icns` icon from `eagle_icon.png`, builds the app bundle via
`TranscriptionAdler-macOS.spec`, signs it ad-hoc and packages a DMG.

### Result

```
dist/TranscriptionAdler.app
TranscriptionAdler.dmg
```

The bundle ships FFmpeg, the VLC runtime (libVLC + plugins) and the Whisper
models — nothing needs to be installed on the target machine.

## Accessibility

The interface follows WCAG 2.1 AA:

- Full keyboard operation (skip link, visible focus indicators)
- ARIA labels and live regions for screen readers (NVDA, JAWS, Narrator)
- Contrast ratios of at least 4.5:1, mostly above 7:1
- Support for `prefers-reduced-motion` and Windows high-contrast mode
- All controls at least 44×44 px (touch friendly)
- Semantically correct HTML structure

## License

MIT — see the LICENSE file (if present).
