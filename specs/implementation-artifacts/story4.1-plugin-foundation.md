# Story 4.1: Plugin Foundation & Build System

**Epic**: Epic 4 - Portainer SSO Integration  
**Priority**: P0  
**Status**: ✅ Completed

## User Story
As a developer, I want to establish the Portainer SSO plugin project structure and build pipeline, so that I can begin implementing single sign-on functionality.

## Prerequisites

**Required**:
- Node.js >= 16.x (tested with 18.x)
- Yarn >= 1.22.x or npm >= 8.x
- Docker installed and running
- Websoft9 cockpit container deployed and running
- Sudo/root access for container operations

**Development Environment**:
- Linux OS (tested on Ubuntu 20.04+, RHEL 8+)
- VS Code or similar editor (recommended)
- Chrome/Firefox with DevTools

**Container Context**:
- Plugin must be deployed INTO the cockpit container for testing
- Host-based testing is NOT supported (no Cockpit installed on host)
- All testing done via container deployment at `http://localhost:9000/portainer`

## Acceptance Criteria
- [x] Project contains basic React application structure (src/, public/, config/)
- [x] package.json configured with necessary dependencies (React, auth libraries, etc.)
- [x] Build script (build.sh) successfully compiles the plugin
- [x] Build artifacts can be deployed to Cockpit
- [x] Plugin displays correctly in Cockpit menu
- [x] Webpack externals configured for Cockpit SDK (`config-overrides.js`)

## Technical Details

**Files Involved**:
- `plugins/portainer/package.json` - NPM dependencies
- `plugins/portainer/build.sh` - Build and deployment script
- `plugins/portainer/config-overrides.js` - Webpack configuration for Cockpit integration
- `plugins/portainer/portainer.json` - Cockpit plugin manifest
- `plugins/portainer/public/` - Static assets (icons, manifest)
- `plugins/portainer/src/` - React source code

**Dependencies**:

**Core**:
- `react`: ^18.2.0 - UI framework
- `react-dom`: ^18.2.0 - DOM rendering
- `axios`: ^1.3.4 - HTTP client for Portainer API
- `cockpit`: external - Cockpit SDK (provided by runtime)

**UI Components**:
- `react-bootstrap`: ^2.7.4 - Bootstrap React components
- `bootstrap`: ^5.2.3 - CSS framework
- `classnames`: ^2.3.1 - CSS class utilities

**Authentication**:
- `jwt-decode`: 3.1.2 - JWT token parsing

**Build Tools**:
- `react-scripts`: 5.0.1 - Create React App build toolchain
- `react-app-rewired`: ^2.2.1 - Override CRA config without ejecting
- `customize-cra`: ^1.0.0 - Webpack configuration overrides

**Testing Libraries** (configured but no tests yet, see Story 4.7):
- `@testing-library/react`: ^13.4.0
- `@testing-library/jest-dom`: ^5.16.5
- `@testing-library/user-event`: ^13.5.0

**Unused Dependencies** (consider removing in future):
- `react-router-dom`: ^6.14.0 - Not currently used (no routing needed)
- `web-vitals`: ^2.1.4 - Performance metrics (optional)

**Build Process**:
```bash
# Development (local testing requires Cockpit environment)
yarn start

# Production build
yarn build

# Deploy to container (via build.sh)
sudo bash build.sh

# Or manually deploy to container:
sudo docker exec -it websoft9-cockpit bash -c \
  "rm -rf /usr/share/cockpit/portainer/* && \
   cp -r /path/to/build/* /usr/share/cockpit/portainer/"
```

**⚠️ Build Script Note**: 
`build.sh` uses absolute path `/data/plugin-cockpit/plugin-portainer/`. 
Update this to match your environment or use container deployment commands above.

## Implementation Notes

### Cockpit Integration
- Uses `customize-cra` to externalize Cockpit SDK
- Webpack configured to treat `cockpit` as external module
- Plugin metadata in `portainer.json` includes version, author, requirements

### Project Structure
```
plugins/portainer/
├── package.json          # Dependencies and scripts
├── build.sh              # Build and deployment automation
├── config-overrides.js   # Webpack customization
├── portainer.json        # Cockpit plugin manifest
├── public/               # Static assets
│   └── manifest.json
├── src/
│   ├── App.js           # Main SSO logic
│   ├── App.css          # Styling
│   └── index.js         # Entry point
└── build/               # Generated artifacts (gitignored)
```

### Current Status
✅ **Completed** - Basic project structure is in place and functional. The plugin successfully builds and deploys to Cockpit.

## Testing

### Build and Deploy to Container
```bash
cd plugins/portainer

# 1. Install dependencies
yarn install

# 2. Build production bundle
yarn build

# 3. Verify build output
ls -la build/
# Expected files: index.html, static/, manifest.json, etc.

# 4. Deploy to cockpit container
# Option A: Using Docker exec
sudo docker exec -it websoft9-cockpit bash -c \
  "rm -rf /usr/share/cockpit/portainer/*"

sudo docker cp ./build/. websoft9-cockpit:/usr/share/cockpit/portainer/

# Option B: Using build.sh (if path is configured)
sudo bash build.sh

# 5. Restart cockpit service in container (if needed)
sudo docker exec -it websoft9-cockpit systemctl restart cockpit

# 6. Verify deployment
sudo docker exec -it websoft9-cockpit ls -la /usr/share/cockpit/portainer/
# Should see: index.html, static/, portainer.json, etc.
```

### Access and Test
```bash
# 1. Access Cockpit in browser
# URL: http://localhost:9000 (or your cockpit port)

# 2. Login to Cockpit
# Default: websoft9/websoft9

# 3. Click "Portainer" in left menu
# Expected: Plugin loads, shows loading spinner, then Portainer iframe

# 4. Check browser console for errors
# F12 > Console tab
# Should see no critical errors

# 5. Verify SSO authentication
# Should automatically authenticate to Portainer (no login prompt)
```

### Development Workflow
```bash
# For iterative development:

# 1. Make code changes
vim src/App.js

# 2. Rebuild
yarn build

# 3. Redeploy to container
sudo docker cp ./build/. websoft9-cockpit:/usr/share/cockpit/portainer/

# 4. Hard refresh browser (Ctrl+Shift+R)
# Test changes

# 5. Check logs if issues
sudo docker logs websoft9-cockpit
```

## Troubleshooting

### Build Issues

**Problem**: `yarn build` fails with module resolution errors
```
Module not found: Error: Can't resolve 'cockpit'
```
**Solution**: 
1. Verify `config-overrides.js` exists and contains:
   ```javascript
   addWebpackExternals({ "cockpit": "cockpit" })
   ```
2. Clear node_modules and reinstall:
   ```bash
   rm -rf node_modules yarn.lock
   yarn install
   ```

**Problem**: Build succeeds but output is empty or corrupted
**Solution**:
1. Check `build/` directory: `ls -la build/`
2. Verify `index.html` exists and is not empty
3. Check for disk space: `df -h`

### Deployment Issues

**Problem**: Plugin not appearing in Cockpit menu after deployment
**Checks**:
1. Verify files copied to container:
   ```bash
   sudo docker exec websoft9-cockpit ls -la /usr/share/cockpit/portainer/
   ```
2. Verify `portainer.json` exists and is valid JSON
3. Restart cockpit service:
   ```bash
   sudo docker exec websoft9-cockpit systemctl restart cockpit
   ```
4. Clear browser cache (Ctrl+Shift+Del)
5. Check container logs:
   ```bash
   sudo docker logs websoft9-cockpit --tail 50
   ```

**Problem**: Docker cp command fails with permission denied
**Solution**:
1. Use `sudo` for all Docker commands
2. Or add user to docker group:
   ```bash
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

**Problem**: Container not running
**Check and Start**:
```bash
# Check container status
docker ps -a | grep cockpit

# Start if stopped
sudo docker start websoft9-cockpit

# Check health
sudo docker inspect websoft9-cockpit | grep Health -A 5
```

### Runtime Issues

**Problem**: Plugin loads but shows blank page
**Debug**:
1. Open browser DevTools (F12) > Console
2. Look for JavaScript errors
3. Check Network tab for failed requests
4. Verify Cockpit SDK loaded: Type `cockpit` in console (should show object)

**Problem**: Plugin shows 404 or Cockpit branding only
**Solution**:
1. Verify files deployed correctly
2. Check `homepage` in package.json is set to `"."`
3. Rebuild with correct configuration

### Version Inconsistencies

**Note**: Two version numbers exist:
- `package.json` version: `0.1.0` (NPM package version)
- `portainer.json` Version: `0.1.4-rc2` (Cockpit plugin version)

**Management**: 
- Update `portainer.json` Version for releases
- `package.json` version is for internal tracking
- Keep them in sync or document the difference

## Notes
- Build script (`build.sh`) uses absolute path `/data/plugin-cockpit/plugin-portainer/`
- Update path to match your environment or use Docker cp commands
- Plugin manifest version: 0.1.4-rc2
- All testing requires container deployment (host-based testing not supported)
- Development mode (`yarn start`) requires Cockpit environment to test integration
