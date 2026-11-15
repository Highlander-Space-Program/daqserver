from server.streaming.simulator import (
    CYCLE_S,
    GrafanaLivePusher,
    Simulator,
    phase_at,
    to_line_protocol,
)


def burn_time() -> float:
    t = 0.0
    while phase_at(t)[0] != "burn":
        t += 0.1
    return t + 2.0  # well into the burn


def lc_value(sim: Simulator, t: float) -> float:
    return next(v for _, port, v in sim.sample(t, 0.1) if port == "LC-1")


def test_phase_at_wraps_cycle():
    assert phase_at(0.0) == ("idle", 0.0)
    assert phase_at(CYCLE_S)[0] == "idle"


def test_one_reading_per_channel():
    sim = Simulator()
    readings = sim.sample(0.0, 0.1)
    assert [port for _, port, _ in readings] == [ch.port for ch in sim.channels]


def test_burn_produces_thrust_and_idle_does_not():
    sim = Simulator()
    assert abs(lc_value(sim, 1.0)) < 10
    assert lc_value(sim, burn_time()) > 200


def test_line_protocol_groups_ports_by_measurement():
    readings = [
        ("pressure", "PT-1", 800.0),
        ("pressure", "PT-2", 760.5),
        ("load", "LC-1", 1.25),
    ]
    assert to_line_protocol(readings, 123) == (
        "pressure PT-1=800.000,PT-2=760.500 123\nload LC-1=1.250 123"
    )


def test_pusher_auth_and_endpoint():
    token_pusher = GrafanaLivePusher("http://g:3000/", "daq_sim", token="glsa_x")
    assert token_pusher.endpoint == "http://g:3000/api/live/push/daq_sim"
    assert token_pusher.session.headers["Authorization"] == "Bearer glsa_x"

    basic_pusher = GrafanaLivePusher("http://g:3000", "daq_sim")
    assert basic_pusher.session.auth == ("admin", "admin")
