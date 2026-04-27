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
  
        document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
  
        document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
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
        Math.floor(backendConfig.graphs.length / GRAPHS_PER_PAGE) + 1
      );
  
      if (currentGraphPage < totalPages - 1) {
        currentGraphPage++;
        renderGraphs();
      }
    };
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
      savedSensor = await apiSend(`/api/sensors/${editingSensorId}`, "PATCH", payload);
  
      const index = backendConfig.sensors.findIndex((s) => s.id === editingSensorId);
      if (index !== -1) backendConfig.sensors[index] = savedSensor;
    } else {
      savedSensor = await apiSend("/api/sensors", "POST", payload);
      backendConfig.sensors.push(savedSensor);
    }
  
    closeSensorModal();
  
    renderLeftPanel();
    renderGraphSensorOptions();
  
    if (typeof updateWebSocketSubscriptions === "function") {
      updateWebSocketSubscriptions();
    }
  }
  
  async function saveEquation() {
    const payload = {
      name: document.getElementById("equation-name-input").value.trim(),
      expression: document.getElementById("equation-code-input").value.trim(),
    };
  
    if (!payload.name || !payload.expression) return;
  
    const testResult = evaluateCustomFunction(payload.expression, [1, 2, 3]);
  
    if (testResult === null) {
      alert("Equation must be a valid JavaScript function, like: (a, b, c) => a + b + c");
      return;
    }
  
    let savedEquation;
  
    if (editingEquationId) {
      savedEquation = await apiSend(`/api/equations/${editingEquationId}`, "PATCH", payload);
  
      const index = backendConfig.equations.findIndex((e) => e.id === editingEquationId);
      if (index !== -1) backendConfig.equations[index] = savedEquation;
    } else {
      savedEquation = await apiSend("/api/equations", "POST", payload);
      backendConfig.equations.push(savedEquation);
    }
  
    closeEquationModal();
  
    renderLeftPanel();
    renderEquationOptions();
  }
  
  async function saveGraph() {
    const payload = {
      name: document.getElementById("graph-name-input").value.trim(),
      sensor_id: document.getElementById("graph-sensor-input").value,
    };
  
    if (!payload.name || !payload.sensor_id) return;
  
    let savedGraph;
  
    if (editingGraphId) {
      savedGraph = await apiSend(`/api/graphs/${editingGraphId}`, "PATCH", payload);
  
      const index = backendConfig.graphs.findIndex((g) => g.id === editingGraphId);
      if (index !== -1) backendConfig.graphs[index] = savedGraph;
    } else {
      savedGraph = await apiSend("/api/graphs", "POST", payload);
      backendConfig.graphs.push(savedGraph);
    }
  
    closeGraphModal();
  
    renderStats();
    renderGraphs();
  
    if (typeof updateWebSocketSubscriptions === "function") {
      updateWebSocketSubscriptions();
    }
  }
  
  async function deleteSensor(sensorId) {
    const confirmed = confirm("Delete this sensor?");
    if (!confirmed) return;
  
    await apiDelete(`/api/sensors/${sensorId}`);
  
    backendConfig.sensors = backendConfig.sensors.filter((s) => s.id !== sensorId);
  
    backendConfig.graphs = backendConfig.graphs.filter((g) => {
      if (g.sensor_id === sensorId) {
        if (typeof chartInstances !== "undefined" && chartInstances[g.id]) {
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
  
    if (typeof updateWebSocketSubscriptions === "function") {
      updateWebSocketSubscriptions();
    }
  }
  
  async function deleteEquation(equationId) {
    const confirmed = confirm("Delete this equation?");
    if (!confirmed) return;
  
    await apiDelete(`/api/equations/${equationId}`);
  
    backendConfig.equations = backendConfig.equations.filter((e) => e.id !== equationId);
  
    backendConfig.sensors.forEach((sensor) => {
      if (sensor.equation_id === equationId) {
        sensor.equation_id = null;
      }
    });
  
    renderLeftPanel();
    renderEquationOptions();
  }
  
  async function deleteGraph(graphId) {
    const confirmed = confirm("Delete this graph?");
    if (!confirmed) return;
  
    await apiDelete(`/api/graphs/${graphId}`);
  
    backendConfig.graphs = backendConfig.graphs.filter((g) => g.id !== graphId);
  
    if (typeof chartInstances !== "undefined" && chartInstances[graphId]) {
      chartInstances[graphId].destroy();
      delete chartInstances[graphId];
    }
  
    renderStats();
    renderGraphs();
  
    if (typeof updateWebSocketSubscriptions === "function") {
      updateWebSocketSubscriptions();
    }
  }
  
  async function tareGraph(graphId) {
    await apiSend(`/api/graphs/${graphId}/tare`, "POST", {});
    alert("Graph tare saved.");
  }