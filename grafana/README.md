# Grafana DAQ Dashboard

This directory contains the Grafana DAQ dashboard definition.

## Dashboard

- Pressure Transducers: combined Grafana Live graph
- Thermocouples: combined Grafana Live graph
- Load Cells: combined Grafana Live graph

## Requirements

- Grafana 13.0.1
- Configured Grafana Live data source
- Configured InfluxDB 3 data source for sensor discovery

The dashboard uses Grafana Live for real-time measurements.
InfluxDB is used for sensor discovery variables.
