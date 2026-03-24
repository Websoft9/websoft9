# Story 5.4: Build & Deployment

**Epic**: Epic 5 - Store Plugin  
**Priority**: P0  
**Status**: Not Started

## User Story
As a developer, I want to build and deploy the store plugin to Cockpit, so that users can access it from the web interface.

## Acceptance Criteria
- [ ] `build.sh` script creates production build
- [ ] Build output copied to Cockpit container
- [ ] Plugin appears in Cockpit menu as "Store"
- [ ] `public/manifest.json` configured correctly
- [ ] No console errors in production build

## Technical Details

**Files**:
- `plugins/store/build.sh` - Build and deploy script
- `plugins/store/public/manifest.json` - Cockpit manifest
- `plugins/store/package.json` - Build scripts

**Build Process**:
```bash
npm run build
# Outputs to build/
# Copy to /usr/share/cockpit/store/
```

**Manifest Configuration**:
```json
{
  "version": "0.1.0",
  "dashboard": {
    "store": {
      "label": "Store",
      "path": "index.html",
      "order": 10
    }
  }
}
```

**Deployment**:
```bash
# Manual
cd plugins/store
npm run build
./build.sh

# Or via Makefile
make plugin store
```

## Testing
- Build succeeds without errors
- Access `http://localhost:9000/store`
- Plugin menu item visible
- Production build size < 2MB
- No 404 errors for assets
