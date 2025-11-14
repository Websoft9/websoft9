#!/bin/bash

# CVE Security Vulnerability Scanner using Trivy
# This script scans Docker images and OS filesystem for vulnerabilities
# Author: Websoft9 Security Team
# Version: 1.0

set -euo pipefail

# Configuration
SCRIPT_NAME=$(basename "$0")
LOG_DIR="/var/log/websoft9"
SCAN_LOG="${LOG_DIR}/cve_scan.log"
REPORT_DIR="/tmp/trivy_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="${REPORT_DIR}/cve_report_${TIMESTAMP}.json"
HTML_REPORT="${REPORT_DIR}/cve_report_${TIMESTAMP}.html"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create necessary directories
mkdir -p "${LOG_DIR}" "${REPORT_DIR}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${SCAN_LOG}"
}

# Print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%H:%M:%S')] ${message}${NC}"
}

# Check if Trivy is installed
check_trivy() {
    print_status "${BLUE}" "Checking Trivy installation..."
    if ! command -v trivy &> /dev/null; then
        print_status "${YELLOW}" "Trivy is not installed, attempting to install automatically..."
        print_status "${BLUE}" "Installing Trivy using multiple installation methods..."
        
        # Method 1: Try official script from GitHub with backup source
        print_status "${BLUE}" "Trying GitHub installation script..."
        
        # Try GitHub first
        if curl -sfL --connect-timeout 10 --max-time 30 https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin; then
            print_status "${GREEN}" "Trivy installed successfully via GitHub"
            log "Trivy installation completed successfully via GitHub"
        # If GitHub fails, try Websoft9 backup source
        elif curl -sfL --connect-timeout 10 --max-time 30 https://artifact.websoft9.com/cloud_data/install.sh | sh -s -- -b /usr/local/bin; then
            print_status "${GREEN}" "Trivy installed successfully via Websoft9 backup source"
            log "Trivy installation completed successfully via Websoft9 backup source"
        else
            print_status "${YELLOW}" "Both GitHub and backup installation failed, trying alternative methods..."
        fi
        
        # Verify installation after any successful installation method
        if command -v trivy &> /dev/null; then
            local trivy_version=$(trivy --version | head -n1)
            print_status "${GREEN}" "Trivy found: ${trivy_version}"
            log "Trivy installation verification passed: ${trivy_version}"
        else
            # If Trivy is still not found, try alternative installation methods
            print_status "${YELLOW}" "Trivy not found after initial installation attempts, trying alternative methods..."
            
            # Method 2: Try using package manager based on OS
            if command -v apt-get &> /dev/null; then
                print_status "${BLUE}" "Trying APT package manager installation..."
                if sudo apt-get update && sudo apt-get install -y wget apt-transport-https gnupg lsb-release; then
                    wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
                    echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
                    sudo apt-get update && sudo apt-get install -y trivy
                    if command -v trivy &> /dev/null; then
                        print_status "${GREEN}" "Trivy installed successfully via APT"
                        log "Trivy installation completed successfully via APT"
                        local trivy_version=$(trivy --version | head -n1)
                        print_status "${GREEN}" "Trivy found: ${trivy_version}"
                        log "Trivy installation verification passed: ${trivy_version}"
                        return 0
                    fi
                fi
            elif command -v yum &> /dev/null; then
                print_status "${BLUE}" "Trying YUM package manager installation..."
                if sudo yum install -y wget; then
                    sudo wget -O /etc/yum.repos.d/trivy.repo https://aquasecurity.github.io/trivy-repo/rpm/releases/trivy.repo
                    sudo yum -y update && sudo yum -y install trivy
                    if command -v trivy &> /dev/null; then
                        print_status "${GREEN}" "Trivy installed successfully via YUM"
                        log "Trivy installation completed successfully via YUM"
                        local trivy_version=$(trivy --version | head -n1)
                        print_status "${GREEN}" "Trivy found: ${trivy_version}"
                        log "Trivy installation verification passed: ${trivy_version}"
                        return 0
                    fi
                fi
            elif command -v dnf &> /dev/null; then
                print_status "${BLUE}" "Trying DNF package manager installation..."
                if sudo dnf install -y wget; then
                    sudo wget -O /etc/yum.repos.d/trivy.repo https://aquasecurity.github.io/trivy-repo/rpm/releases/trivy.repo
                    sudo dnf -y update && sudo dnf -y install trivy
                    if command -v trivy &> /dev/null; then
                        print_status "${GREEN}" "Trivy installed successfully via DNF"
                        log "Trivy installation completed successfully via DNF"
                        local trivy_version=$(trivy --version | head -n1)
                        print_status "${GREEN}" "Trivy found: ${trivy_version}"
                        log "Trivy installation verification passed: ${trivy_version}"
                        return 0
                    fi
                fi
            fi
            
            # Method 3: Direct binary download
            print_status "${BLUE}" "Trying direct binary download..."
            local arch=$(uname -m)
            local os=$(uname -s | tr '[:upper:]' '[:lower:]')
            
            case $arch in
                x86_64) arch="64bit" ;;
                aarch64) arch="ARM64" ;;
                armv7l) arch="ARM" ;;
                *) arch="64bit" ;;
            esac
            
            local trivy_version="v0.47.0"  # 使用稳定版本
            local download_url="https://github.com/aquasecurity/trivy/releases/download/${trivy_version}/trivy_${trivy_version#v}_${os}-${arch}.tar.gz"
            
            print_status "${BLUE}" "Downloading Trivy binary from: ${download_url}"
            
            if wget -O /tmp/trivy.tar.gz "${download_url}" || curl -L -o /tmp/trivy.tar.gz "${download_url}"; then
                cd /tmp && tar zxvf trivy.tar.gz
                if [ -f trivy ]; then
                    sudo mv trivy /usr/local/bin/
                    sudo chmod +x /usr/local/bin/trivy
                    if command -v trivy &> /dev/null; then
                        print_status "${GREEN}" "Trivy installed successfully via direct download"
                        log "Trivy installation completed successfully via direct download"
                        local trivy_version=$(trivy --version | head -n1)
                        print_status "${GREEN}" "Trivy found: ${trivy_version}"
                        log "Trivy installation verification passed: ${trivy_version}"
                        return 0
                    fi
                fi
            fi
            
            # Method 4: 提示手动安装
            print_status "${RED}" "ERROR: All automatic installation methods failed"
            print_status "${YELLOW}" "请手动安装 Trivy，可以尝试以下方法："
            print_status "${YELLOW}" ""
            print_status "${YELLOW}" "方法1: 使用国内镜像下载 (如果有的话)"
            print_status "${YELLOW}" "方法2: 手动下载二进制文件"
            print_status "${YELLOW}" "  wget https://github.com/aquasecurity/trivy/releases/download/v0.47.0/trivy_0.47.0_Linux-64bit.tar.gz"
            print_status "${YELLOW}" "  tar zxvf trivy_0.47.0_Linux-64bit.tar.gz"
            print_status "${YELLOW}" "  sudo mv trivy /usr/local/bin/"
            print_status "${YELLOW}" "  sudo chmod +x /usr/local/bin/trivy"
            print_status "${YELLOW}" ""
            print_status "${YELLOW}" "方法3: 使用Docker运行 (如果网络允许)"
            print_status "${YELLOW}" "  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \\"
            print_status "${YELLOW}" "    -v $PWD:/workspace aquasec/trivy image your-image"
            print_status "${YELLOW}" ""
            print_status "${YELLOW}" "方法4: 联系系统管理员协助安装"
            print_status "${YELLOW}" ""
            print_status "${YELLOW}" "安装完成后重新运行此脚本"
            exit 1
        fi
    else
        local trivy_version=$(trivy --version | head -n1)
        print_status "${GREEN}" "Trivy found: ${trivy_version}"
        log "Trivy installation check passed: ${trivy_version}"
    fi
}

# Check if Docker is running
check_docker() {
    print_status "${BLUE}" "Checking Docker status..."
    if ! docker info &> /dev/null; then
        print_status "${RED}" "ERROR: Docker is not running or not accessible"
        print_status "${YELLOW}" "Please ensure Docker is running and you have permissions to access it"
        exit 1
    fi
    print_status "${GREEN}" "Docker is running"
    log "Docker status check passed"
}

# Update Trivy database
update_trivy_db() {
    print_status "${BLUE}" "Updating Trivy vulnerability database..."
    if trivy image --download-db-only; then
        print_status "${GREEN}" "Trivy database updated successfully"
        log "Trivy database update completed"
    else
        print_status "${YELLOW}" "Warning: Failed to update Trivy database, using cached version"
        log "Warning: Trivy database update failed, continuing with cached version"
    fi
}

# Scan filesystem for OS vulnerabilities
scan_filesystem() {
    print_status "${BLUE}" "Scanning filesystem for OS vulnerabilities..."
    local fs_report="${REPORT_DIR}/filesystem_scan_${TIMESTAMP}.json"
    
    log "Starting filesystem vulnerability scan"
    
    # Scan the root filesystem
    if trivy fs --format json --output "${fs_report}" /; then
        print_status "${GREEN}" "Filesystem scan completed"
        
        # Parse and display critical vulnerabilities
        local critical_count=$(jq '.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL") | .VulnerabilityID' "${fs_report}" 2>/dev/null | wc -l)
        local high_count=$(jq '.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH") | .VulnerabilityID' "${fs_report}" 2>/dev/null | wc -l)
        local medium_count=$(jq '.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM") | .VulnerabilityID' "${fs_report}" 2>/dev/null | wc -l)
        
        print_status "${YELLOW}" "Filesystem vulnerabilities found:"
        echo -e "  ${RED}CRITICAL: ${critical_count}${NC}"
        echo -e "  ${YELLOW}HIGH: ${high_count}${NC}"
        echo -e "  ${BLUE}MEDIUM: ${medium_count}${NC}"
        
        log "Filesystem scan results - CRITICAL: ${critical_count}, HIGH: ${high_count}, MEDIUM: ${medium_count}"
        
        # Display critical vulnerabilities details
        if [ "${critical_count}" -gt 0 ]; then
            print_status "${RED}" "CRITICAL vulnerabilities found in filesystem:"
            jq -r '.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL") | "  - \(.VulnerabilityID): \(.Title // .Description // "No description")"' "${fs_report}" 2>/dev/null | head -10
            if [ "${critical_count}" -gt 10 ]; then
                echo -e "  ${YELLOW}... and $((critical_count - 10)) more CRITICAL vulnerabilities${NC}"
            fi
        fi
        
        echo "${fs_report}" >> "${REPORT_FILE}.list"
    else
        print_status "${RED}" "ERROR: Filesystem scan failed"
        log "Error: Filesystem vulnerability scan failed"
        return 1
    fi
}

# Get all Docker images
get_docker_images() {
    docker images --format "table {{.Repository}}:{{.Tag}}" | tail -n +2 | grep -v "^<none>:<none>$" || true
}

# Scan Docker images for vulnerabilities
scan_docker_images() {
    print_status "${BLUE}" "Scanning Docker images for vulnerabilities..."
    
    local images=$(get_docker_images)
    
    if [ -z "${images}" ]; then
        print_status "${YELLOW}" "No Docker images found to scan"
        log "No Docker images found for scanning"
        return 0
    fi
    
    local image_count=$(echo "${images}" | wc -l)
    print_status "${BLUE}" "Found ${image_count} Docker images to scan"
    log "Found ${image_count} Docker images to scan"
    
    local current_image=1
    local total_critical=0
    local total_high=0
    local total_medium=0
    
    echo "${images}" | while IFS= read -r image; do
        print_status "${BLUE}" "Scanning image (${current_image}/${image_count}): ${image}"
        
        local image_report="${REPORT_DIR}/image_$(echo "${image}" | tr '/:' '_')_${TIMESTAMP}.json"
        
        # Scan for CRITICAL and HIGH vulnerabilities only to speed up the process
        if trivy image --format json --severity CRITICAL,HIGH,MEDIUM --output "${image_report}" "${image}" 2>/dev/null; then
            
            # Parse vulnerabilities
            local critical_count=$(jq '.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL") | .VulnerabilityID' "${image_report}" 2>/dev/null | wc -l)
            local high_count=$(jq '.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH") | .VulnerabilityID' "${image_report}" 2>/dev/null | wc -l)
            local medium_count=$(jq '.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM") | .VulnerabilityID' "${image_report}" 2>/dev/null | wc -l)
            
            if [ "${critical_count}" -gt 0 ] || [ "${high_count}" -gt 0 ] || [ "${medium_count}" -gt 0 ]; then
                echo -e "  ${image}:"
                [ "${critical_count}" -gt 0 ] && echo -e "    ${RED}CRITICAL: ${critical_count}${NC}"
                [ "${high_count}" -gt 0 ] && echo -e "    ${YELLOW}HIGH: ${high_count}${NC}"
                [ "${medium_count}" -gt 0 ] && echo -e "    ${BLUE}MEDIUM: ${medium_count}${NC}"
                
                # Show critical vulnerabilities for this image
                if [ "${critical_count}" -gt 0 ]; then
                    echo -e "    ${RED}Critical CVEs:${NC}"
                    jq -r '.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL") | "      - \(.VulnerabilityID): \(.Title // .Description // "No description")"' "${image_report}" 2>/dev/null | head -5
                    if [ "${critical_count}" -gt 5 ]; then
                        echo -e "      ${YELLOW}... and $((critical_count - 5)) more CRITICAL vulnerabilities${NC}"
                    fi
                fi
                
                total_critical=$((total_critical + critical_count))
                total_high=$((total_high + high_count))
                total_medium=$((total_medium + medium_count))
                
                echo "${image_report}" >> "${REPORT_FILE}.list"
            else
                print_status "${GREEN}" "  No significant vulnerabilities found in ${image}"
                rm -f "${image_report}"
            fi
            
            log "Scanned image: ${image} - CRITICAL: ${critical_count}, HIGH: ${high_count}, MEDIUM: ${medium_count}"
        else
            print_status "${RED}" "  Failed to scan image: ${image}"
            log "Error: Failed to scan image: ${image}"
        fi
        
        current_image=$((current_image + 1))
    done
    
    print_status "${BLUE}" "Docker images scan summary:"
    echo -e "  ${RED}Total CRITICAL: ${total_critical}${NC}"
    echo -e "  ${YELLOW}Total HIGH: ${total_high}${NC}"
    echo -e "  ${BLUE}Total MEDIUM: ${total_medium}${NC}"
    
    log "Docker images scan completed - Total CRITICAL: ${total_critical}, HIGH: ${total_high}, MEDIUM: ${total_medium}"
}

# Generate consolidated report
generate_report() {
    print_status "${BLUE}" "Generating consolidated security report..."
    
    if [ ! -f "${REPORT_FILE}.list" ]; then
        print_status "${YELLOW}" "No vulnerability reports found to consolidate"
        return 0
    fi
    
    # Merge all JSON reports
    echo "{" > "${REPORT_FILE}"
    echo "  \"scan_timestamp\": \"$(date -Iseconds)\"," >> "${REPORT_FILE}"
    echo "  \"scan_type\": \"comprehensive\"," >> "${REPORT_FILE}"
    echo "  \"reports\": [" >> "${REPORT_FILE}"
    
    local first=true
    while IFS= read -r report_file; do
        if [ -f "${report_file}" ]; then
            if [ "${first}" = true ]; then
                first=false
            else
                echo "," >> "${REPORT_FILE}"
            fi
            cat "${report_file}" >> "${REPORT_FILE}"
        fi
    done < "${REPORT_FILE}.list"
    
    echo "]" >> "${REPORT_FILE}"
    echo "}" >> "${REPORT_FILE}"
    
    # Generate HTML report if possible
    if command -v trivy &> /dev/null; then
        trivy convert --format template --template "@contrib/html.tpl" --output "${HTML_REPORT}" "${REPORT_FILE}" 2>/dev/null || true
    fi
    
    print_status "${GREEN}" "Reports generated:"
    echo "  JSON Report: ${REPORT_FILE}"
    [ -f "${HTML_REPORT}" ] && echo "  HTML Report: ${HTML_REPORT}"
    echo "  Log File: ${SCAN_LOG}"
    
    log "Consolidated report generated: ${REPORT_FILE}"
}

# Main execution function
main() {
    print_status "${GREEN}" "=== Websoft9 CVE Security Scanner ==="
    print_status "${BLUE}" "Starting comprehensive vulnerability scan at $(date)"
    
    log "=== CVE Security Scan Started ==="
    log "Scan initiated by user: $(whoami)"
    log "System: $(uname -a)"
    
    # Pre-flight checks
    check_trivy
    check_docker
    
    # Update vulnerability database
    update_trivy_db
    
    echo
    print_status "${BLUE}" "=== Phase 1: Filesystem Vulnerability Scan ==="
    scan_filesystem
    
    echo
    print_status "${BLUE}" "=== Phase 2: Docker Images Vulnerability Scan ==="
    scan_docker_images
    
    echo
    print_status "${BLUE}" "=== Phase 3: Report Generation ==="
    generate_report
    
    echo
    print_status "${GREEN}" "=== Scan Completed Successfully ==="
    print_status "${BLUE}" "Scan finished at $(date)"
    
    log "=== CVE Security Scan Completed Successfully ==="
    
    # Final security advisory
    echo
    print_status "${YELLOW}" "Security Advisory:"
    echo "1. Review all CRITICAL vulnerabilities immediately"
    echo "2. Consider updating/patching affected packages"
    echo "3. For Docker images, consider rebuilding with updated base images"
    echo "4. Schedule regular security scans"
    echo "5. Monitor security advisories for your software stack"
    
    # Check if critical vulnerabilities were found
    if [ -f "${REPORT_FILE}" ]; then
        local total_critical=$(find "${REPORT_DIR}" -name "*_${TIMESTAMP}.json" -exec jq -r '.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL") | .VulnerabilityID' {} \; 2>/dev/null | wc -l)
        if [ "${total_critical}" -gt 0 ]; then
            print_status "${RED}" "WARNING: ${total_critical} CRITICAL vulnerabilities found!"
            print_status "${RED}" "Immediate action required!"
            exit 2
        fi
    fi
    
    print_status "${GREEN}" "No CRITICAL vulnerabilities found or scan completed with warnings."
    exit 0
}

# Handle script interruption
cleanup() {
    print_status "${YELLOW}" "Scan interrupted by user"
    log "Scan interrupted by user"
    exit 130
}

trap cleanup INT TERM

# Help function
show_help() {
    cat << EOF
Usage: ${SCRIPT_NAME} [OPTIONS]

Websoft9 CVE Security Scanner using Trivy

This script performs comprehensive vulnerability scanning of:
1. Operating system and filesystem
2. All Docker images present on the system

OPTIONS:
    -h, --help          Show this help message
    -v, --version       Show script version

REQUIREMENTS:
    - Trivy will be automatically installed if not present
    - Docker must be running (for image scans)
    - jq must be installed for JSON processing
    - Sufficient disk space in /tmp for reports
    - curl/wget must be available for Trivy installation

REPORTS:
    - JSON reports: ${REPORT_DIR}/
    - HTML reports: ${REPORT_DIR}/ (if supported)
    - Logs: ${LOG_DIR}/cve_scan.log

EXIT CODES:
    0 - Success, no critical vulnerabilities
    1 - Script error or requirements not met
    2 - Critical vulnerabilities found
    130 - Interrupted by user

EXAMPLES:
    ${SCRIPT_NAME}                     # Run full scan
    ${SCRIPT_NAME} --help              # Show this help
    ./install_trivy_backup.sh          # Manual Trivy installation with backup sources

For more information, visit: https://www.websoft9.com/

EOF
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    -v|--version)
        echo "${SCRIPT_NAME} version 1.0"
        exit 0
        ;;
    "")
        main "$@"
        ;;
    *)
        print_status "${RED}" "Unknown option: $1"
        echo "Use -h or --help for usage information"
        exit 1
        ;;
esac
