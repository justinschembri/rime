// Global application state
const state = {
    things: {},
    thingsByName: {},
    markers: {},
    currentDatastream: null,
    currentChart: null,
    currentLimit: 1000,
    map: null,
    markerCluster: null,
    maxClusterSize: 1,
    currentThingDatastreams: [],
    currentDatastreamIndex: -1,
    selectedThingId: null,
    searchQuery: '',
    activeStatusFilter: 'all',
    // FROST endpoint: base URL (no version) + version string.
    // frostRoot is always kept in sync as frostBase + '/' + frostVersion.
    frostBase: `${window.location.origin}/FROST-Server`,
    frostVersion: 'v1.1',
    get frostRoot() { return `${this.frostBase}/${this.frostVersion}`; },
    frostReadAuth: null,   // Base64-encoded "user:pass" for read access, or null for anonymous
    fetchGeneration: 0,    // Incremented on every new fetch; stale generations discard their results
};

