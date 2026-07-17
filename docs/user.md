# User Guide

## Installation

Websoft9 runs on any Linux server with Docker installed. The installer requires root privileges.

### Quick Install

```bash
wget -O install.sh https://artifact.websoft9.com/websoft9/release/platform/install.sh && sudo bash install.sh
```

### Install with Custom Options

```bash
sudo bash install.sh \
  --console-port 9000 \
  --channel release \
  --version "latest" \
  --path "/opt/websoft9/source"
```

After installation, access Websoft9 at: **http://<server-ip>:9000**

### Upgrade

```bash
wget -O install.sh https://artifact.websoft9.com/websoft9/release/platform/install.sh && sudo bash install.sh --version "latest"
```

### Uninstall

```bash
# Default uninstall
curl -fsSL https://artifact.websoft9.com/websoft9/release/uninstall.sh | sudo bash

# Keep data
sudo bash uninstall.sh --keep-data

# Full purge
sudo bash uninstall.sh --purge
```

## First Login

After installation, complete the setup wizard:

1. Open `http://<server-ip>:9000`
2. Follow the setup wizard to create the administrator account
3. Configure basic settings (timezone, network, etc.)

## Core Features

### App Store
Browse and install 200+ open source applications with one click. Applications include CMS (WordPress), e-commerce, DevOps tools, databases, and more.

### My Apps
Manage installed applications: start, stop, restart, redeploy, view logs, manage files and volumes.

### File Manager
Web-based file browser for managing files and directories within application containers.

### Terminal
Browser-based terminal for remote server access. Inspect and manage your server directly from the Websoft9 console.

### Proxy & SSL
Manage domains and SSL certificates through Nginx Proxy Manager integration. Automatic Let's Encrypt certificate issuance and renewal.

### Backups
Schedule and manage backups for applications and databases. Support for local and S3 remote storage.

### System Settings
Configure platform settings including ports, mirrors, certificates, and user accounts.
