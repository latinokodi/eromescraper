'use strict';

/**
 * Nebula Erome PRO - UI Controller
 * Refactored for FastAPI backend with WebSocket progress updates.
 */

// --- State Management ---

const state = {
    currentMedia: [],
    activeTasks: new Map(),
    taskToAlbum: new Map(),
    albums: new Map(),
    downloadTotal: 0,
    downloadDone: 0,
    globalGridCounter: 0,
    currentAlbumTitle: null,
    ws: null,
    wsReconnectTimer: null,
    pendingConflict: null,
    itemProgress: new Map() // Fractional progress for active downloads
};

// --- DOM Elements ---

const elements = {
    urlInput: document.getElementById('urlInput'),
    scrapeBtn: document.getElementById('scrapeBtn'),
    downloadBtn: document.getElementById('downloadBtn'),

    viewDashboard: document.getElementById('view-dashboard'),
    viewGrabber: document.getElementById('view-grabber'),
    viewConsole: document.getElementById('view-console'),
    mediaGrid: document.getElementById('mediaGrid'),
    logContainer: document.getElementById('logContainer'),

    albumTitle: document.getElementById('albumTitle'),
    mediaCount: document.getElementById('mediaCount'),
    statusText: document.getElementById('statusText'),
    progressPct: document.getElementById('progressPct'),
    overallProgress: document.getElementById('overallProgress'),
    folderPath: document.getElementById('folderPath'),

    toggleVideo: document.getElementById('toggleVideo'),
    toggleImage: document.getElementById('toggleImage'),

    navDashboard: document.getElementById('nav-dashboard'),
    navGrabber: document.getElementById('nav-grabber'),
    navConsole: document.getElementById('nav-console'),

    appSidebar: document.getElementById('appSidebar')
};

// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
    log("System Initialized. Connecting to server...", "info");

    // Connect WebSocket
    connectWebSocket();

    // Sync clock
    setInterval(() => {
        const now = new Date();
        const timestr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        const sysTime = document.getElementById('sysTime');
        if (sysTime) sysTime.textContent = timestr;
    }, 1000);

    // Load settings
    await loadSettings();
});

// --- WebSocket Connection ---

function connectWebSocket() {
    const wsUrl = `ws://${location.host}/ws/progress`;
    log(`Connecting to WebSocket: ${wsUrl}`, "info");

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        log("WebSocket connected", "success");
        if (state.wsReconnectTimer) {
            clearTimeout(state.wsReconnectTimer);
            state.wsReconnectTimer = null;
        }
    };

    state.ws.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };

    state.ws.onclose = () => {
        log("WebSocket disconnected. Reconnecting...", "error");
        // Attempt reconnect after 2 seconds
        if (!state.wsReconnectTimer) {
            state.wsReconnectTimer = setTimeout(() => {
                state.wsReconnectTimer = null;
                connectWebSocket();
            }, 2000);
        }
    };

    state.ws.onerror = (error) => {
        log("WebSocket error", "error");
        console.error('WebSocket error:', error);
    };
}

function handleWebSocketMessage(message) {
    const { type, data } = message;

    switch (type) {
        case 'progress':
            updateItemProgress(data);
            break;

        case 'album_info':
            elements.albumTitle.textContent = data.name;
            state.currentAlbumTitle = data.name;
            log(`Album: ${data.name} (${data.count} items)`, "info");
            break;

        case 'file_start':
            log(`Starting: ${data.filename}`, "info");
            break;

        case 'file_complete':
            if (data.error) {
                log(`Error: ${data.filename} - ${data.error}`, "error");
            } else {
                log(`Complete: ${data.filename}`, "success");
            }
            handleDownloadComplete(data);
            break;

        case 'media_added':
            handleMediaAdded(data.items);
            break;

        default:
            console.log('Unknown message type:', type, data);
    }
}

function sendWebSocketMessage(message) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(message));
    }
}

// --- Tab Management ---

function switchTab(tab) {
    const views = ['dashboard', 'grabber', 'console'];

    views.forEach(v => {
        const viewEl = document.getElementById(`view-${v}`);
        const navEl = document.getElementById(`nav-${v}`);
        if (viewEl) viewEl.classList.toggle('active', v === tab);
        if (navEl) navEl.classList.toggle('active', v === tab);
    });
}

function toggleSidebar() {
    elements.appSidebar.classList.toggle('collapsed');
    const icon = elements.appSidebar.querySelector('#toggleSidebar i');
    if (elements.appSidebar.classList.contains('collapsed')) {
        icon.className = 'fa-solid fa-angles-right';
    } else {
        icon.className = 'fa-solid fa-bars-staggered';
    }
}

// --- Console Log ---

function log(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = 'log-entry';

    const now = new Date();
    const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;

    entry.innerHTML = `<span class="log-time">${timeStr}</span> <span class="log-msg ${type}">${message}</span>`;
    elements.logContainer.appendChild(entry);
    elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
}

// --- Settings ---

async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        if (response.ok) {
            const settings = await response.json();
            elements.folderPath.textContent = settings.download_folder || 'downloads';
            elements.toggleVideo.checked = true; // Always true in Video-Only Mode
        }
    } catch (e) {
        log("Failed to load settings", "error");
    }
}

// --- Scrape Logic ---

async function scrapeUrl() {
    const url = elements.urlInput.value.trim();
    if (!url || !url.includes('erome.com')) {
        return log("Invalid URL. Please enter a valid Erome album link.", "error");
    }

    elements.scrapeBtn.disabled = true;
    elements.scrapeBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> SCANNING...';

    // No longer resetting state.currentMedia or clearing grid manually
    // The "empty-state" will be cleared inside addGridItem
    
    elements.mediaCount.textContent = 'Scanning assets...';
    // Let's not clear the album title if there are already items, keep context or update?
    // User wants to add MORE, so we append.

    log(`Initializing scan for: ${url}`, 'info');

    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        const result = await response.json();

        if (result.success && result.album) {
            const album = result.album;
            
            // Separate albums with a title update or keep a global count?
            elements.albumTitle.textContent = "Multi-Album View"; 
            state.currentAlbumTitle = album.title;

            // Add media items to grid with deduplication
            let newItems = [];
            album.media.forEach((item) => {
                // Deduplicate by URL
                const exists = state.currentMedia.some(m => m.url === item.url);
                if (!exists) {
                    item.gridUid = state.globalGridCounter;
                    state.currentMedia.push(item);
                    addGridItem(item, state.globalGridCounter);
                    state.globalGridCounter++;
                    newItems.push(item);
                }
            });

            updateStatsUI();
            
            if (newItems.length > 0) {
                // Check if folder existed already
                if (result.folder_exists) {
                    log(`Conflict: Folder '${album.title}' exists. Prompting user...`, 'warn');
                    state.pendingConflict = { album, items: newItems };
                    showConflictModal(album.title);
                } else {
                    log(`Added and enqueued ${newItems.length} new assets from: ${album.title}`, 'success');
                    // Automatically start downloading new items
                    startDownload(newItems);
                }
            } else {
                log(`Scan finished. No new assets found in: ${album.title}`, 'info');
            }
        } else {
            log(`Scrape failed: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (e) {
        log(`Scrape error: ${e.message}`, 'error');
    } finally {
        elements.scrapeBtn.disabled = false;
        elements.scrapeBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> SCRAPE';
        elements.urlInput.value = ''; // Clear input for next album
        updateDownloadButton();
    }
}

// --- Asset Grid Logic ---

function addGridItem(item, index) {
    // Remove empty state
    const empty = elements.mediaGrid.querySelector('.empty-state');
    if (empty) empty.remove();

    const div = document.createElement('div');
    div.className = 'grid-item selected fade-in';
    div.dataset.filename = item.filename;
    div.dataset.album = elements.albumTitle.textContent;

    const icon = item.type === 'video' ? 'fa-video' : 'fa-image';
    const color = item.type === 'video' ? 'var(--neon-red)' : 'var(--neon-purple)';

    const thumbHtml = item.thumbnail
        ? `<img src="${item.thumbnail}" loading="lazy" style="width:100%; height:100%; object-fit:cover;">`
        : `<div style="background: #111; width:100%; height:100%; display:flex; align-items:center; justify-content:center;">
             <i class="fa-solid ${icon}" style="font-size: 2rem; color: ${color}; opacity: 0.3;"></i>
           </div>`;

    div.innerHTML = `
        <div class="thumb-wrapper">
            ${thumbHtml}
            <div class="progress-overlay">
                <div class="item-progress-bar-bg">
                    <div class="item-progress-fill"></div>
                </div>
                <div class="item-progress-info">
                    <span class="item-progress-text">0%</span>
                    <span class="item-size">-- MB</span>
                    <span class="item-progress-speed">0 KB/s</span>
                </div>
                <div class="thumbnail-cancel" onclick="event.stopPropagation(); cancelItem('${item.filename}')" title="Cancel Download">
                    STOP DOWNLOAD
                </div>
            </div>
        </div>
        <div class="type-badge" style="background: ${color}">${item.type}</div>
        <div class="item-meta" title="${item.filename}">${item.filename}</div>
        <div class="checkbox-overlay">
            <input type="checkbox" checked onclick="event.stopPropagation(); updateSelection('${item.filename}')">
        </div>
    `;

    div.onclick = (e) => {
        if (e.target.tagName !== 'INPUT' && !e.target.classList.contains('thumbnail-cancel')) {
            const chk = div.querySelector('input[type="checkbox"]');
            chk.checked = !chk.checked;
            updateSelection(item.filename);
        }
    };

    elements.mediaGrid.appendChild(div);
}

function updateSelection(filename) {
    const div = getItemByFilename(filename);
    if (!div) return;
    const chk = div.querySelector('input[type="checkbox"]');
    if (chk.checked) div.classList.add('selected');
    else div.classList.remove('selected');
    updateDownloadButton();
}

function updateStatsUI() {
    elements.mediaCount.textContent = `${state.currentMedia.length} DETECTED ASSETS`;
}

function updateDownloadButton() {
    const count = document.querySelectorAll('.grid-item.selected:not([style*="display: none"])').length;
    elements.downloadBtn.disabled = count === 0;
    elements.downloadBtn.innerHTML = `<i class="fa-solid fa-download"></i> DOWNLOAD (${count})`;
}

// --- Download Logic ---

async function startDownload(itemsToDownload = null) {
    // Get items for download (either specific list or all selected from grid)
    const selected = itemsToDownload || state.currentMedia.filter((item) => {
        const div = getItemByFilename(item.filename);
        return div && div.classList.contains('selected');
    });

    const albumName = state.currentAlbumTitle || 'Unknown Album';

    if (selected.length === 0) return;

    state.downloadTotal += selected.length;
    if (state.activeTasks.size === 0) {
        state.downloadDone = 0;
    }

    log(`Enqueuing ${selected.length} items for download...`, 'info');
    elements.statusText.textContent = "QUEUING...";
    elements.downloadBtn.disabled = true;

    // Track this album
    if (!state.albums.has(albumName)) {
        state.albums.set(albumName, { done: 0, total: selected.length, pct: 0 });
    } else {
        const album = state.albums.get(albumName);
        album.total += selected.length;
    }

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: selected,
                album_name: albumName,
                max_concurrent: 5
            })
        });

        const result = await response.json();

        if (result.success) {
            log(`Download started: ${result.queued_count} items`, 'success');
        } else {
            log(`Download failed: ${result.error}`, 'error');
        }
    } catch (e) {
        log(`Download error: ${e.message}`, 'error');
    }
}

function handleMediaAdded(items) {
    if (!items || !items.length) return;
    
    // Increment total for global progress tracking
    state.downloadTotal += items.length;
    updateOverallProgress();

    items.forEach(item => {
        // Prevent duplicate grid items
        if (!getItemByFilename(item.filename)) {
            item.gridUid = state.globalGridCounter++;
            state.currentMedia.push(item);
            addGridItem(item, item.gridUid);
            
            // Re-mark as active if it was restored from queue
            const div = getItemByFilename(item.filename);
            if (div) {
                div.classList.add('downloading');
                div.classList.remove('selected');
            }
        }
    });
    
    updateStatsUI();
    updateDownloadButton();
    log(`Restored ${items.length} items to grid`, 'info');
}

function updateItemProgress(data) {
    const gridItem = getItemByFilename(data.filename);

    if (gridItem) {
        gridItem.classList.add('downloading');
        gridItem.classList.remove('selected');
        const fill = gridItem.querySelector('.item-progress-fill');
        const text = gridItem.querySelector('.item-progress-text');
        const speed = gridItem.querySelector('.item-progress-speed');
        const size = gridItem.querySelector('.item-size');

        if (fill) {
            fill.style.width = data.total > 0 ? `${data.percent}%` : '100%';
            if (data.total === 0) {
                fill.classList.add('indeterminate');
            } else {
                fill.classList.remove('indeterminate');
            }
        }
        
        if (text) text.textContent = data.total > 0 ? `${data.percent}%` : '--%';
        if (size && data.total) {
            size.textContent = formatBytes(data.total);
        }
        if (speed && data.speed !== undefined) {
            speed.textContent = formatSpeed(data.speed);
        }
        // Update tracking map for overall progress
        state.itemProgress.set(data.filename, data.percent);

        updateOverallProgress();
    }
}

function updateOverallProgress() {
    if (state.downloadTotal === 0) return;

    // Calculate overall percentage:
    // (completed_files * 100 + sum_of_active_file_percents) / total_files
    let sumActive = 0;
    state.itemProgress.forEach((pct) => sumActive += pct);
    
    const pct = Math.min(100, Math.round(((state.downloadDone * 100) + sumActive) / state.downloadTotal));

    elements.overallProgress.style.width = `${pct}%`;
    elements.progressPct.textContent = `${pct}%`;
    elements.statusText.textContent = `DOWNLOADING... (${state.downloadDone}/${state.downloadTotal})`;
}

function handleDownloadComplete(data) {
    // Remove from active progress tracking
    state.itemProgress.delete(data.filename);
    
    state.downloadDone = Math.min(state.downloadTotal, state.downloadDone + 1);
    updateOverallProgress();

    // Update album state
    if (state.currentAlbumTitle && state.albums.has(state.currentAlbumTitle)) {
        const album = state.albums.get(state.currentAlbumTitle);
        album.done++;
        album.pct = Math.round((album.done / album.total) * 100);
    }

    // Remove completed items from grid using filename as identifier
    const gridItem = getItemByFilename(data.filename);
    if (gridItem) {
        // Only remove if successful (no error)
        if (!data.error) {
            gridItem.remove();
            
            // Remove from state to keep things synchronized
            const index = state.currentMedia.findIndex(m => m.filename === data.filename);
            if (index >= 0) {
                state.currentMedia.splice(index, 1);
            }
            updateStatsUI();
            updateDownloadButton();
            
            log(`Finished: ${data.filename}`, "success");
        } else {
            gridItem.classList.remove('downloading');
            gridItem.classList.add('error');
            log(`Failed: ${data.filename} - ${data.error}`, "error");
        }
    }

    if (state.downloadDone >= state.downloadTotal) {
        elements.statusText.textContent = "BATCH COMPLETE";
        elements.downloadBtn.disabled = false;
        log(`Batch finished: ${state.downloadDone} items processed.`, 'success');
    }
}

// --- Folder Management ---

async function selectFolder() {
    // Removed: Destination is now hardcoded to 'downloads' per USER request
}

function openFolder() {
    // Open the downloads folder in file manager
    // This requires a desktop integration
    log("Opening downloads folder...", "info");
    window.open(`/api/open-folder`, '_blank');
}

// --- Cancel ---

function cancelItem(filename) {
    const div = getItemByFilename(filename);
    if (!div) return;

    log(`Stopping download: ${filename}...`, 'info');
    
    // Tell backend to stop and delete
    sendWebSocketMessage({
        type: 'cancel',
        data: { filename }
    });

    div.classList.remove('downloading');
    div.classList.remove('selected');
    const overlay = div.querySelector('.progress-overlay');
    if (overlay) overlay.style.display = 'none';

    updateDownloadButton();
}

// --- Modal Handlers ---

function showConflictModal(folderName) {
    document.getElementById('conflict-folder-name').textContent = folderName;
    document.getElementById('modal-overlay').classList.add('active');
}

function resolveConflict(choice) {
    document.getElementById('modal-overlay').classList.remove('active');
    
    if (!state.pendingConflict) return;
    const { album, items } = state.pendingConflict;
    state.pendingConflict = null;

    if (choice === 'cancel') {
        log("Operation cancelled by user.", "info");
        return;
    }

    const handleProceed = () => {
        log(`Proceeding with download (${choice})...`, 'info');
        startDownload(items);
    };

    if (choice === 'overwrite') {
        log(`Overwriting existing album: ${album.title}...`, 'warn');
        fetch('/api/delete-album', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ album_name: album.title })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                log("Old folder deleted. Starting fresh.", "success");
                handleProceed();
            } else {
                log(`Failed to delete folder: ${data.error}. Downloading anyway.`, "error");
                handleProceed();
            }
        })
        .catch(err => {
            log(`Error deleting folder: ${err.message}`, "error");
            handleProceed();
        });
    } else {
        // choice === 'skip'
        log("Skipping existing files. Resuming missing assets.", "info");
        handleProceed();
    }
}

// --- Utility Functions ---

function formatSpeed(bytesPerSec) {
    if (bytesPerSec === 0) return '0 KB/s';
    const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
    let i = 0;
    while (bytesPerSec >= 1024 && i < units.length - 1) {
        bytesPerSec /= 1024;
        i++;
    }
    return `${bytesPerSec.toFixed(1)} ${units[i]}`;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return `${bytes.toFixed(1)} ${units[i]}`;
}
/**
 * Safely finds a grid item by its filename, escaping special characters for CSS selectors.
 */
function getItemByFilename(filename) {
    if (!filename) return null;
    // Escape double quotes in the filename attribute selector
    const escaped = filename.replace(/"/g, '\\"');
    // Use 'i' flag for case-insensitive matching
    return document.querySelector(`[data-filename="${escaped}" i]`);
}
