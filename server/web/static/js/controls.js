async function fetchStatus() {
    const res = await fetch("/api/status");
    const data = await res.json();

    renderXbee(data.xbee);
    renderBoards(data.boards);
    renderImportant(data.important_status);
    renderServos(data.servos);
    renderIgniter(data.igniter);
    renderBreakwire(data.breakwire);
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
                <td><button onclick="abortStatus('${name}')">Disarm</button></td>
            </tr>
        `;
    });
}

function renderServos(servos) {
    const body = document.getElementById("servo-body");
    body.innerHTML = "";

    servos.forEach((servo, index) => {
        body.innerHTML += `
            <tr>
                <td>${servo.name}</td>
                <td><span class="status-box ${servo.status === "OPEN" ? "green" : "red"}">${servo.status}</span></td>
                <td><button onclick="openServo(${index})">Open</button></td>
                <td><button onclick="closeServo(${index})">Close</button></td>
            </tr>
        `;
    });
}

function renderIgniter(igniter) {
    const status = document.getElementById("igniter-status");

    status.textContent = igniter.status;
    status.className = "status-box " + (igniter.status === "ON" ? "green" : "red");
}

function renderBreakwire(breakwire) {
    const status = document.getElementById("breakwire-status");

    const connected = breakwire.connected;
    status.textContent = connected ? "CONNECTED" : "DISCONNECTED";
    status.className = "status-box " + (connected ? "green" : "red");
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

async function openServo(row) {
    await fetch("/api/servo/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row })
    });
    fetchStatus();
}

async function closeServo(row) {
    await fetch("/api/servo/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row })
    });
    fetchStatus();
}

async function fireIgniter() {
    await fetch("/api/igniter/fire", { method: "POST" });
    fetchStatus();
}

async function shutoffIgniter() {
    await fetch("/api/igniter/shutoff", { method: "POST" });
    fetchStatus();
}

async function pingBoard() {
    await fetch("/api/ping", { method: "POST" });
    fetchStatus();
}

async function toggleBreakwire() {
    await fetch("/api/breakwire/toggle", { method: "POST" });
    fetchStatus();
}

fetchStatus();
setInterval(fetchStatus, 2000);

// MQTT test connection
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
    console.log(message.toString());
});
