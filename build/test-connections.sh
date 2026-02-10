#!/bin/bash
# Connection Testing Script for Websoft9
# Tests connectivity between apphub and all services
# Called after supervisord starts services

set -e

LOGS_DIR="/websoft9/apphub/logs"
LOG_FILE="$LOGS_DIR/connection-test.log"
STATUS_FILE="$LOGS_DIR/init-status.json"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging
log() {
    echo -e "${GREEN}[TEST]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Test service with retry
test_service() {
    local service_name=$1
    local url=$2
    local max_retries=3
    local retry_delays=(1 2 4)
    
    log "Testing $service_name connectivity: $url"
    
    for i in $(seq 0 $((max_retries - 1))); do
        if curl -sf --connect-timeout 10 "$url" > /dev/null 2>&1; then
            log "✓ $service_name is accessible"
            return 0
        else
            if [ $i -lt $((max_retries - 1)) ]; then
                local delay=${retry_delays[$i]}
                log_error "$service_name not accessible, retrying in ${delay}s... (attempt $((i + 2))/$((max_retries + 1)))"
                sleep $delay
            fi
        fi
    done
    
    log_error "✗ $service_name is NOT accessible after $max_retries retries"
    return 1
}

# Update connection test status in status file
update_connection_status() {
    local service=$1
    local connected=$2
    
    python3 <<EOF
import json
try:
    with open('$STATUS_FILE', 'r') as f:
        data = json.load(f)
    
    if '$service' in data['services']:
        current = data['services']['$service']
        if '$connected' == 'true':
            current['connection_test'] = 'passed'
        else:
            current['connection_test'] = 'failed'
    
    with open('$STATUS_FILE', 'w') as f:
        json.dump(data, f, indent=2)
except Exception as e:
    print(f"Failed to update status: {e}")
EOF
}

# Main testing flow
main() {
    log "========================================="
    log "Service Connection Testing Starting"
    log "========================================="
    
    mkdir -p "$LOGS_DIR"
    
    # Wait a bit for all services to start
    sleep 5
    
    # Test Cockpit
    if test_service "Cockpit" "http://cockpit:9090/ping"; then
        update_connection_status "cockpit" "true"
    else
        update_connection_status "cockpit" "false"
    fi
    
    # Test Gitea
    if test_service "Gitea" "http://git:3000/api/healthz"; then
        update_connection_status "gitea" "true"
    else
        update_connection_status "gitea" "false"
    fi
    
    # Test Portainer
    if test_service "Portainer" "http://portainer:9000/api/status"; then
        update_connection_status "portainer" "true"
    else
        update_connection_status "portainer" "false"
    fi
    
    # Test Apphub
    if test_service "Apphub" "http://localhost:8080/health"; then
        update_connection_status "apphub" "true"
    else
        update_connection_status "apphub" "false"
    fi
    
    log "========================================="
    log "Connection Testing Completed"
    log "Results saved to $STATUS_FILE"
    log "========================================="
}

# Run main function
main
