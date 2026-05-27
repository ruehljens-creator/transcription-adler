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
        self.window = None

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

    def select_files(self):
        """
        Opens a native system file selector as a fallback/alternative to drag-and-drop.
        """
        file_types = ('Video and Audio files (*.mp4;*.mov;*.mkv;*.mp3;*.wav;*.m4a)', 'All files (*.*)')
        result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=(file_types,))
        return result

    def start_transcription(self, files, source_lang, target_lang, model_size):
        """
        Starts processing the dropped files queue in a background thread to prevent UI lockup.
        """
        threading.Thread(
            target=self._process_queue, 
            args=(files, source_lang, target_lang, model_size), 
            daemon=True
        ).start()
        return True

    def _process_queue(self, files, source_lang, target_lang, model_size):
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
                self.window.evaluate_js(js_code)

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
                    progress_callback=report_progress
                )
                
                # 3. Create .docx file in same directory as source file
                report_progress(95, "Generiere Word-Bericht...")
                base_path, _ = os.path.splitext(file_path)
                output_docx = f"{base_path}_transkript.docx"
                
                create_docx(output_docx, meta, result["segments"], target_lang=target_lang)
                
                report_name = os.path.basename(output_docx)
                report_progress(100, f"Erstellt: {report_name}")
                
            except Exception as e:
                print(f"Fehler bei Verarbeitung von {file_name}: {e}")
                report_progress(-1, f"Fehler: {str(e)}")

def setup_events(window, api):
    """
    Hooks window load events to bind the python-side DOM drag-and-drop listener.
    """
    api.window = window
    
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
    
    window = webview.create_window(
        title='Transcription Adler',
        url=html_path,
        js_api=api,
        width=1020,
        height=720,
        min_size=(900, 600),
        background_color='#0f172a' # Matches dashboard dark slate background
    )
    
    webview.start(setup_events, (window, api))

if __name__ == '__main__':
    main()
