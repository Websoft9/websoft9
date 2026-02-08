# Websoft9 Cockpit Container - Docker Compose

This guide explains how to run the Websoft9 Cockpit container using docker-compose.

## Files

- `docker-compose.yml` - Container orchestration configuration
- `.env` - Environment variables and default values

## Quick Start

### Using Makefile (Recommended)

From the project root:

```bash
# Start Cockpit on default port (9091)
make start-cockpit

# Start Cockpit on custom port
make start-cockpit 9092
# or
make start-cockpit PORT=9092

# Stop Cockpit
make stop-cockpit

# Restart Cockpit
make restart-cockpit

# View logs
make logs-cockpit

# Remove container
make clean-cockpit

# Remove container and volumes
make rm
```

### Using Docker Compose Directly

From the `docker/cockpit` directory:

```bash
# Start container
docker-compose up -d

# Start with custom port
HTTP_PORT=9092 docker-compose up -d

# Stop container
docker-compose stop

# Restart container
docker-compose restart

# View logs
docker-compose logs -f

# Remove container
docker-compose down

# Remove container and volumes
docker-compose down -v
```

## Configuration

Edit the `.env` file to customize settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTAINER_NAME` | `websoft9-cockpit` | Container name |
| `HTTP_PORT` | `9091` | HTTP port mapping |
| `IMAGE_TAG` | `latest` | Image tag to use |
| `COMPOSE_DATA_PATH` | `/data/compose` | Path for compose data |
| `PORTAINER_DATA_VOLUME` | `cockpit_portainer_data` | Volume name for Portainer data |
| `RESTART_POLICY` | `unless-stopped` | Container restart policy |

## Access

After starting the container:

- **Cockpit UI**: http://localhost:9091
- **Portainer**: http://localhost:9091/w9deployment/
- **Default Credentials**: 
  - Username: `websoft9`
  - Password: `websoft9`

## Volumes

The container uses the following volumes:

1. **Docker Socket**: `/var/run/docker.sock` (host) → `/var/run/docker.sock` (container)
   - Allows container management from Cockpit/Portainer

2. **Compose Data**: `/data/compose` (host) → `/data/compose` (container)
   - Stores docker-compose configurations

3. **Portainer Data**: `cockpit_portainer_data` (volume) → `/portainer_data` (container)
   - Persistent Portainer configuration and data

## Building Images

From the project root:

```bash
# Build main Cockpit image
make build

# Build base image
make build-base
```

Or using Docker directly:

```bash
# Build base image
docker build -f docker/cockpit/Dockerfile.base -t websoft9/cockpit-base:latest .

# Build main image
docker build -f docker/cockpit/Dockerfile -t websoft9/cockpit:latest .
```

## Troubleshooting

### Container won't start

Check if port 9091 is already in use:

```bash
make kill-port 9091
```

### View container logs

```bash
make logs-cockpit
```

### Reset everything

Remove container and all volumes:

```bash
make rm
```

## Integration with Makefile

The Makefile provides convenient wrappers around docker-compose commands:

- Automatically handles port configuration via `PORT` variable
- Provides consistent command interface across the project
- Includes error handling and user-friendly output
- Works from any directory (uses absolute paths)

Example:

```bash
# Start on custom port from project root
cd /data/dev/websoft9
make start-cockpit PORT=9092

# View logs
make logs-cockpit

# Cleanup
make clean-cockpit
```
