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

async function apiDelete(url) {
    const res = await fetch(url, {
        method: "DELETE"
    });
    return await res.json();
}

function evaluateCustomFunction(funcString, valuesArray) {
    try {
        const fn = eval(funcString);

        if (typeof fn !== "function") {
            throw new Error("Input must be a JavaScript function");
        }

        return fn(...valuesArray);
    } catch (error) {
        console.error("Custom function error:", error);
        return null;
    }
}