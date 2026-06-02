"""
Export der Schnittmarken (In/Out-Bereiche) als CMX3600-EDL.
Wird von Adobe Premiere, Avid Media Composer und DaVinci Resolve gelesen.

Die Schnitt-Zeiten sind 0-basiert (Sekunden, relativ zum Dateianfang).
Mit einem Start-Timecode-Versatz (start_offset) spiegeln die Quell-Timecodes
den echten Timecode der Datei wider (z. B. 10:00:00:00 bei Broadcast-Material).
"""


def seconds_to_timecode(seconds, fps):
    """Wandelt Sekunden in einen Non-Drop-Timecode HH:MM:SS:FF (bei gegebener fps)."""
    if not fps or fps <= 0:
        fps = 25.0
    if seconds < 0:
        seconds = 0.0
    nominal = max(1, int(round(fps)))
    total_frames = int(round(seconds * fps))
    frames = total_frames % nominal
    secs = (total_frames // nominal) % 60
    mins = (total_frames // (nominal * 60)) % 60
    hours = (total_frames // (nominal * 3600))
    return f"{hours:02d}:{mins:02d}:{secs:02d}:{frames:02d}"


def _normalize_cuts(cuts):
    """Akzeptiert [{'start':..,'end':..}, ...] oder [[start, end], ...]."""
    norm = []
    for c in cuts:
        if isinstance(c, dict):
            start, end = c.get("start", 0.0), c.get("end", 0.0)
        else:
            start, end = c[0], c[1]
        start = float(start)
        end = float(end)
        if end > start:
            norm.append((start, end))
    norm.sort(key=lambda x: x[0])
    return norm


def build_edl(title, cuts, fps=25.0, start_offset=0.0):
    """
    Baut den EDL-Text. Quell-Timecodes = start_offset + Schnittzeit; Record-
    Timecodes laufen fortlaufend ab 00:00:00:00 (jeder Schnitt direkt hinter dem
    vorherigen auf der Zeitleiste).
    """
    cuts = _normalize_cuts(cuts)
    fps = fps or 25.0
    safe_title = (title or "Transkript").replace("\n", " ").strip()

    lines = [f"TITLE: {safe_title}", "FCM: NON-DROP FRAME", ""]
    record = 0.0
    for idx, (start, end) in enumerate(cuts, 1):
        duration = end - start
        src_in = seconds_to_timecode(start_offset + start, fps)
        src_out = seconds_to_timecode(start_offset + end, fps)
        rec_in = seconds_to_timecode(record, fps)
        rec_out = seconds_to_timecode(record + duration, fps)
        lines.append(f"{idx:03d}  AX       V     C        {src_in} {src_out} {rec_in} {rec_out}")
        lines.append(f"* FROM CLIP NAME: {safe_title}")
        lines.append("")
        record += duration

    return "\r\n".join(lines) + "\r\n"
