const inputIds = Array.from({ length: 80 }, (_, i) => i + 1);

const defaultSensors = [
    { id: crypto.randomUUID(), name: "Load Cell 1", type: "LoadCell", description: "Default fake load cell", unit: "lbf", mux: "x2", inputPins: [1, 2] },
    { id: crypto.randomUUID(), name: "Load Cell 2", type: "LoadCell", description: "Default fake load cell", unit: "lbf", mux: "x2", inputPins: [3, 4] },
    { id: crypto.randomUUID(), name: "Thermocouple 1", type: "Thermocouple", description: "Default fake thermocouple", unit: "°F", mux: "x2", inputPins: [5, 6] },
    { id: crypto.randomUUID(), name: "Temperature Sensor 1", type: "Temperature", description: "Default fake temperature sensor", unit: "°F", mux: "x1", inputPins: [7] },
    { id: crypto.randomUUID(), name: "Pressure Sensor 1", type: "Pressure", description: "Default fake pressure sensor", unit: "psi", mux: "x1", inputPins: [8] },
    { id: crypto.randomUUID(), name: "Flow Sensor 1", type: "Flow", description: "Default fake flow sensor", unit: "kg/s", mux: "x1", inputPins: [9] }
];

let sensors = [...defaultSensors];
let actionHistory = [];
let chartHistory = [];
let deletedCharts = [];
let charts = [];
let chartInstances = [];

let selectedBasicSensor = defaultSensors[0].id;
let builderMode = "basic";
let advancedEquation = "temperature";

let pendingSensorPins = [1];
let advancedSelectedSensors = [];
let advancedSensorNames = ["Sensor Name 1", "Sensor Name 2"];
let chartBuilderOpen = false;

const equationMeta = {
    temperature: { label: "temperature (2 inputs)", inputCount: 2 },
    loadcell: { label: "loadcell (2 inputs)", inputCount: 2 },
    myCustomEquation: { label: "myCustomEquation (1 input)", inputCount: 1 }
};

const navButtons = document.querySelectorAll(".nav-btn");
const pages = document.querySelectorAll(".page");

const dashboardGrid = document.getElementById("dashboard-grid");
const dashboardEmpty = document.getElementById("dashboard-empty");

const sensorList = document.getElementById("sensor-list");
const historyChartList = document.getElementById("history-chart-list");
const deletedChartList = document.getElementById("deleted-chart-list");
const historyLogList = document.getElementById("history-log-list");

const chartBuilderModal = document.getElementById("chart-builder-modal");
const openChartBuilderBtn = document.getElementById("open-chart-builder");
const closeChartBuilderBtn = document.getElementById("close-chart-builder");

const basicModeBtn = document.getElementById("basic-mode-btn");
const advancedModeBtn = document.getElementById("advanced-mode-btn");
const basicModePanel = document.getElementById("basic-mode-panel");
const advancedModePanel = document.getElementById("advanced-mode-panel");

const basicSensorOptions = document.getElementById("basic-sensor-options");
const advancedSensorInputs = document.getElementById("advanced-sensor-inputs");
const equationOptions = document.getElementById("equation-options");
const customEquationWrap = document.getElementById("custom-equation-wrap");
const customEquationText = document.getElementById("custom-equation-text");

const confirmBasicChartBtn = document.getElementById("confirm-basic-chart");
const confirmAdvancedChartBtn = document.getElementById("confirm-advanced-chart");

const openAddSensorFromAdvancedBtn = document.getElementById("open-add-sensor-from-advanced");
const addMoreEquationBtn = document.getElementById("add-more-equation-btn");

const addSensorModal = document.getElementById("add-sensor-modal");
const showAddSensorBtn = document.getElementById("show-add-sensor");
const closeAddSensorBtn = document.getElementById("close-add-sensor");

const sensorNameInput = document.getElementById("sensor-name-input");
const sensorDescriptionInput = document.getElementById("sensor-description-input");
const sensorTypeInput = document.getElementById("sensor-type-input");
const sensorMuxInput = document.getElementById("sensor-mux-input");
const analogPinList = document.getElementById("analog-pin-list");
const addAnalogPinBtn = document.getElementById("add-analog-pin-btn");
const saveSensorBtn = document.getElementById("save-sensor-btn");

function init() {
    renderSensors();
    renderHistory();
    renderBasicSensorOptions();
    renderAdvancedInputs();
    renderEquationOptions();
    renderAnalogPinSelectors();
    wireEvents();
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

    openChartBuilderBtn.addEventListener("click", () => openChartBuilder());
    closeChartBuilderBtn.addEventListener("click", () => closeChartBuilder());

    basicModeBtn.addEventListener("click", () => setBuilderMode("basic"));
    advancedModeBtn.addEventListener("click", () => setBuilderMode("advanced"));

    confirmBasicChartBtn.addEventListener("click", addBasicChart);
    confirmAdvancedChartBtn.addEventListener("click", addAdvancedChart);

    showAddSensorBtn.addEventListener("click", openAddSensorModal);
    closeAddSensorBtn.addEventListener("click", closeAddSensorModal);

    openAddSensorFromAdvancedBtn.addEventListener("click", openAddSensorModal);
    addMoreEquationBtn.addEventListener("click", openAddSensorModal);

    addAnalogPinBtn.addEventListener("click", () => {
        pendingSensorPins.push(1);
        renderAnalogPinSelectors();
    });

    saveSensorBtn.addEventListener("click", addSensor);

    chartBuilderModal.addEventListener("click", (e) => {
        if (e.target === chartBuilderModal) closeChartBuilder();
    });

    addSensorModal.addEventListener("click", (e) => {
        if (e.target === addSensorModal) closeAddSensorModal();
    });
}

function openChartBuilder() {
    chartBuilderOpen = true;
    chartBuilderModal.classList.remove("hidden");
}

function closeChartBuilder() {
    chartBuilderOpen = false;
    chartBuilderModal.classList.add("hidden");
}

function setBuilderMode(mode) {
    builderMode = mode;

    if (mode === "basic") {
        basicModeBtn.classList.add("active");
        advancedModeBtn.classList.remove("active");
        basicModePanel.classList.remove("hidden");
        advancedModePanel.classList.add("hidden");
    } else {
        advancedModeBtn.classList.add("active");
        basicModeBtn.classList.remove("active");
        advancedModePanel.classList.remove("hidden");
        basicModePanel.classList.add("hidden");
    }
}

function openAddSensorModal() {
    addSensorModal.classList.remove("hidden");
}

function closeAddSensorModal() {
    addSensorModal.classList.add("hidden");
}

function renderSensors() {
    sensorList.innerHTML = "";

    sensors.forEach(sensor => {
        const div = document.createElement("div");
        div.className = "sensor-item";
        div.innerHTML = `
            <strong>${sensor.name}</strong><br>
            <small>${sensor.type} • ${sensor.mux} • AIN ${sensor.inputPins.join(", ")}</small><br>
            <small>${sensor.description || ""}</small>
        `;
        sensorList.appendChild(div);
    });

    renderBasicSensorOptions();
    renderAdvancedInputs();
}

function renderHistory() {
    historyChartList.innerHTML = "";
    deletedChartList.innerHTML = "";
    historyLogList.innerHTML = "";

    if (chartHistory.length === 0) {
        historyChartList.innerHTML = `<div class="history-item">No charts created yet.</div>`;
    } else {
        chartHistory.forEach(chart => {
            const item = document.createElement("div");
            item.className = "history-item row-between";
            item.innerHTML = `
                <div>
                    <strong>${chart.title}</strong><br>
                    <small>${chart.sensorName} • created at ${chart.createdAt}</small>
                </div>
                <button class="secondary-btn restore-btn">Open again</button>
            `;
            item.querySelector(".restore-btn").addEventListener("click", () => restoreChart(chart));
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
                <button class="secondary-btn restore-btn">Restore</button>
            `;
            item.querySelector(".restore-btn").addEventListener("click", () => restoreChart(chart));
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

    sensors.forEach(sensor => {
        const label = document.createElement("label");
        label.className = "sensor-option";
        label.innerHTML = `
            <input type="radio" name="basicSensor" value="${sensor.id}" ${sensor.id === selectedBasicSensor ? "checked" : ""}>
            <span>${sensor.name}</span>
        `;
        basicSensorOptions.appendChild(label);
    });

    document.querySelectorAll('input[name="basicSensor"]').forEach(radio => {
        radio.addEventListener("change", e => {
            selectedBasicSensor = e.target.value;
        });
    });
}

function renderAdvancedInputs() {
    const needed = equationMeta[advancedEquation].inputCount;

    while (advancedSensorNames.length < needed) advancedSensorNames.push(`Sensor Name ${advancedSensorNames.length + 1}`);
    advancedSensorNames = advancedSensorNames.slice(0, needed);
    advancedSelectedSensors = advancedSelectedSensors.slice(0, needed);

    advancedSensorInputs.innerHTML = "";

    for (let i = 0; i < needed; i++) {
        const row = document.createElement("div");
        row.className = "advanced-row";

        const sensorNameBox = document.createElement("input");
        sensorNameBox.type = "text";
        sensorNameBox.value = advancedSensorNames[i] || "";
        sensorNameBox.placeholder = `Sensor Name ${i + 1}`;
        sensorNameBox.addEventListener("input", (e) => {
            advancedSensorNames[i] = e.target.value;
        });

        const sensorSelect = document.createElement("select");
        sensorSelect.innerHTML = `<option value="">Select sensor</option>`;
        sensors.forEach(sensor => {
            const option = document.createElement("option");
            option.value = sensor.id;
            option.textContent = sensor.name;
            if (advancedSelectedSensors[i] === sensor.id) option.selected = true;
            sensorSelect.appendChild(option);
        });

        sensorSelect.addEventListener("change", (e) => {
            const id = e.target.value;
            advancedSelectedSensors[i] = id;
            const sensor = sensors.find(s => s.id === id);
            if (sensor) {
                advancedSensorNames[i] = sensor.name;
                sensorNameBox.value = sensor.name;
            }
        });

        row.appendChild(sensorNameBox);
        row.appendChild(sensorSelect);
        advancedSensorInputs.appendChild(row);
    }
}

function renderEquationOptions() {
    equationOptions.innerHTML = "";

    Object.entries(equationMeta).forEach(([key, meta]) => {
        const label = document.createElement("label");
        label.className = "sensor-option";
        label.innerHTML = `
            <input type="radio" name="equationType" value="${key}" ${advancedEquation === key ? "checked" : ""}>
            <span>${meta.label}</span>
        `;
        equationOptions.appendChild(label);
    });

    document.querySelectorAll('input[name="equationType"]').forEach(radio => {
        radio.addEventListener("change", (e) => {
            advancedEquation = e.target.value;
            renderAdvancedInputs();
            customEquationWrap.classList.toggle("hidden", advancedEquation !== "myCustomEquation");
        });
    });

    customEquationWrap.classList.toggle("hidden", advancedEquation !== "myCustomEquation");
}

function renderAnalogPinSelectors() {
    analogPinList.innerHTML = "";

    pendingSensorPins.forEach((pin, index) => {
        const select = document.createElement("select");
        inputIds.forEach(id => {
            const option = document.createElement("option");
            option.value = id;
            option.textContent = `AIN${id}`;
            if (pin === id) option.selected = true;
            select.appendChild(option);
        });

        select.addEventListener("change", (e) => {
            pendingSensorPins[index] = Number(e.target.value);
        });

        analogPinList.appendChild(select);
    });
}

function addSensor() {
    const name = sensorNameInput.value.trim();
    const description = sensorDescriptionInput.value.trim();
    const type = sensorTypeInput.value;
    const mux = sensorMuxInput.value;

    if (!name) return;

    const newSensor = {
        id: crypto.randomUUID(),
        name,
        description,
        type,
        mux,
        inputPins: [...pendingSensorPins],
        unit: type === "Pressure" ? "psi" : type === "LoadCell" ? "lbf" : type === "Thermocouple" || type === "Temperature" ? "°F" : type === "Flow" ? "kg/s" : "units"
    };

    sensors.push(newSensor);
    actionHistory.unshift(`Added sensor ${name} using ${mux} on AIN ${pendingSensorPins.join(", ")}`);

    sensorNameInput.value = "";
    sensorDescriptionInput.value = "";
    sensorTypeInput.value = "Custom";
    sensorMuxInput.value = "x1";
    pendingSensorPins = [1];

    renderSensors();
    renderHistory();
    renderAnalogPinSelectors();
    closeAddSensorModal();
}

function addBasicChart() {
    const sensor = sensors.find(s => s.id === selectedBasicSensor);
    if (!sensor) return;

    const chart = buildChartObject({
        title: `${sensor.name} Live Chart`,
        sensor
    });

    charts.push(chart.id);
    chartHistory.unshift(chart);
    actionHistory.unshift(`Added basic chart for ${sensor.name}`);
    createChartCard(chart);
    renderHistory();
    closeChartBuilder();
}

function addAdvancedChart() {
    const sensor = sensors.find(s => s.id === advancedSelectedSensors[0]) || sensors[0];
    const title = advancedSensorNames[0] || `${advancedEquation} Live Chart`;

    const chart = buildChartObject({
        title,
        sensor,
        equationType: advancedEquation,
        customEquation: advancedEquation === "myCustomEquation" ? customEquationText.value : ""
    });

    charts.push(chart.id);
    chartHistory.unshift(chart);
    actionHistory.unshift(`Added advanced chart ${title}`);
    createChartCard(chart);
    renderHistory();
    closeChartBuilder();
}

function buildChartObject({ title, sensor, equationType = "", customEquation = "" }) {
    return {
        id: `chart-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        title,
        sensorId: sensor.id,
        sensorName: sensor.name,
        inputId: `AIN ${sensor.inputPins.join(", ")}`,
        unit: sensor.unit || "units",
        equationType,
        customEquation,
        createdAt: new Date().toLocaleTimeString()
    };
}

function deleteChart(chartId) {
    const chartIndex = chartInstances.findIndex(item => item.chart.canvas.id === chartId);
    if (chartIndex === -1) return;

    const chartInfo = chartInstances[chartIndex];
    const deletedChart = chartInfo.meta;

    deletedCharts.unshift(deletedChart);
    actionHistory.unshift(`Deleted chart ${deletedChart.title}`);

    chartInfo.chart.destroy();
    chartInstances.splice(chartIndex, 1);
    charts = charts.filter(id => id !== chartId);

    const card = document.querySelector(`[data-chart-id="${chartId}"]`);
    if (card) card.remove();

    if (dashboardGrid.children.length === 0) {
        dashboardEmpty.classList.remove("hidden");
        dashboardGrid.classList.add("hidden");
    }

    renderHistory();
}

function restoreChart(chart) {
    const restored = {
        ...chart,
        id: `chart-${Date.now()}-${Math.floor(Math.random() * 1000)}`
    };

    charts.push(restored.id);
    actionHistory.unshift(`Restored chart ${restored.title}`);
    createChartCard(restored);
    renderHistory();

    navButtons.forEach(b => b.classList.remove("active"));
    document.querySelector('[data-page="dashboard"]').classList.add("active");
    pages.forEach(page => page.classList.remove("active"));
    document.getElementById("page-dashboard").classList.add("active");
}

function createChartCard(chartMeta) {
    dashboardEmpty.classList.add("hidden");
    dashboardGrid.classList.remove("hidden");

    const card = document.createElement("div");
    card.className = "chart-card";
    card.dataset.chartId = chartMeta.id;

    card.innerHTML = `
        <div class="chart-card-header">
            <div>
                <h3>${chartMeta.title}</h3>
                <div class="chart-subtitle">
                    ${chartMeta.sensorName} • ${chartMeta.inputId} • ${chartMeta.unit}
                    ${chartMeta.equationType ? `• ${chartMeta.equationType}` : ""}
                </div>
            </div>
            <button class="delete-chart-btn">Delete</button>
        </div>
        <div class="chart-wrapper">
            <canvas id="${chartMeta.id}"></canvas>
        </div>
    `;

    dashboardGrid.appendChild(card);

    card.querySelector(".delete-chart-btn").addEventListener("click", () => {
        deleteChart(chartMeta.id);
    });

    const ctx = document.getElementById(chartMeta.id).getContext("2d");
    const chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: Array.from({ length: 20 }, (_, i) => i),
            datasets: [{
                label: chartMeta.title,
                data: makeFakeData(chartMeta.sensorId + chartMeta.equationType),
                borderColor: "#f97316",
                backgroundColor: "rgba(249, 115, 22, 0.15)",
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });

    chartInstances.push({ chart, meta: chartMeta });
}

function makeFakeData(seed) {
    const hash = String(seed).split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    const base = 40 + (hash % 250);

    return Array.from({ length: 20 }, (_, i) => {
        return Number((base + Math.sin(i / 3) * 8 + Math.cos(i / 4) * 2).toFixed(2));
    });
}

setInterval(() => {
    chartInstances.forEach(item => {
        const dataset = item.chart.data.datasets[0].data;
        const labels = item.chart.data.labels;
        const lastX = labels[labels.length - 1];
        const nextValue = Number((dataset[dataset.length - 1] + (Math.random() * 6 - 3)).toFixed(2));

        dataset.push(nextValue);
        labels.push(lastX + 1);

        if (dataset.length > 20) {
            dataset.shift();
            labels.shift();
        }

        item.chart.update();
    });
}, 1000);

init();