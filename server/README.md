# The server

<!-- filetree start -->

```text
daqserver
├── scripts
└── server (You are here)
    ├── db
    ├── streaming
    └── web
        ├── static
        │   ├── css
        │   └── js
        └── templates
```

<!-- filetree end -->

## About server

This is the main server directory, that hosts all of the code related to the server.

Here's a short description of what each of the subdirectories contain:

- `web`
  - Frontend code (html, js, csss)
  - Backend services that serve data through Websockets and HTTP requests
- `streaming`
  - Code that fetches data from our sensors
- `db`
  - Code that saves data to InfluxDB
