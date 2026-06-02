"""
Export der Schnittmarken als FCPXML (Apple Final Cut Pro, Version 1.9).
Die Schnitte werden als Clip-Sequenz (Spine) abgebildet. Auch von Premiere
und DaVinci Resolve importierbar.

FCPXML nutzt rationale, frame-ausgerichtete Zeiten ("num/dens").
"""

import os
from urllib.parse import quote
from xml.sax.saxutils import escape


def _frame_duration(fps):
    """Liefert (num, den) für die Frame-Dauer in Sekunden."""
    if not fps or fps <= 0:
        fps = 25.0
    if abs(fps - 23.976) < 0.05:
        return 1001, 24000
    if abs(fps - 29.97) < 0.05:
        return 1001, 30000
    if abs(fps - 59.94) < 0.05:
        return 1001, 60000
    n = int(round(fps))
    return 100, 100 * n  # z. B. 25 fps -> 100/2500 (= 1/25)


def _rt(seconds, fd_num, fd_den):
    """Frame-ausgerichtete rationale Zeit als '<num>/<den>s'."""
    if seconds < 0:
        seconds = 0.0
    frames = int(round(seconds * fd_den / fd_num))
    return f"{frames * fd_num}/{fd_den}s"


def _file_url(path):
    p = os.path.abspath(path).replace('\\', '/')
    if not p.startswith('/'):
        p = '/' + p
    # ':' und '/' nicht kodieren -> file:///C:/Ordner/Datei.mxf
    return 'file://' + quote(p, safe='/:')


def _normalize_cuts(cuts):
    norm = []
    for c in cuts:
        if isinstance(c, dict):
            s, e = c.get('start', 0.0), c.get('end', 0.0)
        else:
            s, e = c[0], c[1]
        s, e = float(s), float(e)
        if e > s:
            norm.append((s, e))
    norm.sort(key=lambda x: x[0])
    return norm


def build_fcpxml(title, src_path, cuts, fps=25.0, start_offset=0.0,
                 total_duration=0.0, width=1920, height=1080):
    cuts = _normalize_cuts(cuts)
    fps = fps or 25.0
    width = int(width) if width else 1920
    height = int(height) if height else 1080
    fd_num, fd_den = _frame_duration(fps)
    fd = f"{fd_num}/{fd_den}s"

    name = escape(title or 'Transkript')
    media_len = total_duration if (total_duration and total_duration > 0) else 3600.0
    asset_dur = _rt(media_len, fd_num, fd_den)
    asset_start = _rt(start_offset, fd_num, fd_den)
    src = escape(_file_url(src_path))
    total_cut = sum(e - s for s, e in cuts)
    seq_dur = _rt(total_cut if total_cut > 0 else media_len, fd_num, fd_den)

    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<!DOCTYPE fcpxml>')
    out.append('<fcpxml version="1.9">')
    out.append('  <resources>')
    out.append(f'    <format id="r1" name="FFVideoFormat" frameDuration="{fd}" width="{width}" height="{height}"/>')
    out.append(f'    <asset id="r2" name="{name}" start="{asset_start}" duration="{asset_dur}" '
               f'hasVideo="1" hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000" format="r1">')
    out.append(f'      <media-rep kind="original-media" src="{src}"/>')
    out.append('    </asset>')
    out.append('  </resources>')
    out.append('  <library>')
    out.append('    <event name="Transcription Adler">')
    out.append(f'      <project name="{name} &#8211; Schnittliste">')
    out.append(f'        <sequence format="r1" tcStart="0s" tcFormat="NDF" duration="{seq_dur}">')
    out.append('          <spine>')
    offset = 0.0
    for i, (s, e) in enumerate(cuts, 1):
        dur = e - s
        out.append(
            f'            <asset-clip ref="r2" offset="{_rt(offset, fd_num, fd_den)}" '
            f'name="Schnitt {i}" start="{_rt(start_offset + s, fd_num, fd_den)}" '
            f'duration="{_rt(dur, fd_num, fd_den)}" tcFormat="NDF"/>'
        )
        offset += dur
    out.append('          </spine>')
    out.append('        </sequence>')
    out.append('      </project>')
    out.append('    </event>')
    out.append('  </library>')
    out.append('</fcpxml>')
    return '\n'.join(out) + '\n'
