"""
Lädt FFmpeg + FFprobe für Windows von einem stabilen Mirror herunter
und legt die beiden EXEs in das aktuelle Verzeichnis.
"""
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

# BtbN-Builds sind statisch verlinkt und ohne externe DLLs lauffähig.
URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

TARGET_DIR = Path(__file__).parent.resolve()


def download_with_progress(url: str) -> bytes:
    print(f"Lade FFmpeg von:\n  {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "TranscriptionAdler-Build/1.0"})
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        buf = io.BytesIO()
        downloaded = 0
        chunk_size = 1024 * 256
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            buf.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 / total
                sys.stdout.write(f"\r  {downloaded // (1024 * 1024)} / {total // (1024 * 1024)} MB ({pct:.1f} %)")
                sys.stdout.flush()
        sys.stdout.write("\n")
        return buf.getvalue()


def extract_binaries(zip_bytes: bytes) -> None:
    wanted = {"ffmpeg.exe", "ffprobe.exe"}
    found: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            name = Path(member).name.lower()
            if name in wanted and not member.endswith("/"):
                target = TARGET_DIR / name
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                print(f"  -> {target.name} extrahiert ({target.stat().st_size // (1024 * 1024)} MB)")
                found.add(name)
    missing = wanted - found
    if missing:
        raise RuntimeError(f"In ZIP nicht gefunden: {missing}")


def main() -> int:
    try:
        data = download_with_progress(URL)
        extract_binaries(data)
        print("FFmpeg-Download abgeschlossen.")
        return 0
    except Exception as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
