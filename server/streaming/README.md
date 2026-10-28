# Streaming

<!-- filetree start -->

```text
daqserver
├── scripts
└── server 
    ├── db
    ├── web 
    └── streaming (You are here)
        ├── grafana_live.py
        ├── lj.py
        ├── sensors.py
        ├── stream.py
        └── switches.py
```

<!-- filetree end -->

## About streaming

This is the streaming directory that hosts all of the code related to streaming. 

## Grafana Live 
We stream sensor telemetry from Python to Grafana Live for real-time visualization. `grafana_live.py` serializes sensor readings into InfluxDB line protocol and publishes them through the configured WbeSocket connection.

### Step 1: Start the services
From the repository root, start the services defined in docker-compose.yml: `docker compose up -d`. Check that the relevant containers are running: `docker compose ps`. 

If hosting on your local computer, expect for Grafana to be available at http://localhost:3000. If it is on the server, expect for it to be available to 10.10.10.10:3000.

### Step 2: Create a Grafana service account
- Open Grafana in your browser.
- Navigate to __Administration__ &rarr; __Users and access__ &rarr; __Service accounts__.
- Create a service account for the publisher.
- Generate a service-account token.
- Copy the token and store it in .env.
A service account token lets the application to authenticate without using a personal account password. Its permissions depend ont he service account's assigned role and requirements  of the endpoint.

### Verify Grafana authentication
Check if the token is accepted by Grafana with an HTTP API request: `curl -i \
  -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/org`. Change the network address as needed.

 
