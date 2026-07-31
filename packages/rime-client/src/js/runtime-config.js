// Deployment defaults for rime-client.
//
// This is the "no server configured" default: the page starts blank and asks
// the user for a SensorThings server. It applies when web/rime/ is served
// outside Docker, straight from disk or from a plain static host.
//
// In the rime-client container this file is REGENERATED at startup from the
// STA_ENDPOINT / STA_VERSION environment variables — see
// packages/rime-client/runtime-config.js.template. Edits here will not survive
// there; set the environment variables instead.
//
//   staEndpoint  STA base URL *without* the version segment — use
//                "https://sta.example.org", not "https://sta.example.org/v1.1".
//   staVersion   "v1.0", "v1.1" or "v2.0".
window.RIME_CONFIG = {
    staEndpoint: "",
    staVersion: "v1.1"
};
