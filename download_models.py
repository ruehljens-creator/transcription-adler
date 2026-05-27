"""
Lädt die Whisper-Modelle tiny, base und small herunter und legt sie
als tiny.pt / base.pt / small.pt ins aktuelle Verzeichnis.

Wir benutzen die offiziellen URLs aus whisper._MODELS, damit die
Hashes/Versionen identisch zu denen sind, die Whisper zur Laufzeit
erwartet.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS_TO_FETCH = ("tiny", "base", "small")
TARGET_DIR = Path(__file__).parent.resolve()


def fetch(name: str, url: str) -> None:
    target = TARGET_DIR / f"{name}.pt"
    if target.exists():
        print(f"[{name}] schon vorhanden ({target.stat().st_size // (1024 * 1024)} MB) – überspringe.")
        return

    print(f"[{name}] Lade von {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "TranscriptionAdler-Build/1.0"})
    with urllib.request.urlopen(req) as resp, open(target, "wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk = 1024 * 256
        while True:
            data = resp.read(chunk)
            if not data:
                break
            out.write(data)
            downloaded += len(data)
            if total:
                pct = downloaded * 100 / total
                sys.stdout.write(
                    f"\r  {downloaded // (1024 * 1024)} / {total // (1024 * 1024)} MB ({pct:.1f} %)"
                )
                sys.stdout.flush()
        sys.stdout.write("\n")
    print(f"[{name}] fertig: {target}")


def main() -> int:
    try:
        import whisper
    except ImportError:
        print("FEHLER: openai-whisper ist nicht installiert. "
              "Bitte zuerst `pip install -r requirements.txt` ausführen.", file=sys.stderr)
        return 1

    models = getattr(whisper, "_MODELS", None)
    if not models:
        print("FEHLER: whisper._MODELS nicht verfügbar.", file=sys.stderr)
        return 1

    for name in MODELS_TO_FETCH:
        url = models.get(name)
        if not url:
            print(f"WARNUNG: keine URL für Modell '{name}' bekannt – überspringe.")
            continue
        try:
            fetch(name, url)
        except Exception as exc:
            print(f"FEHLER beim Modell '{name}': {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
