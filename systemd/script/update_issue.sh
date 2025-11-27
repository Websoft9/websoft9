#!/bin/bash
#######################################################
# Script: update_issue.sh
# Description: Generate and update /etc/issue with dynamic system information
# Author: Websoft9
# Date: 2025-11-27
#######################################################

set -e

OUTPUT_FILE="/etc/issue"

# Get dynamic system information
CPU_CORES=$(nproc)
MEMORY_USAGE=$(free -h | awk 'NR==2 {print $3 "/" $2}')
DISK_SIZE=$(df -h / | awk 'NR==2 {print $2}')
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}')
IP_ADDRESS=$(hostname -I | cut -d" " -f1)

# Generate /etc/issue content directly
cat > "$OUTPUT_FILE" <<'EOF'
Welcome to Websoft9 IoT applications management  platform

Get  Support: https://www.websoft9.com

==================================================

--------------------------------------------------
Hostname: \n
OS： \s \v \n  \r \m
CPU core: CPU_CORES_PLACEHOLDER
Memory usage: MEMORY_USAGE_PLACEHOLDER
Disk: DISK_SIZE_PLACEHOLDER, DISK_USAGE_PLACEHOLDER usage
--------------------------------------------------

Login to Websoft9 Console

URL: http://IP_ADDRESS_PLACEHOLDER:9000
Username: websoft9


Latest starting time: \t 

\l
EOF

# Replace placeholders with actual values (using | as delimiter to avoid issues with /)
sed -i "s|CPU_CORES_PLACEHOLDER|$CPU_CORES|g" "$OUTPUT_FILE"
sed -i "s|MEMORY_USAGE_PLACEHOLDER|$MEMORY_USAGE|g" "$OUTPUT_FILE"
sed -i "s|DISK_SIZE_PLACEHOLDER|$DISK_SIZE|g" "$OUTPUT_FILE"
sed -i "s|DISK_USAGE_PLACEHOLDER|$DISK_USAGE|g" "$OUTPUT_FILE"
sed -i "s|IP_ADDRESS_PLACEHOLDER|$IP_ADDRESS|g" "$OUTPUT_FILE"

# Set proper permissions
chmod 644 "$OUTPUT_FILE"

echo "Successfully updated $OUTPUT_FILE"


# delete cockpit issue file content
[ -f /usr/share/cockpit/issue/update-issue ] && sed -i '/\/run\/cockpit\/active\.issue/d' /usr/share/cockpit/issue/update-issue

# Set GRUB timeout to 0 if not already set
if [ -f /etc/grub.d/40_custom ] && ! grep -q "set timeout=0" /etc/grub.d/40_custom; then
    tee -a /etc/grub.d/40_custom << EOF
set timeout=0
set timeout_style=hidden
EOF
fi
exit 0
