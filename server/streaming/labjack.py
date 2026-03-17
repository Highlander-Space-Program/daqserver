from asyncio import AbstractEventLoop
from asyncio.queues import Queue
import time
from server.streaming.sensors import load_sensors_from_json, Sensor

import csv
from datetime import datetime
from labjack import ljm
from threading import Lock


AIN_TO_CHANNEL = {
    "AIN52": "tc_1",
    "AIN51": "tc_2",
    "AIN48": "lc_1",
    "AIN21": "lc_2",
    "AIN50": "pt_1",
    "AIN10": "pt_2",
    "AIN6": "pt_3",
    "AIN7": "flow_1",
}


class LabJackT7:
    def __init__(self, loop: AbstractEventLoop) -> None:
        self.loop = loop

    def open(self, connection_type: str = "USB"):
        print(f"Opening T7 over {connection_type}...")
        handle = ljm.openS("T7", connection_type, "ANY")
        info = ljm.getHandleInfo(handle)
        print(
            f"Opened T7: Device type: {info[0]}, "
            f"Connection type: {info[1]}, Serial: {info[2]}, IP: {info[3]}"
        )
        return handle

    def build_scan_list(self, sensors: list[Sensor]):
        channel_names = [s.ain for s in sensors]
        a_addresses, _ = ljm.namesToAddresses(len(channel_names), channel_names)

        print("\nScan list:")
        for name, addr in zip(channel_names, a_addresses):
            print(f"  {name} -> address {addr}")

        return a_addresses, len(a_addresses), channel_names

    def configure_stream_params(self):
        scan_rate_hz = 100
        scans_per_read = 100
        return scan_rate_hz, scans_per_read

    def run_stream(
        self, handle, scan_list, sensors: list[Sensor], channel_names: list[str]
    ):
        # global counter
        scan_rate_hz, scans_per_read = self.configure_stream_params()
        num_channels = len(channel_names)

        sensor_type_by_name = {s.ain: s.sensor_type for s in sensors}

        print("\nStarting stream:")
        print(f"  Scan rate:      {scan_rate_hz} Hz")
        print(f"  Channels:       {channel_names}")
        print(f"  Scans per read: {scans_per_read}")

        # actual_scan_rate = ljm.eStreamStart(
        #     handle,
        #     scans_per_read,
        #     num_channels,
        #     scan_list,
        #     scan_rate_hz,
        # )

        actual_scan_rate = ljm.eStreamStart(
            handle,
            1,
            num_channels,
            scan_list,
            50,
        )

        print(f"Actual stream scan rate: {actual_scan_rate} Hz")
        print("\nStreaming... press Ctrl+C to stop.\n")

        print("\n")
        print("Enter CSV File: ")
        fileToOpen = input()
        csvfile = open(f"{fileToOpen}.csv", "w", newline="")
        writer = csv.DictWriter(
            csvfile,
            fieldnames=[
                "device",
                "ain",
                "sensor",
                "voltage",
                "measurement",
                "timestamp",
            ],
        )
        writer.writeheader()

        try:
            while True:
                data, device_backlog, ljm_backlog = ljm.eStreamRead(handle)
                # counter += 1
                scans = len(data) // num_channels

                for scan_idx in range(scans):
                    base = scan_idx * num_channels
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[
                        :-3
                    ]

                    for ch_idx, ain_name in enumerate(channel_names):
                        value = data[base + ch_idx]

                        row = {
                            "device": "T7",
                            "ain": ain_name,
                            "sensor": sensor_type_by_name.get(ain_name),
                            "voltage": value,
                            "measurement": "sensor_data",
                            "timestamp": timestamp,
                        }

                        # Write to CSV (already doing this)
                        writer.writerow(row)

                        # Update live data for dashboard
                        with live_data_lock:
                            live_data[ain_name] = row

                if scans > 0:
                    # print(
                    #     f"# scans: {scans}, deviceBacklog: {device_backlog}, "
                    #     f"LJMBacklog: {ljm_backlog}"
                    # )
                    pass

        except KeyboardInterrupt:
            print("\nStopping stream (Ctrl+C detected)...")

        finally:
            csvfile.close()
            ljm.eStreamStop(handle)
            ljm.close(handle)
            print("Stream stopped and device closed.")

    def stream_to(self, channel: Queue):
        # Map your AIN channels to dashboard channel names

        output = [0] * 50
        i = 0

        live_data = {}
        live_data_lock = Lock()

        while True:
            with live_data_lock:
                data_copy = live_data.copy()

            if data_copy:
                dash_packet = {
                    "timestamp": time.time(),
                    "board_id": "labjack",
                    "channels": {},
                }

                # Precompute totals FIRST
                total_loadcell_voltage = sum(
                    row["voltage"]
                    for row in data_copy.values()
                    if row["sensor"] == "LoadCell"
                )

                total_loadcell_lbs = total_loadcell_voltage_to_lbs(
                    total_loadcell_voltage
                )

                for ain_name, row in data_copy.items():
                    dash_name = AIN_TO_CHANNEL.get(ain_name)
                    if dash_name:
                        value = row["voltage"]

                        if row["sensor"] == "Thermocouple":
                            value = thermocouple_voltage_to_temperature(value)
                        elif row["sensor"] == "Pressure":
                            value = pressure_voltage_to_psi(value)
                        elif row["sensor"] == "LoadCell":
                            # value = calibration(value)
                            value = loadcell_voltage_to_lbs(value)
                            output[i % len(output)] = value
                            i += 1
                            value = sum(output) / len(output)

                        dash_packet["channels"][dash_name] = value

                # Send to all connected browsers
                # socketio.emit("sensor_data", dash_packet)
                # Thread-safe way to put data into asyncio queue
                self.loop.call_soon_threadsafe(channel.put_nowait, dash_packet)

            time.sleep(0.05)  # ~20 Hz update rate


# def thermocouple_voltage_to_temperature(thermo_voltage, cj_temp_c):
#     """
#     Convert thermocouple voltage (in volts) to temperature in °F.
#
#     This uses a simple linear approximation:
#       - K-type thermocouple sensitivity is approximately 41 µV/°C.
#       - dT (°C) = thermo_voltage (V) / 0.000041
#       - Thermocouple temperature (°C) = Cold Junction Temperature (°C) + dT
#       - Then convert °C to °F.
#
#     Note: This linear approximation is valid only over a narrow temperature range.
#     """
#     # Calculate the temperature difference from the thermocouple voltage
#     dT_c = thermo_voltage / 0.000041  # in °C
#     tc_temp_c = cj_temp_c + dT_c  # thermocouple temperature in °C
#     tc_temp_f = (tc_temp_c * 9 / 5) + 32  # convert °C to °F
#     return tc_temp_f
#


# --- Conversion functions ---
def thermocouple_voltage_to_temperature(
    voltage, cj_temp_c=25.0
):  # Also potentially wrong equation
    """Convert thermocouple voltage (V) to °F using same formula as streaming.py"""
    dT_c = voltage / 0.000041  # in °C
    tc_temp_c = cj_temp_c + dT_c  # thermocouple temperature in °C
    return tc_temp_c


def loadcell_voltage_to_lbs(voltage):
    # return (0.5104 * (voltage*pow(10,5))) * 2.20462
    return ((-0.4995 * (voltage * pow(10, 5))) + 0.8905) * 2.20462


def total_loadcell_voltage_to_lbs(voltage):
    return ((-0.4995 * (voltage * pow(10, 5))) + 0.8905) * 2.20462


def pressure_voltage_to_psi(voltage):
    return ((voltage - 0.5) / (4.0)) * 1600


def calibration(voltage):
    max_load = 1102.31  # lbs
    sens = 2.0  # mV / V
    excitation_voltage = 5.0  # V

    full_scale_voltage = sens * excitation_voltage / 1000

    return -1 * (max_load / full_scale_voltage) * voltage


# Background thread to push live data to the dashboard


def main():
    sensors = load_sensors_from_json("labjack_channels.json")
    if not sensors:
        print("No sensors found in JSON config. Exiting.")
        return

    handle = open_t7("USB")

    for s in sensors:
        s.configure_labjack(ljm, handle)

    scan_list, num_channels, channel_names = build_scan_list(sensors)

    run_stream(handle, scan_list, sensors, channel_names)


if __name__ == "__main__":
    main()
