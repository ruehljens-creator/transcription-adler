import whisper
import os
import numpy as np
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

def extract_speaker_features(audio_segment, sample_rate=16000):
    if len(audio_segment) < 200:
        return np.zeros(20)
    
    frame_length = int(0.025 * sample_rate)
    hop_length = int(0.010 * sample_rate)
    
    frames = []
    for i in range(0, len(audio_segment) - frame_length, hop_length):
        frames.append(audio_segment[i:i+frame_length])
        
    if not frames:
        return np.zeros(20)
        
    frames = np.array(frames)
    window = np.hamming(frame_length)
    windowed_frames = frames * window
    
    fft_size = 512
    spectrogram = np.abs(np.fft.rfft(windowed_frames, n=fft_size, axis=1))
    
    num_bands = 20
    band_size = spectrogram.shape[1] // num_bands
    features = []
    for i in range(num_bands):
        band_energy = np.mean(spectrogram[:, i*band_size:(i+1)*band_size], axis=1)
        features.append(np.log(np.mean(band_energy) + 1e-6))
        
    return np.array(features)

def kmeans(data, k, max_iters=100):
    np.random.seed(42)
    idx = np.random.choice(data.shape[0], k, replace=False)
    centroids = data[idx]
    
    for _ in range(max_iters):
        distances = np.linalg.norm(data[:, np.newaxis] - centroids, axis=2)
        labels = np.argmin(distances, axis=1)
        new_centroids = []
        for i in range(k):
            members = data[labels == i]
            if len(members) > 0:
                new_centroids.append(members.mean(axis=0))
            else:
                new_centroids.append(centroids[i])
        new_centroids = np.array(new_centroids)
        
        if np.allclose(centroids, new_centroids):
            break
        centroids = new_centroids
        
    return labels, centroids

def silhouette_score(data, labels):
    n = len(data)
    if n < 3:
        return 0.0
    
    scores = []
    for i in range(n):
        same_cluster = data[labels == labels[i]]
        if len(same_cluster) > 1:
            a = np.mean(np.linalg.norm(same_cluster - data[i], axis=1))
        else:
            a = 0.0
            
        b = float('inf')
        for label in set(labels):
            if label == labels[i]:
                continue
            other_cluster = data[labels == label]
            dist = np.mean(np.linalg.norm(other_cluster - data[i], axis=1))
            if dist < b:
                b = dist
                
        if max(a, b) > 0:
            scores.append((b - a) / max(a, b))
        else:
            scores.append(0.0)
            
    return np.mean(scores)

def format_timestamp(seconds):
    """
    Formats seconds (float) into HH:MM:SS format.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def transcribe_file(file_path, source_lang=None, target_lang=None, model_name="base", progress_callback=None, diarize=False, speaker_count="2"):
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
    
    # 2.5 Optional Speaker Diarization
    speaker_labels = None
    if diarize and len(raw_segments) > 0:
        if progress_callback:
            progress_callback(72, "Führe Sprechererkennung (Diarisierung) aus...")
        try:
            audio = whisper.load_audio(file_path)
            features = []
            valid_indices = []
            
            for idx, seg in enumerate(raw_segments):
                start_sample = int(seg["start"] * 16000)
                end_sample = int(seg["end"] * 16000)
                seg_audio = audio[start_sample:end_sample]
                feat = extract_speaker_features(seg_audio)
                if feat is not None:
                    features.append(feat)
                    valid_indices.append(idx)
            
            if len(features) > 1:
                features = np.array(features)
                # Normalize features
                mean = features.mean(axis=0)
                std = features.std(axis=0) + 1e-6
                features = (features - mean) / std
                
                # Determine number of speakers
                if speaker_count == "auto":
                    best_k = 2
                    best_score = -1
                    max_k = min(len(features), 4)
                    for k_cand in range(2, max_k + 1):
                        labels, _ = kmeans(features, k_cand)
                        score = silhouette_score(features, labels)
                        if score > best_score:
                            best_score = score
                            best_k = k_cand
                    num_speakers = best_k
                else:
                    num_speakers = min(int(speaker_count), len(features))
                
                if num_speakers > 1:
                    labels, _ = kmeans(features, num_speakers)
                    speaker_labels = {}
                    speaker_names = ["Sprecher A", "Sprecher B", "Sprecher C", "Sprecher D"]
                    for val_idx, label in zip(valid_indices, labels):
                        speaker_labels[val_idx] = speaker_names[label % len(speaker_names)]
                else:
                    speaker_labels = {idx: "Sprecher A" for idx in valid_indices}
            else:
                speaker_labels = {idx: "Sprecher A" for idx in range(len(raw_segments))}
        except Exception as e:
            print(f"Fehler bei der Sprechererkennung: {e}")
            
    if progress_callback:
        progress_callback(75, f"Transkription fertig (Sprache: {detected_lang}). Verarbeite Segmente...")
        
    total_segments = len(raw_segments)
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
            
    for i, seg in enumerate(raw_segments):
        start = seg["start"]
        end = seg["end"]
        original_text = seg["text"].strip()
        
        # Get speaker label
        speaker = speaker_labels.get(i, "") if speaker_labels else ""
        
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
            "translated": translated_text,
            "speaker": speaker
        })
        
        if progress_callback and total_segments > 0:
            percent = 75 + int((i / total_segments) * 20)
            progress_callback(percent, f"Verarbeite Segmente: {i + 1}/{total_segments}...")
            
    if progress_callback:
        progress_callback(100, "Transkription & Übersetzung abgeschlossen!")
        
    return {
        "detected_language": detected_lang,
        "segments": processed_segments
    }
