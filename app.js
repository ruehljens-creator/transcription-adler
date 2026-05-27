// File Queue State
let fileQueue = [];
let isProcessing = false;

// DOM Elements
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

// Toggle target language selection depending on translation enabled state
translateEnableCheckbox.addEventListener('change', () => {
    if (translateEnableCheckbox.checked) {
        targetLangWrapper.classList.remove('disabled');
        targetLangSelect.removeAttribute('disabled');
    } else {
        targetLangWrapper.classList.add('disabled');
        targetLangSelect.setAttribute('disabled', 'true');
    }
});

// Setup drag and drop UI visual cues (actual drop event is intercepted by Python)
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

// Browse Files Button (Fallback)
browseBtn.addEventListener('click', () => {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.select_files().then(paths => {
            if (paths && paths.length > 0) {
                paths.forEach(path => addFileToQueue(path));
            }
        });
    }
});

// Clear queue button
clearBtn.addEventListener('click', () => {
    if (isProcessing) return;
    fileQueue = [];
    renderQueue();
    updateStartButtonState();
});

// Function called by Python on dropping files
window.addFileFromPython = function(filePath) {
    addFileToQueue(filePath);
};

// Add file to the queue and fetch metadata
function addFileToQueue(filePath) {
    // Prevent duplicate entries in queue
    if (fileQueue.some(file => file.path === filePath)) {
        return;
    }

    const filename = filePath.split('/').pop().split('\\').pop(); // Handle Mac/Windows paths
    const newFile = {
        path: filePath,
        name: filename,
        duration: "Warte...",
        creationDate: "Warte...",
        location: "Warte...",
        mapsLink: null,
        status: "queued", // queued, processing, completed, failed
        progress: 0,
        statusMsg: "Wartend in Schlange"
    };

    fileQueue.push(newFile);
    renderQueue();
    updateStartButtonState();

    // Query python for metadata in the background
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_file_metadata(filePath).then(meta => {
            updateFileMetadata(filePath, meta);
        }).catch(err => {
            console.error("Error loading metadata:", err);
            updateFileMetadata(filePath, { error: true });
        });
    }
}

// Update file properties in queue once metadata is extracted
function updateFileMetadata(filePath, meta) {
    const file = fileQueue.find(f => f.path === filePath);
    if (!file) return;

    if (meta.error) {
        file.duration = "Unbekannt";
        file.creationDate = "Unbekannt";
        file.location = "Keine";
    } else {
        file.duration = meta.duration_str || "Unbekannt";
        file.creationDate = meta.creation_date || "Unbekannt";
        if (meta.gps && meta.gps.address) {
            file.location = meta.gps.address;
            file.mapsLink = meta.maps_link;
        } else {
            file.location = "Keine GPS-Daten";
        }
    }

    // Refresh row in table
    renderQueue();
}

// Render queue to DOM table
function renderQueue() {
    // Update badge count
    queueCountBadge.textContent = `${fileQueue.length} ${fileQueue.length === 1 ? 'Clip' : 'Clips'}`;
    
    // Clear list
    queueTbody.innerHTML = '';

    if (fileQueue.length === 0) {
        clearBtn.style.display = 'none';
        queueTbody.innerHTML = `
            <tr id="empty-state">
                <td colspan="5" class="empty-text">
                    Keine Dateien in der Warteschlange. Ziehe Dateien in den oberen Bereich, um sie hinzuzufügen.
                </td>
            </tr>
        `;
        return;
    }

    clearBtn.style.display = isProcessing ? 'none' : 'block';

    fileQueue.forEach(file => {
        const tr = document.createElement('tr');
        
        // 1. Filename Cell
        const tdName = document.createElement('td');
        tdName.className = 'filename-cell';
        tdName.textContent = file.name;
        tdName.title = file.path; // Tooltip shows full path
        tr.appendChild(tdName);

        // 2. Duration Cell
        const tdDuration = document.createElement('td');
        tdDuration.textContent = file.duration;
        tr.appendChild(tdDuration);

        // 3. Creation Date Cell
        const tdDate = document.createElement('td');
        tdDate.textContent = file.creationDate;
        tr.appendChild(tdDate);

        // 4. Location Metadata Cell
        const tdLoc = document.createElement('td');
        if (file.mapsLink) {
            const a = document.createElement('a');
            a.className = 'location-link';
            a.href = '#';
            a.innerHTML = `📍 ${file.location}`;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                if (window.pywebview && window.pywebview.api && file.mapsLink) {
                    // Open link in external default browser
                    window.pywebview.api.window.evaluate_js(`window.open('${file.mapsLink}', '_blank')`);
                }
            });
            tdLoc.appendChild(a);
        } else {
            tdLoc.textContent = file.location;
        }
        tr.appendChild(tdLoc);

        // 5. Status & Progress Cell
        const tdStatus = document.createElement('td');
        const badge = document.createElement('div');
        badge.className = `status-badge ${file.status}`;
        
        let statusHtml = '';
        if (file.status === 'queued') {
            statusHtml = `⏳ Wartend`;
        } else if (file.status === 'processing') {
            statusHtml = `⚙️ ${file.progress}%`;
        } else if (file.status === 'completed') {
            statusHtml = `✅ Fertig`;
        } else if (file.status === 'failed') {
            statusHtml = `❌ Fehler`;
        }
        
        badge.innerHTML = statusHtml;
        tdStatus.appendChild(badge);

        // Add a progress bar under badge if processing
        if (file.status === 'processing') {
            const barContainer = document.createElement('div');
            barContainer.className = 'progress-bar-container';
            const fill = document.createElement('div');
            fill.className = 'progress-bar-fill';
            fill.style.width = `${file.progress}%`;
            barContainer.appendChild(fill);
            tdStatus.appendChild(barContainer);
        }

        // Small detail label under status
        if (file.statusMsg && file.status !== 'queued') {
            const msgLabel = document.createElement('div');
            msgLabel.style.fontSize = '10px';
            msgLabel.style.color = 'var(--text-muted)';
            msgLabel.style.marginTop = '4px';
            msgLabel.textContent = file.statusMsg;
            tdStatus.appendChild(msgLabel);
        }

        tr.appendChild(tdStatus);
        queueTbody.appendChild(tr);
    });
}

function updateStartButtonState() {
    // Only enable if files are in queue and not currently processing
    const hasFiles = fileQueue.length > 0;
    if (hasFiles && !isProcessing) {
        startBtn.removeAttribute('disabled');
    } else {
        startBtn.setAttribute('disabled', 'true');
    }
}

// Start Transcription triggered from Button click
startBtn.addEventListener('click', () => {
    if (isProcessing || fileQueue.length === 0) return;

    const sourceLang = sourceLangSelect.value;
    const targetLang = translateEnableCheckbox.checked ? targetLangSelect.value : null;
    const modelSize = modelSizeSelect.value;

    isProcessing = true;
    updateStartButtonState();
    clearBtn.style.display = 'none';

    // Set all queued files to processing state
    fileQueue.forEach(f => {
        if (f.status !== 'completed') {
            f.status = 'processing';
            f.progress = 0;
            f.statusMsg = 'Initialisiere...';
        }
    });
    renderQueue();

    // Call Python api
    const paths = fileQueue.map(f => f.path);
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.start_transcription(paths, sourceLang, targetLang, modelSize);
    }
});

// Progress callback invoked by Python thread
window.onFileProgress = function(filePath, percent, statusMsg) {
    const file = fileQueue.find(f => f.path === filePath);
    if (!file) return;

    if (percent === 100) {
        file.status = 'completed';
        file.progress = 100;
        file.statusMsg = statusMsg || 'Abgeschlossen';
    } else if (percent === -1) {
        file.status = 'failed';
        file.progress = 0;
        file.statusMsg = statusMsg || 'Fehlgeschlagen';
    } else {
        file.status = 'processing';
        file.progress = percent;
        file.statusMsg = statusMsg || 'Verarbeite...';
    }

    renderQueue();

    // Check if everything in the queue has finished
    const stillRunning = fileQueue.some(f => f.status === 'processing');
    if (!stillRunning) {
        isProcessing = false;
        updateStartButtonState();
        clearBtn.style.display = 'block';
    }
};
