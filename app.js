// ============================================================
// Transcription Adler – Frontend-Logik (barrierefrei)
// ============================================================

// State
let fileQueue = [];
let isProcessing = false;
let customOutputPath = '';

// Liefert die aktuell gewählten Zeitstempel-Modi (Mehrfachauswahl).
// Fällt auf ['every'] zurück, falls nichts ausgewählt ist.
function getSelectedTimecodeModes() {
    const modes = Array.from(document.querySelectorAll('.timecode-mode'))
        .filter(cb => cb.checked)
        .map(cb => cb.value);
    return modes.length > 0 ? modes : ['every'];
}

function saveSettings() {
    try {
        const settings = {
            sourceLang: document.getElementById('source-lang')?.value,
            translateEnable: document.getElementById('translate-enable')?.checked,
            targetLang: document.getElementById('target-lang')?.value,
            modelSize: document.getElementById('model-size')?.value,
            outputDirType: document.getElementById('output-dir-type')?.value,
            customOutputPath: customOutputPath,
            customPathInput: document.getElementById('custom-path-input')?.value,
            diarizationEnable: document.getElementById('diarization-enable')?.checked,
            speakerCount: document.getElementById('speaker-count')?.value,
            docxTransMode: document.getElementById('docx-trans-mode')?.value,
            timecodeModes: getSelectedTimecodeModes()
        };
        const json = JSON.stringify(settings);
        // Primär Python-seitig (überlebt die Session zuverlässig, unabhängig von
        // localStorage-Einschränkungen bei file://). localStorage als Fallback
        // außerhalb der App (z. B. im Browser).
        if (window.pywebview && window.pywebview.api && window.pywebview.api.save_app_settings) {
            window.pywebview.api.save_app_settings(json);
        } else {
            localStorage.setItem('adler_settings', json);
        }
    } catch (e) {
        console.error("Fehler beim Speichern der Einstellungen:", e);
    }
}

function loadSettings() {
    // Lädt die gemerkten Einstellungen primär aus dem Python-Backend (Session),
    // sonst aus localStorage (außerhalb der App).
    try {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.load_app_settings) {
            window.pywebview.api.load_app_settings()
                .then(settings => applySettings(settings))
                .catch(err => console.error("Fehler beim Laden der Einstellungen (API):", err));
        } else {
            const data = localStorage.getItem('adler_settings');
            if (data) applySettings(JSON.parse(data));
        }
    } catch (e) {
        console.error("Fehler beim Laden der Einstellungen:", e);
    }
}

function applySettings(settings) {
    try {
        if (!settings || typeof settings !== 'object') return;

        const srcSelect = document.getElementById('source-lang');
        if (srcSelect && settings.sourceLang) srcSelect.value = settings.sourceLang;
        
        const transChk = document.getElementById('translate-enable');
        if (transChk && settings.translateEnable !== undefined) {
            transChk.checked = settings.translateEnable;
            const targetLangWrapper = document.getElementById('target-lang-wrapper');
            const targetLangSelect = document.getElementById('target-lang');
            const docxGroup = document.getElementById('docx-trans-mode-group');
            const docxSelect = document.getElementById('docx-trans-mode');
            if (transChk.checked) {
                if (targetLangWrapper) targetLangWrapper.classList.remove('disabled');
                if (targetLangSelect) targetLangSelect.removeAttribute('disabled');
                if (docxGroup) docxGroup.classList.remove('disabled');
                if (docxSelect) docxSelect.removeAttribute('disabled');
            } else {
                if (targetLangWrapper) targetLangWrapper.classList.add('disabled');
                if (targetLangSelect) targetLangSelect.setAttribute('disabled', 'true');
                if (docxGroup) docxGroup.classList.add('disabled');
                if (docxSelect) docxSelect.setAttribute('disabled', 'true');
            }
        }
        
        const targetSelect = document.getElementById('target-lang');
        if (targetSelect && settings.targetLang) targetSelect.value = settings.targetLang;
        
        const modelSelect = document.getElementById('model-size');
        if (modelSelect && settings.modelSize) modelSelect.value = settings.modelSize;
        
        const outDirSelect = document.getElementById('output-dir-type');
        if (outDirSelect && settings.outputDirType) {
            outDirSelect.value = settings.outputDirType;
            const customPathContainer = document.getElementById('custom-path-container');
            if (customPathContainer) {
                if (outDirSelect.value === 'custom') {
                    customPathContainer.style.display = 'flex';
                } else {
                    customPathContainer.style.display = 'none';
                }
            }
        }
        
        if (settings.customOutputPath !== undefined) customOutputPath = settings.customOutputPath;
        
        const customPathInput = document.getElementById('custom-path-input');
        if (customPathInput && settings.customPathInput !== undefined) {
            customPathInput.value = settings.customPathInput;
        }
        
        const diarChk = document.getElementById('diarization-enable');
        if (diarChk && settings.diarizationEnable !== undefined) {
            diarChk.checked = settings.diarizationEnable;
            const speakerCountWrapper = document.getElementById('speaker-count-wrapper');
            const speakerCountSelect = document.getElementById('speaker-count');
            if (diarChk.checked) {
                if (speakerCountWrapper) speakerCountWrapper.classList.remove('disabled');
                if (speakerCountSelect) speakerCountSelect.removeAttribute('disabled');
            } else {
                if (speakerCountWrapper) speakerCountWrapper.classList.add('disabled');
                if (speakerCountSelect) speakerCountSelect.setAttribute('disabled', 'true');
            }
        }
        
        const speakerSelect = document.getElementById('speaker-count');
        if (speakerSelect && settings.speakerCount) speakerSelect.value = settings.speakerCount;
        
        const docxSelect = document.getElementById('docx-trans-mode');
        if (docxSelect && settings.docxTransMode) docxSelect.value = settings.docxTransMode;

        if (Array.isArray(settings.timecodeModes)) {
            document.querySelectorAll('.timecode-mode').forEach(cb => {
                cb.checked = settings.timecodeModes.includes(cb.value);
            });
        }

    } catch (e) {
        console.error("Fehler beim Laden der Einstellungen:", e);
    }
}

// DOM
const sourceLangSelect = document.getElementById('source-lang');
const translateEnableCheckbox = document.getElementById('translate-enable');
const targetLangWrapper = document.getElementById('target-lang-wrapper');
const targetLangSelect = document.getElementById('target-lang');
const modelSizeSelect = document.getElementById('model-size');
const startBtn = document.getElementById('start-btn');
const cancelBtn = document.getElementById('cancel-btn');
const clearBtn = document.getElementById('clear-btn');
const browseBtn = document.getElementById('browse-btn');
const dropZone = document.getElementById('drop-zone');
const queueTbody = document.getElementById('queue-tbody');
const queueCountBadge = document.getElementById('queue-count');
const srAnnouncer = document.getElementById('sr-announcer');

// Drawer Elements
const openDrawerBtn = document.getElementById('open-drawer-btn');
const closeDrawerBtn = document.getElementById('close-drawer-btn');
const saveDrawerBtn = document.getElementById('save-drawer-btn');
const drawerOverlay = document.getElementById('drawer-overlay');
const settingsDrawer = document.getElementById('settings-drawer');

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
    const docxGroup = document.getElementById('docx-trans-mode-group');
    const docxSelect = document.getElementById('docx-trans-mode');
    if (translateEnableCheckbox.checked) {
        targetLangWrapper.classList.remove('disabled');
        targetLangSelect.removeAttribute('disabled');
        if (docxGroup && docxSelect) {
            docxGroup.classList.remove('disabled');
            docxSelect.removeAttribute('disabled');
        }
        announce('Übersetzung aktiviert. Zielsprache kann ausgewählt werden.');
    } else {
        targetLangWrapper.classList.add('disabled');
        targetLangSelect.setAttribute('disabled', 'true');
        if (docxGroup && docxSelect) {
            docxGroup.classList.add('disabled');
            docxSelect.setAttribute('disabled', 'true');
        }
        announce('Übersetzung deaktiviert.');
    }
    saveSettings();
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
    if (filePath.toLowerCase().endsWith('.adler')) {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.load_project_file(filePath).then(res => {
                if (res && res.success) {
                    let videoPath = res.video_path;
                    if (!res.video_exists) {
                        if (confirm("Das zugehörige Video wurde unter '" + videoPath + "' nicht gefunden.\nMöchten Sie das Video manuell verknüpfen?")) {
                            window.pywebview.api.locate_video_file().then(newPath => {
                                if (newPath) {
                                    videoPath = newPath;
                                    // Register in Python cache under the new path
                                    window.pywebview.api.cache_project_segments(newPath, JSON.stringify(res.segments));
                                    addLoadedProjectToQueue(filePath, videoPath, res.segments, res.cuts);
                                }
                            });
                        }
                    } else {
                        addLoadedProjectToQueue(filePath, videoPath, res.segments, res.cuts);
                    }
                } else {
                    alert("Fehler beim Laden des Projekts: " + (res ? res.error : 'Unbekannt'));
                }
            }).catch(err => {
                console.error("Fehler beim Laden des Projekts:", err);
                alert("Fehler beim Laden des Projekts.");
            });
        }
        return;
    }

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

function addLoadedProjectToQueue(projectPath, videoPath, segments, cuts) {
    if (fileQueue.some(file => file.path === videoPath)) {
        alert("Dieses Video befindet sich bereits in der Warteschlange.");
        return;
    }

    const filename = videoPath.split('/').pop().split('\\').pop();
    const newFile = {
        path: videoPath,
        name: filename,
        duration: 'Wird geladen…',
        creationDate: 'Wird geladen…',
        location: 'Wird geladen…',
        mapsLink: null,
        status: 'completed',
        progress: 100,
        statusMsg: 'Projekt geladen',
        segments: segments,
        cuts: cuts || []
    };

    fileQueue.push(newFile);
    renderQueue();
    updateStartButtonState();

    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_file_metadata(videoPath).then(meta => {
            updateFileMetadata(videoPath, meta);
        }).catch(err => {
            console.error('Fehler beim Laden der Metadaten:', err);
            updateFileMetadata(videoPath, { error: true });
        });
    }

    announce(`Projekt für ${filename} erfolgreich geladen.`);
    openDetailPanel(newFile);
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
        tr.dataset.path = file.path;

        // Clickable row for completed transcriptions
        if (file.status === 'completed') {
            tr.classList.add('clickable-row');
            tr.setAttribute('tabindex', '0');
            tr.setAttribute('role', 'button');
            tr.setAttribute('aria-label', `${file.name}, fertig. Klicken zum Abspielen und Transkript anzeigen.`);
            tr.addEventListener('click', () => openDetailPanel(file));
            tr.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    openDetailPanel(file);
                }
            });
        }

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

        // Status (eigene Zelle – kann gezielt einzeln aktualisiert werden)
        tr.appendChild(createStatusCell(file));
        queueTbody.appendChild(tr);
    });
}

// ------------------------------------------------------------
// Statuszelle einer Datei aufbauen (Badge, Fortschrittsbalken, Abspiel-Button)
// ------------------------------------------------------------
function createStatusCell(file) {
    const tdStatus = document.createElement('td');
    const statusContainer = document.createElement('div');
    statusContainer.className = 'status-cell-container';
    tdStatus.appendChild(statusContainer);

    const badge = document.createElement('div');
    badge.className = `status-badge ${file.status}`;

    let statusText = '';
    if (file.status === 'queued') statusText = 'Wartet';
    else if (file.status === 'processing') statusText = `${file.progress}%`;
    else if (file.status === 'completed') statusText = 'Fertig';
    else if (file.status === 'failed') statusText = 'Fehler';
    else if (file.status === 'cancelled') statusText = 'Abgebrochen';

    badge.textContent = statusText;
    statusContainer.appendChild(badge);

    if (file.status === 'completed') {
        const playBtn = document.createElement('button');
        playBtn.type = 'button';
        playBtn.className = 'btn-play-row';
        playBtn.innerHTML = '<span aria-hidden="true">▶</span> Abspielen';
        playBtn.setAttribute('aria-label', `Transkript und Player für ${file.name} öffnen`);
        playBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openDetailPanel(file);
        });
        statusContainer.appendChild(playBtn);
    }

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
        statusContainer.appendChild(barContainer);
    }

    if (file.statusMsg && file.status !== 'queued') {
        const msgLabel = document.createElement('div');
        msgLabel.className = 'status-msg';
        msgLabel.textContent = file.statusMsg;
        statusContainer.appendChild(msgLabel);
    }

    return tdStatus;
}

// ------------------------------------------------------------
// Nur die Statuszelle einer einzelnen Zeile neu rendern (für häufige
// Fortschritts-Ticks – vermeidet den teuren Neuaufbau der ganzen Tabelle).
// ------------------------------------------------------------
function updateRowStatus(file) {
    let targetRow = null;
    for (const row of queueTbody.children) {
        if (row.dataset && row.dataset.path === file.path) {
            targetRow = row;
            break;
        }
    }
    if (!targetRow) {
        renderQueue();
        return;
    }
    const oldCell = targetRow.lastElementChild;
    const newCell = createStatusCell(file);
    if (oldCell) {
        targetRow.replaceChild(newCell, oldCell);
    } else {
        targetRow.appendChild(newCell);
    }
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
    if (cancelBtn) {
        cancelBtn.hidden = false;
        cancelBtn.disabled = false;
    }

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
        const docxTransMode = document.getElementById('docx-trans-mode').value;
        const timecodeModes = getSelectedTimecodeModes();
        window.pywebview.api.start_transcription(paths, sourceLang, targetLang, modelSize, outputDirType, customPath, diarize, speakerCount, docxTransMode, timecodeModes);
    }
});

// ------------------------------------------------------------
// Transkription abbrechen
// ------------------------------------------------------------
if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
        if (!isProcessing) return;
        cancelBtn.disabled = true;
        announce('Abbruch angefordert. Verbleibende Dateien werden übersprungen, die laufende Datei wird beendet.');
        if (window.pywebview && window.pywebview.api && window.pywebview.api.cancel_transcription) {
            window.pywebview.api.cancel_transcription();
        }
    });
}

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
    } else if (percent === -2) {
        file.status = 'cancelled';
        file.progress = 0;
        file.statusMsg = statusMsg || 'Abgebrochen';
        if (wasNotCompleted) announce(`${file.name}: abgebrochen.`);
    } else {
        file.status = 'processing';
        file.progress = percent;
        file.statusMsg = statusMsg || 'Wird verarbeitet…';
    }

    // Beim Fertigwerden wird die Zeile klickbar/abspielbar -> volles Rendern.
    // Häufige Fortschritts-Ticks aktualisieren nur die betroffene Statuszelle.
    if (percent === 100) {
        renderQueue();
    } else {
        updateRowStatus(file);
    }

    const stillRunning = fileQueue.some(f => f.status === 'processing');
    if (!stillRunning) {
        isProcessing = false;
        updateStartButtonState();
        clearBtn.hidden = false;
        if (cancelBtn) {
            cancelBtn.hidden = true;
            cancelBtn.disabled = false;
        }
        const anyCancelled = fileQueue.some(f => f.status === 'cancelled');
        announce(anyCancelled ? 'Verarbeitung abgebrochen.' : 'Alle Verarbeitungen abgeschlossen.');
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
        saveSettings();
    });

    selectCustomPathBtn.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.select_output_folder().then(path => {
                if (path) {
                    customOutputPath = path;
                    customPathInput.value = path;
                    announce(`Ausgewählter Speicherort: ${path}`);
                    saveSettings();
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
        saveSettings();
    });
}

// ------------------------------------------------------------
// Settings Drawer (Erweiterte Einstellungen) Steuerung
// ------------------------------------------------------------
if (openDrawerBtn && closeDrawerBtn && saveDrawerBtn && drawerOverlay && settingsDrawer) {
    function openDrawer() {
        settingsDrawer.classList.add('active');
        drawerOverlay.classList.add('active');
        settingsDrawer.setAttribute('aria-hidden', 'false');
        openDrawerBtn.setAttribute('aria-expanded', 'true');
        closeDrawerBtn.focus();
        announce('Erweiterte Einstellungen geöffnet.');
    }

    function closeDrawer() {
        settingsDrawer.classList.remove('active');
        drawerOverlay.classList.remove('active');
        settingsDrawer.setAttribute('aria-hidden', 'true');
        openDrawerBtn.setAttribute('aria-expanded', 'false');
        openDrawerBtn.focus();
        announce('Erweiterte Einstellungen geschlossen.');
    }

    openDrawerBtn.addEventListener('click', openDrawer);
    closeDrawerBtn.addEventListener('click', closeDrawer);
    saveDrawerBtn.addEventListener('click', closeDrawer);
    drawerOverlay.addEventListener('click', closeDrawer);

    // Close on Escape key press
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && settingsDrawer.classList.contains('active')) {
            closeDrawer();
        }
    });
}

// ------------------------------------------------------------
// Schnittmarken (In/Out) State & Hilfsfunktionen
// ------------------------------------------------------------
let cutInTime = null;
let cutOutTime = null;

function formatSecondsForUI(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function setInPoint(time) {
    if (cutOutTime !== null && time > cutOutTime) {
        showCutMessage("IN-Punkt darf nicht nach dem OUT-Punkt liegen.", "error");
        return;
    }
    cutInTime = time;
    updateCutUIControls();
    showCutMessage("IN-Punkt gesetzt auf " + formatSecondsForUI(time) + ". Klicken Sie '+ Schnitt hinzufügen' zum Speichern.", "success");
    announce("IN-Punkt gesetzt auf " + formatSecondsForUI(time));
}

function setOutPoint(time) {
    if (cutInTime !== null && time < cutInTime) {
        showCutMessage("OUT-Punkt darf nicht vor dem IN-Punkt liegen.", "error");
        return;
    }
    cutOutTime = time;
    updateCutUIControls();
    showCutMessage("OUT-Punkt gesetzt auf " + formatSecondsForUI(time) + ". Klicken Sie '+ Schnitt hinzufügen' zum Speichern.", "success");
    announce("OUT-Punkt gesetzt auf " + formatSecondsForUI(time));
}

function addCut() {
    if (cutInTime === null || cutOutTime === null) {
        showCutMessage("Bitte zuerst IN- und OUT-Punkt setzen.", "error");
        return;
    }
    if (cutInTime >= cutOutTime) {
        showCutMessage("IN-Punkt muss vor OUT-Punkt liegen.", "error");
        return;
    }
    if (!currentPlayingFile) return;

    currentPlayingFile.cuts = currentPlayingFile.cuts || [];
    
    // Generiere eindeutige ID
    const id = Date.now() + Math.random().toString(36).slice(2, 11);
    currentPlayingFile.cuts.push({
        id: id,
        start: cutInTime,
        end: cutOutTime
    });

    // Chronologisch sortieren
    currentPlayingFile.cuts.sort((a, b) => a.start - b.start);

    // Aktiven Bereich zurücksetzen
    cutInTime = null;
    cutOutTime = null;

    renderCutList();
    updateCutUIControls();
    showCutMessage("Schnitt zur Liste hinzugefügt.", "success");
    announce("Schnitt zur Liste hinzugefügt.");
}

function deleteCut(id) {
    if (!currentPlayingFile || !currentPlayingFile.cuts) return;
    currentPlayingFile.cuts = currentPlayingFile.cuts.filter(c => c.id !== id);
    
    renderCutList();
    updateCutUIControls();
    showCutMessage("Schnitt gelöscht.", "success");
    announce("Schnitt gelöscht.");
}

function renderCutList() {
    const container = document.getElementById('cut-list-container');
    const countEl = document.getElementById('cut-list-count');
    const totalEl = document.getElementById('cut-total-time');
    
    if (!container || !countEl || !totalEl) return;
    
    container.innerHTML = '';
    
    if (!currentPlayingFile || !currentPlayingFile.cuts || currentPlayingFile.cuts.length === 0) {
        container.innerHTML = '<div class="empty-cut-text">Keine Schnitte in der Liste.</div>';
        countEl.textContent = '0 Schnitte';
        totalEl.textContent = '00:00:00';
        return;
    }
    
    const cuts = currentPlayingFile.cuts;
    countEl.textContent = `${cuts.length} Schnitt${cuts.length === 1 ? '' : 'e'}`;
    
    let totalDuration = 0;
    
    cuts.forEach((cut, index) => {
        const duration = cut.end - cut.start;
        totalDuration += duration;
        
        const cutDiv = document.createElement('div');
        cutDiv.className = 'cut-item';
        cutDiv.setAttribute('title', 'Klicken, um zum Startzeitpunkt zu springen');
        
        cutDiv.addEventListener('click', () => {
            const player = document.getElementById('media-player');
            if (player) {
                player.currentTime = cut.start;
                player.play().catch(e => console.log('Autoplay blocked:', e));
            }
        });
        
        const infoSpan = document.createElement('span');
        infoSpan.className = 'cut-item-info';
        infoSpan.innerHTML = `<strong>#${index + 1}</strong> ${formatSecondsForUI(cut.start)} - ${formatSecondsForUI(cut.end)}`;
        cutDiv.appendChild(infoSpan);
        
        const rightDiv = document.createElement('div');
        rightDiv.className = 'detail-header-actions';
        
        const durSpan = document.createElement('span');
        durSpan.className = 'cut-item-duration';
        durSpan.textContent = `(${Math.round(duration)}s)`;
        rightDiv.appendChild(durSpan);
        
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'btn-delete-cut';
        delBtn.innerHTML = '&times;';
        delBtn.setAttribute('aria-label', `Schnitt ${index + 1} löschen`);
        delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteCut(cut.id);
        });
        rightDiv.appendChild(delBtn);
        
        cutDiv.appendChild(rightDiv);
        container.appendChild(cutDiv);
    });
    
    totalEl.textContent = formatSecondsForUI(totalDuration);
}

function updateCutUIControls() {
    const inEl = document.getElementById('cut-in-time');
    const outEl = document.getElementById('cut-out-time');
    if (!inEl || !outEl) return;

    inEl.textContent = cutInTime !== null ? formatSecondsForUI(cutInTime) : '--:--:--';
    outEl.textContent = cutOutTime !== null ? formatSecondsForUI(cutOutTime) : '--:--:--';

    const segments = document.querySelectorAll('.transcript-segment');
    segments.forEach((segDiv, idx) => {
        if (!currentPlayingFile || !currentPlayingFile.segments) return;
        const seg = currentPlayingFile.segments[idx];
        if (!seg) return;

        segDiv.classList.remove('in-cut-range', 'has-in-mark', 'has-out-mark');
        
        const existingBadges = segDiv.querySelectorAll('.badge-cut-in, .badge-cut-out');
        existingBadges.forEach(b => b.remove());
    });

    if (!currentPlayingFile || !currentPlayingFile.segments) return;
    const fileSegs = currentPlayingFile.segments;
    const cuts = currentPlayingFile.cuts || [];
    
    // We compute which segments are inside a cut range and where the boundary marks are
    const isInsideCutList = new Array(fileSegs.length).fill(false);
    const boundaryLabelsMap = {};
    for (let i = 0; i < fileSegs.length; i++) {
        boundaryLabelsMap[i] = [];
    }

    // Process saved cuts
    cuts.forEach((cut, cIdx) => {
        const overlappingIndices = [];
        fileSegs.forEach((seg, sIdx) => {
            const segStart = seg.start;
            const segEnd = seg.end;
            if (segStart < cut.end && segEnd > cut.start) {
                overlappingIndices.push(sIdx);
                isInsideCutList[sIdx] = true;
            }
        });
        if (overlappingIndices.length > 0) {
            const inIdx = overlappingIndices[0];
            const outIdx = overlappingIndices[overlappingIndices.length - 1];
            boundaryLabelsMap[inIdx].push({ type: 'in', label: `IN #${cIdx + 1}` });
            boundaryLabelsMap[outIdx].push({ type: 'out', label: `OUT #${cIdx + 1}` });
        }
    });

    // Process active temporary cut
    const activeInLabels = {};
    const activeOutLabels = {};

    if (cutInTime !== null && cutOutTime !== null) {
        // Both are set: active range
        const overlappingIndices = [];
        fileSegs.forEach((seg, sIdx) => {
            const segStart = seg.start;
            const segEnd = seg.end;
            if (segStart < cutOutTime && segEnd > cutInTime) {
                overlappingIndices.push(sIdx);
                isInsideCutList[sIdx] = true;
            }
        });
        if (overlappingIndices.length > 0) {
            const inIdx = overlappingIndices[0];
            const outIdx = overlappingIndices[overlappingIndices.length - 1];
            activeInLabels[inIdx] = 'IN';
            activeOutLabels[outIdx] = 'OUT';
        }
    } else {
        // Only one or none is set
        if (cutInTime !== null) {
            const idx = fileSegs.findIndex(seg => cutInTime >= seg.start && cutInTime < seg.end);
            if (idx !== -1) {
                activeInLabels[idx] = 'IN';
            } else {
                let minDiff = Infinity;
                let closestIdx = -1;
                fileSegs.forEach((seg, sIdx) => {
                    const diff = Math.min(Math.abs(seg.start - cutInTime), Math.abs(seg.end - cutInTime));
                    if (diff < minDiff) {
                        minDiff = diff;
                        closestIdx = sIdx;
                    }
                });
                if (closestIdx !== -1) {
                    activeInLabels[closestIdx] = 'IN';
                }
            }
        }
        if (cutOutTime !== null) {
            const idx = fileSegs.findIndex(seg => cutOutTime >= seg.start && cutOutTime < seg.end);
            if (idx !== -1) {
                activeOutLabels[idx] = 'OUT';
            } else {
                let minDiff = Infinity;
                let closestIdx = -1;
                fileSegs.forEach((seg, sIdx) => {
                    const diff = Math.min(Math.abs(seg.start - cutOutTime), Math.abs(seg.end - cutOutTime));
                    if (diff < minDiff) {
                        minDiff = diff;
                        closestIdx = sIdx;
                    }
                });
                if (closestIdx !== -1) {
                    activeOutLabels[closestIdx] = 'OUT';
                }
            }
        }
    }

    // Now apply classes and add badges to the actual DOM elements
    segments.forEach((segDiv, idx) => {
        const seg = fileSegs[idx];
        if (!seg) return;

        if (isInsideCutList[idx]) {
            segDiv.classList.add('in-cut-range');
        }

        // Add saved badges
        const bounds = boundaryLabelsMap[idx] || [];
        bounds.forEach(b => {
            segDiv.classList.add(b.type === 'in' ? 'has-in-mark' : 'has-out-mark');
            const meta = segDiv.querySelector('.segment-meta');
            if (meta) {
                const badge = document.createElement('span');
                badge.className = b.type === 'in' ? 'badge-cut-in' : 'badge-cut-out';
                badge.textContent = b.label;
                meta.appendChild(badge);
            }
        });

        // Add active temporary badges
        if (activeInLabels[idx]) {
            segDiv.classList.add('has-in-mark');
            const meta = segDiv.querySelector('.segment-meta');
            if (meta) {
                const badge = document.createElement('span');
                badge.className = 'badge-cut-in';
                badge.textContent = activeInLabels[idx];
                meta.appendChild(badge);
            }
        }
        if (activeOutLabels[idx]) {
            segDiv.classList.add('has-out-mark');
            const meta = segDiv.querySelector('.segment-meta');
            if (meta) {
                const badge = document.createElement('span');
                badge.className = 'badge-cut-out';
                badge.textContent = activeOutLabels[idx];
                meta.appendChild(badge);
            }
        }
    });
}

function showCutMessage(msg, type) {
    const el = document.getElementById('cut-status-msg');
    if (!el) return;
    el.textContent = msg;
    el.className = 'cut-status-msg ' + type;
    
    if (type === 'success') {
        setTimeout(() => {
            if (el.textContent === msg) {
                el.textContent = '';
                el.className = 'cut-status-msg';
            }
        }, 5000);
    }
}

// ------------------------------------------------------------
// Player & Transkript Detailansicht Steuerung
// ------------------------------------------------------------
let currentPlayingFile = null;
let currentTranscriptLanguage = 'both'; // 'both', 'original', 'translated'

function openDetailPanel(file) {
    const panel = document.getElementById('detail-panel');
    if (!panel) return;

    currentPlayingFile = file;
    file.cuts = file.cuts || [];
    cutInTime = null;
    cutOutTime = null;
    showCutMessage("", "");
    
    panel.classList.add('active');
    panel.setAttribute('aria-hidden', 'false');
    
    // Kino-Modus standardmäßig zurücksetzen
    panel.classList.remove('theater-mode');
    const btnTheater = document.getElementById('btn-toggle-theater');
    if (btnTheater) {
        btnTheater.classList.remove('active');
        btnTheater.textContent = "📽 Kino-Modus";
    }
    
    renderCutList();

    // Linke Spalte schmaler machen
    const leftCol = document.querySelector('.dashboard-left');
    if (leftCol) {
        leftCol.style.flex = '0 0 58%';
    }

    // Dateiname setzen
    const nameEl = document.getElementById('detail-filename');
    if (nameEl) {
        nameEl.textContent = file.name;
        nameEl.setAttribute('title', file.name);
    }

    // Lade-Status anzeigen
    const listContainer = document.getElementById('transcript-segments-list');
    if (listContainer) {
        listContainer.innerHTML = '<div class="empty-text">Lade Transkript...</div>';
    }

        // Player initialisieren
        const playerContainer = document.getElementById('media-player-container');
        if (playerContainer) {
            playerContainer.innerHTML = '';

            const ext = file.name.split('.').pop().toLowerCase();
            const isVideo = ['mp4', 'mov', 'mkv', 'webm'].includes(ext);

            const player = document.createElement(isVideo ? 'video' : 'audio');
            player.id = 'media-player';
            player.controls = true;
            player.preload = 'metadata';
            
            // Set up local web server URL or fall back to file:///
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.get_server_config().then(config => {
                    const encodedPath = encodeURIComponent(file.path);
                    player.src = `http://127.0.0.1:${config.port}/media?token=${config.token}&path=${encodedPath}`;
                }).catch(err => {
                    console.error("Fehler beim Abrufen der Server-Konfiguration:", err);
                    player.src = 'file:///' + encodeURI(file.path.replace(/\\/g, '/'));
                });
            } else {
                player.src = 'file:///' + encodeURI(file.path.replace(/\\/g, '/'));
            }
            playerContainer.appendChild(player);

        // Transkript abrufen aus Python Cache
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_transcript(file.path).then(segments => {
                if (!segments || segments.length === 0) {
                    if (listContainer) {
                        listContainer.innerHTML = '<div class="empty-text">Kein Transkript verfügbar.</div>';
                    }
                    return;
                }

                file.segments = segments;
                renderTranscriptSegments(file);
                setupPlayerSync(player, segments);
            }).catch(err => {
                console.error('Fehler beim Laden des Transkripts:', err);
                if (listContainer) {
                    listContainer.innerHTML = '<div class="empty-text">Fehler beim Laden des Transkripts.</div>';
                }
            });
        } else {
            // Fallback
            if (listContainer) {
                listContainer.innerHTML = '<div class="empty-text">Kein Transkript geladen (außerhalb der App).</div>';
            }
        }
    }
}

function closeDetailPanel() {
    const panel = document.getElementById('detail-panel');
    if (!panel) return;

    // Layout zurücksetzen
    const leftCol = document.querySelector('.dashboard-left');
    if (leftCol) {
        leftCol.style.flex = '1';
    }

    panel.classList.remove('active');
    panel.classList.remove('theater-mode');
    
    const btnTheater = document.getElementById('btn-toggle-theater');
    if (btnTheater) {
        btnTheater.classList.remove('active');
        btnTheater.textContent = "📽 Kino-Modus";
    }
    panel.setAttribute('aria-hidden', 'true');

    // Player stoppen
    const player = document.getElementById('media-player');
    if (player) {
        player.pause();
        player.src = '';
    }

    currentPlayingFile = null;
}

// ------------------------------------------------------------
// Aktuelles Projekt speichern (.adler): Transkript, Video-Verknüpfung und
// Schnittmarken. Beim späteren Öffnen der .adler-Datei werden Player und
// synchroner Text wiederhergestellt.
// ------------------------------------------------------------
function saveCurrentProject() {
    if (!currentPlayingFile) {
        showCutMessage("Kein Projekt geöffnet. Bitte zuerst eine transkribierte Datei öffnen.", "error");
        return;
    }
    const segments = currentPlayingFile.segments || [];
    const cuts = currentPlayingFile.cuts || [];

    showCutMessage("Projekt wird gespeichert...", "");

    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_project_file) {
        window.pywebview.api.save_project_file(
            currentPlayingFile.path,
            JSON.stringify(segments),
            JSON.stringify(cuts)
        ).then(result => {
            if (result && result.success) {
                showCutMessage(`Projekt gespeichert: ${result.filename}`, "success");
                announce(`Projekt erfolgreich gespeichert unter ${result.filename}`);
            } else {
                showCutMessage(`Fehler beim Speichern: ${result.error || 'Abgebrochen'}`, "error");
            }
        }).catch(err => {
            console.error("Fehler bei save_project_file:", err);
            showCutMessage("Fehler beim Aufruf der Python-API.", "error");
        });
    } else {
        showCutMessage("Fehler: Keine App-Verbindung verfügbar.", "error");
    }
}

function renderTranscriptSegments(file) {
    const listContainer = document.getElementById('transcript-segments-list');
    if (!listContainer || !file.segments) return;

    listContainer.innerHTML = '';
    
    const hasTranslation = file.segments.some(seg => seg.translated);
    const langToggle = document.getElementById('lang-toggle-container');
    
    if (langToggle) {
        langToggle.style.display = hasTranslation ? 'flex' : 'none';
    }

    file.segments.forEach((seg, idx) => {
        const segDiv = document.createElement('div');
        segDiv.className = 'transcript-segment';
        segDiv.id = `segment-${idx}`;
        segDiv.setAttribute('tabindex', '0');
        segDiv.setAttribute('role', 'button');
        segDiv.setAttribute('aria-label', `Segment ${idx + 1} ab ${seg.start_str}. Sprecher: ${seg.speaker || 'Unbekannt'}.`);
        
        // Metadaten
        const metaDiv = document.createElement('div');
        metaDiv.className = 'segment-meta';
        
        const timestampSpan = document.createElement('span');
        timestampSpan.className = 'segment-timestamp';
        timestampSpan.textContent = seg.start_str;
        metaDiv.appendChild(timestampSpan);

        if (seg.speaker) {
            const speakerSpan = document.createElement('span');
            speakerSpan.className = 'segment-speaker';
            speakerSpan.textContent = seg.speaker;
            metaDiv.appendChild(speakerSpan);
        }
        
        segDiv.appendChild(metaDiv);

        // Text
        const textDiv = document.createElement('div');
        textDiv.className = 'segment-text';

        if (currentTranscriptLanguage === 'original' || !hasTranslation) {
            textDiv.textContent = seg.original;
        } else if (currentTranscriptLanguage === 'translated') {
            textDiv.textContent = seg.translated || seg.original;
        } else {
            // Beide anzeigen
            const origSpan = document.createElement('div');
            origSpan.className = 'text-orig';
            origSpan.textContent = seg.original;
            textDiv.appendChild(origSpan);

            if (seg.translated) {
                const transSpan = document.createElement('div');
                transSpan.className = 'segment-text translated';
                transSpan.textContent = seg.translated;
                textDiv.appendChild(transSpan);
            }
        }
        
        segDiv.appendChild(textDiv);

        // Klick sucht im Video/Audio
        const seekHandler = () => {
            const player = document.getElementById('media-player');
            if (player) {
                player.currentTime = seg.start;
                player.play().catch(e => console.log('Autoplay blocked:', e));
            }
        };

        segDiv.addEventListener('click', seekHandler);
        segDiv.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                seekHandler();
            } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                setInPoint(seg.start);
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                setOutPoint(seg.end);
            }
        });

        listContainer.appendChild(segDiv);
    });

    // Highlights und Badges fuer Schnittmarken aktualisieren
    updateCutUIControls();
}

function setupPlayerSync(player, segments) {
    let lastActiveIdx = -1;

    player.addEventListener('timeupdate', () => {
        const time = player.currentTime;
        const activeIdx = segments.findIndex(seg => time >= seg.start && time <= seg.end);
        
        if (activeIdx !== lastActiveIdx) {
            if (lastActiveIdx !== -1) {
                const prevEl = document.getElementById(`segment-${lastActiveIdx}`);
                if (prevEl) prevEl.classList.remove('active');
            }
            
            if (activeIdx !== -1) {
                const activeEl = document.getElementById(`segment-${activeIdx}`);
                if (activeEl) {
                    activeEl.classList.add('active');
                    activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
            
            lastActiveIdx = activeIdx;
        }
    });
}

// Binden von Event Listeners für Details Panel
// Falls die Python-API erst nach dem DOM bereitsteht: dann (erneut) laden.
window.addEventListener('pywebviewready', loadSettings);

document.addEventListener('DOMContentLoaded', () => {
    // Einstellungen laden (greift auf localStorage, falls API noch nicht bereit;
    // der pywebviewready-Listener lädt anschließend die Session-Werte aus Python).
    loadSettings();

    // Listeners for setting changes
    const idsToSave = ['source-lang', 'target-lang', 'model-size', 'output-dir-type', 'diarization-enable', 'speaker-count', 'docx-trans-mode'];
    idsToSave.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', saveSettings);
        }
    });

    // Zeitstempel-Modi (Mehrfachauswahl) speichern bei Änderung
    document.querySelectorAll('.timecode-mode').forEach(cb => {
        cb.addEventListener('change', saveSettings);
    });

    // Sidebar Ein-/Ausblenden
    const btnCollapse = document.getElementById('btn-collapse-sidebar');
    const btnExpand = document.getElementById('btn-expand-sidebar');
    const appContainer = document.querySelector('.app-container');
    
    if (btnCollapse && btnExpand && appContainer) {
        btnCollapse.addEventListener('click', () => {
            appContainer.classList.add('sidebar-collapsed');
            announce("Einstellungen ausgeblendet.");
        });
        btnExpand.addEventListener('click', () => {
            appContainer.classList.remove('sidebar-collapsed');
            announce("Einstellungen eingeblendet.");
        });
    }

    // Kino-Modus Umschalten
    const btnTheater = document.getElementById('btn-toggle-theater');
    const detailPanel = document.getElementById('detail-panel');
    if (btnTheater && detailPanel) {
        btnTheater.addEventListener('click', () => {
            const isActive = detailPanel.classList.toggle('theater-mode');
            btnTheater.classList.toggle('active', isActive);
            btnTheater.textContent = isActive ? "📽 Standard" : "📽 Kino-Modus";
            announce(isActive ? "Kino-Modus aktiviert." : "Standard-Modus aktiviert.");
        });
    }

    const closeDetailBtn = document.getElementById('close-detail-btn');
    if (closeDetailBtn) {
        closeDetailBtn.addEventListener('click', closeDetailPanel);
    }

    // Schnittmarken Buttons
    const btnIn = document.getElementById('btn-set-in');
    const btnOut = document.getElementById('btn-set-out');
    const btnAddCut = document.getElementById('btn-add-cut');
    const btnClear = document.getElementById('btn-clear-cut');
    const btnSaveProject = document.getElementById('btn-save-project');
    const btnUpdate = document.getElementById('btn-update-docx');
    
    if (btnIn) {
        btnIn.addEventListener('click', () => {
            const player = document.getElementById('media-player');
            if (player) {
                setInPoint(player.currentTime);
            }
        });
    }
    if (btnOut) {
        btnOut.addEventListener('click', () => {
            const player = document.getElementById('media-player');
            if (player) {
                setOutPoint(player.currentTime);
            }
        });
    }
    if (btnAddCut) {
        btnAddCut.addEventListener('click', addCut);
    }
    if (btnClear) {
        btnClear.addEventListener('click', () => {
            cutInTime = null;
            cutOutTime = null;
            if (currentPlayingFile) {
                currentPlayingFile.cuts = [];
            }
            renderCutList();
            updateCutUIControls();
            showCutMessage("Alle Schnitte gelöscht.", "success");
            announce("Alle Schnitte gelöscht.");
        });
    }
    if (btnSaveProject) {
        btnSaveProject.addEventListener('click', saveCurrentProject);
    }
    if (btnUpdate) {
        btnUpdate.addEventListener('click', () => {
            if (!currentPlayingFile) return;
            const cuts = currentPlayingFile.cuts || [];
            if (cuts.length === 0) {
                showCutMessage("Die Schnittliste ist leer. Bitte fügen Sie Schnitte hinzu.", "error");
                return;
            }
            
            showCutMessage("Aktualisiere Word-Dokument...", "");
            
            if (window.pywebview && window.pywebview.api) {
                const outputDirType = document.getElementById('output-dir-type').value;
                const customPath = customOutputPath;
                const targetLang = translateEnableCheckbox.checked ? targetLangSelect.value : null;
                const docxTransMode = document.getElementById('docx-trans-mode').value;
                const timecodeModes = getSelectedTimecodeModes();

                // Sende Array von [start, end] an Python
                const cutsData = cuts.map(c => [c.start, c.end]);

                window.pywebview.api.update_docx_with_cuts(
                    currentPlayingFile.path,
                    JSON.stringify(cutsData), // Als JSON stringifiziert
                    outputDirType,
                    customPath,
                    targetLang,
                    docxTransMode,
                    timecodeModes
                ).then(result => {
                    if (result && result.success) {
                        showCutMessage(`Erfolgreich erstellt: ${result.filename}`, "success");
                        announce(`Word-Dokument erfolgreich aktualisiert unter ${result.filename}`);
                    } else {
                        showCutMessage(`Fehler: ${result.error || 'Unbekannt'}`, "error");
                    }
                }).catch(err => {
                    console.error("Fehler bei update_docx_with_cuts:", err);
                    showCutMessage("Fehler beim Aufruf der Python-API.", "error");
                });
            } else {
                showCutMessage("Fehler: Keine App-Verbindung verfügbar.", "error");
            }
        });
    }

    const showBothBtn = document.getElementById('show-both-btn');
    const showOriginalBtn = document.getElementById('show-original-btn');
    const showTranslatedBtn = document.getElementById('show-translated-btn');

    if (showBothBtn && showOriginalBtn && showTranslatedBtn) {
        const langButtons = [
            [showBothBtn, 'both'],
            [showOriginalBtn, 'original'],
            [showTranslatedBtn, 'translated']
        ];

        function selectLanguage(mode) {
            currentTranscriptLanguage = mode;
            langButtons.forEach(([btn, btnMode]) => {
                const isActive = btnMode === mode;
                btn.classList.toggle('active', isActive);
                btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            });
            if (currentPlayingFile) renderTranscriptSegments(currentPlayingFile);
        }

        langButtons.forEach(([btn, btnMode]) => {
            btn.addEventListener('click', () => selectLanguage(btnMode));
        });
    }
});
