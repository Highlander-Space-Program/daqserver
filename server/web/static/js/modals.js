function openSensorModal() {
    editingSensorId = null;
    document.getElementById("sensor-modal-title").textContent = "Add Sensor";
    document.getElementById("sensor-name-input").value = "";
    document.getElementById("sensor-port-input").value = backendConfig.ports[0] || "";
    document.getElementById("sensor-equation-input").value = "";
    document.getElementById("sensor-modal").classList.remove("hidden");
}

function openEditSensor(sensor) {
    editingSensorId = sensor.id;
    document.getElementById("sensor-modal-title").textContent = "Edit Sensor";
    document.getElementById("sensor-name-input").value = sensor.name;
    document.getElementById("sensor-port-input").value = sensor.port;
    document.getElementById("sensor-equation-input").value = sensor.equation_id || "";
    document.getElementById("sensor-modal").classList.remove("hidden");
}

function closeSensorModal() {
    document.getElementById("sensor-modal").classList.add("hidden");
}

function openEquationModal() {
    editingEquationId = null;
    document.getElementById("equation-modal-title").textContent = "Add Equation";
    document.getElementById("equation-name-input").value = "";
    document.getElementById("equation-code-input").value = "";
    document.getElementById("equation-modal").classList.remove("hidden");
}

function openEditEquation(eq) {
    editingEquationId = eq.id;
    document.getElementById("equation-modal-title").textContent = "Edit Equation";
    document.getElementById("equation-name-input").value = eq.name;
    document.getElementById("equation-code-input").value = eq.expression;
    document.getElementById("equation-modal").classList.remove("hidden");
}

function closeEquationModal() {
    document.getElementById("equation-modal").classList.add("hidden");
}

function openGraphModal() {
    document.getElementById("graph-name-input").value = "";
    renderGraphSensorOptions();
    document.getElementById("graph-modal").classList.remove("hidden");
}

function closeGraphModal() {
    document.getElementById("graph-modal").classList.add("hidden");
}