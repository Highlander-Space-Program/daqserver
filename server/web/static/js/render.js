const dashboardGrid = document.getElementById("dashboard-grid");
const leftScrollList = document.getElementById("left-scroll-list");
const leftListTitle = document.getElementById("left-list-title");

function renderAll() {
  renderStats();
  renderPortOptions();
  renderEquationOptions();
  renderGraphSensorOptions();
  renderLeftPanel();
  renderGraphs();
}

function renderStats() {
  document.getElementById("read-rate").textContent =
    backendConfig.read_rate_hz === "--"
      ? "-- Hz"
      : `${backendConfig.read_rate_hz} Hz`;

  document.getElementById("active-graphs").textContent =
    backendConfig.graphs.length;
}

function renderPortOptions() {
  const sensorPortInput = document.getElementById("sensor-port-input");
  sensorPortInput.innerHTML = "";

  backendConfig.ports.forEach((port) => {
    const option = document.createElement("option");
    option.value = port;
    option.textContent = port;
    sensorPortInput.appendChild(option);
  });
}

function renderEquationOptions() {
  const sensorEquationInput = document.getElementById("sensor-equation-input");
  sensorEquationInput.innerHTML = "";

  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No equation";
  sensorEquationInput.appendChild(none);

  backendConfig.equations.forEach((eq) => {
    const option = document.createElement("option");
    option.value = eq.id;
    option.textContent = eq.name;
    sensorEquationInput.appendChild(option);
  });
}

function renderGraphSensorOptions() {
  const graphSensorInput = document.getElementById("graph-sensor-input");
  graphSensorInput.innerHTML = "";

  backendConfig.sensors.forEach((sensor) => {
    const option = document.createElement("option");
    option.value = sensor.id;
    option.textContent = `${sensor.name} (${sensor.port})`;
    graphSensorInput.appendChild(option);
  });
}

function renderLeftPanel() {
  leftScrollList.innerHTML = "";

  if (activeLeftTab === "sensors") {
    leftListTitle.textContent = "Active Sensors";

    if (backendConfig.sensors.length === 0) {
      leftScrollList.innerHTML = `<div class="empty-small">No sensors yet.</div>`;
      return;
    }

    backendConfig.sensors.forEach((sensor) => {
      const eq = backendConfig.equations.find(
        (e) => e.id === sensor.equation_id,
      );

      const div = document.createElement("div");
      div.className = "left-item";

      div.innerHTML = `
                <div>
                    <strong>${sensor.name}</strong>
                    <small>${sensor.port} • ${eq ? eq.name : "No equation"}</small>
                </div>
                <div class="item-actions">
                    <button class="tiny-btn edit-btn">Edit</button>
                    <button class="tiny-btn delete-btn">Delete</button>
                </div>
            `;

      div.querySelector(".edit-btn").onclick = () => openEditSensor(sensor);
      div.querySelector(".delete-btn").onclick = () => deleteSensor(sensor.id);

      leftScrollList.appendChild(div);
    });
  }
  if (activeLeftTab === "equations") {
    leftListTitle.textContent = "Saved Equations";

    if (backendConfig.equations.length === 0) {
      leftScrollList.innerHTML = `<div class="empty-small">No equations yet.</div>`;
      return;
    }

    backendConfig.equations.forEach((eq) => {
      const usedBy =
        backendConfig.sensors
          .filter((s) => s.equation_id === eq.id)
          .map((s) => s.name)
          .join(", ") || "No sensors";

      const div = document.createElement("div");
      div.className = "left-item";

      div.innerHTML = `
                <div>
                    <strong>${eq.name}</strong>
                    <small>Used by: ${usedBy}</small>
                </div>
                <div class="item-actions">
                    <button class="tiny-btn edit-btn">Edit</button>
                    <button class="tiny-btn delete-btn">Delete</button>
                </div>
            `;

      div.querySelector(".edit-btn").onclick = () => openEditEquation(eq);
      div.querySelector(".delete-btn").onclick = () => deleteEquation(eq.id);

      leftScrollList.appendChild(div);
    });
  }
}

function renderGraphs() {
  dashboardGrid.innerHTML = "";

  const totalPages = Math.max(
    1,
    Math.ceil(backendConfig.graphs.length / GRAPHS_PER_PAGE),
  );
  if (currentGraphPage >= totalPages) currentGraphPage = totalPages - 1;

  const start = currentGraphPage * GRAPHS_PER_PAGE;
  const pageGraphs = backendConfig.graphs.slice(start, start + GRAPHS_PER_PAGE);

  pageGraphs.forEach((graph) => {
    const sensor = backendConfig.sensors.find((s) => s.id === graph.sensor_id);

    const panel = document.createElement("div");
    panel.className = "graph-panel";

    const canvasId = `chart-${graph.id}`;

    panel.innerHTML = `
            <div class="graph-top">
                <div>
                    <div class="graph-title">${graph.name}</div>
                    <small>${sensor ? sensor.name : "Unknown sensor"}</small>
                </div>
            </div>
            <div class="chart-wrap">
                <canvas id="${canvasId}"></canvas>
            </div>
        `;

    dashboardGrid.appendChild(panel);
    buildBlankChart(canvasId, graph.name, graph.id);
  });

  while (dashboardGrid.children.length < GRAPHS_PER_PAGE) {
    const skeleton = document.createElement("button");
    skeleton.className = "graph-panel skeleton-graph";
    skeleton.innerHTML = `
            <div class="plus">+</div>
            <div>Add Graph</div>
        `;
    skeleton.onclick = openGraphModal;
    dashboardGrid.appendChild(skeleton);
  }

  document.getElementById("graph-page-label").textContent =
    `Page ${currentGraphPage + 1} of ${totalPages}`;
}

