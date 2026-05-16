function initWebSocket() {
  // Close existing connection if we are re-initializing
  if (wsConnection) {
    wsConnection.close();
  }

  // Determine protocol (ws:// or wss://)
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  wsConnection = new WebSocket(`${protocol}//${window.location.host}/ws`);

  wsConnection.onopen = () => {
    console.log("WebSocket Connected.");

    // Figure out which ports we actually need to subscribe to
    const activePorts = new Set();
    backendConfig.graphs.forEach((graph) => {
      const sensor = backendConfig.sensors.find(
        (s) => s.id === graph.sensor_id,
      );
      if (sensor && sensor.port) {
        activePorts.add(sensor.port);
      }
    });

    console.log(activePorts);
    if (activePorts.size > 0) {
      wsConnection.send(
        JSON.stringify({
          action: "subscribe",
          arguments: Array.from(activePorts),
        }),
      );
    }
  };

  wsConnection.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      handleStreamData(message);
    } catch (err) {
      console.error("Failed to parse WebSocket message:", err);
    }
  };

  wsConnection.onclose = () => {
    console.log("WebSocket Disconnected. Attempting reconnect in 2s...");
    setTimeout(initWebSocket, 2000);
  };
}

function handleStreamData(message) {
  const port = message.topic;
  const sensorData = message.payload;

  if (!port || !sensorData || !sensorData.data) return;

  // Ensure we are working with an array of TimeBasedData objects
  const timeBasedDataArray = Array.isArray(sensorData.data)
    ? sensorData.data
    : [sensorData.data];
  if (timeBasedDataArray.length === 0) return;

  // Extract the raw values into an array
  const values = timeBasedDataArray.map((d) => d.value);

  // Grab the timestamp of the latest data point for our X-axis label
  const latestTimeRaw = timeBasedDataArray[timeBasedDataArray.length - 1].time;

  // Format timestamp nicely (e.g., "08:48:29")
  const timeLabel = new Date(latestTimeRaw).toLocaleTimeString([], {
    hour12: false,
  });

  // Update all graphs listening to this specific port
  backendConfig.graphs.forEach((graph) => {
    const sensor = backendConfig.sensors.find((s) => s.id === graph.sensor_id);
    if (!sensor || sensor.port !== port) return;

    let finalValue = values[0]; // Default to the first raw value

    // If an equation is attached, process the values through it
    if (sensor.equation_id) {
      const equation = backendConfig.equations.find(
        (e) => e.id === sensor.equation_id,
      );
      if (equation && equation.expression) {
        try {
          // Evaluate the string into a callable JavaScript function
          const eqFunc = eval(equation.expression);
          // Spread the values array as arguments: eqFunc(1.23, 1.532)
          finalValue = eqFunc(...values);
        } catch (err) {
          console.error(
            `Error executing equation on graph ${graph.name}:`,
            err,
          );
          return; // Skip drawing this tick if the equation errors out
        }
      }
    }

    selectedValueGraphIds.forEach((selectedGraphId, slot) => {
      if (graph.id === selectedGraphId) {
        document.getElementById(`selected-value-${slot}`).textContent = Number(finalValue).toFixed(3);
      }
    });

    // Push data to the specific Chart.js instance
    const chart = chartInstances[graph.id];
    if (chart) {
      chart.data.labels.push(timeLabel);
      chart.data.datasets[0].data.push(finalValue);

      // Shift data off the array so the chart doesn't grow infinitely and crash the browser
      const MAX_DATA_POINTS = 1000;
      if (chart.data.labels.length > MAX_DATA_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
      }

      // Update UI without a full animation loop for better streaming performance
      chart.update("none");
    }
  });
}
function updateWebSocketSubscriptions() {
  // Ensure we have an open connection before trying to send
  if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) return;

  const activePorts = new Set();
  backendConfig.graphs.forEach((graph) => {
    const sensor = backendConfig.sensors.find((s) => s.id === graph.sensor_id);
    if (sensor && sensor.port) {
      activePorts.add(sensor.port);
    }
  });

  if (activePorts.size > 0) {
    wsConnection.send(
      JSON.stringify({
        action: "subscribe",
        arguments: Array.from(activePorts),
      }),
    );
  }
}
