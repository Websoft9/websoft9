# Websoft9 Container - Docker Compose

This guide explains how to run the Websoft9 container using docker-compose.

## Files

- `docker-compose.yml` - Container orchestration configuration
- `.env` - Environment variables and default values

## Quick Start

### Using Makefile (Recommended)

From the project root:

```bash
# Start on default port (9091)
make start

# Start on custom port
make start 9092
# or
make start PORT=9092

# Stop
make stop

# Restart
make restart

# View logs
make logs

# Remove container
make clean-container

# Remove container and volumes
make rm
```

### Using Docker Compose Directly

From the `build` directory:

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
| `CONTAINER_NAME` | `websoft9` | Container name |
| `HTTP_PORT` | `9091` | HTTP port mapping |
| `IMAGE_TAG` | `latest` | Image tag to use |
| `WEBSOFT9_DATA_PATH` | `/websoft9/data` | Websoft9 data directory |
| `RESTART_POLICY` | `unless-stopped` | Container restart policy |

## Access

After starting the container:

- **Websoft9 UI**: http://localhost:9091
- **Portainer**: http://localhost:9091/w9deployment/
- **Default Credentials**: 
  - Username: `websoft9`
  - Password: `websoft9`

## Volumes

The container uses the following volumes:

1. **Docker Socket**: `/var/run/docker.sock` (host) → `/var/run/docker.sock` (container)
   - Allows container management from Cockpit/Portainer

2. **Websoft9 Data**: `/websoft9/data` (host) → `/websoft9/data` (container)
   - Persistent Portainer, Gitea, BaaS data

## Building Images

From the project root:

```bash
# Build main image
make build

# Build base image
make build-base
```

Or using Docker directly:

```bash
# Build base image
docker build -f build/Dockerfile.base -t websoft9-base:latest .

# Build main image
docker build -f build/Dockerfile -t websoft9:latest .
```

## Troubleshooting

### Container won't start

Check if port 9091 is already in use:

```bash
make kill-port 9091
```

### View container logs

```bash
make logs
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
make start PORT=9092

# View logs
make logs

# Cleanup
make clean-container
```
