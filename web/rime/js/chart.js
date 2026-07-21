// Oscilloscope chart panel — time-series trace rendering and navigation.

const CHART_TRACE_COLOR = '#22d3ee';
// Break the trace when an interval exceeds this multiple of the estimated cadence.
const GAP_CADENCE_FACTOR = 2.5;
const CHART_ANIMATION_MS = 420;

const CHART_IDLE_HTML = `
    <div class="no-data-message">
        <div class="no-data-icon" aria-hidden="true">
            <svg viewBox="0 0 48 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M1 12h7l3-9 5 18 4-13 3 7h6l3-4 4 4h8" />
            </svg>
        </div>
        <h3>No signal locked</h3>
        <p>Select a datastream from a Thing to trace its time series</p>
    </div>`;

function initChartPanel() {
    const chartPanelTitle = document.querySelector('.chart-panel-title > div:not(.chart-panel-nav)');
    if (chartPanelTitle) {
        chartPanelTitle.addEventListener('click', (e) => {
            if (!e.target.closest('button') && !e.target.closest('.chart-panel-nav')) {
                toggleChartPanel();
            }
        });
    }

    const chartPanelToggle = document.getElementById('chartPanelToggle');
    if (chartPanelToggle) {
        chartPanelToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleChartPanel();
        });
    }

    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const limit = parseInt(e.target.dataset.limit || e.target.closest('button').dataset.limit, 10);
            setChartLimit(limit);
        });
    });

    const chartNextDatastreamBtn = document.getElementById('chartNextDatastreamBtn');
    if (chartNextDatastreamBtn) {
        chartNextDatastreamBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            navigateToDatastream(1);
        });
    }
}

function resetChartPanel() {
    destroyChartInstance();

    state.currentDatastream = null;
    state.currentDatastreamIndex = -1;

    const dsPills = document.getElementById('chartDatastreamPills');
    if (dsPills) {
        dsPills.hidden = true;
        dsPills.innerHTML = '';
    }

    const content = document.getElementById('chartPanelContent');
    if (content) content.innerHTML = CHART_IDLE_HTML;

    document.getElementById('chartTitle').textContent = 'No signal locked';
    document.getElementById('chartSubtitle').textContent = 'Select a datastream from a Thing to trace it';
    document.getElementById('chartNextDatastreamBtn').style.display = 'none';
}

async function selectDatastream(datastreamId, datastreamName) {
    state.currentDatastream = datastreamId;
    state.currentDatastreamIndex = state.currentThingDatastreams.findIndex(
        ds => frostEntityId(ds) === datastreamId
    );

    document.querySelectorAll('.metadata-datastream-item').forEach(item => {
        item.classList.remove('active');
    });

    document.getElementById('chartTitle').textContent = datastreamName;
    document.getElementById('chartSubtitle').textContent = `Datastream ID: ${datastreamId}`;

    const chartPanel = document.getElementById('chartPanel');
    if (!chartPanel.classList.contains('expanded')) {
        chartPanel.classList.add('expanded');
    }

    mobileCollapseRoster();
    hideThingMetadata();
    updateDatastreamNavigation();
    renderDatastreamPills(datastreamId);

    await loadChartData(datastreamId);
}

function renderDatastreamPills(activeId) {
    const container = document.getElementById('chartDatastreamPills');
    if (!container) return;

    const datastreams = state.currentThingDatastreams || [];
    if (datastreams.length < 2) {
        container.hidden = true;
        container.innerHTML = '';
        return;
    }

    container.innerHTML = '';
    const fragment = document.createDocumentFragment();

    datastreams.forEach(ds => {
        const id = frostEntityId(ds);
        const displayName = formatDatastreamName(ds.name);
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'chart-ds-pill' + (id === activeId ? ' active' : '');
        pill.dataset.datastreamId = id;
        pill.textContent = displayName;
        pill.title = displayName;
        pill.addEventListener('click', (e) => {
            e.stopPropagation();
            if (id !== state.currentDatastream) {
                selectDatastream(id, displayName);
            }
        });
        fragment.appendChild(pill);
    });

    container.appendChild(fragment);
    container.hidden = false;
}

function ensureChartShell() {
    const content = document.getElementById('chartPanelContent');
    if (!content || content.querySelector('#chartTrace')) return;

    content.innerHTML = `
        <div class="chart-trace" id="chartTrace">
            <div class="chart-stats" id="chartStats"></div>
            <div class="chart-container">
                <canvas id="timeSeriesChart"></canvas>
            </div>
        </div>
        <div class="chart-overlay" id="chartOverlay" hidden></div>`;
}

function showChartOverlay(html) {
    ensureChartShell();
    const overlay = document.getElementById('chartOverlay');
    const trace = document.getElementById('chartTrace');
    if (!overlay || !trace) return;

    overlay.innerHTML = html;
    overlay.hidden = false;
    trace.classList.add('is-dimmed');
}

function hideChartOverlay() {
    const overlay = document.getElementById('chartOverlay');
    const trace = document.getElementById('chartTrace');
    if (overlay) {
        overlay.hidden = true;
        overlay.innerHTML = '';
    }
    trace?.classList.remove('is-dimmed');
}

function destroyChartInstance() {
    if (state.currentChart) {
        state.currentChart.destroy();
        state.currentChart = null;
    }
}

async function loadChartData(datastreamId) {
    updateStatus('Loading chart data...', '');
    showChartOverlay('<div class="no-data-message"><div class="loading"></div> Loading trace…</div>');

    try {
        const dsResponse = await frostFetch(`${state.frostRoot}/Datastreams(${datastreamId})`);
        if (!dsResponse.ok) throw new Error(`HTTP error! Status: ${dsResponse.status}`);

        const dsData = await dsResponse.json();
        const unitSymbol = frostUnitSymbol(dsData);
        const datastreamName = formatDatastreamName(dsData.name || 'Unknown');

        const points = await fetchChartPoints(datastreamId, state.currentLimit);
        if (points.length === 0) {
            destroyChartInstance();
            document.getElementById('chartPanelContent').innerHTML = `
                <div class="no-data-message">
                    <h3>No observations found</h3>
                    <p>This datastream has no observation data available.</p>
                </div>`;
            updateStatus('No data available', 'warning');
            return;
        }

        const cadenceMs = estimateCadenceMs(points);
        const segments = splitTraceSegments(points, cadenceMs);
        const stats = calculateChartStats(points, segments.length, unitSymbol, cadenceMs);

        renderOrUpdateChart(points, cadenceMs, unitSymbol, datastreamName, stats);
        hideChartOverlay();
        updateStatus(`Loaded ${stats.totalPoints} observations`, 'success');
    } catch (error) {
        console.error('Error loading chart data:', error);
        destroyChartInstance();
        document.getElementById('chartPanelContent').innerHTML = `
            <div class="no-data-message">
                <h3>Error loading data</h3>
                <p>${error.message}</p>
            </div>`;
        updateStatus(`Error: ${error.message}`, 'error');
    }
}

const CHART_OBSERVATIONS_PAGE_SIZE = 10;

async function fetchChartPoints(datastreamId, pointLimit) {
    let nextUrl =
        `${state.frostRoot}/Datastreams(${datastreamId})/Observations` +
        `?$top=${CHART_OBSERVATIONS_PAGE_SIZE}&$orderby=phenomenonTime%20desc`;
    const collected = [];

    while (nextUrl) {
        const obsResponse = await frostFetch(nextUrl);
        if (!obsResponse.ok) throw new Error(`HTTP error! Status: ${obsResponse.status}`);

        const obsData = await obsResponse.json();
        const page = obsData.value || [];
        if (page.length === 0) break;

        for (const obs of page) {
            const remaining = pointLimit - collected.length;
            collected.push(...expandObservationToPoints(obs, remaining > 0 ? remaining : null));
            if (collected.length >= pointLimit) break;
        }

        if (collected.length >= pointLimit) break;

        nextUrl = frostNextLink(obsData, nextUrl);
        if (nextUrl) nextUrl = nextUrl.replace(/^http:/, window.location.protocol);
    }

    if (collected.length === 0) return [];

    collected.sort((a, b) => a.x.getTime() - b.x.getTime());
    if (collected.length > pointLimit) {
        return collected.slice(-pointLimit);
    }
    return collected;
}

function medianOf(sortedValues) {
    if (sortedValues.length === 0) return null;
    const mid = Math.floor(sortedValues.length / 2);
    if (sortedValues.length % 2 === 0) {
        return (sortedValues[mid - 1] + sortedValues[mid]) / 2;
    }
    return sortedValues[mid];
}

function interPointDeltasMs(points) {
    const deltas = [];
    for (let i = 1; i < points.length; i += 1) {
        const delta = points[i].x.getTime() - points[i - 1].x.getTime();
        if (delta > 0) deltas.push(delta);
    }
    return deltas;
}

// Infer reporting cadence from inter-arrival times, ignoring intervals that
// already look like outages so a long gap does not skew the estimate.
function estimateCadenceMs(points) {
    const deltas = interPointDeltasMs(points);
    if (deltas.length === 0) return null;

    deltas.sort((a, b) => a - b);
    let cadence = medianOf(deltas);
    if (!cadence) return null;

    const inliers = deltas.filter(d => d <= cadence * 4);
    if (inliers.length >= Math.max(2, Math.ceil(deltas.length * 0.25))) {
        inliers.sort((a, b) => a - b);
        cadence = medianOf(inliers);
    }

    return cadence;
}

function gapThresholdMs(cadenceMs) {
    if (!cadenceMs || cadenceMs <= 0) return Infinity;
    return cadenceMs * GAP_CADENCE_FACTOR;
}

function formatCadence(ms) {
    if (!ms || ms <= 0) return null;
    const seconds = ms / 1000;
    if (seconds < 90) return `${Math.round(seconds)}s`;
    const minutes = ms / 60000;
    if (minutes < 90) return `${Math.round(minutes)}m`;
    const hours = ms / 3600000;
    if (hours < 48) return `${hours < 10 ? hours.toFixed(1) : Math.round(hours)}h`;
    const days = ms / 86400000;
    return `${days < 10 ? days.toFixed(1) : Math.round(days)}d`;
}

function splitTraceSegments(points, cadenceMs) {
    if (points.length === 0) return [];
    if (points.length === 1) return [points];

    const gapMs = gapThresholdMs(cadenceMs);
    const segments = [[points[0]]];
    for (let i = 1; i < points.length; i += 1) {
        const prev = points[i - 1];
        const curr = points[i];
        const interval = curr.x.getTime() - prev.x.getTime();
        if (interval > gapMs) {
            segments.push([curr]);
        } else {
            segments[segments.length - 1].push(curr);
        }
    }
    return segments;
}

function calculateChartStats(points, segmentCount, unitSymbol, cadenceMs) {
    const values = points.map(p => p.y);
    const current = values[values.length - 1];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const gaps = Math.max(0, segmentCount - 1);

    return {
        current: current.toFixed(2),
        min: min.toFixed(2),
        max: max.toFixed(2),
        avg: avg.toFixed(2),
        unit: unitSymbol,
        gaps,
        cadence: formatCadence(cadenceMs),
        totalPoints: values.length,
        latestTime: points[points.length - 1].x,
    };
}

function renderChartStats(stats) {
    let latestStampHTML = '';
    if (stats.latestTime instanceof Date && !Number.isNaN(stats.latestTime.getTime())) {
        const mins = (Date.now() - stats.latestTime.getTime()) / 60000;
        const tier = getHealthTier(mins);
        const absText = stats.latestTime.toLocaleString([], {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
        const relText = formatTimeSince(mins);
        const bg = hexToRgba(tier.color, 0.14);
        const bd = hexToRgba(tier.color, 0.34);
        const fg = lightenHex(tier.color, 0.35);
        latestStampHTML = `
            <div class="stat-timestamp" title="${absText}"
                 style="background:${bg};border-color:${bd};color:${fg};">
                ${relText}
            </div>`;
    }

    return `
        <div class="stat-card">
            <span class="stat-label">Latest</span>
            <span class="stat-value">${stats.current}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
            ${latestStampHTML}
        </div>
        <div class="stat-card">
            <span class="stat-label">Min</span>
            <span class="stat-value">${stats.min}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Max</span>
            <span class="stat-value">${stats.max}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Avg</span>
            <span class="stat-value">${stats.avg}<span class="stat-unit">${stats.unit ? ' ' + stats.unit : ''}</span></span>
        </div>
        ${stats.gaps > 0 ? `
        <div class="stat-card stat-card-gap">
            <span class="stat-label">Gaps</span>
            <span class="stat-value"><span class="gap-indicator"></span>${stats.gaps}</span>
        </div>` : ''}
        <div class="stat-card">
            <span class="stat-label">Points</span>
            <span class="stat-value">${stats.totalPoints}</span>
        </div>
        ${stats.cadence ? `
        <div class="stat-card">
            <span class="stat-label">Cadence</span>
            <span class="stat-value">~${stats.cadence}</span>
        </div>` : ''}`;
}

function buildTraceDataset(points, cadenceMs, datastreamName, unitSymbol, gradient) {
    const gapMs = gapThresholdMs(cadenceMs);

    function intervalBefore(index) {
        if (index <= 0) return 0;
        return points[index].x.getTime() - points[index - 1].x.getTime();
    }

    function isGapBoundary(index) {
        return index > 0 && intervalBefore(index) > gapMs;
    }

    return {
        label: datastreamName,
        unitSymbol,
        data: points,
        parsing: false,
        borderColor: CHART_TRACE_COLOR,
        backgroundColor: gradient,
        borderWidth: 2,
        fill: 'origin',
        tension: 0.22,
        cubicInterpolationMode: 'monotone',
        pointRadius: 0,
        pointHoverRadius: 0,
        pointHitRadius: 10,
        // Break line and fill at cadence gaps without splitting into separate
        // datasets (which caused post-gap traces to drop out).
        segment: {
            borderColor(ctx) {
                return isGapBoundary(ctx.p1DataIndex) ? 'transparent' : CHART_TRACE_COLOR;
            },
            backgroundColor(ctx) {
                return isGapBoundary(ctx.p1DataIndex) ? 'transparent' : gradient;
            },
        },
    };
}

function buildChartOptions(points) {
    const xTimes = points.map(p => p.x.getTime());
    const xMin = xTimes.length ? Math.min(...xTimes) : undefined;
    const xMax = xTimes.length ? Math.max(...xTimes) : undefined;

    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: CHART_ANIMATION_MS,
            easing: 'easeOutQuart',
        },
        interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false,
        },
        elements: {
            point: {
                radius: 0,
                hoverRadius: 0,
                hitRadius: 10,
            },
        },
        plugins: {
            legend: { display: false },
            decimation: {
                enabled: points.length > 600,
                algorithm: 'lttb',
                samples: 600,
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
                    label(context) {
                        const v = context.parsed.y;
                        const unit = context.dataset.unitSymbol || '';
                        return `${v != null ? v.toFixed(2) : 'N/A'} ${unit}`.trim();
                    },
                },
            },
        },
        scales: {
            x: {
                type: 'time',
                min: xMin,
                max: xMax,
                time: {
                    tooltipFormat: 'yyyy-MM-dd HH:mm',
                    displayFormats: {
                        minute: 'HH:mm',
                        hour: 'HH:mm',
                        day: 'MMM dd',
                    },
                },
                border: { display: false },
                ticks: {
                    autoSkip: true,
                    maxTicksLimit: 8,
                    maxRotation: 0,
                    color: '#6b7c93',
                    font: { family: "'JetBrains Mono', monospace", size: 10 },
                },
                grid: { display: false },
            },
            y: {
                beginAtZero: false,
                border: { display: false },
                ticks: {
                    color: '#6b7c93',
                    font: { family: "'JetBrains Mono', monospace", size: 10 },
                    padding: 8,
                },
                grid: {
                    color: 'rgba(140, 170, 210, 0.1)',
                    drawTicks: false,
                },
            },
        },
    };
}

function renderOrUpdateChart(points, cadenceMs, unitSymbol, datastreamName, stats) {
    ensureChartShell();

    const statsEl = document.getElementById('chartStats');
    if (statsEl) statsEl.innerHTML = renderChartStats(stats);

    const canvas = document.getElementById('timeSeriesChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 340);
    gradient.addColorStop(0, 'rgba(34, 211, 238, 0.35)');
    gradient.addColorStop(0.55, 'rgba(34, 211, 238, 0.08)');
    gradient.addColorStop(1, 'rgba(34, 211, 238, 0)');

    const dataset = buildTraceDataset(points, cadenceMs, datastreamName, unitSymbol, gradient);
    const options = buildChartOptions(points);

    Chart.defaults.font.family = "'Space Grotesk', sans-serif";
    Chart.defaults.color = '#9fb0c3';

    if (state.currentChart) {
        state.currentChart.data.datasets = [dataset];
        state.currentChart.options.scales.x.min = options.scales.x.min;
        state.currentChart.options.scales.x.max = options.scales.x.max;
        state.currentChart.options.elements = options.elements;
        state.currentChart.options.plugins.decimation = options.plugins.decimation;
        state.currentChart.update('active');
        scheduleChartResize();
        return;
    }

    state.currentChart = new Chart(ctx, {
        type: 'line',
        data: { datasets: [dataset] },
        options,
    });
    scheduleChartResize();
}

function scheduleChartResize() {
    requestAnimationFrame(() => {
        state.currentChart?.resize();
    });
}

function setChartLimit(limit) {
    state.currentLimit = limit;

    document.querySelectorAll('.chart-panel-btn[data-limit]').forEach(btn => {
        btn.classList.toggle('active', parseInt(btn.dataset.limit, 10) === limit);
    });

    if (state.currentDatastream) {
        loadChartData(state.currentDatastream);
    }
}

function toggleChartPanel() {
    document.getElementById('chartPanel')?.classList.toggle('expanded');
}

function updateDatastreamNavigation() {
    const nextBtn = document.getElementById('chartNextDatastreamBtn');
    if (!nextBtn) return;

    const hasMultiple = state.currentThingDatastreams.length > 1;
    nextBtn.style.display = hasMultiple ? 'flex' : 'none';
    nextBtn.disabled = false;
}

function navigateToDatastream(direction) {
    if (state.currentThingDatastreams.length === 0) return;

    let newIndex = state.currentDatastreamIndex + direction;
    if (newIndex < 0) {
        newIndex = state.currentThingDatastreams.length - 1;
    } else if (newIndex >= state.currentThingDatastreams.length) {
        newIndex = 0;
    }

    const datastream = state.currentThingDatastreams[newIndex];
    selectDatastream(frostEntityId(datastream), formatDatastreamName(datastream.name));
}
