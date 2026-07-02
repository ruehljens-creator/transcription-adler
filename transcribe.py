import whisper
import os
import numpy as np
from deep_translator import GoogleTranslator


class TranscriptionCancelled(Exception):
    """Raised inside transcribe_file when the user requested cancellation."""
    pass


# Globally cache the loaded whisper models to avoid reloading them every time
_model_cache = {}

def get_whisper_model(model_name="base"):
    """
    Loads and caches the Whisper model on CPU or MPS (Metal Performance Shaders on Apple Silicon).
    Supports loading bundled model files directly from the frozen executable resources.
    """
    if model_name not in _model_cache:
        import torch
        # Prefer CUDA (NVIDIA), then MPS (Apple Silicon), otherwise CPU.
        if torch.cuda.is_available():
            device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
        
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

# Cache the Resemblyzer voice encoder (pretrained d-vector model) so it is
# loaded only once per process.
_voice_encoder = None

def get_voice_encoder():
    """
    Lazily loads and caches the Resemblyzer VoiceEncoder. It produces a
    256-dim, L2-normalised speaker embedding (d-vector) per utterance and runs
    fully offline on CPU (or CUDA if available). The pretrained weights ship
    inside the resemblyzer package – no runtime download.
    """
    global _voice_encoder
    if _voice_encoder is None:
        import torch
        from resemblyzer import VoiceEncoder
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _voice_encoder = VoiceEncoder(device=device, verbose=False)
    return _voice_encoder

def _assign_missing_speakers(raw_segments, speaker_labels, valid_indices):
    """
    Segments too short for a stable embedding get no label from clustering.
    Assign each of them the speaker of the temporally nearest embedded segment
    so the transcript has no gaps.
    """
    if not valid_indices:
        return
    valid_sorted = sorted(valid_indices)
    for idx in range(len(raw_segments)):
        if idx in speaker_labels:
            continue
        nearest = min(valid_sorted, key=lambda v: abs(v - idx))
        speaker_labels[idx] = speaker_labels.get(nearest, "Sprecher A")

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

def transcribe_file(file_path, source_lang=None, target_lang=None, model_name="base", progress_callback=None, diarize=False, speaker_count="2", cancel_check=None, timecode_offset=0.0):
    """
    Transcribes the audio/video file.
    If target_lang is specified, it will translate the transcription.

    progress_callback: a function that accepts (percent, status_text)
    cancel_check: optional callable returning True when the user requested
                  cancellation. It is polled between the (uninterruptible)
                  Whisper pass and the post-processing steps; when it returns
                  True a TranscriptionCancelled exception is raised.
    """
    def _check_cancel():
        if cancel_check and cancel_check():
            raise TranscriptionCancelled()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")

    _check_cancel()

    if progress_callback:
        progress_callback(10, "Lade Whisper-Modell...")

    model = get_whisper_model(model_name)
    _check_cancel()
    
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

    # fp16 only pays off on CUDA; on CPU it is unsupported (and Whisper warns).
    import torch
    kwargs["fp16"] = torch.cuda.is_available()

    # Run Whisper transcription (this call cannot be interrupted mid-file)
    result = model.transcribe(file_path, **kwargs)
    _check_cancel()

    raw_segments = result.get("segments", [])
    detected_lang = result.get("language", "unknown")
    
    # 2.5 Optional Speaker Diarization
    _check_cancel()
    speaker_labels = None
    if diarize and len(raw_segments) > 0:
        if progress_callback:
            progress_callback(72, "Führe Sprechererkennung (Diarisierung) aus...")
        try:
            audio = whisper.load_audio(file_path)   # 16 kHz mono float32
            encoder = get_voice_encoder()

            # Einen echten Sprecher-Embedding-Vektor (d-vector) pro Segment
            # berechnen. Zu kurze Segmente liefern kein stabiles Embedding und
            # werden anschließend dem nächstgelegenen Sprecher zugeordnet.
            embeddings = []
            valid_indices = []
            min_samples = int(0.4 * 16000)   # < 0.4 s: zu kurz zum Einbetten
            for idx, seg in enumerate(raw_segments):
                start_sample = max(0, int(seg["start"] * 16000))
                end_sample = int(seg["end"] * 16000)
                seg_audio = audio[start_sample:end_sample]
                if len(seg_audio) < min_samples:
                    continue
                try:
                    emb = encoder.embed_utterance(seg_audio)
                except Exception:
                    continue
                embeddings.append(emb)
                valid_indices.append(idx)

            if len(embeddings) > 1:
                embeddings = np.array(embeddings)

                # Sprecheranzahl bestimmen. Die d-Vektoren sind bereits
                # L2-normiert, daher direkt (ohne erneute Skalierung) clustern.
                if speaker_count == "auto":
                    best_k = 1
                    best_score = -1.0
                    max_k = min(len(embeddings), 6)
                    for k_cand in range(2, max_k + 1):
                        labels, _ = kmeans(embeddings, k_cand)
                        score = silhouette_score(embeddings, labels)
                        if score > best_score:
                            best_score = score
                            best_k = k_cand
                    # Nur mehrere Sprecher annehmen, wenn die Trennung überzeugt.
                    num_speakers = best_k if best_score >= 0.10 else 1
                else:
                    num_speakers = min(int(speaker_count), len(embeddings))

                if num_speakers > 1:
                    labels, _ = kmeans(embeddings, num_speakers)
                    speaker_names = ["Sprecher A", "Sprecher B", "Sprecher C",
                                     "Sprecher D", "Sprecher E", "Sprecher F"]
                    speaker_labels = {}
                    for val_idx, label in zip(valid_indices, labels):
                        speaker_labels[val_idx] = speaker_names[label % len(speaker_names)]
                    # Kurze, nicht eingebettete Segmente nachtragen.
                    _assign_missing_speakers(raw_segments, speaker_labels, valid_indices)
                else:
                    speaker_labels = {idx: "Sprecher A" for idx in range(len(raw_segments))}
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
    
    # Translate all segments up front in a single batched request. This replaces
    # one network round-trip per segment with one call for the whole file, which
    # is dramatically faster on long recordings.
    translations = {}
    if translate_needed:
        if progress_callback:
            progress_callback(80, f"Übersetze Text in Zielsprache '{target_lang}'...")
        try:
            translator = GoogleTranslator(source='auto', target=target_lang)
            pairs = [(i, seg["text"].strip()) for i, seg in enumerate(raw_segments) if seg["text"].strip()]
            if pairs:
                indices = [i for i, _ in pairs]
                originals = [t for _, t in pairs]
                try:
                    results = translator.translate_batch(originals)
                    translations = {i: (t or orig) for i, t, orig in zip(indices, results, originals)}
                except Exception as batch_err:
                    print(f"Batch-Übersetzung fehlgeschlagen, Einzelübersetzung als Fallback: {batch_err}")
                    for i, text in pairs:
                        try:
                            translations[i] = translator.translate(text) or text
                        except Exception as seg_err:
                            print(f"Übersetzungsfehler in Segment {i}: {seg_err}")
                            translations[i] = text
        except Exception as e:
            print(f"Fehler beim Initialisieren von GoogleTranslator: {e}")

    for i, seg in enumerate(raw_segments):
        if i % 50 == 0:
            _check_cancel()
        start = seg["start"]
        end = seg["end"]
        original_text = seg["text"].strip()

        # Get speaker label
        speaker = speaker_labels.get(i, "") if speaker_labels else ""

        translated_text = translations.get(i, "")

        # Numeric start/end stay 0-based (used for player seeking/sync/cuts);
        # only the displayed strings get the optional timecode offset applied.
        processed_segments.append({
            "start": start,
            "end": end,
            "start_str": format_timestamp(start + timecode_offset),
            "end_str": format_timestamp(end + timecode_offset),
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
