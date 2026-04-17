let backendConfig = {
    ports: ["A", "B", "C"],
    available_channels: [],
    configured_sources: [],
    sensors: []
};

let sensors = [];
let chartHistory = [];
let deletedCharts = [];
let actionHistory = [];
let charts = [];
let chartInstances = new Map();

let builderMode = "basic";
let sensorBuilderMode = "basic";
let advancedEquation = "temperature";
let editingChartId = null;
let zoomChartInstance = null;
const MAX_POINTS = 50;
const POLL_INTERVAL_MS = 250;

const equationMeta = {
    temperature: { label: "temperature", defaultUnit: "°F" },
    loadcell: { label: "loadcell", defaultUnit: "V" },
    myCustomEquation: { label: "myCustomEquation", defaultUnit: "units" }
};

const navButtons = document.querySelectorAll(".nav-btn");
const pages = document.querySelectorAll(".page");

const dashboardGrid = document.getElementById("dashboard-grid");
const emptyDashboardState = document.getElementById("empty-dashboard-state");
const sensorList = document.getElementById("sensor-list");
const historyChartList = document.getElementById("history-chart-list");
const deletedChartList = document.getElementById("deleted-chart-list");
const historyLogList = document.getElementById("history-log-list");

const addSensorModal = document.getElementById("add-sensor-modal");
const showAddSensorBtn = document.getElementById("show-add-sensor");
const showAddSensorFromDashboard = document.getElementById("show-add-sensor-from-dashboard");
const closeAddSensorBtn = document.getElementById("close-add-sensor");
const saveSensorBtn = document.getElementById("save-sensor-btn");

const sensorNameInput = document.getElementById("sensor-name-input");
const sensorDescriptionInput = document.getElementById("sensor-description-input");
const basicSensorModeBtn = document.getElementById("basic-sensor-mode-btn");
const advancedSensorModeBtn = document.getElementById("advanced-sensor-mode-btn");
const basicSensorPanel = document.getElementById("basic-sensor-panel");
const advancedSensorPanel = document.getElementById("advanced-sensor-panel");
const sensorTypeInput = document.getElementById("sensor-type-input");
const sensorPortInput = document.getElementById("sensor-port-input");
const advancedSensorNameInput = document.getElementById("advanced-sensor-name-input");
const advancedSensorDescriptionInput = document.getElementById("advanced-sensor-description-input");
const advancedSensorPortInput = document.getElementById("advanced-sensor-port-input");
const sensorStreamKeyInput = document.getElementById("sensor-stream-key-input");
const saveAdvancedSensorBtn = document.getElementById("save-advanced-sensor-btn");

const chartBuilderModal = document.getElementById("chart-builder-modal");
const openChartBuilderBtn = document.getElementById("open-chart-builder");
const closeChartBuilderBtn = document.getElementById("close-chart-builder");
const basicModeBtn = document.getElementById("basic-mode-btn");
const advancedModeBtn = document.getElementById("advanced-mode-btn");
const basicModePanel = document.getElementById("basic-mode-panel");
const advancedModePanel = document.getElementById("advanced-mode-panel");
const basicSensorOptions = document.getElementById("basic-sensor-options");
const confirmBasicChartBtn = document.getElementById("confirm-basic-chart");
const confirmAdvancedChartBtn = document.getElementById("confirm-advanced-chart");
const equationOptions = document.getElementById("equation-options");
const advancedUnitInput = document.getElementById("advanced-unit-input");
const advancedChartName = document.getElementById("advanced-chart-name");
const advancedSensorId = document.getElementById("advanced-sensor-id");

const editChartModal = document.getElementById("edit-chart-modal");
const closeEditChartBtn = document.getElementById("close-edit-chart");
const editChartSensorId = document.getElementById("edit-chart-sensor-id");
const editChartPort = document.getElementById("edit-chart-port");
const editChartStreamKey = document.getElementById("edit-chart-stream-key");
const editChartUnit = document.getElementById("edit-chart-unit");
const saveEditChartBtn = document.getElementById("save-edit-chart-btn");

const zoomChartModal = document.getElementById("zoom-chart-modal");
const closeZoomChartBtn = document.getElementById("close-zoom-chart");
const zoomChartCanvas = document.getElementById("zoom-chart-canvas");
const zoomChartTitle = document.getElementById("zoom-chart-title");

function uid() {
    return crypto.randomUUID();
}

function formatTimestampLabel(timestampSeconds) {
    if (!Number.isFinite(timestampSeconds)) {
        return "--:--:--";
    }

    const date = new Date(timestampSeconds * 1000);
    const base = date.toLocaleTimeString([], {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
    const millis = String(date.getMilliseconds()).padStart(3, "0");
    return `${base}.${millis}`;
}

function formatReading(value, unit = "") {
    if (!Number.isFinite(value)) {
        return "--";
    }

    const abs = Math.abs(value);
    let decimals = 6;
    if (abs >= 100) decimals = 2;
    else if (abs >= 10) decimals = 3;
    else if (abs >= 1) decimals = 4;

    return `${value.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;
}

function getDisplayConfig(chartMeta, row) {
    const sensorType = chartMeta.sensorType || "";
    const baseUnit = row.unit || chartMeta.unit || "";
    const useMicroVolts = sensorType === "LoadCell" && baseUnit === "V";

    return {
        scale: useMicroVolts ? 1e6 : 1,
        unit: useMicroVolts ? "uV" : baseUnit,
        minSpan: useMicroVolts ? 20 : 0,
    };
}

function updateYAxisRange(chart, dataset, minSpan = 0) {
    if (!dataset.length) return;

    const min = Math.min(...dataset);
    const max = Math.max(...dataset);
    const span = Math.max(max - min, minSpan);
    const padding = Math.max(span * 0.2, minSpan > 0 ? minSpan * 0.25 : 0.0001);
    const center = (min + max) / 2;

    chart.options.scales.y.min = center - (span / 2) - padding;
    chart.options.scales.y.max = center + (span / 2) + padding;
}

async function init() {
    await loadConfig();
    renderSensors();
    renderHistory();
    renderBasicSensorOptions();
    renderEquationOptions();
    renderAdvancedSensorSelect();
    ensureAutoTestChart();
    wireEvents();
    updateDashboardStats();
}

function getPreferredTestingSensor() {
    return sensors.find(sensor => sensor.type === "LoadCell") || sensors[0] || null;
}

function ensureAutoTestChart() {
    if (charts.length > 0) return;

    const sensor = getPreferredTestingSensor();
    if (!sensor) return;

    createChartCard({
        title: sensor.name,
        sensorId: sensor.id,
        sensorName: sensor.name,
        sensorType: sensor.type,
        unit: sensor.unit,
        port: sensor.port,
        stream_key: sensor.stream_key,
        stopped: false,
        summary: {}
    });
}

function wireEvents() {
    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.dataset.page;
            navButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            pages.forEach(page => page.classList.remove("active"));
            document.getElementById(`page-${target}`).classList.add("active");
        });
    });

    showAddSensorBtn.addEventListener("click", openAddSensorModal);
    showAddSensorFromDashboard.addEventListener("click", openAddSensorModal);
    closeAddSensorBtn.addEventListener("click", closeAddSensorModal);
    saveSensorBtn.addEventListener("click", createSensorFromForm);
    saveAdvancedSensorBtn.addEventListener("click", createAdvancedSensorFromForm);
    basicSensorModeBtn.addEventListener("click", () => setSensorBuilderMode("basic"));
    advancedSensorModeBtn.addEventListener("click", () => setSensorBuilderMode("advanced"));

    addSensorModal.addEventListener("click", (e) => {
        if (e.target === addSensorModal) closeAddSensorModal();
    });

    openChartBuilderBtn.addEventListener("click", openChartBuilder);
    closeChartBuilderBtn.addEventListener("click", closeChartBuilder);

    chartBuilderModal.addEventListener("click", (e) => {
        if (e.target === chartBuilderModal) closeChartBuilder();
    });

    basicModeBtn.addEventListener("click", () => setBuilderMode("basic"));
    advancedModeBtn.addEventListener("click", () => setBuilderMode("advanced"));
    confirmBasicChartBtn.addEventListener("click", addBasicChart);
    confirmAdvancedChartBtn.addEventListener("click", addAdvancedChart);

    closeEditChartBtn.addEventListener("click", closeEditChartModal);
    saveEditChartBtn.addEventListener("click", saveChartEdits);
    editChartModal.addEventListener("click", (e) => {
        if (e.target === editChartModal) closeEditChartModal();
    });

    closeZoomChartBtn.addEventListener("click", closeZoomModal);
    zoomChartModal.addEventListener("click", (e) => {
        if (e.target === zoomChartModal) closeZoomModal();
    });
}

async function loadConfig() {
    sensors = backendConfig.sensors || [];
    renderPortOptions();
    renderChannelOptions();
}

function renderPortOptions() {
    sensorPortInput.innerHTML = "";
    advancedSensorPortInput.innerHTML = "";
    editChartPort.innerHTML = "";

    backendConfig.ports.forEach(port => {
        const option = document.createElement("option");
        option.value = port;
        option.textContent = `Port ${port}`;
        sensorPortInput.appendChild(option);

        const option2 = document.createElement("option");
        option2.value = port;
        option2.textContent = `Port ${port}`;
        advancedSensorPortInput.appendChild(option2);

        const option3 = document.createElement("option");
        option3.value = port;
        option3.textContent = `Port ${port}`;
        editChartPort.appendChild(option3);
    });
}

function renderChannelOptions() {
    sensorStreamKeyInput.innerHTML = "";
    editChartStreamKey.innerHTML = "";

    backendConfig.available_channels.forEach(key => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = key;
        sensorStreamKeyInput.appendChild(option);

        const option2 = document.createElement("option");
        option2.value = key;
        option2.textContent = key;
        editChartStreamKey.appendChild(option2);
    });
}

function renderSensors() {
    sensorList.innerHTML = "";

    if (sensors.length === 0) {
        sensorList.innerHTML = `<div class="sensor-item">No sensors added yet.</div>`;
        return;
    }

    sensors.forEach(sensor => {
        const div = document.createElement("div");
        div.className = "sensor-item";
        div.innerHTML = `
            <strong>${sensor.name}</strong><br>
            <small>${sensor.type} • ${sensor.unit} • Port ${sensor.port} • ${sensor.stream_key}</small><br>
            <small>${sensor.description || ""}</small>
        `;
        sensorList.appendChild(div);
    });

    renderBasicSensorOptions();
    renderAdvancedSensorSelect();
}

function renderHistory() {
    historyChartList.innerHTML = "";
    deletedChartList.innerHTML = "";
    historyLogList.innerHTML = "";

    if (chartHistory.length === 0) {
        historyChartList.innerHTML = `<div class="history-item">No charts added yet.</div>`;
    } else {
        chartHistory.forEach(chart => {
            const item = document.createElement("div");
            item.className = "history-item row-between";
            item.innerHTML = `
                <div>
                    <strong>${chart.title}</strong><br>
                    <small>${chart.sensorName} • ${chart.unit}</small>
                </div>
                <div class="inline-actions">
                    <button class="secondary-btn live-btn" type="button">Live Again</button>
                    <button class="secondary-btn summary-btn" type="button">Summary</button>
                </div>
            `;
            item.querySelector(".live-btn").onclick = () => restoreChart(chart);
            item.querySelector(".summary-btn").onclick = () => {
                alert(
                    `Summary for ${chart.title}\n` +
                    `Unit: ${chart.unit}\n` +
                    `Read Rate: ${chart.summary.avgRate ?? "--"} Hz\n` +
                    `Min: ${chart.summary.min ?? "--"}\n` +
                    `Max: ${chart.summary.max ?? "--"}\n` +
                    `Avg: ${chart.summary.avg ?? "--"}`
                );
            };
            historyChartList.appendChild(item);
        });
    }

    if (deletedCharts.length === 0) {
        deletedChartList.innerHTML = `<div class="history-item">No deleted charts yet.</div>`;
    } else {
        deletedCharts.forEach(chart => {
            const item = document.createElement("div");
            item.className = "history-item row-between";
            item.innerHTML = `
                <div>
                    <strong>${chart.title}</strong><br>
                    <small>${chart.sensorName}</small>
                </div>
                <button class="secondary-btn restore-btn" type="button">Restore</button>
            `;
            item.querySelector(".restore-btn").onclick = () => restoreChart(chart);
            deletedChartList.appendChild(item);
        });
    }

    if (actionHistory.length === 0) {
        historyLogList.innerHTML = `<div class="history-item">No actions yet.</div>`;
    } else {
        actionHistory.forEach(item => {
            const div = document.createElement("div");
            div.className = "history-item";
            div.textContent = item;
            historyLogList.appendChild(div);
        });
    }
}

function renderBasicSensorOptions() {
    basicSensorOptions.innerHTML = "";

    if (sensors.length === 0) {
        basicSensorOptions.innerHTML = `<div class="sensor-option">No sensors available. Add a sensor first.</div>`;
        return;
    }

    sensors.forEach((sensor, idx) => {
        const label = document.createElement("label");
        label.className = "sensor-option";
        label.innerHTML = `
            <input type="radio" name="basicSensor" value="${sensor.id}" ${idx === 0 ? "checked" : ""}>
            <span>${sensor.name} (${sensor.unit})</span>
        `;
        basicSensorOptions.appendChild(label);
    });
}

function renderAdvancedSensorSelect() {
    advancedSensorId.innerHTML = "";
    editChartSensorId.innerHTML = "";

    sensors.forEach(sensor => {
        const option = document.createElement("option");
        option.value = sensor.id;
        option.textContent = `${sensor.name} (${sensor.unit})`;
        advancedSensorId.appendChild(option);

        const option2 = document.createElement("option");
        option2.value = sensor.id;
        option2.textContent = `${sensor.name} (${sensor.unit})`;
        editChartSensorId.appendChild(option2);
    });
}

function renderEquationOptions() {
    equationOptions.innerHTML = "";

    Object.entries(equationMeta).forEach(([key, meta], idx) => {
        const label = document.createElement("label");
        label.className = "sensor-option";
        label.innerHTML = `
            <input type="radio" name="equationType" value="${key}" ${idx === 0 ? "checked" : ""}>
            <span>${meta.label}</span>
        `;
        equationOptions.appendChild(label);
    });

    document.querySelectorAll('input[name="equationType"]').forEach(radio => {
        radio.onchange = (e) => {
            advancedEquation = e.target.value;
            advancedUnitInput.value = equationMeta[advancedEquation].defaultUnit;
        };
    });
}

async function openAddSensorModal() {
    await loadConfig();
    setSensorBuilderMode("basic");
    addSensorModal.classList.remove("hidden");
}

function closeAddSensorModal() {
    addSensorModal.classList.add("hidden");
}

function setSensorBuilderMode(mode) {
    sensorBuilderMode = mode;
    basicSensorModeBtn.classList.toggle("active", mode === "basic");
    advancedSensorModeBtn.classList.toggle("active", mode === "advanced");
    basicSensorPanel.classList.toggle("hidden", mode !== "basic");
    advancedSensorPanel.classList.toggle("hidden", mode !== "advanced");
}

function openChartBuilder() {
    chartBuilderModal.classList.remove("hidden");
}

function closeChartBuilder() {
    chartBuilderModal.classList.add("hidden");
}

function setBuilderMode(mode) {
    builderMode = mode;
    basicModeBtn.classList.toggle("active", mode === "basic");
    advancedModeBtn.classList.toggle("active", mode === "advanced");
    basicModePanel.classList.toggle("hidden", mode !== "basic");
    advancedModePanel.classList.toggle("hidden", mode !== "advanced");
}

async function createSensorFromForm() {
    const payload = {
        name: sensorNameInput.value.trim(),
        description: sensorDescriptionInput.value.trim(),
        type: "Custom",
        unit: "units",
        port: sensorPortInput.value,
        stream_key: ""
    };

    if (!payload.name) return;

    const res = await fetch("/api/sensors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    const sensor = await res.json();
    sensors.push(sensor);
    actionHistory.unshift(`Added sensor ${sensor.name} on port ${sensor.port}`);
    renderSensors();
    renderHistory();

    sensorNameInput.value = "";
    sensorDescriptionInput.value = "";

    closeAddSensorModal();
}

async function createAdvancedSensorFromForm() {
    const payload = {
        name: advancedSensorNameInput.value.trim(),
        description: advancedSensorDescriptionInput.value.trim(),
        type: sensorTypeInput.value,
        port: advancedSensorPortInput.value,
        stream_key: sensorStreamKeyInput.value
    };

    if (!payload.name || !payload.stream_key) return;

    const res = await fetch("/api/sensors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    const sensor = await res.json();
    sensors.push(sensor);
    actionHistory.unshift(`Added sensor ${sensor.name} on port ${sensor.port}`);
    renderSensors();
    renderHistory();

    advancedSensorNameInput.value = "";
    advancedSensorDescriptionInput.value = "";

    closeAddSensorModal();
}

function addBasicChart() {
    const selected = document.querySelector('input[name="basicSensor"]:checked');
    if (!selected) return;

    const sensor = sensors.find(s => s.id === selected.value);
    if (!sensor) return;

    createChartCard({
        title: sensor.name,
        sensorId: sensor.id,
        sensorName: sensor.name,
        sensorType: sensor.type,
        unit: sensor.unit,
        port: sensor.port,
        stream_key: sensor.stream_key,
        stopped: false,
        summary: {}
    });

    closeChartBuilder();
}

function addAdvancedChart() {
    const sensor = sensors.find(s => s.id === advancedSensorId.value);
    if (!sensor) return;

    const title = advancedChartName.value.trim() || `${sensor.name} (${equationMeta[advancedEquation].label})`;

    createChartCard({
        title,
        sensorId: sensor.id,
        sensorName: sensor.name,
        sensorType: sensor.type,
        unit: advancedUnitInput.value || sensor.unit,
        port: sensor.port,
        stream_key: sensor.stream_key,
        equationType: advancedEquation,
        stopped: false,
        summary: {}
    });

    closeChartBuilder();
}

function createChartCard(meta) {
    const chartId = uid();
    const chartMeta = {
        id: chartId,
        ...meta
    };

    charts.push(chartMeta);
    chartHistory.unshift(chartMeta);
    actionHistory.unshift(`Added chart ${chartMeta.title}`);

    const panel = document.createElement("div");
    panel.className = "graph-panel";
    panel.id = `panel-${chartId}`;
    panel.innerHTML = `
        <div class="graph-top">
            <div class="graph-title">${chartMeta.title}</div>
            <div class="inline-actions">
                <button class="secondary-btn tare-btn" type="button">Tare</button>
                <button class="secondary-btn zoom-btn" type="button">Zoom</button>
                <button class="secondary-btn edit-btn" type="button">Edit</button>
                <button class="secondary-btn stop-btn" type="button">Stop</button>
                <button class="secondary-btn delete-btn" type="button">Delete</button>
            </div>
        </div>
        <div class="chart-wrap">
            <canvas id="canvas-${chartId}"></canvas>
        </div>
    `;

    dashboardGrid.appendChild(panel);

    const chart = buildChart(`canvas-${chartId}`, chartMeta);
    chartInstances.set(chartId, chart);

    panel.querySelector(".tare-btn").onclick = async () => {
        await fetch("/api/tare", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stream_key: chartMeta.stream_key })
        });
        actionHistory.unshift(`Tared ${chartMeta.title}`);
        renderHistory();
    };
    panel.querySelector(".zoom-btn").onclick = () => openZoomModal(chartMeta);
    panel.querySelector(".edit-btn").onclick = () => openEditChartModal(chartMeta);
    panel.querySelector(".stop-btn").onclick = () => toggleStopChart(chartMeta.id);
    panel.querySelector(".delete-btn").onclick = () => deleteChart(chartMeta.id);

    updateEmptyState();
    updateDashboardStats();
    renderHistory();
}

function buildChart(canvasId, meta) {
    const ctx = document.getElementById(canvasId).getContext("2d");

    return new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: `${meta.sensorName} (${meta.unit})`,
                data: [],
                borderColor: "#7cefff",
                backgroundColor: "rgba(124,239,255,0.16)",
                borderWidth: 2,
                fill: true,
                tension: 0.18,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: "bottom",
                    labels: {
                        color: "#ffffff",
                        boxWidth: 14
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: "Time",
                        color: "#ffffff"
                    },
                    grid: {
                        color: "rgba(255,255,255,0.16)"
                    },
                    ticks: {
                        color: "#ffffff",
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 6
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: `${meta.sensorName} (${meta.unit})`,
                        color: "#ffffff"
                    },
                    grid: {
                        color: "rgba(255,255,255,0.16)"
                    },
                    ticks: {
                        color: "#ffffff"
                    }
                }
            }
        }
    });
}

function toggleStopChart(chartId) {
    const chartMeta = charts.find(c => c.id === chartId);
    if (!chartMeta) return;

    chartMeta.stopped = !chartMeta.stopped;
    actionHistory.unshift(`${chartMeta.stopped ? "Stopped" : "Resumed"} ${chartMeta.title}`);
    renderHistory();
}

function deleteChart(chartId) {
    const idx = charts.findIndex(c => c.id === chartId);
    if (idx === -1) return;

    const chartMeta = charts[idx];
    deletedCharts.unshift(chartMeta);
    actionHistory.unshift(`Deleted chart ${chartMeta.title}`);

    charts.splice(idx, 1);

    const chart = chartInstances.get(chartId);
    if (chart) {
        chart.destroy();
        chartInstances.delete(chartId);
    }

    const panel = document.getElementById(`panel-${chartId}`);
    if (panel) panel.remove();

    updateEmptyState();
    updateDashboardStats();
    renderHistory();
}

function restoreChart(chartMeta) {
    createChartCard({
        title: chartMeta.title,
        sensorId: chartMeta.sensorId,
        sensorName: chartMeta.sensorName,
        sensorType: chartMeta.sensorType,
        unit: chartMeta.unit,
        port: chartMeta.port,
        stream_key: chartMeta.stream_key,
        equationType: chartMeta.equationType,
        stopped: false,
        summary: chartMeta.summary || {}
    });

    navButtons.forEach(b => b.classList.remove("active"));
    document.querySelector('[data-page="dashboard"]').classList.add("active");
    pages.forEach(page => page.classList.remove("active"));
    document.getElementById("page-dashboard").classList.add("active");
}

function openEditChartModal(chartMeta) {
    editingChartId = chartMeta.id;
    editChartSensorId.value = chartMeta.sensorId;
    editChartPort.value = chartMeta.port;

    editChartStreamKey.innerHTML = "";
    backendConfig.available_channels.forEach(key => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = key;
        if (key === chartMeta.stream_key) option.selected = true;
        editChartStreamKey.appendChild(option);
    });

    editChartUnit.value = chartMeta.unit;
    editChartModal.classList.remove("hidden");
}

function closeEditChartModal() {
    editChartModal.classList.add("hidden");
    editingChartId = null;
}

async function saveChartEdits() {
    const chartMeta = charts.find(c => c.id === editingChartId);
    if (!chartMeta) return;

    const sensor = sensors.find(s => s.id === editChartSensorId.value);
    if (!sensor) return;

    const payload = {
        name: sensor.name,
        type: sensor.type,
        unit: editChartUnit.value,
        port: editChartPort.value,
        stream_key: editChartStreamKey.value
    };

    await fetch(`/api/sensors/${sensor.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    // refresh local sensors
    await loadConfig();
    renderSensors();

    chartMeta.sensorId = sensor.id;
    chartMeta.sensorName = sensor.name;
    chartMeta.sensorType = sensor.type;
    chartMeta.unit = editChartUnit.value;
    chartMeta.port = editChartPort.value;
    chartMeta.stream_key = editChartStreamKey.value;

    const panel = document.getElementById(`panel-${chartMeta.id}`);
    if (panel) {
        panel.querySelector(".graph-title").textContent = chartMeta.title;
    }

    const chart = chartInstances.get(chartMeta.id);
    if (chart) {
        chart.data.datasets[0].label = `${chartMeta.sensorName} (${chartMeta.unit})`;
        chart.options.scales.y.title.text = `${chartMeta.sensorName} (${chartMeta.unit})`;
        chart.update();
    }

    actionHistory.unshift(`Edited chart ${chartMeta.title}`);
    renderHistory();
    closeEditChartModal();
}

function openZoomModal(chartMeta) {
    zoomChartTitle.textContent = chartMeta.title;
    zoomChartModal.classList.remove("hidden");

    if (zoomChartInstance) {
        zoomChartInstance.destroy();
        zoomChartInstance = null;
    }

    const sourceChart = chartInstances.get(chartMeta.id);
    if (!sourceChart) return;

    const ctx = zoomChartCanvas.getContext("2d");
    zoomChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: [...sourceChart.data.labels],
            datasets: [{
                ...sourceChart.data.datasets[0],
                data: [...sourceChart.data.datasets[0].data]
            }]
        },
        options: JSON.parse(JSON.stringify(sourceChart.options))
    });
}

function closeZoomModal() {
    zoomChartModal.classList.add("hidden");
    if (zoomChartInstance) {
        zoomChartInstance.destroy();
        zoomChartInstance = null;
    }
}

function updateEmptyState() {
    emptyDashboardState.classList.toggle("hidden", charts.length > 0);
}

function updateDashboardStats(avgRate = null) {
    const graphCount = charts.length;
    document.getElementById("graph-count").textContent = String(graphCount);
    document.getElementById("global-read-rate").textContent = avgRate == null ? "-- Hz" : `${avgRate} Hz`;
}

async function pollLatest() {
    const res = await fetch("/api/latest");
    const data = await res.json();

    backendConfig.available_channels = data.available_channels || [];
    renderChannelOptions();
    ensureAutoTestChart();

    updateDashboardStats(data.avg_rate_hz);

    charts.forEach(chartMeta => {
        if (chartMeta.stopped) return; //instead of pull use the backend pusblisher subcriber model, 

        const row = data.latest_by_sensor[chartMeta.sensorId];
        if (!row || row.value == null) return;

        const chart = chartInstances.get(chartMeta.id);
        if (!chart) return;

        const labels = chart.data.labels;
        const dataset = chart.data.datasets[0].data;
        const display = getDisplayConfig(chartMeta, row);
        const nextValue = Number(row.value) * display.scale;
        const nextLabel = formatTimestampLabel(Number(row.timestamp));

        if (!Number.isFinite(nextValue)) return;

        if (row.unit) {
            chartMeta.unit = row.unit;
        }
        chartMeta.displayUnit = display.unit;

        labels.push(nextLabel);
        dataset.push(nextValue);

        if (dataset.length > MAX_POINTS) {
            dataset.shift();
            labels.shift();
        }

        chart.data.datasets[0].label = `${chartMeta.sensorName} (${display.unit})`;
        chart.options.scales.y.title.text = `${chartMeta.sensorName} (${display.unit})`;
        updateYAxisRange(chart, dataset, display.minSpan);
        chart.update("none");

        const min = dataset.length ? Math.min(...dataset) : null;
        const max = dataset.length ? Math.max(...dataset) : null;
        const avg = dataset.length ? (dataset.reduce((a, b) => a + b, 0) / dataset.length).toFixed(2) : null;

        chartMeta.summary = {
            avgRate: row.rate_hz ?? data.avg_rate_hz ?? "--",
            min,
            max,
            avg,
            unit: display.unit
        };
    });

    renderHistory();
}

function startPolling() {
    pollLatest();
}

init();
