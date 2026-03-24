# Services Plugin

Cockpit plugin for managing supervisord services within the container.

## Overview

This plugin provides a web-based UI for monitoring and managing supervisord-managed processes. It's designed to run inside a container and communicate with the local supervisord instance via XML-RPC.

## Features (Story 6.1)

- **Service List**: View all supervisord programs with their current status
- **Real-time Updates**: Auto-refresh every 5 seconds
- **Status Indicators**: Color-coded labels for different states (RUNNING, STOPPED, FATAL, etc.)
- **Process Info**: Display PID and uptime for each program

## Development

### Prerequisites

- Node.js 18+
- npm or yarn
- Running websoft9-cockpit container

### Install Dependencies

```bash
npm install
```

### Start Development Server

```bash
npm start
```

### Build for Production

```bash
npm run build
```

This will:
1. Build the React app
2. Deploy to the running websoft9-cockpit container

## Architecture

```
plugins/services/
├── public/
│   ├── index.html        # HTML entry point with Cockpit script
│   └── manifest.json     # Cockpit plugin manifest
├── src/
│   ├── index.js          # React entry point with dark theme support
│   ├── App.js            # Main application component
│   ├── App.css           # App styles
│   ├── components/
│   │   ├── ServiceTable.js       # PatternFly table component
│   │   └── ProgramStatusLabel.js # Status indicator component
│   └── utils/
│       └── api.js        # Supervisord XML-RPC client
├── package.json
└── build.sh              # Deployment script
```

## Supervisord Configuration

The plugin requires supervisord XML-RPC server to be enabled. Add to `supervisord.conf`:

```ini
[inet_http_server]
port=127.0.0.1:9001
username=admin
password=%(ENV_ADMIN_PASSWORD)s

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
```

## API Reference

### XML-RPC Endpoint

- **URL**: `http://127.0.0.1:9001/RPC2`
- **Method**: `supervisor.getAllProcessInfo()`
- **Auth**: HTTP Basic Authentication

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| name | string | Program name |
| statename | string | RUNNING, STOPPED, FATAL, etc. |
| pid | int | Process ID (0 if not running) |
| start | int | Unix timestamp when started |
| description | string | Human-readable status |

## Future Work (Story 6.2)

- Start/Stop/Restart operations
- Process log viewing
- Configuration editing
