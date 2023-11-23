#!/bin/bash

# Command-line options
# ==============================================================================
#
# --version
# Use the --version option to install a special version for installation. default is latest, for example:
#
#  $ sudo bash install.sh --version "0.8.25"
#
# --port check ports
# Use the --port option to check port, for example:
#
#   $ sudo bash check_ports.sh --port 9001,9001
# ==============================================================================


# 获取参数值
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            IFS=',' read -ra ports <<< "$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

check_ports() {
    for port in "${ports[@]}"; do
        if ss -tuln | grep ":$port " >/dev/null; then
            echo "Port $port is in use!"
            return 1
        fi
    done

    echo "All ports are available"
    return 0
}

check_ports
