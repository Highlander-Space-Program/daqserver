"""
grafana_setup.py

Reads labjack_channels.json and calls the Grafana HTTP API to create
a dashboard with one panel per sensor type (Pressure, Loadcell, Thermocouple).

Called once on server startup when GRAFANA_TOKEN is set.
"""

import json
import os
import httpx
from server.states import PIN_MAPPING


def load_config(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def group_by_sensor_type(sensors: list[dict]) -> dict[str, list[dict]]:
    """Group sensors by their SensorType field."""
    groups: dict[str, list[dict]] = {}
    for sensor in sensors:
        sensor_type = sensor.get("SensorType", "Unknown").lower()
        groups.setdefault(sensor_type, []).append(sensor)
    return groups

LIVE_CHANNELS = {
    "pressure": "stream/daq/pressuretransducer",
    "pt": "stream/daq/pressuretransducer",

    "thermocouple": "stream/daq/thermocouple",
    "tc": "stream/daq/thermocouple",

    "loadcell": "stream/daq/loadcell",
    "load_cell": "stream/daq/loadcell",
    "lc": "stream/daq/loadcell",
}

def build_panel(panel_id, sensor_type, sensors, y_pos):
    type_titles = {
        "pressure": "Pressure Transducers (psi)",
        "pt": "Pressure Transducers (psi)",
        "loadcell": "Load Cells (lbf)",
        "lc": "Load Cells (lbf)",
        "thermocouple": "Thermocouples (°C)",
        "tc": "Thermocouples (°C)",
    }

    title = type_titles.get(sensor_type.lower(), sensor_type.capitalize())

    queries = []

    for index, sensor in enumerate(sensors):
        config_ain = sensor["AIN"]

        pin_info = PIN_MAPPING.get(config_ain)
        if pin_info is None:
            raise ValueError(f"No PIN_MAPPING entry for {config_ain}")

        physical_ain = pin_info["cb37_pin"]

        queries.append({
            "kind": "PanelQuery",
            "spec": {
                "query": {
                    "kind": "DataQuery",
                    "group": "datasource",
                    "version": "v0",
                    "datasource": {
                        "name": "grafana"
                    },
                    "spec": {
                        "channel": f"stream/daq/{physical_ain.lower()}",
                        "filter": {
                            "fields": []
                        },
                        "queryType": "measurements",
                    },
                },
                "refId": chr(65 + index),
                "hidden": False,
            },
        })

    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "gridPos": {
            "x": 0,
            "y": y_pos,
            "w": 24,
            "h": 8,
        },
        "targets": queries,
    }

def build_dashboard(groups):
    panels = []
    panel_id = 1
    y_pos = 0

    for sensor_type, sensors in groups.items():
        panel = build_panel(
            panel_id,
            sensor_type,
            sensors,
            y_pos,
        )

        panels.append(panel)
        panel_id += 1
        y_pos += 8

    return {
        "dashboard": {
            "id": None,
            "uid": "daq-auto",
            "title": "DAQ Live Dashboard",
            "tags": ["daq", "auto-generated"],
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 1,
            "refresh": "",
            "time": {
                "from": "now-30m",
                "to": "now",
            },
            "panels": panels,
        },
        "folderId": 0,
        "overwrite": True,
    }

def setup_grafana_dashboard():
    """
    Main entry point. Reads config and pushes dashboard to Grafana API.
    Call this on server startup.
    """
    GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
    GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN")
    CONFIG_PATH = os.getenv("DAQ_CONFIG", "labjack_channels.json")

    if not GRAFANA_TOKEN:
        print("[GrafanaSetup] GRAFANA_TOKEN not set, skipping dashboard setup.")
        return

    try:
        sensors = load_config(CONFIG_PATH)
    except FileNotFoundError:
        print(f"[GrafanaSetup] Config file not found: {CONFIG_PATH}")
        return

    groups = group_by_sensor_type(sensors)
    dashboard_payload = build_dashboard(groups)

    headers = {
        "Authorization": f"Bearer {GRAFANA_TOKEN}",
        "Content-Type": "application/json",
    }

    url = f"{GRAFANA_URL}/api/dashboards/db"

    try:
        response = httpx.post(url, json=dashboard_payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"[GrafanaSetup] Dashboard created: {response.json().get('url', '')}")
    except httpx.HTTPStatusError as e:
        print(f"[GrafanaSetup] Failed to create dashboard: {e.response.status_code} {e.response.text}")
    except httpx.RequestError as e:
        print(f"[GrafanaSetup] Could not reach Grafana at {GRAFANA_URL}: {e}")
