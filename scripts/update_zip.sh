#!/bin/bash

## This script is used for download zip files to a target directory
## apphub dockerfile is depends on this script

# Command-line options
# ==========================================================
#
# --channel <release|dev>
# Use the --channel option to install a release(production) or dev distribution. default is release, for example:
#
#  $ sudo bash install.sh --channel release
#
# --package_name
# Use the --package_name option to define a zip file, for example:
#
#  $ sudo bash install.sh --package_name media.zip
#
# --sync_to
# Use the sync_to option to define the target directory which zip file will unzip, for example:
#
#  $ sudo bash install.sh --sync_to "/websoft9/media"

channel="release"
while [[ $# -gt 0 ]]; do
    case $1 in
        --channel)
            channel="$2"
            shift 2
            ;;
        --package_name)
            package_name="$2"
            shift 2
            ;;
        --sync_to)
            sync_to="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [ -z "$package_name" ] || [ -z "$sync_to" ]; then
    echo "Parameter package_name and sync_to is necessary"
    exit 1
fi

artifact_base="${WEBSOFT9_ARTIFACT_BASE:-https://artifact.websoft9.com}"
artifact_base="${artifact_base%/}"

# Define the artifact URL as a global variable
artifact_url="$artifact_base/$channel/websoft9/plugin"

upgrade_zip() {
    local plugin_name=${package_name%%-*}
    local url="$artifact_url/$plugin_name/$package_name"
    local checksum_url="${url}.sha256"
    local attempts=0
    local max_attempts=2
    local work_dir
    local zip_path
    local checksum_path
    local extract_dir
    local package_directory
    local source_dir
    local expected_checksum
    local actual_checksum

    work_dir=$(mktemp -d /tmp/update-zip.XXXXXX)
    zip_path="$work_dir/$package_name"
    checksum_path="$work_dir/${package_name}.sha256"
    extract_dir="$work_dir/extract"
    mkdir -p "$extract_dir"

    while [[ $attempts -lt $max_attempts ]]; do
        rm -f "$zip_path"
        if wget --timeout=120 --no-clobber "$url" -O "$zip_path"; then
            break
        fi

        attempts=$((attempts+1))
        echo "Download attempt $attempts failed. Retrying in 5 seconds..."
        sleep 5
    done

    if [[ $attempts -eq $max_attempts ]]; then
        echo "Download failed for package: $package_name after $max_attempts attempts."
        rm -rf "$work_dir"
        return 1
    fi

    if wget --timeout=120 --no-clobber "$checksum_url" -O "$checksum_path"; then
        expected_checksum=$(awk '{print $1}' "$checksum_path")
        actual_checksum=$(sha256sum "$zip_path" | awk '{print $1}')

        if [[ -z "$expected_checksum" ]]; then
            echo "Checksum file is empty or invalid for package: $package_name"
            rm -rf "$work_dir"
            return 1
        fi

        if [[ "$expected_checksum" != "$actual_checksum" ]]; then
            echo "Checksum verification failed for package: $package_name"
            rm -rf "$work_dir"
            return 1
        fi

        echo "Checksum verified for package: $package_name"
    else
        echo "Checksum file not found for package: $package_name, continuing without verification."
        rm -f "$checksum_path"
    fi

    if ! unzip "$zip_path" -d "$extract_dir" >/dev/null; then
        echo "Unzip failed for package: $package_name"
        rm -rf "$work_dir"
        return 1
    fi

    package_directory="${package_name%.zip}"
    package_directory="${package_directory%%-*}"

    if [[ -d "$extract_dir/$package_directory" ]]; then
        source_dir="$extract_dir/$package_directory"
    else
        local child_count=0
        local child_path=""
        local candidate

        shopt -s nullglob
        for candidate in "$extract_dir"/*; do
            child_count=$((child_count+1))
            child_path="$candidate"
        done
        shopt -u nullglob

        if [[ $child_count -eq 1 && -d "$child_path" ]]; then
            source_dir="$child_path"
        else
            source_dir="$extract_dir"
        fi
    fi

    mkdir -p "$sync_to"
    if ! rsync -av "$source_dir/" "$sync_to/"; then
        echo "Sync failed for package: $package_name"
        rm -rf "$work_dir"
        return 1
    fi

    echo "Successfully downloaded, unzipped, and synced package: $package_name"

    rm -rf "$work_dir"
    return 0
}

upgrade_zip
