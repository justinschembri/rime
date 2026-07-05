// Roster lists, search/filter, and Locations view.

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
            easeLinearity: 0.25,
        });
        highlightThingInList(thing.name);
        showThingMetadata(thing['@iot.id']);
        await loadDatastreamsForThing(thing['@iot.id']);
    });

    return li;
}

function appendThingToList(thing) {
    const li = buildThingListItem(thing);
    if (li) document.getElementById('thingsList').appendChild(li);
}

function highlightThingInList(thingName) {
    document.querySelectorAll('.thing-item').forEach(item => {
        item.classList.remove('active');
    });

    const thingElement = document.querySelector(
        `[data-thing-name="${thingName.replace(/"/g, '\\"')}"]`
    );
    if (thingElement) {
        thingElement.classList.add('active');
        thingElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function filterThings(query) {
    state.searchQuery = (query || '').toLowerCase().trim();
    applyFilters();
}

function setStatusFilter(filter) {
    state.activeStatusFilter = filter || 'all';

    document.querySelectorAll('.legend-chip').forEach(chip => {
        chip.classList.toggle('active', chip.dataset.filter === state.activeStatusFilter);
    });

    applyFilters();
}

function applyFilters() {
    const query = state.searchQuery || '';
    const statusFilter = state.activeStatusFilter || 'all';

    document.querySelectorAll('.thing-item:not(.location-item)').forEach(item => {
        const name = (item.dataset.thingName || '').toLowerCase();
        const status = item.dataset.status || 'unknown';
        const matchesSearch = name.includes(query);
        const matchesStatus = statusFilter === 'all' || status === statusFilter;
        item.style.display = matchesSearch && matchesStatus ? '' : 'none';
    });

    document.querySelectorAll('.location-item').forEach(item => {
        const name = (item.dataset.locationName || '').toLowerCase();
        const coords = (item.dataset.locationCoords || '').toLowerCase();
        const matchesSearch = name.includes(query) || coords.includes(query);
        item.style.display = matchesSearch ? '' : 'none';
    });
}

function setRosterView(view) {
    if (view !== 'things' && view !== 'locations') return;
    state.rosterView = view;

    document.querySelectorAll('.roster-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });

    const thingsList = document.getElementById('thingsList');
    const locationsList = document.getElementById('locationsList');

    if (view === 'locations') {
        buildLocationsList();
        if (thingsList) thingsList.hidden = true;
        if (locationsList) locationsList.hidden = false;
    } else {
        if (locationsList) locationsList.hidden = true;
        if (thingsList) thingsList.hidden = false;
    }

    applyFilters();
}

function buildLocationsList() {
    const locationsList = document.getElementById('locationsList');
    if (!locationsList) return;

    const groups = new Map();
    Object.values(state.things).forEach(thing => {
        if (!thing.coordinates) return;
        const [lat, lng] = thing.coordinates;
        const key = `${lat.toFixed(6)},${lng.toFixed(6)}`;
        let group = groups.get(key);
        if (!group) {
            group = {
                key,
                coordinates: thing.coordinates,
                name: thing.locationName || '',
                thingNames: [],
            };
            groups.set(key, group);
        }
        group.thingNames.push(thing.name);
        if (!group.name && thing.locationName) {
            group.name = thing.locationName;
        }
    });

    const locations = [...groups.values()].sort((a, b) =>
        (a.name || a.key).localeCompare(b.name || b.key)
    );

    locationsList.innerHTML = '';
    const fragment = document.createDocumentFragment();

    locations.forEach(loc => {
        const [lat, lng] = loc.coordinates;
        const label = loc.name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;

        const li = document.createElement('li');
        li.className = 'thing-item location-item';
        li.dataset.locationName = label;
        li.dataset.locationCoords = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
        li.innerHTML = `
            <div class="thing-name"><span class="thing-name-text">${label}</span></div>
            <div class="thing-description">${lat.toFixed(4)}, ${lng.toFixed(4)}</div>
        `;
        li.addEventListener('click', () => {
            state.map.setView(loc.coordinates, 16, {
                animate: true,
                duration: 0.8,
                easeLinearity: 0.25,
            });
            mobileCollapseRoster();
        });
        fragment.appendChild(li);
    });

    locationsList.appendChild(fragment);
}

function updateStatusCounts() {
    const counts = { total: 0 };
    [...HEALTH_TIERS, NODATA_TIER].forEach(t => { counts[t.key] = 0; });

    Object.values(state.things).forEach(thing => {
        counts.total += 1;
        const status = thing.healthStatus;
        if (status && status !== 'unknown' && counts[status] !== undefined) {
            counts[status] += 1;
        }
    });

    const totalEl = document.getElementById('countTotal');
    if (totalEl) totalEl.textContent = counts.total;

    [...HEALTH_TIERS, NODATA_TIER].forEach(tier => {
        const el = document.getElementById(`count-${tier.key}`);
        if (el) el.textContent = counts[tier.key];
    });

    const mobileBadge = document.getElementById('mobileStatusBadge');
    if (mobileBadge) {
        const parts = [`${counts.total}`];
        if (counts.fresh > 0) parts.push(`${counts.fresh} fresh`);
        mobileBadge.textContent = parts.join(' · ');
    }
}
