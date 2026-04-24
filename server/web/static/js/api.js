async function apiGet(url) {
    const res = await fetch(url);
    return await res.json();
}

async function apiSend(url, method, payload) {
    const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return await res.json();
}

async function loadConfig() {
    backendConfig = await apiGet("/api/config");
    renderAll();
}