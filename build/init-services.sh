#!/bin/bash
# Service Initialization Script for Websoft9
# This script initializes all services in the cockpit container
# Called by entrypoint.sh before supervisord starts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="/websoft9/apphub/src/config"
LOGS_DIR="/websoft9/apphub/logs"
SECRETS_DIR="/websoft9/.secrets"
STATUS_FILE="$LOGS_DIR/init-status.json"
LOG_FILE="$LOGS_DIR/init.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[INIT]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Initialize status tracking
init_status_file() {
    mkdir -p "$LOGS_DIR"
    cat > "$STATUS_FILE" <<EOF
{
  "initialized_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "services": {
    "cockpit": {"status": "pending", "message": ""},
    "apphub": {"status": "pending", "message": ""},
    "gitea": {"status": "pending", "message": ""},
    "portainer": {"status": "pending", "message": ""}
  }
}
EOF
}

# Update service status
update_status() {
    local service=$1
    local status=$2
    local message=$3
    
    python3 -c "
import json
with open('$STATUS_FILE', 'r') as f:
    data = json.load(f)
data['services']['$service'] = {'status': '$status', 'message': '''$message'''}
with open('$STATUS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
"
}

# Generate secure random password
generate_password() {
    python3 -c "import secrets, string; chars = string.ascii_letters + string.digits + '!@#$%^&*'; print(''.join(secrets.choice(chars) for _ in range(24)))"
}

# Ensure config files exist
ensure_config_files() {
    log "Ensuring configuration files exist..."
    
    mkdir -p "$CONFIG_DIR"
    
    # Copy system.ini template if not exists
    if [ ! -f "$CONFIG_DIR/system.ini" ]; then
        log "Creating system.ini from template"
        cp "$SCRIPT_DIR/config-templates/system.ini.default" "$CONFIG_DIR/system.ini"
    fi
    
    # Copy config.ini template if not exists
    if [ ! -f "$CONFIG_DIR/config.ini" ]; then
        log "Creating config.ini from template"
        cp "$SCRIPT_DIR/config-templates/config.ini.default" "$CONFIG_DIR/config.ini"
    fi
}

# Generate and encrypt passwords
generate_passwords() {
    log "Checking for passwords in config.ini..."
    
    # Check if passwords already exist
    if grep -q "admin_password_encrypted = AES256:" "$CONFIG_DIR/config.ini" 2>/dev/null; then
        log "Passwords already exist in config.ini, skipping generation"
        return 0
    fi
    
    log "Generating secure random passwords..."
    
    # Generate passwords
    local cockpit_pwd=$(generate_password)
    local gitea_pwd=$(generate_password)
    local portainer_pwd=$(generate_password)
    local apphub_key=$(generate_password)
    local webhook_secret=$(generate_password)
    
    # Ensure Python cryptography is available
    if ! python3 -c "import cryptography" 2>/dev/null; then
        log_warn "cryptography module not found, installing..."
        pip3 install -q cryptography
    fi
    
    # Encrypt passwords
    log "Encrypting passwords..."
    local cockpit_encrypted=$(python3 "$SCRIPT_DIR/encrypt-password.py" "$cockpit_pwd")
    local gitea_encrypted=$(python3 "$SCRIPT_DIR/encrypt-password.py" "$gitea_pwd")
    local portainer_encrypted=$(python3 "$SCRIPT_DIR/encrypt-password.py" "$portainer_pwd")
    local apphub_encrypted=$(python3 "$SCRIPT_DIR/encrypt-password.py" "$apphub_key")
    local webhook_encrypted=$(python3 "$SCRIPT_DIR/encrypt-password.py" "$webhook_secret")
    
    # Update config.ini with encrypted passwords
    log "Storing encrypted passwords in config.ini..."
    
    # Use Python to safely update INI file
    python3 <<EOF
import configparser
config = configparser.ConfigParser()
config.read('$CONFIG_DIR/config.ini')

if 'cockpit' not in config:
    config.add_section('cockpit')
config.set('cockpit', 'admin_password_encrypted', '$cockpit_encrypted')

if 'git' not in config:
    config.add_section('git')
config.set('git', 'admin_password_encrypted', '$gitea_encrypted')
config.set('git', 'webhook_secret_encrypted', '$webhook_encrypted')

if 'portainer' not in config:
    config.add_section('portainer')
config.set('portainer', 'admin_password_encrypted', '$portainer_encrypted')

if 'apphub' not in config:
    config.add_section('apphub')
config.set('apphub', 'api_key_encrypted', '$apphub_encrypted')

with open('$CONFIG_DIR/config.ini', 'w') as f:
    config.write(f)
EOF

    log "✓ Passwords generated and encrypted successfully"
    
    # Store plaintext passwords temporarily for initialization (will be deleted after services init)
    echo "$gitea_pwd" > /tmp/.gitea_init_pwd
    echo "$portainer_pwd" > /tmp/.portainer_init_pwd
    chmod 600 /tmp/.gitea_init_pwd /tmp/.portainer_init_pwd
}

# Initialize Cockpit
init_cockpit() {
    log "Initializing Cockpit..."
    update_status "cockpit" "initializing" "Setting up Cockpit service"
    
    # Cockpit admin user already created in entrypoint.sh (websoft9:websoft9)
    if id "websoft9" &>/dev/null; then
        log "✓ Cockpit user 'websoft9' already exists"
        update_status "cockpit" "success" "Admin user ready"
    else
        log_error "Cockpit user 'websoft9' not found"
        update_status "cockpit" "failed" "Admin user not found"
        return 1
    fi
}

# Initialize Apphub
init_apphub() {
    log "Initializing Apphub..."
    update_status "apphub" "initializing" "Setting up Apphub database and config"
    
    # Ensure database directory exists
    mkdir -p /var/lib/apphub
    
    # Check if database needs initialization
    if [ ! -f "/var/lib/apphub/db.sqlite" ]; then
        log "Creating Apphub database schema..."
        # Database will be auto-created by apphub on first run
        touch /var/lib/apphub/db.sqlite
        chmod 644 /var/lib/apphub/db.sqlite
    fi
    
    # Ensure log directory
    mkdir -p "$LOGS_DIR"
    
    log "✓ Apphub initialized successfully"
    update_status "apphub" "success" "Database and config ready"
}

# Initialize Gitea (background job - service must be running)
init_gitea_background() {
    log "Scheduling Gitea initialization (background)..."
    update_status "gitea" "pending" "Waiting for Gitea service to start"
    
    (
        sleep 15  # Wait for Gitea to start
        
        if [ -f /tmp/.gitea_init_pwd ]; then
            local gitea_pwd=$(cat /tmp/.gitea_init_pwd)
            
            log "Creating Gitea admin user..."
            if su -c "/usr/local/bin/gitea admin user create --admin --username websoft9 --password '$gitea_pwd' --email admin@websoft9.com --config /etc/gitea/app.ini 2>/dev/null || true" git; then
                log "✓ Gitea admin user created"
                update_status "gitea" "success" "Admin user created"
            else
                log_warn "Gitea admin user creation skipped (may already exist)"
                update_status "gitea" "success" "Admin user ready"
            fi
            
            # Clean up temp password file
            rm -f /tmp/.gitea_init_pwd
            
            touch /var/lib/gitea/.initialized
        fi
    ) &
}

# Initialize Portainer (background job - service must be running)
init_portainer_background() {
    log "Scheduling Portainer initialization (background)..."
    update_status "portainer" "pending" "Waiting for Portainer service to start"
    
    (
        sleep 20  # Wait for Portainer to start
        
        log "Checking Portainer health..."
        for i in {1..5}; do
            if curl -sf http://portainer:9000/api/status > /dev/null 2>&1; then
                log "✓ Portainer is healthy"
                update_status "portainer" "success" "Service ready"
                break
            fi
            log "Waiting for Portainer... (attempt $i/5)"
            sleep 2
        done
        
        # Clean up temp password file
        rm -f /tmp/.portainer_init_pwd
    ) &
}

# Main initialization flow
main() {
    log "========================================="
    log "Websoft9 Service Initialization Starting"
    log "========================================="
    
    # Initialize status file
    init_status_file
    
    # Ensure config files
    ensure_config_files
    
    # Generate passwords if needed
    generate_passwords
    
    # Initialize services
    init_cockpit || log_error "Cockpit initialization failed (non-fatal)"
    init_apphub || log_error "Apphub initialization failed (non-fatal)"
    init_gitea_background
    init_portainer_background
    
    log "========================================="
    log "Service Initialization Completed"
    log "Check $STATUS_FILE for status"
    log "========================================="
}

# Run main function
main
