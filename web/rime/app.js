// Core application — map, health, things fetch, metadata, and bootstrap.
// Shared modules: js/config.js, js/state.js, js/api.js, js/ui.js, js/chart.js, js/roster.js

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
        // Disable the built-in top-left zoom control (the roster sits over it);
        // custom +/- buttons live in the right-side .map-controls stack instead.
        zoomControl: false,
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
    buildLegend();

    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        filterThings(e.target.value);
    });

    document.querySelectorAll('.legend-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const filter = chip.dataset.filter;
            setStatusFilter(state.activeStatusFilter === filter ? 'all' : filter);
        });
    });

    const healthCheckBtn = document.getElementById('healthCheckBtn');
    if (healthCheckBtn) {
        healthCheckBtn.addEventListener('click', runHealthCheck);
    }

    initializeEndpointSwitcher();
    initChartPanel();

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

    document.querySelectorAll('.roster-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => setRosterView(btn.dataset.view));
    });

    const zoomInBtn = document.getElementById('zoomInBtn');
    if (zoomInBtn) zoomInBtn.addEventListener('click', () => state.map && state.map.zoomIn());
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => state.map && state.map.zoomOut());

    const zoomExtentsBtn = document.getElementById('zoomExtentsBtn');
    if (zoomExtentsBtn) zoomExtentsBtn.addEventListener('click', zoomToExtents);

    const thingMetadataClose = document.getElementById('thingMetadataClose');
    if (thingMetadataClose) {
        thingMetadataClose.addEventListener('click', () => hideThingMetadata());
    }

    const loadingErrorBtn = document.getElementById('loadingErrorBtn');
    if (loadingErrorBtn) {
        loadingErrorBtn.addEventListener('click', () => hideLoadingOverlay(true));
    }

    initMobileBottomSheet();
}

// Non-health UI colours (health tier colours come from HEALTH_TIER_MAP).
const SELECTED_COLOR = '#22d3ee';
const UNKNOWN_COLOR  = '#6b7c93';

// Resolve any status key (health tier, 'selected', or 'unknown') to a colour.
function getStatusColor(status) {
    if (status === 'selected') return SELECTED_COLOR;
    if (!status || status === 'unknown') return UNKNOWN_COLOR;
    return HEALTH_TIER_MAP[status]?.color || UNKNOWN_COLOR;
}

// Build a status-aware map marker icon
function makePinIcon(status, isSelected) {
    const color = isSelected ? SELECTED_COLOR : getStatusColor(status);
    const classes = ['rime-pin'];
    if (isSelected) classes.push('selected');
    // Only the freshest tier pulses (keeps the map calm once health is graded).
    if (status === 'fresh' && !isSelected) classes.push('pulse');
    return L.divIcon({
        className: 'custom-marker',
        html: `<div class="${classes.join(' ')}" style="position:relative;background:${color};color:${color};"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
    });
}

// Map "minutes since last observation" to a graded health tier.
function calculateThingHealthStatus(timeSinceLastObservationMinutes) {
    const tier = getHealthTier(timeSinceLastObservationMinutes);
    return { status: tier.key, label: tier.label, color: tier.color };
}


// Format time since last observation
function formatTimeSince(minutes) {
    if (minutes === null || minutes === undefined || Number.isNaN(minutes)) {
        return 'Never';
    }

    if (minutes < 60) {
        return `${Math.round(minutes)}m ago`;
    } else if (minutes < 1440) {
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        return `${hours}h ${mins}m ago`;
    } else if (minutes < 43200) {
        const days = Math.floor(minutes / 1440);
        const hours = Math.floor((minutes % 1440) / 60);
        return `${days}d ${hours}h ago`;
    } else if (minutes < 525600) {
        const months = Math.floor(minutes / 43200);
        const days = Math.floor((minutes % 43200) / 1440);
        return `${months}mo ${days}d ago`;
    } else {
        const years = Math.floor(minutes / 525600);
        const months = Math.floor((minutes % 525600) / 43200);
        return `${years}y ${months}mo ago`;
    }
}

// Update status tags on things
function updateThingStatusTags() {
    // Update roster list — skip nodes whose health is not yet known
    document.querySelectorAll('.thing-item').forEach(item => {
        const thingId = item.dataset.thingId;
        const thing = state.things[thingId];
        if (!thing || !thing.healthStatus || thing.healthStatus === 'unknown') return;
        updateThingItemStatus(item, thing.healthStatus, thing.healthLabel, thing.timeSinceLastObservation);
    });

    refreshMarkerStatusColors();
    updateStatusCounts();

    // Update metadata sidebar if open
    const metadataSidebar = document.getElementById('thingMetadataSidebar');
    if (metadataSidebar && metadataSidebar.classList.contains('open')) {
        const thingId = Object.keys(state.things).find(id => {
            const t = state.things[id];
            return t && document.getElementById('thingMetadataTitle')?.textContent === t.name;
        });
        if (thingId) {
            const thing = state.things[thingId];
            if (thing.healthStatus && thing.healthStatus !== 'unknown') {
                updateMetadataSidebarStatus(thing.healthStatus, thing.healthLabel, thing.timeSinceLastObservation);
            }
        }
    }
}

// Apply a health tier's colour scheme to a pill-style element (roster tag or
// inspector status tag).
function applyTierStyle(el, status) {
    const color = getStatusColor(status);
    el.style.background = hexToRgba(color, 0.14);
    el.style.borderColor = hexToRgba(color, 0.34);
    el.style.color = lightenHex(color, 0.35);
}

// Update thing item with status tag
function updateThingItemStatus(item, status, label, timeSince = null) {
    // Reflect status on the item's accent border via a CSS custom property
    item.style.setProperty('--status-color', getStatusColor(status));
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
    statusTag.className = 'thing-status-tag';
    applyTierStyle(statusTag, status);
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
    const timeText = timeSince !== null ? `<div class="metadata-value" style="font-size: 0.8rem; color: var(--txt-dim); margin-top: 0.5rem;">Last observation: ${formatTimeSince(timeSince)}</div>` : '';
    statusSection.innerHTML = `
        <div class="metadata-section">
            <h3>Status</h3>
            <div class="metadata-item">
                <div class="status-tag">${label}</div>
                ${timeText}
            </div>
        </div>
    `;
    const tag = statusSection.querySelector('.status-tag');
    if (tag) applyTierStyle(tag, status);

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

// ── Manual health check ──────────────────────────────────────────────────
// The graded health scan (fetchHealthData) is heavy on the FROST server, so it
// runs only when the user presses the "Check health" button — never on load,
// never per click, never on a timer.
function setHealthCheckButtonState(stateName) {
    const btn = document.getElementById('healthCheckBtn');
    const label = document.getElementById('healthCheckLabel');
    if (!btn || !label) return;

    btn.classList.remove('checking', 'done');
    switch (stateName) {
        case 'disabled':                 // before nodes are loaded
            btn.disabled = true;
            label.textContent = 'Check health';
            break;
        case 'ready':                    // nodes loaded, scan not yet run
            btn.disabled = false;
            label.textContent = 'Check health';
            break;
        case 'checking':                 // scan in progress
            btn.disabled = true;
            btn.classList.add('checking');
            label.textContent = 'Checking…';
            break;
        case 'done':                     // scan finished, allow manual rescan
            btn.disabled = false;
            btn.classList.add('done');
            label.textContent = 'Recheck';
            break;
    }
}

async function runHealthCheck() {
    const btn = document.getElementById('healthCheckBtn');
    if (!btn || btn.disabled) return;
    if (Object.keys(state.things).length === 0) return;

    setHealthCheckButtonState('checking');
    updateStatus('Scanning Thing health…', '');
    try {
        await fetchHealthData(state.fetchGeneration);
        setHealthCheckButtonState('done');
    } catch (err) {
        console.error('Health check failed:', err);
        updateStatus(`Health check failed: ${err.message}`, 'error');
        setHealthCheckButtonState('ready');
        
        if (!document.getElementById('loadingOverlay')?.classList.contains('status-error')) {
            if (err instanceof TypeError || err.message.startsWith('HTTP error') || err.message.includes('Failed to fetch')) {
                const msg = (err instanceof TypeError || err.message.includes('Failed to fetch')) 
                    ? 'Network or CORS error. Check endpoint and credentials.' 
                    : err.message;
                showErrorOverlay('Health Check Failed', msg);
            }
        }
    }
}

// ── Status legend ──────────────────────────────────────────────────────────
// Builds the graded health legend/filters from HEALTH_TIERS so colours and
// labels stay in sync with config.js. The "all" (total) chip is authored in
// HTML; tier chips are injected after it.
function buildLegend() {
    const legend = document.getElementById('statusLegend');
    if (!legend) return;

    // Remove any previously-built tier chips (keep the total chip).
    legend.querySelectorAll('.legend-chip[data-tier]').forEach(el => el.remove());

    [...HEALTH_TIERS, NODATA_TIER].forEach(tier => {
        const chip = document.createElement('button');
        chip.className = 'legend-chip';
        chip.dataset.filter = tier.key;
        chip.dataset.tier = tier.key;
        chip.title = `${tier.label} since last observation`;
        chip.innerHTML = `
            <span class="legend-dot" style="background:${tier.color};box-shadow:0 0 9px ${tier.color};color:${tier.color}"></span>
            <span class="legend-count" id="count-${tier.key}">0</span>
            <span class="legend-label">${tier.label}</span>
        `;
        legend.appendChild(chip);
    });
}

// ── Phase 1: place all markers on the map as fast as possible ────────────
// Uses $expand=Locations only — the lightest query the server can answer.
// Health (Phase 2) is NOT triggered automatically: once markers are placed the
// "Check health" button is enabled so the user can run the heavy scan on demand.
async function fetchThings() {
    const gen = ++state.fetchGeneration;
    const stale = () => state.fetchGeneration !== gen;

    setHealthCheckButtonState('disabled');
    updateStatus('Fetching Things…', '');
    showLoadingOverlay('Fetching Things…', 'Contacting the SensorThings Server');

    const allThings = [];
    // Large $top collapses dozens of sequential pages into one or two requests.
    // The $top is carried forward by @iot.nextLink, so we only set it here.
    let nextUrl = `${state.frostRoot}/Things?$expand=Locations&$top=${THINGS_PAGE_SIZE}`;

    try {
        while (nextUrl) {
            const response = await frostFetch(nextUrl);
            if (stale()) return;

            if (!response.ok) {
                if (response.status === 401) {
                    showErrorOverlay('Unauthorized', 'Invalid credentials for this server');
                }
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            const data = await response.json();
            if (stale()) return;

            const pageThings = data.value || [];
            const pageAdded  = [];
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
                state.markerCluster.addLayers(pageMarkers);

                const thingsList = document.getElementById('thingsList');
                const fragment   = document.createDocumentFragment();
                for (const thing of pageAdded) {
                    const li = buildThingListItem(thing);
                    if (li) fragment.appendChild(li);
                }
                thingsList.appendChild(fragment);
                updateStatus(`Loading… ${allThings.length} Things`, '');
                updateLoadingOverlay(`${allThings.length} Things placed…`);
                // Keep the top-bar total in sync as Things stream in, even
                // before any health check has run.
                updateStatusCounts();
            }

            nextUrl = data['@iot.nextLink'] || null;
            if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
        }

        if (stale()) return;

        if (allThings.length === 0) {
            hideLoadingOverlay();
            throw new Error('No Things found at this endpoint');
        }

        if (state.markerCluster.getLayers().length > 0) {
            state.markerCluster.refreshClusters();
            state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
                animate: true, duration: 1.0, padding: [20, 20]
            });
        }

        updateStatus(`Loaded ${allThings.length} Things · health on demand`, 'success');
        updateStatusCounts();
        hideLoadingOverlay();

        // Health is no longer scanned automatically — it is a heavy, server-
        // taxing operation. The user triggers it explicitly via the
        // "Check health" button (see runHealthCheck). Enable it now.
        setHealthCheckButtonState('ready');

    } catch (error) {
        if (stale()) return;
        
        // Show overlay for network/CORS errors which throw TypeErrors, or other HTTP errors
        if (!document.getElementById('loadingOverlay')?.classList.contains('status-error')) {
            if (error instanceof TypeError || error.message.startsWith('HTTP error') || error.message.includes('Failed to fetch')) {
                const msg = (error instanceof TypeError || error.message.includes('Failed to fetch')) 
                    ? 'Network or CORS error. Check endpoint and credentials.' 
                    : error.message;
                showErrorOverlay('Connection Failed', msg);
            }
        }

        // Don't auto-hide if we just showed an error overlay
        const overlay = document.getElementById('loadingOverlay');
        if (!overlay || !overlay.classList.contains('status-error')) {
            hideLoadingOverlay();
        }
        console.error('Error fetching things:', error);
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

// ── Phase 2 (on-demand): grade every node's health ───────────────────────
// Invoked only by runHealthCheck. Fetches a cheap count, then requests health
// pages in parallel via $skip (fallback: sequential @iot.nextLink).

const HEALTH_EXPAND =
    'Datastreams($select=id;$expand=Observations($select=phenomenonTime;$top=1;$orderby=phenomenonTime%20desc))';

function buildHealthPageUrl(skip) {
    return `${state.frostRoot}/Things?$select=id&$expand=${HEALTH_EXPAND}` +
        `&$top=${HEALTH_PAGE_SIZE}&$skip=${skip}&$orderby=%40iot.id%20asc`;
}

// Apply health grades from one paginated Things response.
function processHealthPageThings(things, gen) {
    if (state.fetchGeneration !== gen) return false;

    for (const thing of (things || [])) {
        if (state.fetchGeneration !== gen) return false;
        const stored = state.things[thing['@iot.id']];
        if (!stored) continue;

        const datastreams = thing.Datastreams || [];
        // NOTE: do NOT cache these into stored.datastreams — the health query
        // uses $select to fetch only id + phenomenonTime (no name/unit/result),
        // which would break the inspector's datastream rendering if reused.

        const times = datastreams
            .map(ds => parsePhenomenonTime(ds.Observations?.[0]?.phenomenonTime))
            .filter(Boolean);

        if (times.length > 0) {
            const mostRecent = Math.max(...times.map(t => t.getTime()));
            const mins   = (Date.now() - mostRecent) / 60000;
            const health = calculateThingHealthStatus(mins);
            stored.timeSinceLastObservation = mins;
            stored.healthStatus = health.status;
            stored.healthLabel  = health.label;
        } else {
            stored.timeSinceLastObservation = null;
            stored.healthStatus = NODATA_TIER.key;
            stored.healthLabel  = NODATA_TIER.label;
        }
    }
    return true;
}

async function fetchThingsCount(gen) {
    const response = await frostFetch(`${state.frostRoot}/Things?$count=true&$top=0`);
    if (state.fetchGeneration !== gen) return null;
    if (!response.ok) {
        if (response.status === 401) {
            showErrorOverlay('Unauthorized', 'Invalid credentials for health scan');
        }
        return null;
    }
    const data = await response.json();
    if (state.fetchGeneration !== gen) return null;
    const count = data['@iot.count'];
    return typeof count === 'number' ? count : null;
}

async function fetchHealthDataSequential(gen) {
    let nextUrl = buildHealthPageUrl(0);

    while (nextUrl) {
        if (state.fetchGeneration !== gen) return;

        const response = await frostFetch(nextUrl);
        if (state.fetchGeneration !== gen) return;
        if (!response.ok) {
            if (response.status === 401) {
                showErrorOverlay('Unauthorized', 'Invalid credentials for health scan');
            }
            return;
        }

        const data = await response.json();
        if (state.fetchGeneration !== gen) return;

        if (processHealthPageThings(data.value, gen)) {
            scheduleStatusUpdate();
        }

        nextUrl = data['@iot.nextLink'] || null;
        if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
    }
}

async function fetchHealthDataParallel(gen, total) {
    const pageCount = Math.ceil(total / HEALTH_PAGE_SIZE);
    const skips = Array.from({ length: pageCount }, (_, i) => i * HEALTH_PAGE_SIZE);
    let completed = 0;

    const taskFns = skips.map(skip => async () => {
        if (state.fetchGeneration !== gen) return;

        const response = await frostFetch(buildHealthPageUrl(skip));
        if (state.fetchGeneration !== gen) return;
        if (!response.ok) {
            if (response.status === 401) {
                showErrorOverlay('Unauthorized', 'Invalid credentials for health scan');
            }
            throw new Error(`Health page failed (skip=${skip}): HTTP ${response.status}`);
        }

        const data = await response.json();
        if (state.fetchGeneration !== gen) return;

        if (processHealthPageThings(data.value, gen)) {
            completed += 1;
            updateStatus(`Scanning Thing health… ${completed}/${pageCount}`, '');
            scheduleStatusUpdate();
        }
    });

    await runConcurrent(taskFns, HEALTH_PARALLEL_WORKERS);
}

async function fetchHealthData(gen) {
    try {
        const total = await fetchThingsCount(gen);
        if (state.fetchGeneration !== gen) return;

        if (total !== null) {
            if (total > 0) {
                await fetchHealthDataParallel(gen, total);
            }
        } else {
            // Count unavailable on this server — fall back to nextLink paging.
            await fetchHealthDataSequential(gen);
        }

        if (state.fetchGeneration === gen) {
            updateStatus(`${Object.keys(state.things).length} Things · health ready`, 'success');
        }
    } catch (err) {
        if (state.fetchGeneration === gen) {
            console.error('Error fetching health data:', err);
            throw err;
        }
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
    const locationName = locationEntry.name || '';
    const locationDescription = locationEntry.description || '';
    
    // Create custom icon for marker (status colour filled in once health is known)
    const defaultIcon = makePinIcon('unknown', false);

    // GeoJSON coordinates are [longitude, latitude]; Leaflet expects [latitude, longitude]
    const latLng = [coordinates[1], coordinates[0]];
    const marker = L.marker(latLng, {
        icon: defaultIcon
    });
    
    // Store thing data — healthStatus starts as 'unknown' (not undefined) so that
    // || 'active' fallbacks elsewhere never fire before Phase 2 sets a real value.
    state.things[thingId] = {
        marker,
        name: thing.name,
        description: thing.description || '',
        coordinates: latLng,
        locationName,
        locationDescription,
        thingId,
        healthStatus: 'unknown',
        healthLabel: null,
        timeSinceLastObservation: null,
        datastreams: [],
    };
    
    state.thingsByName[thing.name] = {
        marker,
        id: thingId,
        coordinates: latLng,
        description: thing.description || '',
        locationDescription
    };
    
    state.markers[thingId] = marker;

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

// Load datastreams (with their latest observation) for a thing.
//
// Two optimisations over the previous implementation:
//   (2) Cache: if a prior health check already inlined Datastreams+Observations
//       on this thing, render straight from cache — zero network calls.
//   (3) Single expand: otherwise fetch datastreams AND their latest observation
//       in ONE request, instead of 1 list call + N per-datastream observation
//       calls (which previously also ran twice — see the duplicate-request bug).
async function loadDatastreamsForThing(thingId, gen = state.fetchGeneration) {
    if (state.fetchGeneration !== gen) return;
    const thing = state.things[thingId];
    if (!thing) return;

    // (2) Serve from cache when datastreams already carry inline Observations.
    const cached = thing.datastreams;
    if (Array.isArray(cached) && cached.length > 0 && cached.some(ds => ds.Observations)) {
        updateThingMetadataDatastreams(thingId, cached);
        return;
    }

    try {
        // (3) One round-trip for datastreams + their single latest observation.
        const url = `${state.frostRoot}/Things(${thingId})?$expand=Datastreams($expand=Observations($top=1;$orderby=phenomenonTime%20desc))`;
        const response = await frostFetch(url);
        if (state.fetchGeneration !== gen) return;

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        if (state.fetchGeneration !== gen) return;

        const datastreams = data.Datastreams || [];
        thing.datastreams = datastreams; // cache for subsequent opens
        updateThingMetadataDatastreams(thingId, datastreams);

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

// Zoom to extents (fit all markers)
function zoomToExtents() {
    if (state.markerCluster && state.markerCluster.getLayers().length > 0) {
        state.map.fitBounds(state.markerCluster.getBounds().pad(0.1), {
            animate: true,
            duration: 1.2,
            padding: [30, 30],
            maxZoom: 18,
        });
        updateStatus('Zoomed to show all sensors', 'success');
    } else {
        updateStatus('No sensors to zoom to', 'warning');
    }
}

function updateMarkerIcon(thingId, isSelected) {
    const marker = state.markers[thingId];
    if (!marker) return;

    const thing = state.things[thingId];
    const status = (thing && thing.healthStatus) || 'unknown';
    marker.setIcon(makePinIcon(status, isSelected));
}

function refreshMarkerStatusColors() {
    Object.keys(state.markers).forEach(thingId => {
        if (state.selectedThingId === thingId) return;
        updateMarkerIcon(thingId, false);
    });
}

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
    // On mobile, collapse the roster sheet so the inspector can fill the screen
    mobileCollapseRoster();

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
    const healthStatus = (thing.healthStatus && thing.healthStatus !== 'unknown') ? thing.healthStatus : null;
    if (healthStatus) {
        updateMetadataSidebarStatus(healthStatus, thing.healthLabel, thing.timeSinceLastObservation);
    }
    
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

// Render datastreams in the inspector sidebar.
// Reads the latest reading straight from each datastream's inlined Observation
// (provided by loadDatastreamsForThing's single expand query or the health
// cache) — no per-datastream network calls.
function updateThingMetadataDatastreams(thingId, datastreams) {
    const datastreamsDiv = document.getElementById('thingMetadataDatastreams');
    if (!datastreamsDiv) return;

    // Track for the chart panel's next/prev datastream navigation.
    state.currentThingDatastreams = datastreams || [];

    if (!datastreams || datastreams.length === 0) {
        datastreamsDiv.innerHTML = '<div style="color: var(--txt-mute); font-size: 0.85rem;">No datastreams available</div>';
        return;
    }

    datastreamsDiv.innerHTML = '';
    const fragment = document.createDocumentFragment();

    datastreams.forEach((ds) => {
        const unitSymbol = ds.unitOfMeasurement?.symbol || '';
        const obs = Array.isArray(ds.Observations) ? ds.Observations[0] : null;
        const hasValue = obs && obs.result !== undefined && obs.result !== null;
        const latestValue = hasValue ? obs.result : '-';
        const latestText = `${latestValue}${hasValue && unitSymbol ? ' ' + unitSymbol : ''}`;

        // Relative time of the latest observation (handles interval times).
        const obsDate = obs ? parsePhenomenonTime(obs.phenomenonTime) : null;
        const metaLeft = obsDate
            ? formatTimeSince((Date.now() - obsDate.getTime()) / 60000)
            : 'Latest reading';

        const displayName = formatDatastreamName(ds.name);
        const dsItem = document.createElement('div');
        dsItem.className = 'metadata-datastream-item';
        dsItem.innerHTML = `
            <div class="metadata-datastream-name">${displayName}</div>
            <div class="metadata-datastream-meta">
                <span>${metaLeft}</span>
                <span class="ds-latest">${latestText}</span>
            </div>
        `;
        dsItem.addEventListener('click', () => {
            selectDatastream(ds['@iot.id'], displayName);
        });
        fragment.appendChild(dsItem);
    });

    datastreamsDiv.appendChild(fragment);
    updateDatastreamNavigation();
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