# FAQ

## Installation

### Q: What are the system requirements?
A: Any Linux server with Docker 20.10+. Minimum 2 CPU cores, 2 GB RAM, 20 GB disk. See [Deployment Guide](deployment.md) for details.

### Q: Can I install without root?
A: The installer requires root privileges to configure Docker and system services. Use `sudo` if running from a non-root user.

### Q: Installation fails with Docker errors?
A: Ensure Docker is installed and the daemon is running: `docker info`. On Ubuntu, the installer will attempt to install Docker automatically.

## Usage

### Q: How do I access the console?
A: Open `http://<server-ip>:9000` in your browser after installation.

### Q: How do I install an application?
A: Go to App Store → browse or search → click Install. Most apps install in under 2 minutes.

### Q: How do I add a custom domain with SSL?
A: Go to My Apps → select app → Proxy/Access → add domain. NPM will handle Let's Encrypt certificate issuance.

### Q: Can I deploy my own Docker Compose file?
A: Yes. Go to My Apps → Compose → upload or paste your `docker-compose.yml`.

## Troubleshooting

### Q: Container is running but console is unreachable?
A: Check if port 9000 is open: `netstat -tlnp | grep 9000`. Check firewall rules.

### Q: Application install hangs or fails?
A: Check Docker daemon health. Verify the app template exists in the catalog. Check logs in Console → Logs.

### Q: How do I reset the admin password?
A: Remove the auth database and restart the setup wizard:
```bash
rm -f /opt/websoft9/data/config/product-auth/product-auth.sqlite
rm -f /opt/websoft9/data/config/setup-wizard/state.json
docker restart websoft9
```

### Q: SSL certificate not renewing?
A: Ensure port 80 is accessible from the internet (Let's Encrypt HTTP challenge). Check NPM logs via Console → Services.

## Upgrading

### Q: How do I upgrade Websoft9?
A: Run the installer with `--version latest`:
```bash
wget -O install.sh https://artifact.websoft9.com/websoft9/release/install.sh && sudo bash install.sh --version "latest"
```

### Q: Will upgrading affect my installed apps?
A: No. Application data is stored in `/opt/websoft9/data/apps/` and is not affected by platform upgrades.
