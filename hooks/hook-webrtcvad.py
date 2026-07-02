# Lokaler Override für den PyInstaller-Contrib-Hook von webrtcvad.
#
# Wir installieren "webrtcvad-wheels" (vorgebautes Wheel, damit kein C-Compiler
# nötig ist). Es stellt zwar das Import-Modul "webrtcvad" bereit, die
# Distribution heißt aber "webrtcvad-wheels". Der Contrib-Hook ruft
# copy_metadata('webrtcvad') auf und bricht dadurch den Build ab.
# Dieser Override fängt das ab und bindet die Metadaten des tatsächlich
# installierten Pakets ein.
from PyInstaller.utils.hooks import copy_metadata

datas = []
for _dist in ("webrtcvad", "webrtcvad-wheels"):
    try:
        datas = copy_metadata(_dist)
        break
    except Exception:
        continue
