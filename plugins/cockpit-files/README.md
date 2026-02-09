# cockpit-files Plugin

This plugin downloads the official [cockpit-files](https://github.com/cockpit-project/cockpit-files) release instead of maintaining our own build.

## Quick Start

```bash
cd /data/dev/websoft9/plugins/cockpit-files
./download.sh
```

## Usage

Download and extract cockpit-files:

```bash
# Download default version (35)
./download.sh

# Download specific version
./download.sh 36
```

The script will:
1. Download the release from GitHub (with mirror fallback for China)
2. Extract the tar.xz archive
3. Copy the `dist` folder contents to `build/` directory
4. Clean up temporary files automatically

## Directory Structure

```
plugins/cockpit-files/
├── download.sh       # Download script
├── build/            # Extracted dist files (committed to git)
│   ├── manifest.json
│   ├── index.html
│   ├── index.js.gz
│   ├── index.css.gz
│   └── ...
└── README.md         # This file
```

## Integration

### Before Docker Build

Run the download script to populate the build directory:

```bash
# In project root or CI pipeline
cd plugins/cockpit-files
./download.sh
```

### Dockerfile Usage

The Dockerfile already uses the build directory:

```dockerfile
COPY plugins/cockpit-files/build /usr/share/cockpit/cockpit-files
```

### CI/CD Integration

Add to your build pipeline:

```yaml
- name: Download cockpit-files
  run: |
    cd plugins/cockpit-files
    ./download.sh 35
```

## Features

### 🚀 Multi-Mirror Support

The script automatically tries multiple sources:
1. `https://github.com` (Primary)
2. `https://ghproxy.com` (China mirror)
3. `https://gh.api.99988866.xyz` (Backup mirror)

Each mirror is attempted 3 times before moving to the next.

### 🛡️ Error Handling

- Connection timeout: 10 seconds
- Maximum download time: 120 seconds
- Automatic retry on failure
- Detailed error messages

### 🧹 Auto Cleanup

Temporary files are automatically cleaned up:
- On successful completion
- On error (via trap)

## Maintenance

### Update Version

To use a newer version of cockpit-files:

```bash
./download.sh 36  # Replace with desired version number
```

Check available versions at: https://github.com/cockpit-project/cockpit-files/releases

### Verify Build

```bash
# Check manifest
cat build/manifest.json

# Count files
find build -type f | wc -l

# Verify key files exist
ls -lh build/{manifest.json,index.html,index.js.gz}
```

## Troubleshooting

### Download Fails

If all mirrors fail:
1. Check network connectivity
2. Verify version exists: https://github.com/cockpit-project/cockpit-files/releases
3. Try with a specific version number

### Build Directory Empty

```bash
# Clean and retry
rm -rf build/*
./download.sh
```

### Permission Issues

Ensure script is executable:
```bash
chmod +x download.sh
```

## Development Notes

- The `build/` directory is committed to git (contains stable releases)
- Run `./download.sh` to update to a newer version
- Downloaded files are production-ready (pre-built dist files)
- No build tools or dependencies required
