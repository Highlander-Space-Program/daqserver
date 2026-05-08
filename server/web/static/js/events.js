function wireEvents() {
  document.getElementById("open-daq-page").onclick = () => {
    window.location.href = "/";
  };

  document.getElementById("open-controls-page").onclick = () => {
    window.open("/controls", "_blank");
  };

  document.getElementById("open-cameras-page").onclick = () => {
    window.open("/cameras", "_blank");
  };

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.onclick = () => {
      const target = btn.dataset.page;

      document
        .querySelectorAll(".nav-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      document
        .querySelectorAll(".page")
        .forEach((page) => page.classList.remove("active"));
      document.getElementById(`page-${target}`).classList.add("active");
    };
  });

  document.getElementById("show-sensors-tab").onclick = () => {
    activeLeftTab = "sensors";
    document.getElementById("show-sensors-tab").classList.add("active");
    document.getElementById("show-equations-tab").classList.remove("active");
    renderLeftPanel();
  };

  document.getElementById("show-equations-tab").onclick = () => {
    activeLeftTab = "equations";
    document.getElementById("show-equations-tab").classList.add("active");
    document.getElementById("show-sensors-tab").classList.remove("active");
    renderLeftPanel();
  };

  document.getElementById("open-sensor-modal").onclick = openSensorModal;
  document.getElementById("open-equation-modal").onclick = openEquationModal;

  document.getElementById("close-sensor-modal").onclick = closeSensorModal;
  document.getElementById("close-equation-modal").onclick = closeEquationModal;
  document.getElementById("close-graph-modal").onclick = closeGraphModal;

  document.getElementById("save-sensor-btn").onclick = saveSensor;
  document.getElementById("save-equation-btn").onclick = saveEquation;
  document.getElementById("save-graph-btn").onclick = saveGraph;

  document.getElementById("prev-graph-page").onclick = () => {
    if (currentGraphPage > 0) {
      currentGraphPage--;
      renderGraphs();
    }
  };

  document.getElementById("next-graph-page").onclick = () => {
    const totalPages = Math.max(
      1,
      Math.ceil(backendConfig.graphs.length / GRAPHS_PER_PAGE),
    );
    if (currentGraphPage < totalPages - 1) {
      currentGraphPage++;
      renderGraphs();
    }
  };

  document.getElementById("delete-sensor-btn").onclick = async () => {
    if (!editingSensorId) return;

    await deleteSensor(editingSensorId);
    closeSensorModal();
  }
}

async function saveSensor() {
  const payload = {
    name: document.getElementById("sensor-name-input").value.trim(),
    port: document.getElementById("sensor-port-input").value,
    equation_id: document.getElementById("sensor-equation-input").value || null,
  };

  if (!payload.name) return;

  let savedSensor;
  if (editingSensorId) {
    savedSensor = await apiSend(
      `/api/sensors/${editingSensorId}`,
      "PATCH",
      payload,
    );
    // Update local state
    const index = backendConfig.sensors.findIndex(
      (s) => s.id === editingSensorId,
    );
    if (index !== -1) backendConfig.sensors[index] = savedSensor;
  } else {
    savedSensor = await apiSend("/api/sensors", "POST", payload);
    // Add to local state
    backendConfig.sensors.push(savedSensor);
  }

  closeSensorModal();

  // Targeted Renders: Sensors affect the left panel and the graph creation dropdown
  renderLeftPanel();
  renderGraphSensorOptions();
  updateWebSocketSubscriptions();
}

async function saveEquation() {
  const payload = {
    name: document.getElementById("equation-name-input").value.trim(),
    expression: document.getElementById("equation-code-input").value.trim(),
  };

  if (!payload.name || !payload.expression) return;

  const testResult = evaluateCustomFunction(payload.expression, [1, 2, 3]);

  if (testResult === null) {
    alert(
      "Equation must be a valid JavaScript function, like: (a, b, c) => a + b + c",
    );
    return;
  }

  let savedEquation;
  if (editingEquationId) {
    savedEquation = await apiSend(
      `/api/equations/${editingEquationId}`,
      "PATCH",
      payload,
    );
    // Update local state
    const index = backendConfig.equations.findIndex(
      (e) => e.id === editingEquationId,
    );
    if (index !== -1) backendConfig.equations[index] = savedEquation;
  } else {
    savedEquation = await apiSend("/api/equations", "POST", payload);
    // Add to local state
    backendConfig.equations.push(savedEquation);
  }

  closeEquationModal();

  // Targeted Renders: Equations affect the left panel and sensor creation dropdown
  renderLeftPanel();
  renderEquationOptions();
}

async function saveGraph() {
  const payload = {
    name: document.getElementById("graph-name-input").value.trim(),
    sensor_id: document.getElementById("graph-sensor-input").value,
  };

  if (!payload.name || !payload.sensor_id) return;

  const savedGraph = await apiSend("/api/graphs", "POST", payload);

  backendConfig.graphs.push(savedGraph);

  closeGraphModal();

  renderStats();
  renderGraphs();
  updateWebSocketSubscriptions();
}

async function deleteSensor(sensorId) {
  const confirmed = confirm("Delete this sensor?");
  if (!confirmed) return;

  await apiDelete(`/api/sensors/${sensorId}`);

  // Update local state: Remove the sensor
  backendConfig.sensors = backendConfig.sensors.filter(
    (s) => s.id !== sensorId,
  );

  // NOTE: Your backend also deletes any graphs attached to this sensor.
  backendConfig.graphs = backendConfig.graphs.filter((g) => {
    if (g.sensor_id === sensorId) {
      // clean up Chart.js memory
      if (chartInstances && chartInstances[g.id]) {
        chartInstances[g.id].destroy();
        delete chartInstances[g.id];
      }
      return false;
    }
    return true;
  });

  renderLeftPanel();
  renderGraphSensorOptions();
  renderStats();
  renderGraphs();
  updateWebSocketSubscriptions();
}

async function deleteEquation(equationId) {
  const confirmed = confirm("Delete this equation?");
  if (!confirmed) return;

  await apiDelete(`/api/equations/${equationId}`);

  // Update local state: Remove the equation
  backendConfig.equations = backendConfig.equations.filter(
    (e) => e.id !== equationId,
  );

  // NOTE: backend sets the equation_id to NULL for any sensors using it.
  backendConfig.sensors.forEach((sensor) => {
    if (sensor.equation_id === equationId) {
      sensor.equation_id = null;
    }
  });

  renderLeftPanel();
  renderEquationOptions();
}

function tareSensor(sensorID) {
  console.log("Tare clicked for sensor:", sensorID);

  fetch(`/api/sensors/${sensorID}/tare`, {
    method: "POST"
  })
  .then(res => res.json())
  .then(data => {
    console.log("Tare Successful:", data);
  })
  .catch(err => {
    console.error("Tare failed", err);
  });
}

async function deleteGraph(graphId) {
  try {
    await apiDelete(`/api/graphs/${graphId}`);

    backendConfig.graphs = backendConfig.graphs.filter(
      (g) => g.id !== graphId
    );

    if (chartInstances[graphId]) {
      chartInstances[graphId].destroy();
      delete chartInstances[graphId];
    }

    renderStats();
    renderGraphs();
    updateWebSocketSubscriptions();
  } catch (err) {
    console.error("Failed to delete graph:", err);
  }
}

window.deleteGraph = deleteGraph;

