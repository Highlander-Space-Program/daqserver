"""Simulated DAQ sensor data, pushed to Grafana Live.

Run:
    uv run python -m server.streaming.simulator

Every tick it POSTs Influx line protocol to Grafana's Live push endpoint
(/api/live/push/<stream>). In a Grafana panel pick the "-- Grafana --" data
source, query type "Live Measurements", and one of these channels:

    stream/<stream>/pressure      PT-1..PT-4   (psi)
    stream/<stream>/temperature   TC-1..TC-3   (degC)
    stream/<stream>/load          LC-1         (lbs)

Values follow a repeating static-fire profile:

    idle -> pressurize -> hold -> burn -> vent -> (repeat)

Configuration (environment or .env):
    GRAFANA_URL          default http://localhost:3000
    GRAFANA_TOKEN        service account token (Editor role). If unset, falls
                         back to basic auth with GRAFANA_USER / GRAFANA_PASSWORD
                         (default admin/admin, matching docker-compose.yml)
    GRAFANA_LIVE_STREAM  default daq_sim
    DAQ_SIM_RATE_HZ      default 10
"""

import math
import os
import random
import time
from dataclasses import dataclass
from typing import Callable

import requests
from dotenv import load_dotenv

# (phase name, duration in seconds)
PHASES: tuple[tuple[str, float], ...] = (
    ("idle", 10.0),
    ("pressurize", 15.0),
    ("hold", 10.0),
    ("burn", 8.0),
    ("vent", 17.0),
)
CYCLE_S = sum(duration for _, duration in PHASES)
AMBIENT_C = 22.0

PRESSURE = "pressure"
TEMPERATURE = "temperature"
LOAD = "load"

type Reading = tuple[str, str, float]  # (measurement, port, value)


def phase_at(t: float) -> tuple[str, float]:
    """Return (phase, progress 0..1 within that phase) at time t seconds."""
    t %= CYCLE_S
    for name, duration in PHASES:
        if t < duration:
            return name, t / duration
        t -= duration
    return PHASES[-1][0], 1.0


def tank_level(phase: str, p: float) -> float:
    """Normalized tank pressure, 0..1."""
    match phase:
        case "pressurize":
            return 1 - math.exp(-4 * p)
        case "hold":
            return 1 - math.exp(-4) * (1 - p)  # finish settling to 1
        case "burn":
            return 1 - 0.6 * p  # blowdown
        case "vent":
            return 0.4 * math.exp(-6 * p)
        case _:
            return 0.0


def thrust_level(phase: str, p: float) -> float:
    """Normalized thrust, 0..1. Non-zero only during burn."""
    if phase != "burn":
        return 0.0
    rise = min(1.0, p / 0.05)  # ignition transient
    tail = min(1.0, (1 - p) / 0.1)  # tail-off
    return rise * tail * tank_level(phase, p)


def regulator_level(phase: str, p: float) -> float:
    match phase:
        case "pressurize":
            return min(1.0, p / 0.2)
        case "hold" | "burn":
            return 1.0
        case "vent":
            return math.exp(-8 * p)
        case _:
            return 0.0


@dataclass
class SimChannel:
    port: str
    measurement: str
    model: Callable[[str, float], float]  # (phase, progress) -> target value
    noise: float  # gaussian std dev, in output units
    tau: float = 0.0  # first-order lag in seconds (0 = follows target instantly)
    value: float | None = None

    def step(self, phase: str, progress: float, dt: float) -> float:
        target = self.model(phase, progress)
        if self.value is None or self.tau <= 0:
            self.value = target
        else:
            self.value += (target - self.value) * min(1.0, dt / self.tau)
        return self.value + random.gauss(0.0, self.noise)


def default_channels() -> list[SimChannel]:
    return [
        # Pressure transducers (psi)
        SimChannel("PT-1", PRESSURE, lambda ph, p: 800 * tank_level(ph, p), noise=2.0),
        SimChannel("PT-2", PRESSURE, lambda ph, p: 760 * tank_level(ph, p), noise=2.0, tau=0.3),
        SimChannel("PT-3", PRESSURE, lambda ph, p: 450 * thrust_level(ph, p), noise=1.5),
        SimChannel("PT-4", PRESSURE, lambda ph, p: 500 * regulator_level(ph, p), noise=1.0),
        # Thermocouples (degC) - lag behind the burn at different rates
        SimChannel("TC-1", TEMPERATURE, lambda ph, p: AMBIENT_C + 350 * thrust_level(ph, p), noise=0.5, tau=3.0),
        SimChannel("TC-2", TEMPERATURE, lambda ph, p: AMBIENT_C + 120 * thrust_level(ph, p), noise=0.5, tau=8.0),
        SimChannel("TC-3", TEMPERATURE, lambda ph, p: AMBIENT_C + 40 * thrust_level(ph, p), noise=0.3, tau=20.0),
        # Load cell (lbs)
        SimChannel("LC-1", LOAD, lambda ph, p: 350 * thrust_level(ph, p), noise=1.5),
    ]


class Simulator:
    def __init__(self, channels: list[SimChannel] | None = None) -> None:
        self.channels = channels if channels is not None else default_channels()

    def sample(self, t: float, dt: float) -> list[Reading]:
        """One reading per channel at simulated time t."""
        phase, progress = phase_at(t)
        return [
            (ch.measurement, ch.port, ch.step(phase, progress, dt))
            for ch in self.channels
        ]


def to_line_protocol(readings: list[Reading], timestamp_ns: int) -> str:
    """One line per measurement, with each port as a field.

    e.g. pressure PT-1=801.2,PT-2=757.9 1731600000000000000
    """
    fields: dict[str, list[str]] = {}
    for measurement, port, value in readings:
        fields.setdefault(measurement, []).append(f"{port}={value:.3f}")
    return "\n".join(
        f"{measurement} {','.join(f)} {timestamp_ns}"
        for measurement, f in fields.items()
    )


class GrafanaLivePusher:
    def __init__(
        self,
        url: str,
        stream_id: str,
        token: str | None = None,
        user: str = "admin",
        password: str = "admin",
        timeout: float = 2.0,
    ) -> None:
        self.endpoint = f"{url.rstrip('/')}/api/live/push/{stream_id}"
        self.timeout = timeout
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.auth = (user, password)

    def push(self, body: str) -> None:
        response = self.session.post(
            self.endpoint, data=body.encode(), timeout=self.timeout
        )
        response.raise_for_status()


def run(pusher: GrafanaLivePusher, sim: Simulator, rate_hz: float) -> None:
    period = 1.0 / rate_hz
    start = last = time.monotonic()
    last_warning = 0.0

    while True:
        now = time.monotonic()
        body = to_line_protocol(sim.sample(now - start, now - last), time.time_ns())
        last = now

        try:
            pusher.push(body)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403):
                raise SystemExit(
                    f"Grafana rejected the credentials ({e.response.status_code}). "
                    "Set GRAFANA_TOKEN to a service account token with the Editor role."
                )
            if now - last_warning > 5:
                print(f"Push failed: {e}", flush=True)
                last_warning = now
        except requests.RequestException as e:
            if now - last_warning > 5:
                print(f"Cannot reach Grafana at {pusher.endpoint}: {e}", flush=True)
                last_warning = now

        time.sleep(max(0.0, period - (time.monotonic() - now)))


def main() -> None:
    load_dotenv()
    url = os.getenv("GRAFANA_URL", "http://localhost:3000")
    stream_id = os.getenv("GRAFANA_LIVE_STREAM", "daq_sim")
    rate_hz = float(os.getenv("DAQ_SIM_RATE_HZ", "10"))

    pusher = GrafanaLivePusher(
        url,
        stream_id,
        token=os.getenv("GRAFANA_TOKEN") or None,
        user=os.getenv("GRAFANA_USER", "admin"),
        password=os.getenv("GRAFANA_PASSWORD", "admin"),
    )
    sim = Simulator()

    measurements = sorted({ch.measurement for ch in sim.channels})
    print(f"Pushing {len(sim.channels)} channels at {rate_hz} Hz to {pusher.endpoint}", flush=True)
    for m in measurements:
        print(f"  Grafana channel: stream/{stream_id}/{m}", flush=True)
    print(f"Test cycle repeats every {CYCLE_S:.0f}s. Ctrl+C to stop.", flush=True)

    try:
        run(pusher, sim, rate_hz)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
