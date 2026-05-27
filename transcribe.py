import whisper
import os
from deep_translator import GoogleTranslator

# Globally cache the loaded whisper models to avoid reloading them every time
_model_cache = {}

def get_whisper_model(model_name="base"):
    """
    Loads and caches the Whisper model on CPU or MPS (Metal Performance Shaders on Apple Silicon).
    Supports loading bundled model files directly from the frozen executable resources.
    """
    if model_name not in _model_cache:
        import torch
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        
        # Check if the model weights are bundled in the PyInstaller executable
        model_path = model_name
        import sys
        if getattr(sys, 'frozen', False):
            bundle_dir = sys._MEIPASS
            local_model_file = f"{model_name}.pt"
            bundled_path = os.path.join(bundle_dir, local_model_file)
            if os.path.exists(bundled_path):
                model_path = bundled_path
                print(f"Nutze gebündelte Modelldatei: {bundled_path}")
        
        print(f"Lade Whisper-Modell '{model_name}' auf Device '{device}'...")
        try:
            _model_cache[model_name] = whisper.load_model(model_path, device=device)
        except Exception as e:
            print(f"WARNUNG: Laden auf {device} fehlgeschlagen: {e}. Verwende CPU-Fallback.")
            try:
                _model_cache[model_name] = whisper.load_model(model_path, device="cpu")
            except Exception as err2:
                # If path failed, try default name download fallback
                print(f"Fehler beim Laden von Pfad {model_path}. Versuche Online-Download Fallback: {err2}")
                _model_cache[model_name] = whisper.load_model(model_name, device="cpu")
    return _model_cache[model_name]

def format_timestamp(seconds):
    """
    Formats seconds (float) into HH:MM:SS format.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def transcribe_file(file_path, source_lang=None, target_lang=None, model_name="base", progress_callback=None):
    """
    Transcribes the audio/video file.
    If target_lang is specified, it will translate the transcription.
    
    progress_callback: a function that accepts (percent, status_text)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")

    if progress_callback:
        progress_callback(10, "Lade Whisper-Modell...")
        
    model = get_whisper_model(model_name)
    
    if progress_callback:
        progress_callback(30, f"Transkribiere Datei ({os.path.basename(file_path)})...")
        
    # Configure transcription options
    kwargs = {}
    if source_lang and source_lang != "auto":
        kwargs["language"] = source_lang
        
    # Whisper native translation only supports translating TO English.
    # If the user explicitly wants English as target language, we use Whisper's native translation.
    use_native_translation = (target_lang == "en")
    if use_native_translation:
        kwargs["task"] = "translate"
        
    # Run Whisper transcription
    result = model.transcribe(file_path, **kwargs)
    
    raw_segments = result.get("segments", [])
    detected_lang = result.get("language", "unknown")
    
    if progress_callback:
        progress_callback(70, f"Transkription fertig (Sprache: {detected_lang}). Verarbeite Segmente...")
        
    processed_segments = []
    
    # Check if translation is needed and it's not Whisper's native translation to English
    translate_needed = target_lang and target_lang != detected_lang and not use_native_translation
    
    translator = None
    if translate_needed:
        if progress_callback:
            progress_callback(80, f"Übersetze Text in Zielsprache '{target_lang}'...")
        try:
            translator = GoogleTranslator(source='auto', target=target_lang)
        except Exception as e:
            print(f"Fehler beim Initialisieren von GoogleTranslator: {e}")
            
    total_segments = len(raw_segments)
    for i, seg in enumerate(raw_segments):
        start = seg["start"]
        end = seg["end"]
        original_text = seg["text"].strip()
        
        translated_text = ""
        if translate_needed and translator and original_text:
            try:
                translated_text = translator.translate(original_text)
            except Exception as e:
                print(f"Übersetzungsfehler in Segment {i}: {e}")
                translated_text = original_text # Fallback to original text
                
        processed_segments.append({
            "start": start,
            "end": end,
            "start_str": format_timestamp(start),
            "end_str": format_timestamp(end),
            "original": original_text,
            "translated": translated_text
        })
        
        if progress_callback and total_segments > 0:
            percent = 70 + int((i / total_segments) * 20)
            progress_callback(percent, f"Verarbeite Segmente: {i + 1}/{total_segments}...")
            
    if progress_callback:
        progress_callback(100, "Transkription & Übersetzung abgeschlossen!")
        
    return {
        "detected_language": detected_lang,
        "segments": processed_segments
    }
