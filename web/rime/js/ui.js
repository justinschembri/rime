// Shared UI helpers — status bar, loading overlay, mobile sheet, endpoint switcher.

const isMobileView = () => window.matchMedia('(max-width: 640px)').matches;

function mobileCollapseRoster() {
    if (!isMobileView()) return;
    document.getElementById('roster')?.classList.remove('sheet-expanded');
}

function initMobileBottomSheet() {
    const roster = document.getElementById('roster');
    const handle = document.getElementById('sheetHandle');
    const head = roster?.querySelector('.roster-head');
    const mapEl = document.getElementById('map');
    const searchBox = document.getElementById('searchBox');
    const searchToggle = document.getElementById('mobileSearchToggle');
    const chartTraceToggle = document.getElementById('chartTraceToggle');
    const chartPanel = document.getElementById('chartPanel');

    function sheetToggle(e) {
        if (!isMobileView()) return;
        if (e && e.target.closest('button, a, input, select')) return;
        roster.classList.toggle('sheet-expanded');
        setTimeout(() => state.map?.invalidateSize(), 420);
    }

    if (handle) handle.addEventListener('click', sheetToggle);
    if (head) head.addEventListener('click', sheetToggle);

    if (mapEl) {
        mapEl.addEventListener('click', () => {
            if (!isMobileView()) return;
            roster?.classList.remove('sheet-expanded');
            searchBox?.classList.remove('mobile-open');
            searchToggle?.classList.remove('active');
        });
    }

    if (searchToggle && searchBox) {
        searchToggle.addEventListener('click', () => {
            if (!isMobileView()) return;
            const opening = !searchBox.classList.contains('mobile-open');
            searchBox.classList.toggle('mobile-open', opening);
            searchToggle.classList.toggle('active', opening);
            if (opening) searchBox.querySelector('input')?.focus();
        });

        searchBox.querySelector('input')?.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' || e.key === 'Enter') {
                searchBox.classList.remove('mobile-open');
                searchToggle.classList.remove('active');
            }
        });
    }

    if (chartTraceToggle && chartPanel) {
        chartTraceToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!isMobileView()) return;
            const expanding = !chartPanel.classList.contains('mobile-trace-expanded');
            chartPanel.classList.toggle('mobile-trace-expanded', expanding);
            chartTraceToggle.classList.toggle('trace-active', expanding);
            const label = chartTraceToggle.querySelector('.trace-label');
            if (label) label.textContent = expanding ? 'Stats' : 'Trace';
        });
    }
}

function updateStatus(message, type = '') {
    const statusEl = document.getElementById('statusMessage');
    statusEl.className = `status-message ${type}`;
    statusEl.innerHTML = '<span class="status-dot"></span>';
    statusEl.appendChild(document.createTextNode(message));
}

let _loadingHideTimer = null;

function showLoadingOverlay(title, subtitle, type = 'loading') {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;
    if (_loadingHideTimer) {
        clearTimeout(_loadingHideTimer);
        _loadingHideTimer = null;
    }

    if (type === 'loading') overlay.classList.remove('status-error');

    if (title) document.getElementById('loadingTitle').textContent = title;
    if (subtitle !== undefined) document.getElementById('loadingSubtitle').textContent = subtitle;

    overlay.classList.remove('is-leaving', 'status-error');
    if (type === 'error') overlay.classList.add('status-error');

    overlay.hidden = false;
}

function showErrorOverlay(title, subtitle) {
    showLoadingOverlay(title, subtitle, 'error');
}

function updateLoadingOverlay(subtitle) {
    const sub = document.getElementById('loadingSubtitle');
    if (sub && subtitle !== undefined) sub.textContent = subtitle;
}

function hideLoadingOverlay(force = false) {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay || overlay.hidden) return;

    if (!force && overlay.classList.contains('status-error')) return;

    overlay.classList.add('is-leaving');
    _loadingHideTimer = setTimeout(() => {
        overlay.hidden = true;
        overlay.classList.remove('is-leaving', 'status-error');
        _loadingHideTimer = null;
    }, 460);
}

function initializeEndpointSwitcher() {
    const display = document.getElementById('endpointDisplay');
    const popover = document.getElementById('endpointPopover');
    const input = document.getElementById('endpointInput');
    const applyBtn = document.getElementById('endpointApply');
    const label = document.getElementById('endpointLabel');
    const versionGroup = document.getElementById('endpointVersionGroup');
    const authToggle = document.getElementById('endpointAuthToggle');
    const authFields = document.getElementById('endpointAuthFields');
    const authChevron = document.getElementById('endpointAuthChevron');
    const authToggleLabel = document.getElementById('endpointAuthToggleLabel');
    const usernameInput = document.getElementById('endpointUsername');
    const passwordInput = document.getElementById('endpointPassword');

    function syncLabel() {
        const host = state.frostBase.replace(/^https?:\/\//, '');
        label.textContent = `${host} @ ${state.frostVersion}`;
        display.classList.toggle('has-auth', !!state.frostReadAuth);
    }
    syncLabel();

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

    popover.querySelectorAll('.endpoint-quickpick').forEach(btn => {
        btn.addEventListener('click', () => {
            input.value = btn.dataset.base;
            input.focus();
        });
    });

    authToggle.addEventListener('click', () => {
        const isOpen = !authFields.hidden;
        authFields.hidden = isOpen;
        authChevron.style.transform = isOpen ? '' : 'rotate(180deg)';
        authToggleLabel.textContent = isOpen ? 'Add credentials' : 'Hide credentials';
        if (!isOpen) usernameInput.focus();
    });

    function openPopover() {
        input.value = state.frostBase;
        syncVersionButtons();

        if (state.frostReadAuth) {
            try {
                const decoded = atob(state.frostReadAuth);
                const colon = decoded.indexOf(':');
                usernameInput.value = decoded.substring(0, colon);
                passwordInput.value = decoded.substring(colon + 1);
            } catch (_) { /* ignore malformed auth */ }
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

    function applyEndpoint() {
        let raw = input.value.trim().replace(/\/+$/, '');

        const versionMatch = raw.match(/\/(v\d+(?:\.\d+)?)$/i);
        if (versionMatch) {
            let v = versionMatch[1].toLowerCase();
            if (v === 'v1') v = 'v1.0';
            else if (v === 'v2') v = 'v2.0';

            const known = ['v1.0', 'v1.1', 'v2.0'];
            if (known.includes(v)) {
                state.frostVersion = v;
                syncVersionButtons();
            }
            raw = raw.replace(/\/(v\d+(?:\.\d+)?)$/i, '');
        }

        if (!raw) {
            closePopover();
            return;
        }

        const user = usernameInput.value.trim();
        const pass = passwordInput.value;
        state.frostBase = raw;
        state.frostReadAuth = (user || pass) ? btoa(`${user}:${pass}`) : null;

        syncLabel();
        closePopover();
        resetAndReload();
    }

    applyBtn.addEventListener('click', applyEndpoint);
    [input, usernameInput, passwordInput].forEach(el => {
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') applyEndpoint();
            if (e.key === 'Escape') closePopover();
        });
    });
}

function resetAndReload() {
    hideThingMetadata();
    document.getElementById('chartPanel')?.classList.remove('expanded');

    if (state.markerCluster) state.markerCluster.clearLayers();

    state.things = {};
    state.thingsByName = {};
    state.markers = {};
    state.currentThingDatastreams = [];
    state.selectedThingId = null;
    state.maxClusterSize = 1;
    state.searchQuery = '';
    state.activeStatusFilter = 'all';
    state.showVirtualThings = false;

    document.getElementById('thingsList').innerHTML = '';
    const locationsListEl = document.getElementById('locationsList');
    if (locationsListEl) locationsListEl.innerHTML = '';
    const virtualCheckbox = document.getElementById('virtualThingsCheckbox');
    if (virtualCheckbox) virtualCheckbox.checked = false;
    document.querySelector('.app-shell')?.classList.remove('virtual-things-mode', 'roster-collapsed');
    clearVirtualLayer();
    syncVirtualModeChrome();
    setRosterView('things');
    resetChartPanel();

    document.getElementById('searchInput').value = '';
    document.querySelectorAll('.legend-chip').forEach(c => c.classList.remove('active'));
    document.querySelector('.legend-chip[data-filter="all"]')?.classList.add('active');
    ['countTotal', ...[...HEALTH_TIERS, NODATA_TIER].map(t => `count-${t.key}`)].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '0';
    });
    setHealthCheckButtonState('disabled');

    fetchThings();
}
