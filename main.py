import sys
import os

# Make the bundled ffmpeg/ffprobe discoverable for subprocess calls (used by
# metadata extraction and Whisper's audio loading). When frozen, they live next
# to the executable in sys._MEIPASS; when running from source, they live in the
# project folder. Windows does not reliably search the current working directory
# for bare command names, so we prepend the right folder to PATH explicitly.
if getattr(sys, 'frozen', False):
    _bin_dir = sys._MEIPASS
else:
    _bin_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = _bin_dir + os.pathsep + os.environ.get("PATH", "")

import webview
import threading
from webview.dom import DOMEventHandler
from metadata import get_metadata
from transcribe import transcribe_file, TranscriptionCancelled
from docx_generator import create_docx
from edl_export import build_edl
import socket
import secrets
from bottle import Bottle, request, response, static_file

def set_dock_icon():
    """
    Sets the custom macOS Dock icon using PyObjC AppKit if running on macOS.
    """
    try:
        import platform
        if platform.system() == 'Darwin':
            current_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(current_dir, 'eagle_icon.png')
            if os.path.exists(icon_path):
                from AppKit import NSApplication, NSImage
                app = NSApplication.sharedApplication()
                image = NSImage.alloc().initByReferencingFile_(icon_path)
                if image:
                    app.setApplicationIconImage_(image)
                    print("macOS Dock Icon erfolgreich gesetzt.")
            else:
                print(f"Dock Icon nicht gefunden unter: {icon_path}")
    except Exception as e:
        print(f"Fehler beim Setzen des Dock Icons: {e}")

class Api:
    def __init__(self):
        self._window = None
        self._transcripts = {}
        # Set by the UI to request cancellation of the whole running queue.
        self._cancel_event = threading.Event()

        # Mutable processing queue shared with the UI (per-file control).
        self._queue = []                       # pending file paths, in order
        self._queue_lock = threading.Lock()
        self._worker_running = False
        self._current_file = None              # path currently being transcribed
        self._cancel_current = threading.Event()  # cancels only the current file
        self._proc_params = {}                 # transcription parameters for the run

        # UI settings, persisted to disk so they survive app restarts.
        self._settings_path = self._get_settings_path()
        self._settings = self._read_settings_file()

        # Native VLC player (plays MXF / pro codecs in its own window).
        self._vlc_instance = None
        self._vlc_player = None
        self._current_media_path = None
        # Owned, resizable native video window (VLC renders into it via set_hwnd).
        self._video_hwnd = None
        self._video_thread = None
        self._video_wndproc = None
        self._user32 = None
        self._embedded = False     # True = video als Kind-Fenster in der App
        self._main_hwnd = None     # Handle des Hauptfensters (für Embedding)

        # Start secure local HTTP server for media files
        self._server_token = secrets.token_hex(16)
        self._server_port = self._find_free_port()
        self._start_media_server()

    @staticmethod
    def _get_settings_path():
        """Returns the path to the persisted settings file (in the user profile)."""
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        folder = os.path.join(base, 'TranscriptionAdler')
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            folder = base
        return os.path.join(folder, 'settings.json')

    def _read_settings_file(self):
        """Loads persisted settings from disk; returns {} if none/unreadable."""
        try:
            if os.path.exists(self._settings_path):
                import json
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Fehler beim Lesen der Einstellungsdatei: {e}")
        return {}

    def save_app_settings(self, settings_json):
        """
        Stores the UI settings and persists them to disk so they survive a restart.
        """
        try:
            import json
            self._settings = json.loads(settings_json)
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Fehler beim Speichern der Einstellungen: {e}")
            return False

    def load_app_settings(self):
        """
        Returns the persisted UI settings (or {} if none have been saved yet).
        """
        return self._settings

    def _find_free_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def _start_media_server(self):
        app = Bottle()

        @app.route('/media')
        def serve_media():
            token = request.query.get('token')
            if token != self._server_token:
                response.status = 403
                return "Forbidden"
            
            file_path = request.query.get('path')
            if not file_path:
                response.status = 400
                return "Missing path"
            
            file_path = os.path.abspath(file_path)
            if not os.path.exists(file_path):
                response.status = 404
                return "File not found"
            
            dirname = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            return static_file(filename, root=dirname)

        def run():
            app.run(host='127.0.0.1', port=self._server_port, quiet=True)

        threading.Thread(target=run, daemon=True).start()

    def get_server_config(self):
        """
        Returns the port and security token of the local HTTP server.
        """
        return {
            "port": self._server_port,
            "token": self._server_token
        }

    # Suffix appended to the report filename per timecode mode (only used when
    # more than one mode is selected, so a single mode keeps the clean name).
    _TIMECODE_SUFFIX = {
        "every": "",
        "rows": "_sprecherwechsel",
        "blocks": "_sprecherbloecke",
    }

    @staticmethod
    def _normalize_timecode_modes(timecode_modes):
        """
        Accepts the timecode mode selection from the frontend (a list, a single
        string, or None) and returns a clean, ordered list of valid modes.
        """
        valid = ["every", "rows", "blocks"]
        if not timecode_modes:
            return ["every"]
        if isinstance(timecode_modes, str):
            timecode_modes = [timecode_modes]
        # Keep valid modes, preserve order, drop duplicates
        seen = []
        for m in timecode_modes:
            if m in valid and m not in seen:
                seen.append(m)
        return seen or ["every"]

    @staticmethod
    def _resolve_output_docx(file_path, output_dir_type, custom_path, suffix=""):
        """
        Determines where the generated .docx report should be written, based on
        the user's output preference (desktop / custom folder / next to source).
        An optional suffix is inserted before the extension to distinguish
        multiple reports of the same clip (one per timecode mode).
        """
        name_without_ext, _ = os.path.splitext(os.path.basename(file_path))
        output_name = f"{name_without_ext}_transkript{suffix}.docx"

        if output_dir_type == "desktop":
            return os.path.join(os.path.expanduser("~"), "Desktop", output_name)
        if output_dir_type == "custom" and custom_path and os.path.isdir(custom_path):
            return os.path.join(custom_path, output_name)
        # Default: alongside the source file
        base_path, _ = os.path.splitext(file_path)
        return f"{base_path}_transkript{suffix}.docx"

    def _generate_reports(self, file_path, meta, segments, output_dir_type, custom_path,
                          target_lang, docx_trans_mode, timecode_modes, cuts=None):
        """
        Generates one Word report per selected timecode mode and returns the list
        of created file basenames. With a single mode the clean filename is used;
        with several modes each gets a descriptive suffix to avoid overwriting.
        """
        modes = self._normalize_timecode_modes(timecode_modes)
        multiple = len(modes) > 1
        created = []
        for mode in modes:
            suffix = self._TIMECODE_SUFFIX.get(mode, "") if multiple else ""
            output_docx = self._resolve_output_docx(file_path, output_dir_type, custom_path, suffix)
            create_docx(
                output_docx,
                meta,
                segments,
                target_lang=target_lang,
                cuts=cuts,
                docx_trans_mode=docx_trans_mode,
                timecode_mode=mode
            )
            created.append(os.path.basename(output_docx))
        return created

    def update_docx_with_cuts(self, file_path, cuts_json, output_dir_type="source", custom_path="", target_lang=None, docx_trans_mode="both", timecode_modes=None):
        """
        Re-generates the Word Document(s), highlighting the list of cuts in the segments table.
        Called from the JS frontend when the user clicks "Bericht aktualisieren".
        One report is written per selected timecode mode.
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": "Datei existiert nicht"}

        segments = self._transcripts.get(file_path)
        if not segments:
            return {"success": False, "error": "Keine Transkriptionsdaten im Cache gefunden"}

        try:
            import json
            cuts_list = json.loads(cuts_json)  # Parses list of [start, end] pairs

            meta = get_metadata(file_path)

            created = self._generate_reports(
                file_path, meta, segments, output_dir_type, custom_path,
                target_lang, docx_trans_mode, timecode_modes, cuts=cuts_list
            )

            return {
                "success": True,
                "filename": ", ".join(created),
                "filenames": created
            }
        except Exception as e:
            print(f"Fehler bei Aktualisierung des Berichts: {e}")
            return {"success": False, "error": str(e)}

    def export_cuts(self, file_path, cuts_json, fmt="edl"):
        """
        Exports the cut list as an edit decision list. Currently CMX3600 EDL
        (read by Premiere / Avid / Resolve). Source timecodes reflect the file's
        start timecode + cut position; uses the file's frame rate.
        """
        try:
            if not os.path.exists(file_path):
                return {"success": False, "error": "Datei nicht gefunden"}
            import json
            cuts = json.loads(cuts_json)
            if not cuts:
                return {"success": False, "error": "Keine Schnitte vorhanden"}

            meta = get_metadata(file_path)
            fps = meta.get("fps") or 25.0
            start_offset = meta.get("start_offset") or 0.0
            title = meta.get("clip_name") or os.path.basename(file_path)
            content = build_edl(title, cuts, fps=fps, start_offset=start_offset)

            name_without_ext, _ = os.path.splitext(os.path.basename(file_path))
            file_types = ('EDL (*.edl)', 'All files (*.*)')
            save_path = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=os.path.dirname(file_path),
                save_filename=f"{name_without_ext}.edl",
                file_types=file_types
            )
            if not save_path:
                return {"success": False, "error": "Dialog abgebrochen"}
            if isinstance(save_path, (list, tuple)):
                save_path = save_path[0] if save_path else None
                if not save_path:
                    return {"success": False, "error": "Dialog abgebrochen"}

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "filename": os.path.basename(save_path)}
        except Exception as e:
            import traceback
            print("Fehler beim EDL-Export:")
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def get_file_metadata(self, file_path):
        """
        Fetches metadata (duration, creation date, GPS info) for a single file.
        Called from the JS frontend.
        """
        if not os.path.exists(file_path):
            return {"error": "Datei existiert nicht"}
        try:
            return get_metadata(file_path)
        except Exception as e:
            return {"error": str(e)}

    def select_output_folder(self):
        """
        Opens a folder dialog to let the user select a custom output directory.
        """
        try:
            result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if result and len(result) > 0:
                return result[0] if isinstance(result, (list, tuple)) else result
            return ""
        except Exception as e:
            import sys
            print(f"Error in select_output_folder: {e}", file=sys.stderr)
            sys.stderr.flush()
            return ""

    def select_files(self):
        """
        Opens a native system file selector as a fallback/alternative to drag-and-drop.
        """
        try:
            import sys
            file_types = ('Supported Files (*.mp4;*.mov;*.mkv;*.mp3;*.wav;*.m4a;*.adler)', 'Transcription Adler Project (*.adler)', 'All files (*.*)')
            result = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=file_types)
            return result
        except Exception as e:
            import sys
            print(f"Error in select_files: {e}", file=sys.stderr)
            sys.stderr.flush()
            return []

    def get_transcript(self, file_path):
        """
        Returns the cached transcript segments for a file.
        """
        return self._transcripts.get(file_path, [])

    def open_project_file_dialog(self):
        """
        Opens a dialog filtered to .adler project files and returns the chosen path
        (or '' if cancelled). The frontend then loads it like a dropped .adler file.
        """
        try:
            file_types = ('Transcription Adler Projekt (*.adler)', 'All files (*.*)')
            result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
            if result and len(result) > 0:
                return result[0] if isinstance(result, (list, tuple)) else result
            return ""
        except Exception as e:
            import sys
            print(f"Error in open_project_file_dialog: {e}", file=sys.stderr)
            sys.stderr.flush()
            return ""

    def get_supported_languages(self):
        """
        Returns the full set of languages the app can use, so the user can enable
        additional ones in the settings:
          - recognition: all Whisper languages (offline, built into the model)
          - translation: all Google Translator target languages (online service)
        Each entry is {code, name}, sorted by name. No download required – these
        are already available; the UI just exposes them on demand.
        """
        result = {"recognition": [], "translation": []}
        try:
            from whisper.tokenizer import LANGUAGES as whisper_langs
            result["recognition"] = sorted(
                [{"code": code, "name": name.title()} for code, name in whisper_langs.items()],
                key=lambda x: x["name"]
            )
        except Exception as e:
            print(f"Fehler beim Laden der Erkennungssprachen: {e}")
        try:
            from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES as google_langs
            result["translation"] = sorted(
                [{"code": code, "name": name.title()} for name, code in google_langs.items()],
                key=lambda x: x["name"]
            )
        except Exception as e:
            print(f"Fehler beim Laden der Übersetzungssprachen: {e}")
        return result

    # ------------------------------------------------------------
    # Native VLC playback (MXF / professional codecs) in its own window
    # ------------------------------------------------------------
    def _ensure_vlc(self):
        """Lazily creates the libVLC instance/player; locates the VLC runtime."""
        if self._vlc_player is not None:
            return self._vlc_player

        candidates = []
        if getattr(sys, 'frozen', False):
            candidates.append(os.path.join(sys._MEIPASS, 'vlc'))
        candidates += [
            r"C:\Program Files\VideoLAN\VLC",
            r"C:\Program Files (x86)\VideoLAN\VLC",
        ]
        vlc_dir = next(
            (c for c in candidates if os.path.isdir(c) and os.path.exists(os.path.join(c, 'libvlc.dll'))),
            None
        )
        if vlc_dir:
            try:
                os.add_dll_directory(vlc_dir)
            except Exception:
                pass
            os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")
            # Diese explizit setzen, damit python-vlc die *gebündelte* libVLC nimmt
            # (und nicht eine evtl. system-installierte).
            os.environ["PYTHON_VLC_LIB_PATH"] = os.path.join(vlc_dir, "libvlc.dll")
            os.environ["VLC_PLUGIN_PATH"] = os.path.join(vlc_dir, "plugins")

        import vlc
        self._vlc_instance = vlc.Instance("--quiet", "--no-video-title-show")
        self._vlc_player = self._vlc_instance.media_player_new()
        return self._vlc_player

    def _ensure_video_window(self):
        """
        Creates a resizable native window (~1/4 of the screen) that VLC renders
        into. Returns its HWND, or None on failure (then VLC uses its own window).
        The window is created once and reused, so user resizing is preserved.
        """
        if self._video_hwnd:
            return self._video_hwnd
        if os.name != 'nt':
            return None
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL('user32', use_last_error=True)
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

            LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
            WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            class WNDCLASS(ctypes.Structure):
                _fields_ = [
                    ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR),
                ]

            user32.DefWindowProcW.restype = LRESULT
            user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.CreateWindowExW.restype = wintypes.HWND
            user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                               ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                               wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
            user32.RegisterClassW.restype = wintypes.ATOM
            user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
            user32.GetMessageW.restype = ctypes.c_int
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.DispatchMessageW.restype = LRESULT
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int
            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.LoadCursorW.restype = wintypes.HANDLE
            user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            gdi32.GetStockObject.restype = wintypes.HANDLE
            gdi32.GetStockObject.argtypes = [ctypes.c_int]

            # Für Embedding/Reparenting
            user32.SetParent.restype = wintypes.HWND
            user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
            user32.SetWindowLongW.restype = ctypes.c_long
            user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
            user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
            user32.FindWindowW.restype = wintypes.HWND
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]

            self._user32 = user32

            WS_OVERLAPPEDWINDOW = 0x00CF0000
            WS_VISIBLE = 0x10000000
            WM_CLOSE = 0x0010

            def py_wndproc(hwnd, msg, wparam, lparam):
                if msg == WM_CLOSE:
                    user32.ShowWindow(hwnd, 0)  # SW_HIDE statt zerstören
                    try:
                        if self._vlc_player is not None:
                            self._vlc_player.stop()
                    except Exception:
                        pass
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            self._video_wndproc = WNDPROC(py_wndproc)  # Referenz halten (GC!)

            hinst = kernel32.GetModuleHandleW(None)
            class_name = "TranscriptionAdlerVideoWindow"

            wc = WNDCLASS()
            wc.style = 0x0003  # CS_HREDRAW | CS_VREDRAW
            wc.lpfnWndProc = self._video_wndproc
            wc.hInstance = hinst
            wc.hCursor = user32.LoadCursorW(None, ctypes.c_wchar_p(32512))  # IDC_ARROW
            wc.hbrBackground = gdi32.GetStockObject(4)  # BLACK_BRUSH
            wc.lpszClassName = class_name
            user32.RegisterClassW(ctypes.byref(wc))

            sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            sh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            w = max(480, sw // 2)            # halbe Breite × halbe Höhe = 1/4 Fläche
            h = max(320, sh // 2)
            x = (sw - w) // 2
            y = (sh - h) // 2

            import threading
            created = threading.Event()

            def run():
                try:
                    hwnd = user32.CreateWindowExW(
                        0, class_name, "Transcription Adler – Video",
                        WS_OVERLAPPEDWINDOW | WS_VISIBLE,
                        x, y, w, h, None, None, hinst, None
                    )
                    self._video_hwnd = hwnd
                    created.set()
                    msg = wintypes.MSG()
                    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                except Exception as e:
                    print("Video-Fenster-Thread Fehler:", e)
                    created.set()

            self._video_thread = threading.Thread(target=run, daemon=True)
            self._video_thread.start()
            created.wait(2.0)
            return self._video_hwnd
        except Exception as e:
            print("Konnte Video-Fenster nicht erstellen:", e)
            return None

    def _show_video_window(self):
        """Ensures the owned video window is visible (e.g. after it was hidden)."""
        try:
            if self._video_hwnd and self._user32:
                self._user32.ShowWindow(self._video_hwnd, 5)  # SW_SHOW
        except Exception:
            pass

    def _set_video_mode(self, embedded, x=0, y=0, w=0, h=0):
        """
        Switches the (same) VLC video window between embedded (child of the main
        window, positioned over a reserved region) and detached (own resizable
        top-level window). VLC keeps rendering into the same HWND – no reload.
        """
        try:
            if not self._video_hwnd or not self._user32:
                return
            u = self._user32
            GWL_STYLE = -16
            WS_CHILD = 0x40000000
            WS_VISIBLE = 0x10000000
            WS_OVERLAPPEDWINDOW = 0x00CF0000
            SWP_FRAMECHANGED = 0x0020

            if embedded:
                if not self._main_hwnd:
                    self._main_hwnd = u.FindWindowW(None, "Transcription Adler")
                if not self._main_hwnd:
                    return  # Hauptfenster nicht gefunden -> abgekoppelt lassen
                u.SetWindowLongW(self._video_hwnd, GWL_STYLE, WS_CHILD | WS_VISIBLE)
                u.SetParent(self._video_hwnd, self._main_hwnd)
                u.SetWindowPos(self._video_hwnd, 0, int(x), int(y), max(1, int(w)), max(1, int(h)), SWP_FRAMECHANGED)
                u.ShowWindow(self._video_hwnd, 5)
            else:
                u.SetParent(self._video_hwnd, None)
                u.SetWindowLongW(self._video_hwnd, GWL_STYLE, WS_OVERLAPPEDWINDOW | WS_VISIBLE)
                sw = u.GetSystemMetrics(0)
                sh = u.GetSystemMetrics(1)
                ww = max(480, sw // 2)
                wh = max(320, sh // 2)
                u.SetWindowPos(self._video_hwnd, 0, (sw - ww) // 2, (sh - wh) // 2, ww, wh, SWP_FRAMECHANGED)
                u.ShowWindow(self._video_hwnd, 5)
        except Exception as e:
            print("Video-Modus setzen fehlgeschlagen:", e)

    def player_set_embedded(self, embedded, x=0, y=0, w=0, h=0):
        """Sets embedded/detached mode and positions the video accordingly."""
        self._embedded = bool(embedded)
        self._ensure_video_window()
        self._set_video_mode(self._embedded, x, y, w, h)
        return True

    def player_update_embed_rect(self, x, y, w, h):
        """While embedded, keeps the video aligned to the reserved HTML region."""
        try:
            if self._embedded and self._video_hwnd and self._user32:
                self._user32.MoveWindow(self._video_hwnd, int(x), int(y), max(1, int(w)), max(1, int(h)), True)
            return True
        except Exception:
            return False

    def player_open(self, file_path):
        """Loads a file into the native VLC player and starts playback (own window)."""
        try:
            if not os.path.exists(file_path):
                return {"success": False, "error": "Datei nicht gefunden"}
            player = self._ensure_vlc()

            # In unser eigenes, resizables Fenster rendern (sonst VLC-Auto-Fenster).
            hwnd = self._ensure_video_window()
            if hwnd:
                try:
                    player.set_hwnd(int(hwnd))
                    self._show_video_window()
                except Exception as e:
                    print("set_hwnd fehlgeschlagen, nutze VLC-Auto-Fenster:", e)

            self._current_media_path = file_path
            media = self._vlc_instance.media_new(file_path)
            player.set_media(media)
            player.play()
            return {"success": True}
        except Exception as e:
            print(f"VLC-Fehler beim Öffnen: {e}")
            return {"success": False, "error": str(e)}

    def _ensure_playable(self):
        """
        If playback has ended/stopped, reloads the media so play/seek work again
        (libVLC won't resume from the 'Ended' state without re-setting the media).
        Returns True if a reload was performed.
        """
        import vlc
        p = self._vlc_player
        if p is None:
            return False
        if p.get_state() in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
            if self._current_media_path:
                media = self._vlc_instance.media_new(self._current_media_path)
                p.set_media(media)
                p.play()
                return True
        return False

    def player_toggle_pause(self):
        """Toggles play/pause. Restarts from the beginning if playback had ended."""
        try:
            if self._ensure_playable():
                return True  # reloaded -> now playing from start
            self._vlc_player.pause()  # libVLC pause() toggles
            return bool(self._vlc_player.is_playing())
        except Exception:
            return False

    def player_set_time(self, seconds):
        """Seeks to an absolute position (seconds); reloads first if ended/stopped."""
        try:
            self._ensure_playable()
            self._vlc_player.set_time(int(float(seconds) * 1000))
            return True
        except Exception:
            return False

    def player_get_state(self):
        """Returns current time, total length (seconds) and playing flag for the UI."""
        try:
            p = self._vlc_player
            if p is None:
                return {"time": 0.0, "length": 0.0, "playing": False, "active": False}
            return {
                "time": max(p.get_time(), 0) / 1000.0,
                "length": max(p.get_length(), 0) / 1000.0,
                "playing": bool(p.is_playing()),
                "active": True
            }
        except Exception:
            return {"time": 0.0, "length": 0.0, "playing": False, "active": False}

    def player_stop(self):
        """Stops playback and hides the owned video window."""
        try:
            if self._vlc_player is not None:
                self._vlc_player.stop()
            if self._video_hwnd and self._user32:
                self._user32.ShowWindow(self._video_hwnd, 0)  # SW_HIDE
            return True
        except Exception:
            return False

    def cancel_transcription(self):
        """
        Requests cancellation of the currently running queue. Remaining files are
        skipped; the file being transcribed stops as soon as its current Whisper
        pass returns (the Whisper call itself cannot be interrupted mid-file).
        """
        self._cancel_event.set()
        return True

    def _emit_progress(self, file_path, percent, msg):
        """Pushes a progress update for a single file to the JS frontend."""
        safe_msg = str(msg).replace("\\", "\\\\").replace("'", "\\'")
        safe_file = file_path.replace("\\", "\\\\").replace("'", "\\'")
        self._window.evaluate_js(f"onFileProgress('{safe_file}', {percent}, '{safe_msg}')")

    def remove_from_queue(self, file_path):
        """Removes a still-pending file from the processing queue."""
        with self._queue_lock:
            self._queue = [p for p in self._queue if p != file_path]
        return True

    def cancel_file(self, file_path):
        """
        Cancels a single file: if it is the one currently being transcribed it is
        aborted after the current Whisper pass; if it is still pending it is removed
        from the queue so it won't be started.
        """
        if self._current_file == file_path:
            self._cancel_current.set()
        else:
            with self._queue_lock:
                self._queue = [p for p in self._queue if p != file_path]
        return True

    def prioritize_file(self, file_path):
        """Moves a pending file to the front of the queue so it is processed next."""
        with self._queue_lock:
            if file_path in self._queue:
                self._queue.remove(file_path)
                self._queue.insert(0, file_path)
        return True

    def requeue_file(self, file_path, source_lang, target_lang, model_size, output_dir_type="source", custom_path="", diarize=False, speaker_count="2", docx_trans_mode="both", timecode_modes=None, use_original_timecode=False):
        """
        Re-queues a single file (e.g. after it was cancelled or failed) using the
        current settings, and starts the worker if it isn't running.
        """
        self._cancel_event.clear()
        self._proc_params = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "model_size": model_size,
            "output_dir_type": output_dir_type,
            "custom_path": custom_path,
            "diarize": diarize,
            "speaker_count": speaker_count,
            "docx_trans_mode": docx_trans_mode,
            "timecode_modes": timecode_modes,
            "use_original_timecode": use_original_timecode,
        }
        with self._queue_lock:
            if file_path != self._current_file and file_path not in self._queue:
                self._queue.append(file_path)
        self._ensure_worker()
        return True

    def start_transcription(self, files, source_lang, target_lang, model_size, output_dir_type="source", custom_path="", diarize=False, speaker_count="2", docx_trans_mode="both", timecode_modes=None, use_original_timecode=False):
        """
        Queues the given files and starts (or continues) the background worker.
        """
        self._cancel_event.clear()
        self._proc_params = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "model_size": model_size,
            "output_dir_type": output_dir_type,
            "custom_path": custom_path,
            "diarize": diarize,
            "speaker_count": speaker_count,
            "docx_trans_mode": docx_trans_mode,
            "timecode_modes": timecode_modes,
            "use_original_timecode": use_original_timecode,
        }
        with self._queue_lock:
            # Replace the pending queue; never re-queue the file currently running.
            self._queue = [f for f in files if f != self._current_file]
        self._ensure_worker()
        return True

    def _ensure_worker(self):
        """Starts the background worker thread if it isn't already running."""
        with self._queue_lock:
            if self._worker_running:
                return
            self._worker_running = True
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def _worker_loop(self):
        """Consumes the shared queue until it is empty or globally cancelled."""
        while True:
            if self._cancel_event.is_set():
                with self._queue_lock:
                    remaining = self._queue[:]
                    self._queue = []
                    self._worker_running = False
                for p in remaining:
                    if os.path.exists(p):
                        self._emit_progress(p, -2, "Abgebrochen")
                return

            with self._queue_lock:
                if not self._queue:
                    # Mark not-running atomically with the empty check to avoid races.
                    self._worker_running = False
                    return
                file_path = self._queue.pop(0)
                self._current_file = file_path

            self._cancel_current.clear()
            self._process_one(file_path)
            self._current_file = None

    def _process_one(self, file_path):
        """Transcribes a single file and writes the report(s)."""
        if not os.path.exists(file_path):
            self._emit_progress(file_path, -1, "Fehler: Datei nicht gefunden")
            return

        p = self._proc_params
        file_name = os.path.basename(file_path)

        def report_progress(percent, msg):
            self._emit_progress(file_path, percent, msg)

        # Cancel when either the whole queue or just this file is cancelled.
        def should_cancel():
            return self._cancel_event.is_set() or self._cancel_current.is_set()

        try:
            report_progress(5, "Analysiere Datei-Metadaten...")
            meta = get_metadata(file_path)

            # Optional: Zeitstempel am Original-Timecode der Datei ausrichten.
            timecode_offset = meta.get("start_offset", 0.0) if p.get("use_original_timecode") else 0.0

            report_progress(10, "Lade Whisper-Modell...")
            result = transcribe_file(
                file_path,
                source_lang=p.get("source_lang"),
                target_lang=p.get("target_lang"),
                model_name=p.get("model_size", "base"),
                progress_callback=report_progress,
                diarize=p.get("diarize", False),
                speaker_count=p.get("speaker_count", "2"),
                cancel_check=should_cancel,
                timecode_offset=timecode_offset
            )

            self._transcripts[file_path] = result["segments"]

            report_progress(95, "Generiere Word-Bericht...")
            created = self._generate_reports(
                file_path, meta, result["segments"],
                p.get("output_dir_type", "source"), p.get("custom_path", ""),
                p.get("target_lang"), p.get("docx_trans_mode", "both"), p.get("timecode_modes")
            )

            if len(created) == 1:
                report_progress(100, f"Erstellt: {created[0]}")
            else:
                report_progress(100, f"{len(created)} Berichte erstellt")

        except TranscriptionCancelled:
            report_progress(-2, "Abgebrochen")
        except Exception as e:
            print(f"Fehler bei Verarbeitung von {file_name}: {e}")
            report_progress(-1, f"Fehler: {str(e)}")

    def save_project_file(self, video_path, segments_json, cuts_json):
        """
        Saves the transcription data, video file path and cut points into a .adler JSON project file.
        """
        try:
            base_name = os.path.basename(video_path)
            name_without_ext, _ = os.path.splitext(base_name)
            default_filename = f"{name_without_ext}.adler"
            
            file_types = ('Transcription Adler Project (*.adler)', 'All files (*.*)')
            save_path = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=os.path.dirname(video_path),
                save_filename=default_filename,
                file_types=file_types
            )
            if not save_path:
                return {"success": False, "error": "Dialog abgebrochen"}
            
            if isinstance(save_path, (list, tuple)):
                if len(save_path) > 0:
                    save_path = save_path[0]
                else:
                    return {"success": False, "error": "Dialog abgebrochen"}
            
            import json
            project_data = {
                "video_path": video_path,
                "segments": json.loads(segments_json),
                "cuts": json.loads(cuts_json)
            }
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
                
            return {"success": True, "filename": os.path.basename(save_path)}
        except Exception as e:
            import traceback
            print("Fehler in save_project_file:")
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def load_project_file(self, project_path):
        """
        Loads the .adler project file data and registers segments cache.
        """
        if not os.path.exists(project_path):
            return {"success": False, "error": "Projektdatei existiert nicht"}
        try:
            import json
            with open(project_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            video_path = project_data.get("video_path")
            video_exists = False
            if video_path and os.path.exists(video_path):
                video_exists = True
                
            # Pre-cache transcription segments so word report updates still work
            if video_exists and video_path:
                self._transcripts[video_path] = project_data.get("segments", [])
                
            return {
                "success": True,
                "project_path": project_path,
                "video_path": video_path,
                "video_exists": video_exists,
                "segments": project_data.get("segments", []),
                "cuts": project_data.get("cuts", [])
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def locate_video_file(self):
        """
        Opens dialog to let user re-link/locate a video file.
        """
        try:
            file_types = ('Video and Audio files (*.mp4;*.mov;*.mkv;*.mp3;*.wav;*.m4a)', 'All files (*.*)')
            result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
            if result and len(result) > 0:
                return result[0] if isinstance(result, (list, tuple)) else result
            return ""
        except Exception as e:
            return ""

    def cache_project_segments(self, video_path, segments_json):
        """
        Caches segments manually if the project video was relocated.
        """
        try:
            import json
            self._transcripts[video_path] = json.loads(segments_json)
            return True
        except Exception as e:
            return False

def setup_events(window, api):
    """
    Hooks window load events to bind the python-side DOM drag-and-drop listener.
    """
    api._window = window
    
    def on_loaded():
        print("DOM geladen. Binde native Drag & Drop Events...")
        try:
            def on_drop(e):
                files = e.get('dataTransfer', {}).get('files', [])
                for file in files:
                    path = file.get('pywebviewFullPath')
                    if path:
                        safe_path = path.replace("\\", "\\\\").replace("'", "\\'")
                        # Send absolute path to the Javascript queue
                        window.evaluate_js(f"addFileFromPython('{safe_path}')")
            
            # Bind to drop event
            window.dom.document.events.drop += DOMEventHandler(
                on_drop, 
                prevent_default=True, 
                stop_propagation=True
            )
            print("Drag-and-Drop erfolgreich gebunden.")
        except Exception as err:
            print(f"Fehler bei Drag-and-Drop Binding: {err}")
            
    window.events.loaded += on_loaded

def main():
    api = Api()
    
    # Set custom macOS Dock icon
    set_dock_icon()
    
    # Resolve the index.html path relative to main.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, 'index.html')
    
    # Allow loading local file:// URLs in WebView
    webview.settings['ALLOW_FILE_URLS'] = True
    
    window = webview.create_window(
        title='Transcription Adler',
        url=html_path,
        js_api=api,
        width=1200,
        height=850,
        min_size=(900, 600),
        background_color='#111111' # Matches the dark settings background
    )
    
    webview.start(setup_events, (window, api))

if __name__ == '__main__':
    main()
