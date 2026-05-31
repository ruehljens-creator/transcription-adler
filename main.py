import sys
import os

# If running as a bundled executable, add the bundle folder to PATH
# so that the application and libraries (like Whisper) can locate bundled ffmpeg/ffprobe.
if getattr(sys, 'frozen', False):
    os.environ["PATH"] = sys._MEIPASS + os.pathsep + os.environ.get("PATH", "")

import webview
import threading
from webview.dom import DOMEventHandler
from metadata import get_metadata
from transcribe import transcribe_file
from docx_generator import create_docx
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
        
        # Start secure local HTTP server for media files
        self._server_token = secrets.token_hex(16)
        self._server_port = self._find_free_port()
        self._start_media_server()

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

    @staticmethod
    def _resolve_output_docx(file_path, output_dir_type, custom_path):
        """
        Determines where the generated .docx report should be written, based on
        the user's output preference (desktop / custom folder / next to source).
        """
        name_without_ext, _ = os.path.splitext(os.path.basename(file_path))
        output_name = f"{name_without_ext}_transkript.docx"

        if output_dir_type == "desktop":
            return os.path.join(os.path.expanduser("~"), "Desktop", output_name)
        if output_dir_type == "custom" and custom_path and os.path.isdir(custom_path):
            return os.path.join(custom_path, output_name)
        # Default: alongside the source file
        base_path, _ = os.path.splitext(file_path)
        return f"{base_path}_transkript.docx"

    def update_docx_with_cuts(self, file_path, cuts_json, output_dir_type="source", custom_path="", target_lang=None, docx_trans_mode="both"):
        """
        Re-generates the Word Document, highlighting the list of cuts in the segments table.
        Called from the JS frontend when the user clicks "Bericht aktualisieren".
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

            output_docx = self._resolve_output_docx(file_path, output_dir_type, custom_path)

            create_docx(
                output_docx, 
                meta, 
                segments, 
                target_lang=target_lang, 
                cuts=cuts_list,
                docx_trans_mode=docx_trans_mode
            )
            
            return {
                "success": True, 
                "path": output_docx, 
                "filename": os.path.basename(output_docx)
            }
        except Exception as e:
            print(f"Fehler bei Aktualisierung des Berichts: {e}")
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

    def start_transcription(self, files, source_lang, target_lang, model_size, output_dir_type="source", custom_path="", diarize=False, speaker_count="2", docx_trans_mode="both"):
        """
        Starts processing the dropped files queue in a background thread to prevent UI lockup.
        """
        threading.Thread(
            target=self._process_queue, 
            args=(files, source_lang, target_lang, model_size, output_dir_type, custom_path, diarize, speaker_count, docx_trans_mode), 
            daemon=True
        ).start()
        return True

    def _process_queue(self, files, source_lang, target_lang, model_size, output_dir_type="source", custom_path="", diarize=False, speaker_count="2", docx_trans_mode="both"):
        """
        Processes files in the background: transcribes, translates, and writes word documents.
        """
        for file_path in files:
            if not os.path.exists(file_path):
                continue
            
            file_name = os.path.basename(file_path)
            
            def report_progress(percent, msg):
                safe_msg = msg.replace("'", "\\'")
                safe_file = file_path.replace("\\", "\\\\").replace("'", "\\'")
                js_code = f"onFileProgress('{safe_file}', {percent}, '{safe_msg}')"
                self._window.evaluate_js(js_code)

            try:
                # 1. Fetch metadata
                report_progress(5, "Analysiere Datei-Metadaten...")
                meta = get_metadata(file_path)
                
                # 2. Run Whisper Transcription
                report_progress(10, "Lade Whisper-Modell...")
                result = transcribe_file(
                    file_path, 
                    source_lang=source_lang, 
                    target_lang=target_lang, 
                    model_name=model_size,
                    progress_callback=report_progress,
                    diarize=diarize,
                    speaker_count=speaker_count
                )
                
                # Cache the segments for the frontend player
                self._transcripts[file_path] = result["segments"]
                
                # 3. Create .docx file in chosen output directory
                report_progress(95, "Generiere Word-Bericht...")

                output_docx = self._resolve_output_docx(file_path, output_dir_type, custom_path)

                create_docx(output_docx, meta, result["segments"], target_lang=target_lang, docx_trans_mode=docx_trans_mode)
                
                report_name = os.path.basename(output_docx)
                report_progress(100, f"Erstellt: {report_name}")
                
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
                file_name=default_filename, 
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
