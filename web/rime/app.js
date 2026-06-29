// Configuration and state are now in separate modules (js/config.js and js/state.js)

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeMap();
    initializeEventListeners();
    fetchThings();
});

// Initialize Leaflet map
function initializeMap() {
    state.map = L.map('map', {
        zoomAnimation: true,
        zoomAnimationThreshold: 4, // Animate zoom if difference is less than 4 levels
        fadeAnimation: true,
        markerZoomAnimation: true,
        zoomControl: true,
        doubleClickZoom: true,
        scrollWheelZoom: true
    }).setView([52.00482, 4.37034], 13);

    // Modern basemaps (CARTO + Esri imagery) with a tasteful default
    const voyager = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
        updateWhenZooming: true
    });

    const positron = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    });

    const darkMatter = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    });

    const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
        maxZoom: 19
    });

    satellite.addTo(state.map);

    L.control.layers({
        'Satellite': satellite,
        'Dark': darkMatter,
        'Streets': voyager,
        'Light': positron,
    }, null, { position: 'topright', collapsed: true }).addTo(state.map);

    // Initialize marker cluster group
    state.markerCluster = L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 80, // Cluster markers within 80 pixels
        disableClusteringAtZoom: 15, // Only show individual markers at zoom 15+
        spiderfyOnMaxZoom: false, // Don't spiderfy, just zoom
        showCoverageOnHover: true, // Show circle indicating cluster area on hover
        zoomToBoundsOnClick: true, // Zoom to bounds when clicking cluster
        animate: true, // Animate marker clustering/unclustering
        animateAddingMarkers: true, // Animate when adding markers
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();

            if (count > state.maxClusterSize) {
                state.maxClusterSize = count;
            }

            // Cluster glow scales cyan -> indigo with group size
            const maxCount = Math.max(state.maxClusterSize, 10);
            const normalized = Math.min(Math.log(count + 1) / Math.log(maxCount + 1), 1);
            // Cyan-400 (#22d3ee) -> Indigo-400 (#818cf8)
            const red = Math.round(34 + (129 - 34) * normalized);
            const green = Math.round(211 - (211 - 140) * normalized);
            const blue = Math.round(238 + (248 - 238) * normalized);
            const color = `rgb(${red}, ${green}, ${blue})`;

            let size = 'small';
            let iconSize = 40;
            if (count > 100) {
                size = 'large';
                iconSize = 60;
            } else if (count > 10) {
                size = 'medium';
                iconSize = 50;
            }

            return L.divIcon({
                html: `<div style="background-color: ${color};"><span>${count}</span></div>`,
                className: 'marker-cluster marker-cluster-' + size,
                iconSize: L.point(iconSize, iconSize)
            });
        }
    });

    state.map.addLayer(state.markerCluster);
    
    // Handle cluster click to zoom to cluster extents
    state.markerCluster.on('clusterclick', function(a) {
        const cluster = a.layer;
        const bounds = cluster.getBounds();
        
        // Zoom to cluster bounds with animation
        state.map.fitBounds(bounds, {
            animate: true,
            duration: 0.8,
            padding: [30, 30],
            maxZoom: 18
        });
    });
    
    updateStatus('Map initialized', 'success');
}

// Initialize event listeners
function initializeEventListeners() {
    // Search functionality
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        filterThings(e.target.value);
    });

    // Status legend filter chips
    document.querySelectorAll('.legend-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const filter = chip.dataset.filter;
            // Toggle off if the same chip is clicked again
            setStatusFilter(state.activeStatusFilter === filter ? 'all' : filter);
        });
    });

    // Endpoint switcher
    initializeEndpointSwitcher();

    // Roster collapse / reopen
    const appShell = document.querySelector('.app-shell');
    const rosterCollapse = document.getElementById('rosterCollapse');
    const rosterReopen = document.getElementById('rosterReopen');
    if (rosterCollapse && appShell) {
        rosterCollapse.addEventListener('click', () => {
            appShell.classList.add('roster-collapsed');
            setTimeout(() => state.map && state.map.invalidateSize(), 450);
        });
    }
    if (rosterReopen && appShell) {
        rosterReopen.addEventListener('click', () => {
            appShell.classList.remove('roster-collapsed');
            setTimeout(() => state.map && state.map.invalidateSize(), 450);
        });
    }

    // Chart panel toggle - only on header title area, not buttons
    const chartPanelTitle = document.querySelector('.chart-panel-title > div:not(.chart-panel-nav)');
    if (chartPanelTitle) {
        chartPanelTitle.addEventListener('click', (e) => {
            // Only toggle if clicking on the title text area, not on buttons
            if (!e.target.closest('button') && !e.target.closest('.chart-panel-nav')) {
                toggleChartPanel();
            }
        });
    }

    // Chart panel toggle button (separate handler)
    const chartPanelToggle = document.getElementById('chartPanelToggle');
    if (chartPanelToggle) {
        chartPanelToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleChartPanel();
        });
    }

    // Chart limit buttons
    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const limit = parseInt(e.target.dataset.limit || e.target.closest('button').dataset.limit);
            setChartLimit(limit);
        });
    });

    // Zoom extents button
    const zoomExtentsBtn = document.getElementById('zoomExtentsBtn');
    if (zoomExtentsBtn) {
        zoomExtentsBtn.addEventListener('click', zoomToExtents);
    }

    // Thing metadata sidebar close button
    const thingMetadataClose = document.getElementById('thingMetadataClose');
    if (thingMetadataClose) {
        thingMetadataClose.addEventListener('click', () => {
            hideThingMetadata();
        });
    }

    // Chart next datastream button
    const chartNextDatastreamBtn = document.getElementById('chartNextDatastreamBtn');
    if (chartNextDatastreamBtn) {
        chartNextDatastreamBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            navigateToDatastream(1);
        });
    }
}

// FROST-aware fetch wrapper -----------------------------------------------
// Injects Authorization header when read credentials are set.
function frostFetch(url, options = {}) {
    if (state.frostReadAuth) {
        options = {
            ...options,
            headers: {
                'Authorization': `Basic ${state.frostReadAuth}`,
                ...(options.headers || {}),
            },
        };
    }
    return fetch(url, options);
}

// Endpoint switcher -------------------------------------------------------

function initializeEndpointSwitcher() {
    const display      = document.getElementById('endpointDisplay');
    const popover      = document.getElementById('endpointPopover');
    const input        = document.getElementById('endpointInput');
    const applyBtn     = document.getElementById('endpointApply');
    const label        = document.getElementById('endpointLabel');
    const versionGroup = document.getElementById('endpointVersionGroup');
    const authToggle   = document.getElementById('endpointAuthToggle');
    const authFields   = document.getElementById('endpointAuthFields');
    const authChevron  = document.getElementById('endpointAuthChevron');
    const authToggleLabel = document.getElementById('endpointAuthToggleLabel');
    const usernameInput = document.getElementById('endpointUsername');
    const passwordInput = document.getElementById('endpointPassword');

    // ---- label pill ----
    function syncLabel() {
        // Show "host/path @ vX.X", strip protocol
        const host = state.frostBase.replace(/^https?:\/\//, '');
        label.textContent = `${host} @ ${state.frostVersion}`;
        display.classList.toggle('has-auth', !!state.frostReadAuth);
    }
    syncLabel();

    // ---- version button group ----
    function syncVersionButtons() {
        versionGroup.querySelectorAll('.endpoint-version-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.version === state.frostVersion);
        });
    }
    syncVersionButtons();

    versionGroup.addEventListener('click', (e) => {
        const btn = e.target.closest('.endpoint-version-btn');
        if (!btn) return;
        state.frostVersion = btn.dataset.version;
        syncVersionButtons();
    });

    // ---- quick-picks ----
    popover.querySelectorAll('.endpoint-quickpick').forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = btn.dataset.base;
            input.focus();
        });
    });

    // ---- credentials toggle ----
    authToggle.addEventListener('click', () => {
        const isOpen = !authFields.hidden;
        authFields.hidden = isOpen;
        authChevron.style.transform = isOpen ? '' : 'rotate(180deg)';
        authToggleLabel.textContent = isOpen ? 'Add credentials' : 'Hide credentials';
        if (!isOpen) usernameInput.focus();
    });

    // ---- open / close popover ----
    function openPopover() {
        // Strip any trailing version segment the user may have left in the URL
        input.value = state.frostBase;
        syncVersionButtons();

        if (state.frostReadAuth) {
            try {
                const decoded = atob(state.frostReadAuth);
                const colon = decoded.indexOf(':');
                usernameInput.value = decoded.substring(0, colon);
                passwordInput.value = decoded.substring(colon + 1);
            } catch (_) {}
            authFields.hidden = false;
            authChevron.style.transform = 'rotate(180deg)';
            authToggleLabel.textContent = 'Hide credentials';
        }
        popover.hidden = false;
        display.classList.add('active');
        input.focus();
        input.select();
    }

    function closePopover() {
        popover.hidden = true;
        display.classList.remove('active');
    }

    display.addEventListener('click', (e) => {
        e.stopPropagation();
        popover.hidden ? openPopover() : closePopover();
    });

    document.addEventListener('click', (e) => {
        if (!document.getElementById('endpointSwitcher').contains(e.target)) {
            closePopover();
        }
    });

    // ---- apply ----
    function applyEndpoint() {
        // Strip trailing slashes and any version suffix the user may have typed
        let raw = input.value.trim().replace(/\/+$/, '');
        // If they accidentally included a version suffix (/v1, /v1.1, /v2) strip it
        raw = raw.replace(/\/(v\d+(\.\d+)?)$/i, '');
        if (!raw) { closePopover(); return; }

        const user = usernameInput.value.trim();
        const pass = passwordInput.value;
        const newAuth = (user || pass) ? btoa(`${user}:${pass}`) : null;

        const authChanged = newAuth !== state.frostReadAuth;

        const prevRoot = state.frostRoot;
        state.frostBase    = raw;
        // frostVersion was already updated live by the button group
        state.frostReadAuth = newAuth;
        const newRoot = state.frostRoot;

        syncLabel();
        closePopover();

        if (prevRoot !== newRoot || authChanged) {
            resetAndReload();
        }
    }

    applyBtn.addEventListener('click', applyEndpoint);
    [input, usernameInput, passwordInput].forEach(el => {
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') applyEndpoint();
            if (e.key === 'Escape') closePopover();
        });
    });
}

// Clear all sensor state and re-fetch from the current state.frostRoot
function resetAndReload() {
    // Cancel any in-flight viewport health refresh
    if (state.healthRefreshTimer) {
        clearInterval(state.healthRefreshTimer);
        state.healthRefreshTimer = null;
    }
    if (state._moveendHandler) {
        state.map.off('moveend', state._moveendHandler);
        state._moveendHandler = null;
    }
    if (_moveendDebounceTimer) {
        clearTimeout(_moveendDebounceTimer);
        _moveendDebounceTimer = null;
    }

    // Close any open panels
    hideThingMetadata();
    const chartPanel = document.getElementById('chartPanel');
    if (chartPanel) chartPanel.classList.remove('expanded');

    // Destroy existing chart
    if (state.currentChart) {
        state.currentChart.destroy();
        state.currentChart = null;
    }

    // Clear all markers from the cluster layer and map
    if (state.markerCluster) {
        state.markerCluster.clearLayers();
    }

    // Reset state collections
    state.things = {};
    state.thingsByName = {};
    state.markers = {};
    state.currentDatastream = null;
    state.currentThingDatastreams = [];
    state.currentDatastreamIndex = -1;
    state.selectedThingId = null;
    state.maxClusterSize = 1;
    state.searchQuery = '';
    state.activeStatusFilter = 'all';

    // Reset UI
    document.getElementById('thingsList').innerHTML = '';
    document.getElementById('chartPanelContent').innerHTML = `
        <div class="no-data-message">
            <div class="no-data-icon" aria-hidden="true">
                <svg viewBox="0 0 48 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M1 12h7l3-9 5 18 4-13 3 7h6l3-4 4 4h8" />
                </svg>
            </div>
            <h3>No signal locked</h3>
            <p>Select a datastream from a node to trace its time series</p>
        </div>`;
    document.getElementById('chartTitle').textContent = 'No signal locked';
    document.getElementById('chartSubtitle').textContent = 'Select a datastream from a node to trace it';
    document.getElementById('chartNextDatastreamBtn').style.display = 'none';
    document.getElementById('searchInput').value = '';
    document.querySelectorAll('.legend-chip').forEach(c => c.classList.remove('active'));
    document.querySelector('.legend-chip[data-filter="all"]')?.classList.add('active');
    ['countTotal', 'countActive', 'countWarning', 'countDown'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '0';
    });

    fetchThings();
}

// Update status message
function updateStatus(message, type = '') {
    const statusEl = document.getElementById('statusMessage');
    statusEl.className = `status-message ${type}`;
    statusEl.innerHTML = '<span class="status-dot"></span>';
    statusEl.appendChild(document.createTextNode(message));
}

// Status colour palette shared by markers + UI (tuned for the dark stage)
const STATUS_COLORS = {
    active: '#34d399',
    warning: '#fbbf24',
    down: '#fb7185',
    selected: '#22d3ee',
    unknown: '#6b7c93'
};

function getStatusColor(status) {
    return STATUS_COLORS[status] || STATUS_COLORS.unknown;
}

// Build a status-aware map marker icon
function makePinIcon(status, isSelected) {
    const color = isSelected ? STATUS_COLORS.selected : getStatusColor(status);
    const classes = ['rime-pin'];
    if (isSelected) classes.push('selected');
    if (status === 'active' && !isSelected) classes.push('pulse');
    return L.divIcon({
        className: 'custom-marker',
        html: `<div class="${classes.join(' ')}" style="position:relative;background:${color};color:${color};"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
    });
}

// Calculate thing health status asynchronously
async function calculateThingHealthStatusAsync(thingId, datastreams, gen = state.fetchGeneration) {
    if (state.fetchGeneration !== gen) return;
    const thing = state.things[thingId];
    if (!thing || !datastreams || datastreams.length === 0) {
        if (thing) {
            thing.healthStatus = 'active';
            thing.timeSinceLastObservation = null;
            updateThingStatusTags();
        }
        return;
    }
    
    // Fetch last observations for all datastreams in parallel
    const currentProtocol = window.location.protocol;
    const observationPromises = datastreams.map(async (ds) => {
        try {
            const obsUrl = ds['Observations@iot.navigationLink'] + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await frostFetch(secureObsUrl);
            const obsData = await obsResponse.json();
            
            if (obsData.value && obsData.value.length > 0) {
                return new Date(obsData.value[0].phenomenonTime);
            }
            return null;
        } catch (error) {
            console.warn(`Error fetching last observation for datastream ${ds['@iot.id']}:`, error);
            return null;
        }
    });
    
    const observationTimes = await Promise.all(observationPromises);
    if (state.fetchGeneration !== gen) return;
    
    // Find the most recent observation
    const validTimes = observationTimes.filter(t => t !== null);
    let mostRecentTime = null;
    
    if (validTimes.length > 0) {
        mostRecentTime = new Date(Math.max(...validTimes.map(t => t.getTime())));
    }
    
    if (mostRecentTime) {
        const now = new Date();
        const timeDiffMinutes = (now - mostRecentTime) / (1000 * 60);
        thing.timeSinceLastObservation = timeDiffMinutes;
        const healthInfo = calculateThingHealthStatus(timeDiffMinutes);
        thing.healthStatus = healthInfo.status;
        thing.healthLabel = healthInfo.label;
    } else {
        thing.timeSinceLastObservation = null;
        thing.healthStatus = 'down';
        thing.healthLabel = 'No data';
    }

    // Coalesce DOM updates: many health checks can complete within the same
    // animation frame; scheduleStatusUpdate batches them into one flush.
    scheduleStatusUpdate();
}

// Calculate thing health status based on time since last observation
function calculateThingHealthStatus(timeSinceLastObservationMinutes) {
    if (timeSinceLastObservationMinutes === null || timeSinceLastObservationMinutes === undefined) {
        return { status: 'down', label: 'No data' }; // No observations
    }
    
    if (timeSinceLastObservationMinutes < 60) {
        return { status: 'active', label: '<60mins' };
    } else if (timeSinceLastObservationMinutes < 120) {
        return { status: 'warning', label: '<120mins' };
    } else {
        return { status: 'down', label: '>120mins' };
    }
}

// ── Viewport-aware health refresh (Option B) ─────────────────────────────
//
// Health status is initially computed synchronously from inline $expand data.
// These functions keep it current by re-fetching latest observations only for
// Things currently visible in the map viewport, on a 5-minute timer and also
// whenever the user pans to a new area.

const HEALTH_REFRESH_INTERVAL_MS  = 5 * 60 * 1000; // 5 minutes
const HEALTH_REFRESH_MOVEEND_MAX   = 150;            // skip pan-refresh if > N nodes visible
const HEALTH_REFRESH_MOVEEND_DELAY = 1500;           // ms to wait after pan stops

let _moveendDebounceTimer = null;

// Return IDs of Things whose markers lie within the current map viewport.
function getVisibleThingIds() {
    const bounds = state.map.getBounds();
    return Object.keys(state.things).filter(id => {
        const coords = state.things[id]?.coordinates;
        return coords && bounds.contains(L.latLng(coords[0], coords[1]));
    });
}

// Re-fetch the latest observation for every datastream of a single Thing and
// update its health status.  Uses the Observations navigation links that were
// stored during the initial $expand load.
async function refreshThingHealth(thingId) {
    const thing = state.things[thingId];
    if (!thing) return;

    const datastreams = thing.datastreams || [];
    if (datastreams.length === 0) return;

    const currentProtocol = window.location.protocol;
    const times = await Promise.all(datastreams.map(async ds => {
        try {
            const navLink = ds['Observations@iot.navigationLink'];
            if (!navLink) return null;
            const url = navLink.replace(/^http:/, currentProtocol) +
                        '?$top=1&$orderby=phenomenonTime%20desc';
            const res  = await frostFetch(url);
            const data = await res.json();
            const t = data.value?.[0]?.phenomenonTime;
            return t ? new Date(t) : null;
        } catch {
            return null;
        }
    }));

    const valid = times.filter(Boolean);
    const mostRecent = valid.length
        ? new Date(Math.max(...valid.map(t => t.getTime())))
        : null;

    if (mostRecent) {
        const mins   = (Date.now() - mostRecent) / 60000;
        const health = calculateThingHealthStatus(mins);
        thing.timeSinceLastObservation = mins;
        thing.healthStatus  = health.status;
        thing.healthLabel   = health.label;
    } else {
        thing.timeSinceLastObservation = null;
        thing.healthStatus  = 'down';
        thing.healthLabel   = 'No data';
    }
    scheduleStatusUpdate();
}

// Refresh health for a given list of Thing IDs with bounded concurrency.
async function refreshHealthForIds(ids, gen) {
    await runConcurrent(
        ids.map(id => () => {
            if (state.fetchGeneration !== gen) return Promise.resolve();
            return refreshThingHealth(id);
        }),
        5
    );
}

// Kick off a refresh for all Things in the current viewport.
function refreshViewportHealth(gen) {
    if (state.fetchGeneration !== gen) return;
    refreshHealthForIds(getVisibleThingIds(), gen);
}

// Start the periodic timer and moveend listener for viewport health refresh.
// Called once after the initial load; cancelled by resetAndReload.
function startViewportHealthRefresh(gen) {
    // Clear any previous timer / listener
    if (state.healthRefreshTimer) {
        clearInterval(state.healthRefreshTimer);
        state.healthRefreshTimer = null;
    }
    if (state._moveendHandler) {
        state.map.off('moveend', state._moveendHandler);
        state._moveendHandler = null;
    }

    // Periodic full-viewport refresh every 5 minutes
    state.healthRefreshTimer = setInterval(() => {
        if (state.fetchGeneration !== gen) {
            clearInterval(state.healthRefreshTimer);
            state.healthRefreshTimer = null;
            return;
        }
        refreshViewportHealth(gen);
    }, HEALTH_REFRESH_INTERVAL_MS);

    // Pan-triggered refresh: fires 1.5 s after the user stops panning,
    // but only when the viewport is small enough to be sensible.
    state._moveendHandler = () => {
        if (state.fetchGeneration !== gen) return;
        if (_moveendDebounceTimer) clearTimeout(_moveendDebounceTimer);
        _moveendDebounceTimer = setTimeout(() => {
            _moveendDebounceTimer = null;
            if (state.fetchGeneration !== gen) return;
            const ids = getVisibleThingIds();
            if (ids.length <= HEALTH_REFRESH_MOVEEND_MAX) {
                refreshHealthForIds(ids, gen);
            }
        }, HEALTH_REFRESH_MOVEEND_DELAY);
    };
    state.map.on('moveend', state._moveendHandler);
}
// ─────────────────────────────────────────────────────────────────────────────

// Format time since last observation
function formatTimeSince(minutes) {
    if (minutes === null || minutes === undefined) {
        return 'Never';
    }
    
    if (minutes < 60) {
        return `${Math.round(minutes)}m ago`;
    } else if (minutes < 1440) {
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        return `${hours}h ${mins}m ago`;
    } else {
        const days = Math.floor(minutes / 1440);
        const hours = Math.floor((minutes % 1440) / 60);
        return `${days}d ${hours}h ago`;
    }
}

// Update status tags on things
function updateThingStatusTags() {
    // Update sidebar list
    document.querySelectorAll('.thing-item').forEach(item => {
        const thingId = item.dataset.thingId;
        const thing = state.things[thingId];
        if (!thing) return;
        
        // Get status from thing's last observation time
        const status = thing.healthStatus || 'active';
        const label = thing.healthLabel || '<60mins';
        const timeSince = thing.timeSinceLastObservation;
        updateThingItemStatus(item, status, label, timeSince);
    });

    // Reflect health on the map markers and the sidebar counters
    refreshMarkerStatusColors();
    updateStatusCounts();
    
    // Update metadata sidebar if open
    const metadataSidebar = document.getElementById('thingMetadataSidebar');
    if (metadataSidebar && metadataSidebar.classList.contains('open')) {
        const thingId = Object.keys(state.things).find(id => {
            const thing = state.things[id];
            return thing && document.getElementById('thingMetadataTitle')?.textContent === thing.name;
        });
        if (thingId) {
            const thing = state.things[thingId];
            const status = thing.healthStatus || 'active';
            const label = thing.healthLabel || '<60mins';
            const timeSince = thing.timeSinceLastObservation;
            updateMetadataSidebarStatus(status, label, timeSince);
        }
    }
}

// Update thing item with status tag
function updateThingItemStatus(item, status, label, timeSince = null) {
    // Reflect status on the item's accent border
    item.classList.remove('status-active', 'status-warning', 'status-down');
    item.classList.add(`status-${status}`);
    item.dataset.status = status;

    // Remove existing status tag
    const existingTag = item.querySelector('.thing-status-tag');
    if (existingTag) {
        existingTag.remove();
    }
    
    const thingName = item.querySelector('.thing-name');
    if (!thingName) return;
    
    // Wrap the text content if it's not already wrapped
    let nameText = thingName.querySelector('.thing-name-text');
    if (!nameText) {
        // Get the current text content
        const currentText = thingName.textContent;
        // Clear the thing-name element
        thingName.textContent = '';
        // Create a text wrapper
        nameText = document.createElement('span');
        nameText.className = 'thing-name-text';
        nameText.textContent = currentText;
        thingName.appendChild(nameText);
    }
    
    // Add new status tag
    const statusTag = document.createElement('div');
    statusTag.className = `thing-status-tag thing-status-${status}`;
    statusTag.textContent = label;
    if (timeSince !== null) {
        statusTag.title = `Last observation: ${formatTimeSince(timeSince)}`;
    }
    
    thingName.appendChild(statusTag);
}

// Update metadata sidebar with status
function updateMetadataSidebarStatus(status, label, timeSince = null) {
    const content = document.getElementById('thingMetadataContent');
    if (!content) return;
    
    // Remove existing status section
    const existingStatus = content.querySelector('.metadata-status-section');
    if (existingStatus) {
        existingStatus.remove();
    }
    
    // Add status section at the top
    const statusSection = document.createElement('div');
    statusSection.className = 'metadata-status-section';
    const timeText = timeSince !== null ? `<div class="metadata-value" style="font-size: 0.875rem; color: var(--gray-600); margin-top: 0.5rem;">Last observation: ${formatTimeSince(timeSince)}</div>` : '';
    statusSection.innerHTML = `
        <div class="metadata-section">
            <h3>Status</h3>
            <div class="metadata-item">
                <div class="status-tag status-tag-${status}">${label}</div>
                ${timeText}
            </div>
        </div>
    `;
    
    content.insertBefore(statusSection, content.firstChild);
}

// Run an array of async task-functions with a bounded concurrency.
// taskFns: array of () => Promise, limit: max simultaneous tasks.
async function runConcurrent(taskFns, limit) {
    let i = 0;
    async function worker() {
        while (i < taskFns.length) {
            await taskFns[i++]();
        }
    }
    await Promise.all(
        Array.from({ length: Math.min(limit, taskFns.length) }, worker)
    );
}

// Debounced status tag update ─────────────────────────────────────────────
// Health checks complete at ~5/batch; without batching, updateThingStatusTags
// would be called thousands of times, each doing a full DOM scan. Instead,
// we coalesce all calls within a single animation frame into one flush.
let _statusUpdatePending = false;
function scheduleStatusUpdate() {
    if (_statusUpdatePending) return;
    _statusUpdatePending = true;
    requestAnimationFrame(() => {
        _statusUpdatePending = false;
        updateThingStatusTags();
    });
}

// Fetch things from FROST API, following @iot.nextLink pagination.
// Uses a generation counter so that switching endpoints while loading is in
// progress cancels all pending work from the previous endpoint.
async function fetchThings() {
    // Claim this generation; any concurrent/previous call will see a mismatch and exit.
    const gen = ++state.fetchGeneration;
    const stale = () => state.fetchGeneration !== gen;

    updateStatus('Fetching nodes…', '');

    const allThings = [];
    // Inline both Locations (coordinates) and each Datastream's latest Observation (health)
    // so health status can be computed synchronously — no per-Thing background requests.
    let nextUrl = `${state.frostRoot}/Things?$expand=Locations,Datastreams($expand=Observations($top=1;$orderby=phenomenonTime%20desc))`;

    try {
        while (nextUrl) {
            const response = await frostFetch(nextUrl);
            if (stale()) return;

            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

            const data = await response.json();
            if (stale()) return;

            const pageThings = data.value || [];
            const pageAdded = [];
            const pageMarkers = [];

            for (const thing of pageThings) {
                if (stale()) return;
                try {
                    const marker = await processThing(thing);
                    if (stale()) return;
                    if (marker) {
                        pageMarkers.push(marker);
                        pageAdded.push(thing);
                        allThings.push(thing);
                    }
                } catch (err) {
                    console.error(`Error processing thing ${thing['@iot.id']}:`, err);
                }
            }

            if (pageAdded.length > 0 && !stale()) {
                // Add all markers for this page in one call — single smooth cluster animation
                state.markerCluster.addLayers(pageMarkers);

                // Batch all roster DOM inserts for this page into one DocumentFragment
                const thingsList = document.getElementById('thingsList');
                const fragment = document.createDocumentFragment();
                for (const thing of pageAdded) {
                    const li = buildThingListItem(thing);
                    if (li) fragment.appendChild(li);
                }
                thingsList.appendChild(fragment);
                updateStatus(`Loading… ${allThings.length} nodes`, '');

                // Flush health colours for this page immediately — health was computed
                // synchronously from inline data, so no requests needed.
                scheduleStatusUpdate();
            }

            nextUrl = data['@iot.nextLink'] || null;
            if (nextUrl) {
                nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
            }
        }

        if (stale()) return;

        if (allThings.length === 0) {
            throw new Error('No Things found at this endpoint');
        }

        if (state.markerCluster.getLayers().length > 0) {
            state.markerCluster.refreshClusters();
            state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
                animate: true,
                duration: 1.0,
                padding: [20, 20]
            });
        }

        updateStatus(`Loaded ${allThings.length} nodes`, 'success');

        // Health was already computed synchronously from inline $expand data — no background
        // requests needed here.  Start the viewport-aware periodic refresh instead.
        startViewportHealthRefresh(gen);

    } catch (error) {
        if (stale()) return; // ignore errors from a superseded load
        console.error('Error fetching things:', error);
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

// Process a single thing.
// Locations are expected to be inlined via $expand=Locations.
// Falls back to a separate fetch via the navigation link if not present.
async function processThing(thing) {
    const thingId = thing['@iot.id'];

    let locationEntry;
    if (thing.Locations && thing.Locations.length > 0) {
        // Fast path: location was inlined by $expand
        locationEntry = thing.Locations[0];
    } else {
        // Fallback: fetch from the navigation link
        const locationUrl = thing['Locations@iot.navigationLink'];
        const secureUrl = locationUrl.replace(/^http:/, window.location.protocol);
        const locationResponse = await frostFetch(secureUrl);
        const locationData = await locationResponse.json();
        if (!locationData.value || locationData.value.length === 0) return;
        locationEntry = locationData.value[0];
    }

    if (!locationEntry?.location?.coordinates) return;

    const coordinates = locationEntry.location.coordinates;
    const locationDescription = locationEntry.description || '';
    
    // Create custom icon for marker (status colour filled in once health is known)
    const defaultIcon = makePinIcon('unknown', false);

    // GeoJSON coordinates are [longitude, latitude]; Leaflet expects [latitude, longitude]
    const latLng = [coordinates[1], coordinates[0]];
    const marker = L.marker(latLng, {
        icon: defaultIcon
    });
    
    // Store thing data
    state.things[thingId] = {
        marker,
        name: thing.name,
        description: thing.description || '',
        coordinates: latLng,
        locationDescription,
        thingId
    };
    
    state.thingsByName[thing.name] = {
        marker,
        id: thingId,
        coordinates: latLng,
        description: thing.description || '',
        locationDescription
    };
    
    state.markers[thingId] = marker;

    // --- Inline health from nested $expand -----------------------------------
    // Store datastreams so the viewport refresher can use navigation links later.
    const inlineDatastreams = thing.Datastreams || [];
    state.things[thingId].datastreams = inlineDatastreams;

    if (inlineDatastreams.length > 0) {
        const times = inlineDatastreams
            .map(ds => ds.Observations?.[0]?.phenomenonTime)
            .filter(Boolean)
            .map(t => new Date(t));

        if (times.length > 0) {
            const mostRecent = new Date(Math.max(...times.map(t => t.getTime())));
            const mins = (Date.now() - mostRecent) / 60000;
            const health = calculateThingHealthStatus(mins);
            state.things[thingId].timeSinceLastObservation = mins;
            state.things[thingId].healthStatus = health.status;
            state.things[thingId].healthLabel = health.label;
        } else {
            // Datastreams exist but no observations yet
            state.things[thingId].timeSinceLastObservation = null;
            state.things[thingId].healthStatus = 'down';
            state.things[thingId].healthLabel = 'No data';
        }
    }
    // -------------------------------------------------------------------------

    // Handle marker click - no popup, just open sidebar
    marker.on('click', async () => {
        highlightThingInList(thing.name);
        showThingMetadata(thingId);
        await loadDatastreamsForThing(thingId);
    });

    // Caller is responsible for adding to the cluster group (in bulk via addLayers)
    return marker;
}

// Create popup content for marker
function createPopupContent(thing) {
    let content = `<div style="min-width: 250px;">`;
    content += `<h3 style="margin: 0 0 0.5rem 0; color: #3b82f6; font-weight: 600;">${thing.name}</h3>`;
    
    if (thing.description) {
        content += `<p style="margin: 0 0 0.5rem 0; color: #6b7280; font-size: 0.875rem;">${thing.description}</p>`;
    }
    
    content += `<div id="datastreams-${thing['@iot.id']}" style="margin-top: 0.5rem;">`;
    content += `<div style="color: #9ca3af; font-size: 0.875rem;">Loading datastreams...</div>`;
    content += `</div>`;
    content += `</div>`;
    
    return content;
}

// Load datastreams for a thing
async function loadDatastreamsForThing(thingId, gen = state.fetchGeneration) {
    if (state.fetchGeneration !== gen) return;
    const thing = state.things[thingId];
    if (!thing) return;
    
    try {
        const response = await frostFetch(`${state.frostRoot}/Things(${thingId})/Datastreams`);
        if (state.fetchGeneration !== gen) return;
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const datastreamData = await response.json();
        if (state.fetchGeneration !== gen) return;
        
        // Calculate time since last observation for this thing (async, don't block)
        calculateThingHealthStatusAsync(thingId, datastreamData.value, gen);
        
        // Update metadata sidebar if open
        updateThingMetadataDatastreams(thingId, datastreamData.value);
        
    } catch (error) {
        if (state.fetchGeneration !== gen) return;
        console.error(`Error fetching datastreams for thing ${thingId}:`, error);
        updateStatus(`Error loading datastreams: ${error.message}`, 'error');
    }
}

// Update popup with datastreams
async function updatePopupWithDatastreams(thingId, datastreams) {
    const thing = state.things[thingId];
    if (!thing) return;
    
    const popup = thing.marker.getPopup();
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = popup.getContent();
    
    const datastreamDiv = tempDiv.querySelector(`#datastreams-${thingId}`);
    if (!datastreamDiv) return;
    
    if (datastreams.length === 0) {
        datastreamDiv.innerHTML = `<div style="color: #9ca3af; font-size: 0.875rem;">No datastreams available</div>`;
        popup.setContent(tempDiv.innerHTML);
        if (thing.marker.isPopupOpen()) {
            thing.marker.openPopup();
        }
        return;
    }
    
    // Show loading state
    datastreamDiv.innerHTML = `<div style="color: #9ca3af; font-size: 0.875rem;">Loading datastreams...</div>`;
    popup.setContent(tempDiv.innerHTML);
    if (thing.marker.isPopupOpen()) {
        thing.marker.openPopup();
    }
    
    // Fetch latest observations for all datastreams
    const datastreamPromises = datastreams.map(async (ds) => {
        const unitSymbol = ds.unitOfMeasurement?.symbol || '';
        try {
            const currentProtocol = window.location.protocol;
            const obsUrl = ds['Observations@iot.navigationLink'] + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await frostFetch(secureObsUrl);
            const obsData = await obsResponse.json();
            return { 
                ds, 
                latestValue: obsData.value?.[0]?.result ?? '-', 
                unitSymbol,
                error: false
            };
        } catch (error) {
            return { 
                ds, 
                latestValue: 'Error', 
                unitSymbol,
                error: true 
            };
        }
    });
    
    const results = await Promise.all(datastreamPromises);
    
    // Build content
    let newContent = `<div style="margin-top: 0.5rem;">`;
    results.forEach(({ ds, latestValue, unitSymbol, error }) => {
        const displayName = formatDatastreamName(ds.name);
        const escapedName = ds.name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const escapedDisplayName = displayName.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        newContent += `
            <div style="padding: 0.5rem; margin: 0.25rem 0; background: #f3f4f6; border-radius: 0.375rem; cursor: pointer; transition: background 0.2s;"
                 onclick="selectDatastream(${ds['@iot.id']}, '${escapedDisplayName}')"
                 onmouseover="this.style.background='#93c5fd'"
                 onmouseout="this.style.background='#f3f4f6'">
                <div style="font-weight: 500; margin-bottom: 0.25rem;">${displayName}</div>
                <div style="font-size: 0.75rem; color: ${error ? '#ef4444' : '#6b7280'};">
                    Latest: <strong>${latestValue} ${unitSymbol}</strong>
                </div>
            </div>
        `;
    });
    newContent += `</div>`;
    
    // Update popup
    datastreamDiv.innerHTML = newContent;
    popup.setContent(tempDiv.innerHTML);
    if (thing.marker.isPopupOpen()) {
        thing.marker.openPopup();
    }
}


// Populate things list in sidebar (used by resetAndReload for a clean rebuild)
function populateThingsList(things) {
    const thingsList = document.getElementById('thingsList');
    thingsList.innerHTML = '';
    const fragment = document.createDocumentFragment();
    for (const thing of things) {
        const li = buildThingListItem(thing);
        if (li) fragment.appendChild(li);
    }
    thingsList.appendChild(fragment);
}

// Build a roster <li> for a Thing without inserting it into the DOM.
// Callers batch-insert via DocumentFragment for performance.
function buildThingListItem(thing) {
    const thingData = state.things[thing['@iot.id']];
    if (!thingData) return null;

    const li = document.createElement('li');
    li.className = 'thing-item';
    li.dataset.thingId = thing['@iot.id'];
    li.dataset.thingName = thing.name;
    li.innerHTML = `<div class="thing-name"><span class="thing-name-text">${thing.name}</span></div>`;

    li.addEventListener('click', async () => {
        state.map.setView(thingData.coordinates, 15, {
            animate: true,
            duration: 0.8,
            easeLinearity: 0.25
        });
        highlightThingInList(thing.name);
        showThingMetadata(thing['@iot.id']);
        await loadDatastreamsForThing(thing['@iot.id']);
    });

    return li;
}

// Append a single Thing to the roster (convenience wrapper; use buildThingListItem
// + DocumentFragment for bulk inserts).
function appendThingToList(thing) {
    const li = buildThingListItem(thing);
    if (li) document.getElementById('thingsList').appendChild(li);
}

// Highlight thing in list
function highlightThingInList(thingName) {
    document.querySelectorAll('.thing-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const thingElement = document.querySelector(`[data-thing-name="${thingName.replace(/"/g, '\\"')}"]`);
    if (thingElement) {
        thingElement.classList.add('active');
        thingElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// Filter things by search query (kept for the search input handler)
function filterThings(query) {
    state.searchQuery = (query || '').toLowerCase().trim();
    applyFilters();
}

// Set the active status filter from the legend chips
function setStatusFilter(filter) {
    state.activeStatusFilter = filter || 'all';

    document.querySelectorAll('.legend-chip').forEach(chip => {
        chip.classList.toggle('active', chip.dataset.filter === state.activeStatusFilter);
    });

    applyFilters();
}

// Apply combined search + status filtering to the sidebar list
function applyFilters() {
    const query = state.searchQuery || '';
    const statusFilter = state.activeStatusFilter || 'all';

    document.querySelectorAll('.thing-item').forEach(item => {
        const name = item.dataset.thingName.toLowerCase();
        const status = item.dataset.status || 'active';
        const matchesSearch = name.includes(query);
        const matchesStatus = statusFilter === 'all' || status === statusFilter;
        item.style.display = matchesSearch && matchesStatus ? '' : 'none';
    });
}

// Update the sidebar status counters
function updateStatusCounts() {
    const counts = { total: 0, active: 0, warning: 0, down: 0 };

    Object.values(state.things).forEach(thing => {
        counts.total += 1;
        const status = thing.healthStatus || 'active';
        if (counts[status] !== undefined) {
            counts[status] += 1;
        }
    });

    const set = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };

    set('countTotal', counts.total);
    set('countActive', counts.active);
    set('countWarning', counts.warning);
    set('countDown', counts.down);
}

// Select datastream and load chart
async function selectDatastream(datastreamId, datastreamName) {
    state.currentDatastream = datastreamId;
    
    // Find current datastream index
    state.currentDatastreamIndex = state.currentThingDatastreams.findIndex(ds => ds['@iot.id'] === datastreamId);
    
    // Update UI
    document.querySelectorAll('.datastream-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const activeItem = document.querySelector(`[data-datastream-id="${datastreamId}"]`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
    
    // Update chart panel
    document.getElementById('chartTitle').textContent = datastreamName;
    document.getElementById('chartSubtitle').textContent = `Datastream ID: ${datastreamId}`;
    
    // Expand chart panel
    const chartPanel = document.getElementById('chartPanel');
    if (!chartPanel.classList.contains('expanded')) {
        chartPanel.classList.add('expanded');
    }
    
    // Close metadata sidebar
    hideThingMetadata();
    
    // Update navigation arrows visibility
    updateDatastreamNavigation();
    
    // Load chart data
    await loadChartData(datastreamId);
}

// Load chart data
async function loadChartData(datastreamId) {
    updateStatus('Loading chart data...', '');
    
    const chartPanelContent = document.getElementById('chartPanelContent');
    chartPanelContent.innerHTML = '<div class="no-data-message"><div class="loading"></div> Loading data...</div>';
    
    try {
        // Fetch datastream info
        const dsResponse = await frostFetch(`${state.frostRoot}/Datastreams(${datastreamId})`);
        if (!dsResponse.ok) throw new Error(`HTTP error! Status: ${dsResponse.status}`);
        
        const dsData = await dsResponse.json();
        const unitSymbol = dsData.unitOfMeasurement?.symbol || '';
        const datastreamName = formatDatastreamName(dsData.name || 'Unknown');
        const datastreamDescription = dsData.description || '';
        
        // Fetch observations
        const obsUrl = `${state.frostRoot}/Datastreams(${datastreamId})/Observations?$top=${state.currentLimit}&$orderby=phenomenonTime%20desc`;
        const obsResponse = await frostFetch(obsUrl);
        
        if (!obsResponse.ok) throw new Error(`HTTP error! Status: ${obsResponse.status}`);
        
        const obsData = await obsResponse.json();
        
        if (!obsData.value || obsData.value.length === 0) {
            chartPanelContent.innerHTML = `
                <div class="no-data-message">
                    <h3>No observations found</h3>
                    <p>This datastream has no observation data available.</p>
                </div>
            `;
            updateStatus('No data available', 'warning');
            return;
        }
        
        // Process observations
        const processedData = processObservations(obsData.value);
        
        // Calculate stats
        const stats = calculateStats(processedData, unitSymbol);
        
        // Render chart
        renderChart(processedData, unitSymbol, datastreamName, stats);
        
        updateStatus(`Loaded ${processedData.length} observations`, 'success');
        
                } catch (error) {
        console.error('Error loading chart data:', error);
        chartPanelContent.innerHTML = `
            <div class="no-data-message">
                <h3>Error loading data</h3>
                <p>${error.message}</p>
            </div>
        `;
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

// Process observations and detect gaps (original style with gap fillers)
function processObservations(observations) {
    const gapThreshold = 15 * 60 * 1000; // 15 minutes
    const fillerInterval = 5 * 60 * 1000; // 5 minutes
    let formattedData = [];
    let previousTime = null;
    
    // Sort by time (oldest first)
    const sorted = [...observations].sort((a, b) => {
        return new Date(a.phenomenonTime) - new Date(b.phenomenonTime);
    });
    
    sorted.forEach(entry => {
        const timestamp = new Date(entry.phenomenonTime);
        const value = entry.result;
        
        if (previousTime) {
            const gap = timestamp - previousTime;
            
            // If gap is larger than threshold, insert a null break so the
            // line visibly disconnects instead of dropping to zero
            if (gap > gapThreshold) {
                let fillerTime = new Date(previousTime.getTime() + fillerInterval);
                while (fillerTime < timestamp) {
                    formattedData.push({ 
                        x: fillerTime, 
                        y: null, 
                        gapFiller: true 
                    });
                    fillerTime = new Date(fillerTime.getTime() + fillerInterval);
                }
            }
        }
        
        formattedData.push({ 
            x: timestamp, 
            y: value, 
            gapFiller: false 
        });
        previousTime = timestamp;
    });
    
    return formattedData;
}

// Calculate statistics
function calculateStats(data, unitSymbol) {
    const validData = data.filter(d => !d.gapFiller && d.y !== null);
    
    if (validData.length === 0) {
        return {
            current: 'N/A',
            min: 'N/A',
            max: 'N/A',
            avg: 'N/A',
            unit: unitSymbol
        };
    }
    
    const values = validData.map(d => d.y);
    const current = values[values.length - 1];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    
    // Count gap fillers
    const gaps = data.filter(d => d.gapFiller).length;
    
    return {
        current: current.toFixed(2),
        min: min.toFixed(2),
        max: max.toFixed(2),
        avg: avg.toFixed(2),
        unit: unitSymbol,
        gaps: gaps,
        totalPoints: validData.length
    };
}

// Render chart
function renderChart(data, unitSymbol, datastreamName, stats) {
    const chartPanelContent = document.getElementById('chartPanelContent');
    
    // Destroy existing chart
    if (state.currentChart) {
        state.currentChart.destroy();
    }
    
    // Create stats HTML
    const statsHTML = `
        <div class="chart-stats">
            <div class="stat-card">
                <div class="stat-label">Current Value</div>
                <div class="stat-value">${stats.current} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Minimum</div>
                <div class="stat-value">${stats.min} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Maximum</div>
                <div class="stat-value">${stats.max} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Average</div>
                <div class="stat-value">${stats.avg} <span class="stat-unit">${stats.unit}</span></div>
            </div>
            ${stats.gaps > 0 ? `
            <div class="stat-card" style="border-color: var(--gap-color); background: var(--gap-bg);">
                <div class="stat-label">Data Gaps</div>
                <div class="stat-value"><span class="gap-indicator"></span>${stats.gaps}</div>
            </div>
            ` : ''}
            <div class="stat-card">
                <div class="stat-label">Data Points</div>
                <div class="stat-value">${stats.totalPoints}</div>
            </div>
        </div>
    `;
    
    // Create chart container
    const chartHTML = `
        ${statsHTML}
        <div class="chart-container">
            <canvas id="timeSeriesChart"></canvas>
        </div>
    `;
    
    chartPanelContent.innerHTML = chartHTML;
    
    // Check for valid data
    const validValues = data.filter(d => !d.gapFiller && d.y !== null).map(d => d.y);
    
    if (validValues.length === 0) {
        chartPanelContent.innerHTML = `
            <div class="no-data-message">
                <h3>No valid data points</h3>
                <p>Unable to render chart with available data.</p>
            </div>
        `;
        return;
    }

    const ctx = document.getElementById('timeSeriesChart').getContext('2d');

    // Neon cyan trace with a luminous gradient fill on the dark stage
    const gradient = ctx.createLinearGradient(0, 0, 0, 340);
    gradient.addColorStop(0, 'rgba(34, 211, 238, 0.42)');
    gradient.addColorStop(0.55, 'rgba(34, 211, 238, 0.1)');
    gradient.addColorStop(1, 'rgba(34, 211, 238, 0)');

    const chartData = {
        datasets: [
            {
                label: datastreamName,
                data: data,
                borderColor: '#22d3ee',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.35,
                cubicInterpolationMode: 'monotone',
                spanGaps: false,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: '#22d3ee',
                pointHoverBorderColor: '#03121a',
                pointHoverBorderWidth: 2
            }
        ]
    };

    Chart.defaults.font.family = "'Space Grotesk', sans-serif";
    Chart.defaults.color = '#9fb0c3';

    // Subtle glow under the trace line
    const glowPlugin = {
        id: 'rimeGlow',
        beforeDatasetDraw(chart) {
            const c = chart.ctx;
            c.save();
            c.shadowColor = 'rgba(34, 211, 238, 0.55)';
            c.shadowBlur = 12;
        },
        afterDatasetDraw(chart) {
            chart.ctx.restore();
        }
    };

    state.currentChart = new Chart(ctx, {
        type: 'line',
        data: chartData,
        plugins: [glowPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(5, 9, 18, 0.92)',
                    borderColor: 'rgba(34, 211, 238, 0.4)',
                    borderWidth: 1,
                    titleColor: '#9fb0c3',
                    bodyColor: '#e6eef7',
                    padding: 12,
                    cornerRadius: 10,
                    displayColors: false,
                    titleFont: { family: "'Space Grotesk', sans-serif", weight: '500', size: 11 },
                    bodyFont: { family: "'JetBrains Mono', monospace", weight: '600', size: 13 },
                    callbacks: {
                        label: (context) => {
                            if (context.raw.gapFiller) {
                                return 'Data gap';
                            }
                            const v = context.raw.y;
                            return `${v != null ? v.toFixed(2) : 'N/A'} ${unitSymbol}`.trim();
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        tooltipFormat: 'yyyy-MM-dd HH:mm',
                        displayFormats: {
                            minute: 'HH:mm',
                            hour: 'HH:mm',
                            day: 'MMM dd'
                        }
                    },
                    border: { display: false },
                    ticks: {
                        autoSkip: true,
                        maxTicksLimit: 8,
                        maxRotation: 0,
                        color: '#6b7c93',
                        font: { family: "'JetBrains Mono', monospace", size: 10 }
                    },
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: false,
                    border: { display: false },
                    ticks: {
                        color: '#6b7c93',
                        font: { family: "'JetBrains Mono', monospace", size: 10 },
                        padding: 8
                    },
                    grid: {
                        color: 'rgba(140, 170, 210, 0.1)',
                        drawTicks: false
                    }
                }
            }
        }
    });
}

// Set chart limit
function setChartLimit(limit) {
    state.currentLimit = limit;
    
    // Update button states
    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.classList.remove('active');
        if (parseInt(btn.dataset.limit) === limit) {
            btn.classList.add('active');
        }
    });
    
    // Reload chart if datastream is selected
    if (state.currentDatastream) {
        loadChartData(state.currentDatastream);
    }
}

// Toggle chart panel
function toggleChartPanel() {
    const chartPanel = document.getElementById('chartPanel');
    const isExpanded = chartPanel.classList.contains('expanded');
    
    if (isExpanded) {
        chartPanel.classList.remove('expanded');
    } else {
        chartPanel.classList.add('expanded');
    }
    
    // Update toggle icon rotation
    const toggleIcon = document.getElementById('chartPanelToggle').querySelector('svg');
    if (chartPanel.classList.contains('expanded')) {
        toggleIcon.style.transform = 'rotate(180deg)';
    } else {
        toggleIcon.style.transform = 'rotate(0deg)';
    }
}

// Zoom to extents (fit all markers)
function zoomToExtents() {
    if (state.markerCluster && state.markerCluster.getLayers().length > 0) {
        state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
            animate: true,
            duration: 1.2, // 1.2 second smooth animation
            padding: [30, 30], // Padding in pixels
            maxZoom: 18 // Don't zoom in too far
        });
        updateStatus('Zoomed to show all sensors', 'success');
    } else {
        updateStatus('No sensors to zoom to', 'warning');
    }
}

// Update marker icon based on selection + health state
function updateMarkerIcon(thingId, isSelected) {
    const marker = state.markers[thingId];
    if (!marker) return;

    const thing = state.things[thingId];
    const status = (thing && thing.healthStatus) || 'unknown';
    marker.setIcon(makePinIcon(status, isSelected));
}

// Recolour every (unselected) marker to reflect current health status
function refreshMarkerStatusColors() {
    Object.keys(state.markers).forEach(thingId => {
        if (state.selectedThingId === thingId) return;
        updateMarkerIcon(thingId, false);
    });
}

// Show thing metadata sidebar
function showThingMetadata(thingId) {
    const thing = state.things[thingId];
    if (!thing) return;
    
    // Update marker icons - deselect previous, select current
    if (state.selectedThingId && state.selectedThingId !== thingId) {
        updateMarkerIcon(state.selectedThingId, false);
    }
    state.selectedThingId = thingId;
    updateMarkerIcon(thingId, true);
    
    const sidebar = document.getElementById('thingMetadataSidebar');
    const title = document.getElementById('thingMetadataTitle');
    const content = document.getElementById('thingMetadataContent');
    const mainContent = document.querySelector('.main-content');
    
    title.textContent = thing.name;
    
    // Add class to main content to adjust chart panel
    if (mainContent) {
        mainContent.classList.add('has-metadata-sidebar');
    }
    
    // Build metadata content (status will be added by updateMetadataSidebarStatus)
    let metadataHTML = `
        <div class="metadata-section">
            <h3>Location</h3>
            <div class="metadata-item">
                <div class="metadata-label">Coordinates</div>
                <div class="metadata-value">${thing.coordinates[0].toFixed(6)}, ${thing.coordinates[1].toFixed(6)}</div>
            </div>
            ${thing.locationDescription ? `
            <div class="metadata-item">
                <div class="metadata-label">Description</div>
                <div class="metadata-value">${thing.locationDescription}</div>
            </div>
            ` : ''}
        </div>
        ${thing.description ? `
        <div class="metadata-section">
            <h3>Thing Details</h3>
            <div class="metadata-item">
                <div class="metadata-label">Description</div>
                <div class="metadata-value">${thing.description}</div>
            </div>
        </div>
        ` : ''}
        <div class="metadata-section">
            <h3>Datastreams</h3>
            <div class="metadata-datastreams" id="thingMetadataDatastreams">
                <div style="color: var(--gray-500); font-size: 0.875rem;">Loading datastreams...</div>
            </div>
        </div>
    `;
    
    content.innerHTML = metadataHTML;
    sidebar.classList.add('open');
    
    // Update status section after sidebar is open
    const healthStatus = thing.healthStatus || 'active';
    const healthLabel = thing.healthLabel || '<60mins';
    const timeSince = thing.timeSinceLastObservation;
    updateMetadataSidebarStatus(healthStatus, healthLabel, timeSince);
    
    // Add download button after status is added
    setTimeout(() => {
        addDownloadButton(thingId);
    }, 0);
}

// Hide thing metadata sidebar
function hideThingMetadata() {
    // Deselect marker when sidebar is closed
    if (state.selectedThingId) {
        updateMarkerIcon(state.selectedThingId, false);
        state.selectedThingId = null;
    }
    
    const sidebar = document.getElementById('thingMetadataSidebar');
    const mainContent = document.querySelector('.main-content');
    
    sidebar.classList.remove('open');
    
    // Remove class from main content to restore chart panel
    if (mainContent) {
        mainContent.classList.remove('has-metadata-sidebar');
    }
}

// Update datastreams in metadata sidebar
function updateThingMetadataDatastreams(thingId, datastreams) {
    const datastreamsDiv = document.getElementById('thingMetadataDatastreams');
    if (!datastreamsDiv) return;
    
    if (datastreams.length === 0) {
        datastreamsDiv.innerHTML = '<div style="color: var(--gray-500); font-size: 0.875rem;">No datastreams available</div>';
        return;
    }
    
    datastreamsDiv.innerHTML = '';
    
    datastreams.forEach(async (ds) => {
        const unitSymbol = ds.unitOfMeasurement?.symbol || '';
        
        try {
            const currentProtocol = window.location.protocol;
            const obsUrl = ds['Observations@iot.navigationLink'] + '?$top=1&$orderby=phenomenonTime%20desc';
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            const obsResponse = await frostFetch(secureObsUrl);
            const obsData = await obsResponse.json();
            const latestValue = obsData.value?.[0]?.result || '-';
            
            const displayName = formatDatastreamName(ds.name);
            const latestText = `${latestValue}${unitSymbol ? ' ' + unitSymbol : ''}`;
            const dsItem = document.createElement('div');
            dsItem.className = 'metadata-datastream-item';
            dsItem.innerHTML = `
                <div class="metadata-datastream-name">${displayName}</div>
                <div class="metadata-datastream-meta">
                    <span>Latest reading</span>
                    <span class="ds-latest">${latestText}</span>
                </div>
            `;
            dsItem.addEventListener('click', () => {
                selectDatastream(ds['@iot.id'], displayName);
            });
            datastreamsDiv.appendChild(dsItem);
        } catch (error) {
            const displayName = formatDatastreamName(ds.name);
            const dsItem = document.createElement('div');
            dsItem.className = 'metadata-datastream-item';
            dsItem.innerHTML = `
                <div class="metadata-datastream-name">${displayName}</div>
                <div class="metadata-datastream-meta" style="color: #ef4444;">Error loading</div>
            `;
            dsItem.addEventListener('click', () => {
                selectDatastream(ds['@iot.id'], displayName);
            });
            datastreamsDiv.appendChild(dsItem);
        }
    });
}

// Update datastream navigation button visibility
function updateDatastreamNavigation() {
    const nextBtn = document.getElementById('chartNextDatastreamBtn');
    
    if (!nextBtn) return;
    
    const hasMultiple = state.currentThingDatastreams.length > 1;
    
    if (hasMultiple) {
        nextBtn.style.display = 'flex';
        // Button is always enabled - it cycles through all datastreams
        nextBtn.disabled = false;
    } else {
        nextBtn.style.display = 'none';
    }
}

// Navigate to next datastream (cycles through all)
function navigateToDatastream(direction) {
    if (state.currentThingDatastreams.length === 0) return;
    
    let newIndex = state.currentDatastreamIndex + direction;
    // Wrap around: if at end, go to beginning; if at beginning going back, go to end
    if (newIndex < 0) {
        newIndex = state.currentThingDatastreams.length - 1;
    } else if (newIndex >= state.currentThingDatastreams.length) {
        newIndex = 0;
    }
    
    const datastream = state.currentThingDatastreams[newIndex];
    const displayName = formatDatastreamName(datastream.name);
    selectDatastream(datastream['@iot.id'], displayName);
}

// Fetch all observations for a datastream (with pagination and date filtering)
async function fetchAllObservations(observationsUrl, maxRetries = 5, delay = 50, startDate = null, endDate = null) {
    const observations = [];
    let nextUrl = observationsUrl;
    let retries = 0;
    const currentProtocol = window.location.protocol;
    
    // Build filter for date range
    let dateFilter = '';
    if (startDate || endDate) {
        const filters = [];
        if (startDate) {
            const startISO = startDate.toISOString();
            filters.push(`phenomenonTime ge ${startISO}`);
        }
        if (endDate) {
            const endISO = endDate.toISOString();
            filters.push(`phenomenonTime le ${endISO}`);
        }
        if (filters.length > 0) {
            dateFilter = filters.join(' and ');
        }
    }
    
    while (nextUrl) {
        const secureUrl = nextUrl.replace(/^http:/, currentProtocol);
        const params = new URLSearchParams({ '$select': 'phenomenonTime,resultTime,result' });
        
        // Add date filter if provided
        if (dateFilter) {
            params.append('$filter', dateFilter);
        }
        
        const urlWithParams = secureUrl.includes('?') 
            ? `${secureUrl}&${params.toString()}` 
            : `${secureUrl}?${params.toString()}`;
        
        try {
            await new Promise(resolve => setTimeout(resolve, delay));
            const response = await frostFetch(urlWithParams);
            
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!data.value) {
                throw new Error('No content found.');
            }
            
            // Add observations
            for (const obs of data.value) {
                observations.push({
                    phenomenonTime: obs.phenomenonTime,
                    resultTime: obs.resultTime || obs.phenomenonTime,
                    result: obs.result
                });
            }
            
            // Check for next page
            if (data['@iot.nextLink']) {
                nextUrl = data['@iot.nextLink'];
                // Add filter to nextLink if it doesn't already have one
                if (dateFilter && !nextUrl.includes('$filter')) {
                    nextUrl += (nextUrl.includes('?') ? '&' : '?') + `$filter=${encodeURIComponent(dateFilter)}`;
                }
            } else {
                nextUrl = null;
            }
            
        } catch (error) {
            if (retries >= maxRetries) {
                throw error;
            }
            retries++;
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }
    
    return observations;
}

// Download all data for a Thing
async function downloadThingData(thingId, startDate = null, endDate = null) {
    const thing = state.things[thingId];
    if (!thing) {
        updateStatus('Thing not found', 'error');
        return;
    }
    
    // Validate dates
    if (startDate && endDate && startDate > endDate) {
        updateStatus('Start date must be before end date', 'error');
        return;
    }
    
    updateStatus('Preparing download...', '');
    
    try {
        // Fetch all datastreams for the thing
        const response = await frostFetch(`${state.frostRoot}/Things(${thingId})/Datastreams`);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const datastreamData = await response.json();
        const datastreams = datastreamData.value || [];
        
        if (datastreams.length === 0) {
            updateStatus('No datastreams found for this thing', 'warning');
            return;
        }
        
        const dateRangeText = startDate && endDate 
            ? ` (${startDate.toISOString().split('T')[0]} to ${endDate.toISOString().split('T')[0]})`
            : '';
        updateStatus(`Downloading data from ${datastreams.length} datastream(s)${dateRangeText}...`, '');
        
        // Fetch all observations for each datastream
        const allData = [];
        let totalObservations = 0;
        
        for (const ds of datastreams) {
            const dsName = formatDatastreamName(ds.name);
            const unitSymbol = ds.unitOfMeasurement?.symbol || '';
            const currentProtocol = window.location.protocol;
            const obsUrl = ds['Observations@iot.navigationLink'];
            const secureObsUrl = obsUrl.replace(/^http:/, currentProtocol);
            
            try {
                updateStatus(`Fetching ${dsName}...`, '');
                const observations = await fetchAllObservations(secureObsUrl, 5, 50, startDate, endDate);
                totalObservations += observations.length;
                
                // Add metadata to each observation
                for (const obs of observations) {
                    allData.push({
                        thingName: thing.name,
                        thingId: thingId,
                        datastreamName: ds.name,
                        datastreamDisplayName: dsName,
                        unitOfMeasurement: unitSymbol,
                        phenomenonTime: obs.phenomenonTime,
                        resultTime: obs.resultTime,
                        result: obs.result
                    });
                }
                
            } catch (error) {
                console.error(`Error fetching observations for ${dsName}:`, error);
                updateStatus(`Error fetching ${dsName}: ${error.message}`, 'error');
            }
        }
        
        if (allData.length === 0) {
            const rangeText = startDate && endDate 
                ? ' for selected date range'
                : '';
            updateStatus(`No observations found to download${rangeText}`, 'warning');
            return;
        }
        
        // Convert to CSV
        updateStatus('Converting to CSV...', '');
        const csv = convertToCSV(allData);
        
        // Trigger download
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        const dateSuffix = startDate && endDate 
            ? `_${startDate.toISOString().split('T')[0]}_to_${endDate.toISOString().split('T')[0]}`
            : '';
        link.setAttribute('href', url);
        link.setAttribute('download', `${thing.name.replace(/[^a-z0-9]/gi, '_')}_data${dateSuffix}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        updateStatus(`Downloaded ${totalObservations.toLocaleString()} observations`, 'success');
        
    } catch (error) {
        console.error('Error downloading thing data:', error);
        updateStatus(`Download error: ${error.message}`, 'error');
    }
}

// Convert data array to CSV format
function convertToCSV(data) {
    if (data.length === 0) return '';
    
    // Get headers
    const headers = Object.keys(data[0]);
    
    // Create CSV rows
    const rows = [headers.join(',')];
    
    for (const row of data) {
        const values = headers.map(header => {
            const value = row[header];
            // Escape commas and quotes, wrap in quotes if needed
            if (value === null || value === undefined) return '';
            const stringValue = String(value);
            if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
                return `"${stringValue.replace(/"/g, '""')}"`;
            }
            return stringValue;
        });
        rows.push(values.join(','));
    }
    
    return rows.join('\n');
}

// Add download button and date picker to metadata sidebar
function addDownloadButton(thingId) {
    const content = document.getElementById('thingMetadataContent');
    if (!content) return;
    
    // Remove existing download section if any
    const existingSection = content.querySelector('.download-section');
    if (existingSection) {
        existingSection.remove();
    }
    
    // Set default dates (last 30 days)
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);
    
    const dateFormat = (date) => {
        return date.toISOString().split('T')[0];
    };
    
    // Create download section
    const downloadSection = document.createElement('div');
    downloadSection.className = 'download-section';
    downloadSection.innerHTML = `
        <div class="metadata-section">
            <h3>Download Data</h3>
            <div class="download-option-group">
                <label class="download-option-label">
                    <input type="radio" name="downloadOption" value="range" checked class="download-option-radio">
                    <span>Date Range</span>
                </label>
                <label class="download-option-label">
                    <input type="radio" name="downloadOption" value="all" class="download-option-radio">
                    <span>All Data</span>
                </label>
            </div>
            <div class="download-date-range" id="downloadDateRange">
                <div class="date-input-group">
                    <label for="downloadStartDate">Start Date</label>
                    <input type="date" id="downloadStartDate" value="${dateFormat(startDate)}" class="date-input">
                </div>
                <div class="date-input-group">
                    <label for="downloadEndDate">End Date</label>
                    <input type="date" id="downloadEndDate" value="${dateFormat(endDate)}" class="date-input">
                </div>
            </div>
            <button class="download-thing-btn" id="downloadThingBtn">
                <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" style="margin-right: 0.5rem;">
                    <path d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"/>
                </svg>
                Download Data
            </button>
        </div>
    `;
    
    // Insert after status section or at the beginning
    const statusSection = content.querySelector('.metadata-status-section');
    if (statusSection && statusSection.nextSibling) {
        content.insertBefore(downloadSection, statusSection.nextSibling);
    } else {
        content.insertBefore(downloadSection, content.firstChild);
    }
    
    // Add event listeners
    const downloadBtn = document.getElementById('downloadThingBtn');
    const startDateInput = document.getElementById('downloadStartDate');
    const endDateInput = document.getElementById('downloadEndDate');
    const dateRangeDiv = document.getElementById('downloadDateRange');
    const optionRadios = document.querySelectorAll('.download-option-radio');
    
    // Toggle date range visibility based on option
    const toggleDateRange = () => {
        const selectedOption = document.querySelector('.download-option-radio:checked').value;
        dateRangeDiv.style.display = selectedOption === 'range' ? 'grid' : 'none';
    };
    
    optionRadios.forEach(radio => {
        radio.addEventListener('change', toggleDateRange);
    });
    
    // Validate dates on change (only if date range is selected)
    const validateDates = () => {
        const selectedOption = document.querySelector('.download-option-radio:checked').value;
        if (selectedOption === 'all') {
            downloadBtn.disabled = false;
            return;
        }
        
        const startDate = new Date(startDateInput.value);
        const endDate = new Date(endDateInput.value);
        
        if (startDate > endDate) {
            downloadBtn.disabled = true;
            return;
        }
        
        downloadBtn.disabled = false;
    };
    
    startDateInput.addEventListener('change', validateDates);
    endDateInput.addEventListener('change', validateDates);
    
    downloadBtn.addEventListener('click', async () => {
        const selectedOption = document.querySelector('.download-option-radio:checked').value;
        
        if (selectedOption === 'all') {
            await downloadThingData(thingId, null, null);
        } else {
            const startDate = new Date(startDateInput.value);
            const endDate = new Date(endDateInput.value);
            endDate.setHours(23, 59, 59, 999); // Include full end date
            await downloadThingData(thingId, startDate, endDate);
        }
    });
    
    // Initial setup
    toggleDateRange();
    validateDates();
}

// Make selectDatastream available globally for onclick handlers
window.selectDatastream = selectDatastream;