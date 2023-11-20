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

# Define the artifact URL as a global variable
artifact_url="https://w9artifact.blob.core.windows.net/$channel/websoft9/plugin"

upgrade_zip() {

    # Create the full URL by appending the package name to the artifact URL
    local plugin_name=${package_name%%-*}
    local url="$artifact_url/$plugin_name/$package_name"

    # Initialize download attempts
    local attempts=0
    local max_attempts=2

    # Download the package using wget
    while [ $attempts -lt $max_attempts ]; do
        rm -f "/tmp/$package_name"
        wget --timeout=120 --no-clobber "$url" -O "/tmp/$package_name"
        # Check if the download was successful
        if [ $? -eq 0 ]; then
            break
        fi
        attempts=$((attempts+1))
        echo "Download attempt $attempts failed. Retrying in 5 seconds..."
        sleep 5
    done

    # If the download still failed after max attempts, report an error and exit
    if [ $attempts -eq $max_attempts ]; then
        echo "Download failed for package: $package_name after $max_attempts attempts."
        return 1
    fi

    # Unzip the downloaded package
    unzip "/tmp/$package_name" -d "/tmp"

    # Check if the unzip was successful
    if [ $? -ne 0 ]; then
        echo "Unzip failed for package: $package_name"
        return 1
    fi
    
    # Get the name of the package without the .zip extension for syncing
    local package_directory="${package_name%.zip}"
    package_directory="${package_directory%%-*}"

    if [ "$unzipped_folder" != "/tmp/$package_directory/" ]; then
        mv "$unzipped_folder" "/tmp/$package_directory"
    else
        echo "The unzipped folder has the same name as the target folder."
    fi

    # Sync the unzipped package to the desired location
    rsync -av "/tmp/$package_directory/" "$sync_to"

    # Check if the sync was successful
    if [ $? -ne 0 ]; then
        echo "Sync failed for package: $package_name"
        return 1
    fi

    echo "Successfully downloaded, unzipped, and synced package: $package_name"

    # Remove the downloaded .zip file and the unzipped directory
    rm -f "/tmp/$package_name"
    rm -rf "/tmp/$package_directory"

    return 0
}

upgrade_zip
