
"""
grafana_setup.py

Automatically creates and reconciles the DAQ Live Dashboard.

- One panel per configured sensor.
- Uses config_ain directly as the Grafana Live channel.
- Uses Live Measurements as the query type.
- Adds missing panels.
- Updates panels whose configuration changed.
- Leaves unchanged panels and dashboards untouched.
- Preserves unrelated dashboard panels.

Requires Grafana 12+.
"""

import json
import os
import zlib

import httpx


DASHBOARD_UID = "daq-auto"
DASHBOARD_TITLE = "DAQ Live Dashboard"
API_VERSION = "dashboard.grafana.app/v1"
TYPE_TITLES = {
    "pressure": "Pressure Transducers (psi)",
    "loadcell": "Load Cells (lbf)",
    "thermocouple": "Thermocouples (°C)",
    "tc": "Thermocouples (°C)",
    "lc": "Load Cells (lbf)",
    "pt": "Pressure Transducers (psi)",
}


def load_config(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def build_panel(sensor: dict, y_pos: int) -> dict:
    """Build one panel for one sensor."""

    config_ain = sensor["AIN"]

    # Stable panel ID based on the sensor's AIN.
    panel_id = zlib.crc32(config_ain.encode()) & 0x7FFFFFFF
    panel_id = max(panel_id, 1)

    sensor_type = sensor.get("SensorType", "Unknown").lower()
    title = TYPE_TITLES.get(sensor_type, sensor_type.capitalize()) + " - " + sensor.get("Name", config_ain)

    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "description": f"DAQ managed sensor: {config_ain}",
        "gridPos": {
            "x": 0,
            "y": y_pos,
            "w": 24,
            "h": 8,
        },
        "datasource": {
            "type": "grafana",
            "uid": "grafana",
        },
        "targets": [
            {
                "refId": "A",
                "queryType": "measurements",
                "channel": f"stream/daq/{config_ain.lower()}",
                "datasource": {
                    "type": "grafana",
                    "uid": "grafana",
                },
            }
        ],
    }


def managed_sensor(panel: dict) -> str | None:
    """Return the AIN of a DAQ-managed panel."""

    description = panel.get("description", "")
    prefix = "DAQ managed sensor: "

    if description.startswith(prefix):
        return description[len(prefix):]

    return None


def panel_needs_update(
    current: dict,
    desired: dict,
) -> bool:
    """Compare the properties managed by this script."""

    managed_fields = [
        "title",
        "description",
        "type",
        "datasource",
        "targets",
        "gridPos",
    ]

    return any(
        current.get(field) != desired.get(field)
        for field in managed_fields
    )


def reconcile_panels(
    current_panels: list[dict],
    sensors: list[dict],
) -> tuple[list[dict], bool]:
    """
    Compare configured sensors with existing dashboard panels.

    Returns:
        (updated_panels, changed)
    """

    panels = list(current_panels)
    changed = False

    # Index existing DAQ-managed panels by AIN.
    existing = {}

    for panel in panels:
        config_ain = managed_sensor(panel)

        if config_ain is not None:
            if config_ain in existing:
                raise ValueError(
                    f"Duplicate DAQ panel for {config_ain}"
                )

            existing[config_ain] = panel

    # Find the next available vertical position.
    y_pos = max(
        (
            panel.get("gridPos", {}).get("y", 0)
            + panel.get("gridPos", {}).get("h", 8)
            for panel in panels
        ),
        default=0,
    )

    used_ids = {
        panel.get("id")
        for panel in panels
        if panel.get("id") is not None
    }

    configured_ains = set()

    for sensor in sensors:
        config_ain = sensor["AIN"]

        if config_ain in configured_ains:
            raise ValueError(
                f"Duplicate AIN in sensor configuration: {config_ain}"
            )

        configured_ains.add(config_ain)

        desired = build_panel(sensor, y_pos)

        panel_id = desired["id"]

        if panel_id in used_ids:
            # An existing panel for this AIN can reuse its ID.
            current = existing.get(config_ain)

            if current is None or current.get("id") != panel_id:
                raise ValueError(
                    f"Panel ID collision for {config_ain}: {panel_id}"
                )

        current = existing.get(config_ain)

        if current is None:
            # Missing panel: add it.
            panels.append(desired)
            used_ids.add(panel_id)

            print(
                f"[GrafanaSetup] Added panel: {config_ain}"
            )

            y_pos += 8
            changed = True

        elif panel_needs_update(current, desired):
            # Existing panel: update only if necessary.
            current.update(desired)

            print(
                f"[GrafanaSetup] Updated panel: {config_ain}"
            )

            changed = True

        else:
            print(
                f"[GrafanaSetup] Unchanged panel: {config_ain}"
            )

    return panels, changed


def build_new_dashboard(sensors: list[dict]) -> dict:
    """Create the initial dashboard resource."""

    panels = []
    y_pos = 0

    for sensor in sensors:
        panels.append(build_panel(sensor, y_pos))
        y_pos += 8

    return {
        "kind": "Dashboard",
        "apiVersion": API_VERSION,
        "metadata": {
            "name": DASHBOARD_UID,
        },
        "spec": {
            "title": DASHBOARD_TITLE,
            "tags": ["daq", "auto-generated"],
            "timezone": "browser",
            "schemaVersion": 41,
            "version": 1,
            "refresh": "",
            "time": {
                "from": "now-30m",
                "to": "now",
            },
            "panels": panels,
        },
    }


def setup_grafana_dashboard():
    """Create or reconcile the DAQ dashboard."""

    grafana_url = os.getenv(
        "GRAFANA_URL",
        "http://localhost:3000",
    ).rstrip("/")

    grafana_token = os.getenv("GRAFANA_TOKEN")

    namespace = os.getenv(
        "GRAFANA_NAMESPACE",
        "default",
    )

    config_path = os.getenv(
        "DAQ_CONFIG",
        "labjack_channels.json",
    )

    if not grafana_token:
        print(
            "[GrafanaSetup] GRAFANA_TOKEN not set. "
            "Skipping dashboard setup."
        )
        return

    try:
        sensors = load_config(config_path)

    except FileNotFoundError:
        print(
            f"[GrafanaSetup] Config file not found: {config_path}"
        )
        return

    headers = {
        "Authorization": f"Bearer {grafana_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    dashboard_url = (
        f"{grafana_url}/apis/{API_VERSION}"
        f"/namespaces/{namespace}/dashboards/{DASHBOARD_UID}"
    )

    try:
        with httpx.Client(timeout=10) as client:

            # 1. Retrieve existing dashboard.
            response = client.get(
                dashboard_url,
                headers=headers,
            )

            if response.status_code == 404:
                # 2. Dashboard doesn't exist: create it.
                payload = build_new_dashboard(sensors)

                response = client.put(
                    dashboard_url,
                    json=payload,
                    headers=headers,
                )

                response.raise_for_status()

                print(
                    "[GrafanaSetup] Dashboard created."
                )

                return

            response.raise_for_status()

            current = response.json()

            # 3. Get existing dashboard configuration.
            spec = current["spec"]

            current_panels = spec.get("panels", [])

            # 4. Reconcile configured sensors.
            updated_panels, panels_changed = reconcile_panels(
                current_panels,
                sensors,
            )

            if not panels_changed:
                print(
                    "[GrafanaSetup] Dashboard already up to date. "
                    "No changes made."
                )
                return

            # 5. Preserve everything else in the dashboard.
            spec["panels"] = updated_panels

            payload = {
                "kind": "Dashboard",
                "apiVersion": API_VERSION,
                "metadata": {
                    "name": DASHBOARD_UID,
                    "resourceVersion": (
                        current.get("metadata", {}).get(
                            "resourceVersion"
                        )
                    ),
                },
                "spec": spec,
            }

            # 6. Only save when changes were detected.
            response = client.put(
                dashboard_url,
                json=payload,
                headers=headers,
            )

            response.raise_for_status()

            print(
                "[GrafanaSetup] Dashboard successfully updated."
            )

            print(
                f"[GrafanaSetup] URL: "
                f"{grafana_url}/d/{DASHBOARD_UID}"
            )

    except httpx.HTTPStatusError as e:
        print(
            "[GrafanaSetup] HTTP error: "
            f"{e.response.status_code} {e.response.text}"
        )

    except httpx.RequestError as e:
        print(
            f"[GrafanaSetup] Could not reach Grafana: {e}"
        )

    except (ValueError, KeyError) as e:
        print(
            f"[GrafanaSetup] Configuration error: {e}"
        )

# vim: et:sw=4
