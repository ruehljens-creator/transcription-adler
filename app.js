// ============================================================
// Transcription Adler – Frontend-Logik (barrierefrei)
// ============================================================

// State
let fileQueue = [];
let isProcessing = false;

// DOM
const sourceLangSelect = document.getElementById('source-lang');
const translateEnableCheckbox = document.getElementById('translate-enable');
const targetLangWrapper = document.getElementById('target-lang-wrapper');
const targetLangSelect = document.getElementById('target-lang');
const modelSizeSelect = document.getElementById('model-size');
const startBtn = document.getElementById('start-btn');
const clearBtn = document.getElementById('clear-btn');
const browseBtn = document.getElementById('browse-btn');
const dropZone = document.getElementById('drop-zone');
const queueTbody = document.getElementById('queue-tbody');
const queueCountBadge = document.getElementById('queue-count');
const srAnnouncer = document.getElementById('sr-announcer');

// ------------------------------------------------------------
// Screenreader-Ankündigung
// ------------------------------------------------------------
function announce(message) {
    if (!srAnnouncer) return;
    // Reset für wiederholte gleiche Meldungen
    srAnnouncer.textContent = '';
    setTimeout(() => {
        srAnnouncer.textContent = message;
    }, 50);
}

// ------------------------------------------------------------
// Übersetzungs-Toggle
// ------------------------------------------------------------
translateEnableCheckbox.addEventListener('change', () => {
    if (translateEnableCheckbox.checked) {
        targetLangWrapper.classList.remove('disabled');
        targetLangSelect.removeAttribute('disabled');
        announce('Übersetzung aktiviert. Zielsprache kann ausgewählt werden.');
    } else {
        targetLangWrapper.classList.add('disabled');
        targetLangSelect.setAttribute('disabled', 'true');
        announce('Übersetzung deaktiviert.');
    }
});

// ------------------------------------------------------------
// Drag & Drop – nur visuelle Cues, Drop-Event übernimmt Python
// ------------------------------------------------------------
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
});

// ------------------------------------------------------------
// Dateien-Dialog (Tastatur-Alternative zu Drag & Drop)
// ------------------------------------------------------------
browseBtn.addEventListener('click', () => {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_files().then(paths => {
            if (paths && paths.length > 0) {
                paths.forEach(path => addFileToQueue(path));
                announce(`${paths.length} Datei${paths.length === 1 ? '' : 'en'} hinzugefügt.`);
            }
        });
    }
});

// ------------------------------------------------------------
// Liste leeren
// ------------------------------------------------------------
clearBtn.addEventListener('click', () => {
    if (isProcessing) return;
    fileQueue = [];
    renderQueue();
    updateStartButtonState();
    announce('Warteschlange geleert.');
});

// ------------------------------------------------------------
// Eintrag aus Python (Drop-Event)
// ------------------------------------------------------------
window.addFileFromPython = function (filePath) {
    addFileToQueue(filePath);
    const file = fileQueue[fileQueue.length - 1];
    if (file) announce(`${file.name} hinzugefügt.`);
};

// ------------------------------------------------------------
// Datei zur Queue hinzufügen
// ------------------------------------------------------------
function addFileToQueue(filePath) {
    if (fileQueue.some(file => file.path === filePath)) return;

    const filename = filePath.split('/').pop().split('\\').pop();
    const newFile = {
        path: filePath,
        name: filename,
        duration: 'Wird geladen…',
        creationDate: 'Wird geladen…',
        location: 'Wird geladen…',
        mapsLink: null,
        status: 'queued',
        progress: 0,
        statusMsg: 'Wartet'
    };

    fileQueue.push(newFile);
    renderQueue();
    updateStartButtonState();

    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_file_metadata(filePath).then(meta => {
            updateFileMetadata(filePath, meta);
        }).catch(err => {
            console.error('Fehler beim Laden der Metadaten:', err);
            updateFileMetadata(filePath, { error: true });
        });
    }
}

// ------------------------------------------------------------
// Metadaten aktualisieren
// ------------------------------------------------------------
function updateFileMetadata(filePath, meta) {
    const file = fileQueue.find(f => f.path === filePath);
    if (!file) return;

    if (meta.error) {
        file.duration = 'Unbekannt';
        file.creationDate = 'Unbekannt';
        file.location = 'Nicht verfügbar';
    } else {
        file.duration = meta.duration_str || 'Unbekannt';
        file.creationDate = meta.creation_date || 'Unbekannt';
        if (meta.gps && meta.gps.address) {
            file.location = meta.gps.address;
            file.mapsLink = meta.maps_link;
        } else {
            file.location = 'Keine GPS-Daten';
        }
    }
    renderQueue();
}

// ------------------------------------------------------------
// Queue rendern
// ------------------------------------------------------------
function renderQueue() {
    const count = fileQueue.length;
    queueCountBadge.textContent = `${count} ${count === 1 ? 'Datei' : 'Dateien'}`;

    queueTbody.innerHTML = '';

    if (count === 0) {
        clearBtn.hidden = true;
        const tr = document.createElement('tr');
        tr.id = 'empty-state';
        tr.innerHTML = `
            <td colspan="5" class="empty-text">
                Keine Dateien in der Warteschlange. Dateien zum oberen Bereich hinzufügen, um zu beginnen.
            </td>
        `;
        queueTbody.appendChild(tr);
        return;
    }

    clearBtn.hidden = isProcessing;

    fileQueue.forEach(file => {
        const tr = document.createElement('tr');

        // Dateiname
        const tdName = document.createElement('td');
        tdName.className = 'filename-cell';
        tdName.textContent = file.name;
        tdName.setAttribute('aria-label', `Dateiname: ${file.name}. Pfad: ${file.path}`);
        tr.appendChild(tdName);

        // Dauer
        const tdDuration = document.createElement('td');
        tdDuration.textContent = file.duration;
        tr.appendChild(tdDuration);

        // Datum
        const tdDate = document.createElement('td');
        tdDate.textContent = file.creationDate;
        tr.appendChild(tdDate);

        // Ort
        const tdLoc = document.createElement('td');
        if (file.mapsLink) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'location-link';
            btn.textContent = file.location;
            btn.setAttribute('aria-label', `Karte öffnen für: ${file.location}`);
            btn.addEventListener('click', () => {
                if (window.pywebview && window.pywebview.api && file.mapsLink) {
                    // Über Python-API in externem Browser öffnen
                    window.open(file.mapsLink, '_blank');
                }
            });
            tdLoc.appendChild(btn);
        } else {
            tdLoc.textContent = file.location;
        }
        tr.appendChild(tdLoc);

        // Status
        const tdStatus = document.createElement('td');
        const badge = document.createElement('div');
        badge.className = `status-badge ${file.status}`;

        let statusText = '';
        if (file.status === 'queued') statusText = 'Wartet';
        else if (file.status === 'processing') statusText = `${file.progress}%`;
        else if (file.status === 'completed') statusText = 'Fertig';
        else if (file.status === 'failed') statusText = 'Fehler';

        badge.textContent = statusText;
        tdStatus.appendChild(badge);

        if (file.status === 'processing') {
            const barContainer = document.createElement('div');
            barContainer.className = 'progress-bar-container';
            barContainer.setAttribute('role', 'progressbar');
            barContainer.setAttribute('aria-valuemin', '0');
            barContainer.setAttribute('aria-valuemax', '100');
            barContainer.setAttribute('aria-valuenow', file.progress);
            barContainer.setAttribute('aria-label', `Fortschritt für ${file.name}`);
            const fill = document.createElement('div');
            fill.className = 'progress-bar-fill';
            fill.style.width = `${file.progress}%`;
            barContainer.appendChild(fill);
            tdStatus.appendChild(barContainer);
        }

        if (file.statusMsg && file.status !== 'queued') {
            const msgLabel = document.createElement('div');
            msgLabel.className = 'status-msg';
            msgLabel.textContent = file.statusMsg;
            tdStatus.appendChild(msgLabel);
        }

        tr.appendChild(tdStatus);
        queueTbody.appendChild(tr);
    });
}

// ------------------------------------------------------------
// Start-Button-Zustand
// ------------------------------------------------------------
function updateStartButtonState() {
    const hasFiles = fileQueue.length > 0;
    if (hasFiles && !isProcessing) {
        startBtn.removeAttribute('disabled');
    } else {
        startBtn.setAttribute('disabled', 'true');
    }
}

// ------------------------------------------------------------
// Transkription starten
// ------------------------------------------------------------
startBtn.addEventListener('click', () => {
    if (isProcessing || fileQueue.length === 0) return;

    const sourceLang = sourceLangSelect.value;
    const targetLang = translateEnableCheckbox.checked ? targetLangSelect.value : null;
    const modelSize = modelSizeSelect.value;

    isProcessing = true;
    updateStartButtonState();
    clearBtn.hidden = true;

    fileQueue.forEach(f => {
        if (f.status !== 'completed') {
            f.status = 'processing';
            f.progress = 0;
            f.statusMsg = 'Wird initialisiert…';
        }
    });
    renderQueue();
    announce(`Transkription gestartet für ${fileQueue.length} Datei${fileQueue.length === 1 ? '' : 'en'}.`);

    const paths = fileQueue.map(f => f.path);
    if (window.pywebview && window.pywebview.api) {
        const outputDirType = document.getElementById('output-dir-type').value;
    const customPath = customOutputPath;
    const diarize = document.getElementById('diarization-enable').checked;
    const speakerCount = document.getElementById('speaker-count').value;
    window.pywebview.api.start_transcription(paths, sourceLang, targetLang, modelSize, outputDirType, customPath, diarize, speakerCount);
    }
});

// ------------------------------------------------------------
// Fortschritts-Callback aus Python
// ------------------------------------------------------------
window.onFileProgress = function (filePath, percent, statusMsg) {
    const file = fileQueue.find(f => f.path === filePath);
    if (!file) return;

    const wasNotCompleted = file.status !== 'completed' && file.status !== 'failed';

    if (percent === 100) {
        file.status = 'completed';
        file.progress = 100;
        file.statusMsg = statusMsg || 'Abgeschlossen';
        if (wasNotCompleted) announce(`${file.name}: fertig.`);
    } else if (percent === -1) {
        file.status = 'failed';
        file.progress = 0;
        file.statusMsg = statusMsg || 'Fehlgeschlagen';
        if (wasNotCompleted) announce(`${file.name}: Fehler – ${file.statusMsg}`);
    } else {
        file.status = 'processing';
        file.progress = percent;
        file.statusMsg = statusMsg || 'Wird verarbeitet…';
    }

    renderQueue();

    const stillRunning = fileQueue.some(f => f.status === 'processing');
    if (!stillRunning) {
        isProcessing = false;
        updateStartButtonState();
        clearBtn.hidden = false;
        announce('Alle Verarbeitungen abgeschlossen.');
    }
};

// ------------------------------------------------------------
// Info & Lizenzen Modal Steuerung
// ------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    const infoBtn = document.getElementById('info-btn');
    const infoModal = document.getElementById('info-modal');
    const closeInfoBtn = document.getElementById('close-info-btn');
    const modalContent = infoModal ? infoModal.querySelector('.modal-content') : null;

    if (!infoBtn || !infoModal || !closeInfoBtn) return;

    function openModal() {
        infoModal.classList.add('active');
        infoModal.setAttribute('aria-hidden', 'false');
        if (modalContent) {
            modalContent.focus();
        }
    }

    function closeModal() {
        infoModal.classList.remove('active');
        infoModal.setAttribute('aria-hidden', 'true');
        infoBtn.focus();
    }

    infoBtn.addEventListener('click', openModal);
    closeInfoBtn.addEventListener('click', closeModal);

    // Schließen bei Klick außerhalb des Modals
    infoModal.addEventListener('click', (e) => {
        if (e.target === infoModal) {
            closeModal();
        }
    });

    // Schließen bei Drücken der Escape-Taste
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && infoModal.classList.contains('active')) {
            closeModal();
        }
    });
});

// ------------------------------------------------------------
// Speicherort-Steuerung (Einstellungsmenü)
// ------------------------------------------------------------
let customOutputPath = '';
const outputDirTypeSelect = document.getElementById('output-dir-type');
const customPathContainer = document.getElementById('custom-path-container');
const customPathInput = document.getElementById('custom-path-input');
const selectCustomPathBtn = document.getElementById('select-custom-path-btn');

if (outputDirTypeSelect && customPathContainer && customPathInput && selectCustomPathBtn) {
    outputDirTypeSelect.addEventListener('change', () => {
        if (outputDirTypeSelect.value === 'custom') {
            customPathContainer.style.display = 'flex';
        } else {
            customPathContainer.style.display = 'none';
        }
    });

    selectCustomPathBtn.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.select_output_folder().then(path => {
                if (path) {
                    customOutputPath = path;
                    customPathInput.value = path;
                    announce(`Ausgewählter Speicherort: ${path}`);
                }
            });
        }
    });
}

// ------------------------------------------------------------
// Sprechererkennungs-Steuerung (Einstellungsmenü)
// ------------------------------------------------------------
const diarizationEnableCheckbox = document.getElementById('diarization-enable');
const speakerCountWrapper = document.getElementById('speaker-count-wrapper');
const speakerCountSelect = document.getElementById('speaker-count');

if (diarizationEnableCheckbox && speakerCountWrapper && speakerCountSelect) {
    diarizationEnableCheckbox.addEventListener('change', () => {
        if (diarizationEnableCheckbox.checked) {
            speakerCountWrapper.classList.remove('disabled');
            speakerCountSelect.removeAttribute('disabled');
            announce('Sprechererkennung aktiviert.');
        } else {
            speakerCountWrapper.classList.add('disabled');
            speakerCountSelect.setAttribute('disabled', 'true');
            announce('Sprechererkennung deaktiviert.');
        }
    });
}
