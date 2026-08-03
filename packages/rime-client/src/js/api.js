// FROST-aware fetch wrapper — injects read credentials when configured.

function frostFetch(url, options = {}) {
    if (state.frostReadAuth) {
        options = {
            ...options,
            headers: {
                Authorization: `Basic ${state.frostReadAuth}`,
                ...(options.headers || {}),
            },
        };
    }
    return fetch(url, options);
}
