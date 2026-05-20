async function fetchStatus() {
    const res = await fetch("/api/status");
    const data = await res.json();

    renderXbee(data.xbee);
    renderBoards(data.boards);
    renderImportant(data.important_status);
    renderSensors("tc-body", "TC", data.sensors.tc);
    renderSensors("lc-body", "LC", data.sensors.lc);
    renderSensors("pt-body", "PT", data.sensors.pt);
    renderSolenoids(data.solenoids);
    renderLog(data.event_log);
}

function renderXbee(xbee) {
    const dot = document.getElementById("xbee-dot");
    const status = document.getElementById("xbee-status");
    const port = document.getElementById("xbee-port");

    status.textContent = xbee.status;
    port.textContent = xbee.port ? `Port: ${xbee.port}` : "";
    dot.className = "dot " + (xbee.connected ? "green" : "red");
}

function renderBoards(boards) {
    const body = document.getElementById("board-status-body");
    body.innerHTML = "";

    Object.entries(boards).forEach(([name, alive]) => {
        body.innerHTML += `
            <tr>
                <td>${name}</td>
                <td><span class="status-box ${alive ? "green" : "red"}">${alive ? "ALIVE" : "DEAD"}</span></td>
            </tr>
        `;
    });
}

function renderImportant(items) {
    const body = document.getElementById("important-status-body");
    body.innerHTML = "";

    Object.entries(items).forEach(([name, armed]) => {
        body.innerHTML += `
            <tr>
                <td>${name}</td>
                <td><span class="status-box ${armed ? "green" : "red"}">${armed ? "ARMED" : "DISARMED"}</span></td>
                <td><button onclick="armStatus('${name}')">Arm</button></td>
                <td><button onclick="abortStatus('${name}')">Abort</button></td>
            </tr>
        `;
    });
}

function renderSensors(bodyId, label, values) {
    const body = document.getElementById(bodyId);
    body.innerHTML = "";

    values.forEach((value, index) => {
        body.innerHTML += `
            <tr>
                <td>${label}${index + 1}</td>
                <td>${value}</td>
            </tr>
        `;
    });
}

function renderSolenoids(solenoids) {
    const body = document.getElementById("solenoid-body");
    body.innerHTML = "";

    solenoids.forEach((solenoid, index) => {
        body.innerHTML += `
            <tr>
                <td>${solenoid.valve}</td>
                <td><span class="status-box ${solenoid.status === "OPEN" ? "green" : "red"}">${solenoid.status}</span></td>
                <td><button onclick="openSolenoid(${index})">Open</button></td>
                <td><button onclick="closeSolenoid(${index})">Close</button></td>
                <td><span class="status-box ${solenoid.power === "CONNECTED" ? "green" : "red"}">${solenoid.power}</span></td>
                <td><button onclick="togglePower(${index})">${solenoid.power === "CONNECTED" ? "ON" : "OFF"}</button></td>
            </tr>
        `;
    });
}

function renderLog(events) {
    const log = document.getElementById("event-log");
    log.innerHTML = events.map(event => `<div>${event}</div>`).join("");
}

async function connectXbee() {
    await fetch("/api/connect", { method: "POST" });
    fetchStatus();
}

async function disconnectXbee() {
    await fetch("/api/disconnect", { method: "POST" });
    fetchStatus();
}

async function armStatus(name) {
    await fetch("/api/arm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
    });
    fetchStatus();
}

async function abortStatus(name) {
    await fetch("/api/abort", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
    });
    fetchStatus();
}

async function openSolenoid(row) {
    await fetch("/api/solenoid/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row })
    });
    fetchStatus();
}

async function closeSolenoid(row) {
    await fetch("/api/solenoid/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row })
    });
    fetchStatus();
}

async function togglePower(row) {
    await fetch("/api/solenoid/power", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row })
    });
    fetchStatus();
}

fetchStatus();
setInterval(fetchStatus, 2000);

// const client = mqtt.connect("mqtt://localhost:1883");
const client = mqtt.connect("ws://localhost:9001");

client.on("connect", () => {
    console.log("Connected to MQTT broker");
    client.subscribe("presence", (err) => {
        if (!err) {
            client.publish("presence", "Hello mqtt");
        }
    });
});

client.on("message", (topic, message) => {
    // message is Buffer
    console.log(message.toString());
    //   client.end();
});
