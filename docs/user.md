# User Guide

## Installation

Websoft9 runs on any Linux server with Docker installed. The installer requires root privileges.

### Quick Install

```bash
wget -O install.sh https://artifact.websoft9.com/websoft9/release/install.sh && sudo bash install.sh
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
wget -O install.sh https://artifact.websoft9.com/websoft9/release/install.sh && sudo bash install.sh --version "latest"
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

## Command Line

### Install an Application

Use `websoft9 app install` to install an application from the local application library. The command runs the same validation and installation service as the Websoft9 console, but waits for completion before returning.

```bash
websoft9 app install <app_name> \
  --app-id <id-prefix> \
  --version <version> \
  --domain <domain-or-server-ip> \
  [--dist community] \
  [--profile <profile>] \
  [--no-proxy] \
  [--set KEY=VALUE]... \
  [--endpoint-id <id>] \
  [--json]
```

| Parameter | Meaning |
| --- | --- |
| `<app_name>` | Application name from the local library, such as `wordpress`. |
| `--app-id` | Application ID prefix: 2-20 lowercase letters or numbers, starting with a letter. Websoft9 appends a random suffix for the deployed application, for example `test` becomes `test_g73ht`. |
| `--version` | Application version available in the local library. |
| `--dist` | Application distribution. Defaults to `community`. |
| `--domain` | Application domain name or server IP. Repeat this option to configure multiple names. It is required even with `--no-proxy`. |
| `--profile` | Optional installation profile defined by the application, such as `external-db`. Profile-specific settings must be passed with `--set`. |
| `--no-proxy` | Do not create an Nginx Proxy Manager host. Use one `--domain` value containing the server IP for direct access. |
| `--set KEY=VALUE` | Adds an application setting to its generated `.env` file. Repeat for multiple settings. All template settings, including ports and database settings, use this option. |
| `--endpoint-id` | Target Portainer endpoint ID. If omitted, Websoft9 uses the local endpoint. |
| `--json` | Prints the final application ID and installation tracking ID as JSON. |
| `--from-json FILE` | Reads the complete installation request from a JSON file. It cannot be combined with application arguments or `--set`; only `--endpoint-id` and `--json` may be added. |

Install WordPress with a proxy host and a host port selected by the application template:

```bash
websoft9 app install wordpress \
  --app-id mywordpress \
  --version 6.9 \
  --domain wp.example.com \
  --set W9_HTTP_PORT_SET=9003
```

### Multiple Settings

Repeat `--set` once for every application setting. Values are written to the application's generated `.env` file; the last occurrence of the same key takes precedence. Replace the placeholder keys below with keys published by the selected application template or installation profile.

```bash
websoft9 app install <app_name> \
  --app-id <id-prefix> \
  --version <version> \
  --domain <domain> \
  --set KEY_ONE=value-one \
  --set KEY_TWO=value-two
```

Only use setting names published by the selected application template or installation profile. Do not add `W9_DATABASE_MODE` or compose-control variables manually; a selected profile manages those values.

### Multiple Domains

Repeat `--domain` to create one proxy host with several domain names. The first value is the primary domain name, so place the canonical domain first.

```bash
websoft9 app install wordpress \
  --app-id mywordpress \
  --version 6.9 \
  --domain wp.example.com \
  --domain www.example.com \
  --set W9_HTTP_PORT_SET=9003
```

Multiple domains require the default proxy-enabled mode. With `--no-proxy`, pass exactly one `--domain` value and make it the server IP address.

### WordPress with an External MySQL Database

WordPress offers the `external-db` profile for an existing MySQL-compatible database, including MySQL, MariaDB, and Aurora MySQL. Create the database and database user before installation, ensure the product container can reach the database host and port, and grant the user access to the database. Websoft9 validates the connection with read-only queries; it does not create the database, user, or permissions.

The `external-db` profile requires all six settings below. Pass each as a separate `--set` option.

| Setting | Meaning |
| --- | --- |
| `W9_HTTP_PORT_SET` | Host port exposed by the WordPress container. |
| `W9_DB_HOST_SET` | Reachable MySQL or MariaDB hostname/IP, without a URI scheme. |
| `W9_DB_PORT_SET` | Database TCP port, usually `3306`. |
| `W9_DB_NAME_SET` | Name of the existing database for this WordPress instance. |
| `W9_DB_USER_SET` | Database username with access to the named database. |
| `W9_DB_PASSWORD_SET` | Password for that database user. |

```bash
websoft9 app install wordpress \
  --app-id wordpressprod \
  --version 6.9 \
  --domain wp.example.com \
  --profile external-db \
  --set W9_HTTP_PORT_SET=9004 \
  --set W9_DB_HOST_SET=mysql.example.internal \
  --set W9_DB_PORT_SET=3306 \
  --set W9_DB_NAME_SET=wordpress_prod \
  --set W9_DB_USER_SET=wordpress_user \
  --set 'W9_DB_PASSWORD_SET=replace-with-a-strong-password'
```

Do not omit `W9_HTTP_PORT_SET`, even though the database is external. Do not pass `W9_DATABASE_MODE`, `W9_DB_EXPOSE`, or `WORDPRESS_DB_*`: Websoft9 derives them from the selected profile and validated database connection.

Passwords passed through `--set` may be retained in shell history or exposed in process listings. For production credentials, use the JSON-file workflow below and restrict the file permissions.

Install without a proxy host for direct access through the server IP:

```bash
websoft9 app install wordpress \
  --app-id mywordpress \
  --version 6.9 \
  --domain 192.0.2.10 \
  --no-proxy \
  --set W9_HTTP_PORT_SET=9003
```

For complex requests, create a JSON file matching the `appInstall` API payload:

```json
{
  "app_name": "wordpress",
  "edition": { "dist": "community", "version": "6.9" },
  "app_id": "mywordpress",
  "proxy_enabled": true,
  "domain_names": ["wp.example.com"],
  "settings": {
    "W9_HTTP_PORT_SET": "9003",
    "W9_DB_HOST_SET": "mysql.example.internal",
    "W9_DB_PORT_SET": "3306",
    "W9_DB_NAME_SET": "wordpress_prod",
    "W9_DB_USER_SET": "wordpress_user",
    "W9_DB_PASSWORD_SET": "replace-with-a-strong-password"
  },
  "profile": "external-db"
}
```

Then run:

```bash
chmod 600 wordpress-install.json
websoft9 app install --from-json wordpress-install.json --json
```

Use `websoft9 app install --help` to view the options available in the installed product version. Do not place credentials directly on the command line when `--set` values contain passwords, because they may be retained in shell history.

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
