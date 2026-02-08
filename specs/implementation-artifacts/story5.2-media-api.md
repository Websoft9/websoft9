# Story 5.2: Media API Integration

**Epic**: Epic 5 - Store Plugin  
**Priority**: P0  
**Status**: ready-for-dev

## User Story
As a developer, I want to load media data from nginx-served static JSON files, so that the store displays real application information with complete apphub decoupling and optimal performance.

## Acceptance Criteria

**Infrastructure** (Prerequisites):
- [ ] Nginx `/media/` location configured for static file serving
- [ ] Media volume mounted to nginx container (read-only)
- [ ] Static JSON files accessible via HTTP

**Plugin Implementation**:
- [ ] Static file loader functions in `src/utils/api.js`
- [ ] Fetch catalog data from `/media/catalog_{locale}.json`
- [ ] Fetch product data from `/media/product_{locale}.json`
- [ ] Handle network errors with retry logic (3 attempts, exponential backoff)
- [ ] Loading spinner displayed during JSON fetch
- [ ] User-friendly error messages on failure
- [ ] Locale detection works (Cockpit language → browser language → default 'en')
- [ ] Replace mock data in App.js with static JSON loading

**Decoupling Verification**:
- [ ] Store plugin works when apphub container is stopped
- [ ] No API calls to `/api/apps/*` endpoints

## Definition of Done

**Infrastructure**:
- [ ] Nginx configuration deployed and verified
- [ ] Media volume mounted to nginx (verified with `docker exec`)
- [ ] Static files accessible via HTTP (curl test passed)

**Code Quality**:
- [ ] Code review passed (error handling, retry logic verified)
- [ ] All acceptance criteria met
- [ ] Static JSON loading works in both dev and container environments
- [ ] No mock data remaining in App.js
- [ ] Loading spinner displays during initial fetch
- [ ] Error boundary catches network failures gracefully
- [ ] Console logging only in development mode

**Decoupling Validation** (Critical):
- [ ] Store plugin works when apphub container is stopped
- [ ] No network requests to `/api/apps/*` endpoints
- [ ] Only requests to `/media/*.json` and `/media/logos/*`

**Performance**:
- [ ] 300+ apps load in < 2 seconds (initial load)
- [ ] Subsequent loads use browser cache (< 100ms)

**Backward Compatibility**:
- [ ] Existing appstore plugin still works (if it uses old API)
- [ ] Rollback plan tested and documented

---

## Developer Context

### ⚠️ Prerequisites Check

**Environment**:
- [ ] Story 5.1 completed (UI components ready)
- [ ] Nginx proxy container running
- [ ] Cockpit language detection available (optional)

**Media Data Availability**:
- [ ] Media files exist: `/websoft9/media/catalog_en.json`
- [ ] Media files exist: `/websoft9/media/product_en.json`
- [ ] Media files exist: `/websoft9/media/logos/*.png`
- [ ] Nginx can access `/websoft9/media/` directory

### 🚨 BLOCKER Prerequisites

**⚠️ CRITICAL**: This story CANNOT start until infrastructure changes are deployed.

**Required Infrastructure Changes** (requires DevOps/admin access):

1. **Nginx Configuration Update**:
   - File: `docker/proxy/config/initproxy.conf`
   - Change: `/media/` location from proxy to static serving
   - Authority: Requires container restart

2. **Docker Compose Update**:
   - File: `docker/docker-compose.yml`
   - Change: Mount `apphub_media` volume to nginx container
   - Authority: Requires service restart

3. **Verification Command**:
   ```bash
   curl http://localhost:9000/media/catalog_en.json
   # Must return JSON (not proxy to apphub)
   # Must NOT include header: X-Powered-By: FastAPI
   ```

**Action Required**: 
- Coordinate with DevOps team BEFORE starting implementation
- Or complete infrastructure changes yourself if you have access
- Verify all 3 checks pass before writing any plugin code

### 🎯 Architecture Decision: Nginx Static Files (Not Apphub API)

**Decision**: Serve media data (JSON + images) directly via Nginx static files, NOT through apphub API.

**Rationale**:
1. ✅ **Complete Decoupling** - Store plugin has ZERO dependency on apphub
2. ✅ **Performance** - Nginx serves static files faster than FastAPI processing
3. ✅ **Simplicity** - No API layer, no business logic, just file serving
4. ✅ **Caching** - Nginx's static file caching is more efficient
5. ✅ **Consistency** - Images already served via nginx, JSON uses same path
6. ✅ **Scalability** - Easy to move to CDN/object storage later

**Architecture Flow**:
```
Store Plugin (Browser)
  ↓ HTTP GET /media/catalog_en.json
Nginx Proxy (Port 9000)
  ↓ Static file serving
Media Volume (apphub_media)
  ↓ Direct file access
/websoft9/media/
  ├── catalog_en.json
  ├── catalog_zh.json
  ├── product_en.json
  ├── product_zh.json
  ├── logos/*.png
  └── screenshots/
```

**Why NOT Apphub API?**
- ❌ Unnecessary coupling to apphub business logic
- ❌ Extra latency through FastAPI layer
- ❌ API key requirements (if added later)
- ❌ Cache invalidation complexity

### 📋 Media Static Files (Nginx Served)

**Location**: Media volume mounted to nginx → `/websoft9/media/`

**Current Nginx Config** (in `docker/proxy/config/initproxy.conf`):
```nginx
location /media/ {
    # TODO: Change this to direct static file serving
    # Current: proxy_pass http://websoft9-apphub:8081/images/;
    # Proposed: Direct nginx static serving (see implementation below)
}
```

**1. Catalog Data** (Categories and grouping)
```
GET /media/catalog_en.json
GET /media/catalog_zh.json

Response: JSON array
[
  {
    "key": "repository",
    "title": "Code Repository",
    "catalogCollection": {
      "items": [
        {
          "key": "itdeveloper",
          "title": "IT Developer"
        }
      ]
    }
  }
]
```

**2. Product Data** (Full app details with media URLs)
```
GET /media/product_en.json
GET /media/product_zh.json

Response: JSON array
[
  {
    "key": "wordpress",
    "trademark": "WordPress",
    "logo": {
      "imageurl": "/media/logos/wordpress.png"
    },
    "overview": "Short description",
    "description": "Markdown description",
    "catalogCollection": {
      "items": [
        {
          "key": "cms",
          "title": "CMS",
          "catalogCollection": {
            "items": [{"key": "category", "title": "Category"}]
          }
        }
      ]
    },
    "screenshots": [
      {
        "id": 1,
        "key": "screenshot1",
        "value": "/media/screenshots/en/wordpress.png"
      }
    ],
    "websiteurl": "https://wordpress.org",
    "distribution": [...],  // Version info
    "settings": {},         // App-specific settings
    "is_web_app": true,
    "vcpu": "1",
    "memory": "1",
    "storage": "10"
  }
]
```

**3. Static Media Files** (Images served via Nginx)
```
GET /media/logos/{filename}
GET /media/screenshots/{locale}/{filename}

Example:
  /media/logos/wordpress.png
  /media/screenshots/en/wordpress.png
```

### 🔧 Implementation Plan

**Phase 1: API Utility Setup**

Create `src/utils/api.js`:
```javascript
// Base configuration - Media served directly by nginx
const MEDIA_BASE = process.env.REACT_APP_MEDIA_URL || '/media';

// Detect locale (from Cockpit or default to 'en')
const getLocale = () => {
  // Try Cockpit language first
  if (window.cockpit && window.cockpit.language) {
    return window.cockpit.language.startsWith('zh') ? 'zh' : 'en';
  }
  // Fallback to browser language
  const browserLang = navigator.language || navigator.userLanguage;
  return browserLang.startsWith('zh') ? 'zh' : 'en';
};

// Fetch with retry logic
const fetchWithRetry = async (url, options = {}, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      if (i === retries - 1) throw error;
      // Wait before retry (exponential backoff)
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)));
    }
  }
};

// Fetch catalog data (static JSON)
export const fetchCatalog = async () => {
  const locale = getLocale();
  return fetchWithRetry(`${MEDIA_BASE}/catalog_${locale}.json`);
};

// Fetch product data (static JSON)
export const fetchProducts = async () => {
  const locale = getLocale();
  return fetchWithRetry(`${MEDIA_BASE}/product_${locale}.json`);
};

// Helper: Get full media URL for images
export const getMediaUrl = (relativePath) => {
  // relativePath format: "/media/logos/wordpress.png" or "logos/wordpress.png"
  if (relativePath.startsWith('/media/')) {
    return relativePath; // Already full path
  }
  if (relativePath.startsWith('/')) {
    return `${MEDIA_BASE}${relativePath}`;
  }
  return `${MEDIA_BASE}/${relativePath}`;
};
```

**Phase 2: Update App.js**

Replace mock data with static file loading:
```javascript
import { fetchCatalog, fetchProducts, getMediaUrl } from './utils/api';

function App() {
  const [mediaData, setMediaData] = useState([]);
  const [categories, setCategories] = useState(['all']);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadMediaData();
  }, []);

  const loadMediaData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch catalog and products in parallel (both static JSON)
      const [catalogData, productsData] = await Promise.all([
        fetchCatalog(),
        fetchProducts()
      ]);
      
      // Extract unique categories from catalog data
      const uniqueCategories = new Set(['all']);
      catalogData.forEach(catalog => {
        uniqueCategories.add(catalog.title || catalog.key);
        // Add sub-categories if available
        if (catalog.catalogCollection?.items) {
          catalog.catalogCollection.items.forEach(subCat => {
            uniqueCategories.add(subCat.title || subCat.key);
          });
        }
      });
      
      setCategories(Array.from(uniqueCategories));
      setMediaData(productsData);
      setLoading(false);
    } catch (err) {
      console.error('Failed to load media data:', err);
      setError(err.message || 'Failed to load applications');
      setLoading(false);
    }
  };
  
  // ... rest of component
}
```

**Phase 3: Update MediaCard Component**

Use `getMediaUrl` for images:
```javascript
import { getMediaUrl } from '../utils/api';

const MediaCard = ({ item }) => {
  const logoUrl = item.logo?.imageurl 
    ? getMediaUrl(item.logo.imageurl) 
    : '/placeholder.png';
    
  return (
    <Card>
      <CardMedia
        component="img"
        image={logoUrl}
        alt={item.trademark}
        onError={(e) => { e.target.src = '/placeholder.png'; }}
      />
      {/* ... */}
    </Card>
  );
};
```

### 📝 Files to Create/Modify

**New Files**:
- `src/utils/api.js` - Media data loading utilities (NEW)

**Files to Modify (Store Plugin)**:
- `src/App.js` - Replace mock data with static JSON loading
- `src/components/MediaCard.js` - Use getMediaUrl() for image paths
- `.env` (optional) - Add MEDIA_BASE override for dev testing

**Files to Modify (Infrastructure)** - ⚠️ Required for architecture change:
- `docker/proxy/config/initproxy.conf` - Update nginx /media/ location
- `docker/docker-compose.yml` - Mount media volume to nginx container

**Infrastructure Changes Required**:
```nginx
# In docker/proxy/config/initproxy.conf
# Change from:
location /media/ {
    proxy_pass http://websoft9-apphub:8081/images/;
}

# Change to:
location /media/ {
    alias /websoft9/media/;
    autoindex off;
    expires 1h;
    add_header Cache-Control "public, immutable";
    
    # Enable CORS for JSON files
    location ~ \.(json)$ {
        add_header Access-Control-Allow-Origin *;
        add_header Content-Type application/json;
    }
}
```

```yaml
# In docker/docker-compose.yml
# Add volume mount to proxy service:
proxy:
  volumes:
    - nginx_data:/data
    - apphub_media:/websoft9/media:ro  # Add this line (read-only)
```

**Reference Files**:
- `apphub/src/services/app_manager.py` - Current file reading logic (can be removed later)
- `docker/proxy/config/initproxy.conf` - Nginx configuration

### ⚠️ Error Handling Strategy

**Network Errors**:
```javascript
try {
  const [catalogData, productsData] = await Promise.all([
    fetchCatalog(),
    fetchProducts()
  ]);
} catch (error) {
  if (error.message.includes('Failed to fetch')) {
    // Network offline or CORS issue
    setError('Cannot connect to server. Check network connection.');
  } else if (error.message.includes('HTTP 404')) {
    // Static files not found (nginx misconfigured or media missing)
    setError('Media data not available. Contact administrator.');
  } else if (error.message.includes('HTTP 500')) {
    // Nginx server error
    setError('Server error. Please try again later.');
  } else {
    // Generic error (could be JSON parse error)
    setError('Failed to load applications. Invalid data format.');
  }
}
```

**Retry Logic**:
- 3 attempts with exponential backoff (1s, 2s, 4s)
- Only retry on network errors, not on 404/403
- Show retry count to user (optional)

**Graceful Degradation**:
```javascript
// Option 1: Show cached data (if available)
const cachedData = localStorage.getItem('media_cache');
if (cachedData && error) {
  setMediaData(JSON.parse(cachedData));
  setError('Using cached data. ' + error);
}

// Option 2: Show empty state
if (error && mediaData.length === 0) {
  return <EmptyState message={error} />;
}
```

### 🔙 Rollback Plan

**If nginx static serving fails after deployment:**

**Symptoms**:
- Store plugin shows "Media data not available"
- 404 errors in browser console for `/media/*.json`
- `curl http://localhost:9000/media/catalog_en.json` returns 404 or 502

**Quick Rollback** (5-10 minutes):

```bash
# Step 1: Revert nginx config to proxy mode
cd /data/dev/websoft9/docker/proxy/config
git checkout HEAD -- initproxy.conf
# Or manually edit:
# location /media/ {
#     proxy_pass http://websoft9-apphub:8081/images/;
# }

# Step 2: Revert docker-compose volume mount
cd /data/dev/websoft9/docker
git checkout HEAD -- docker-compose.yml
# Or manually remove line: apphub_media:/websoft9/media:ro

# Step 3: Restart nginx container
docker restart websoft9-proxy

# Step 4: Verify old behavior restored
curl -I http://localhost:9000/media/logos/wordpress.png
# Should return: X-Powered-By: ... (proxied through apphub)
```

**Validation After Rollback**:
- [ ] Existing appstore plugin works normally
- [ ] Images load via apphub proxy
- [ ] Store plugin shows error (expected - not yet adapted)

**Root Cause Analysis Required**:
- Check nginx error logs: `docker logs websoft9-proxy 2>&1 | grep media`
- Check volume mount: `docker exec websoft9-proxy ls -la /websoft9/media`
- Check file permissions: `docker exec websoft9-proxy cat /websoft9/media/catalog_en.json`

**Re-deployment Prerequisites**:
- Fix identified issue
- Test in development environment first
- Have rollback plan ready again

### 🧪 Testing Requirements

**Infrastructure Setup** (One-time):
```bash
# 1. Update nginx config and restart
cd /data/dev/websoft9/docker
# Edit proxy/config/initproxy.conf (see Files to Modify section)
# Edit docker-compose.yml (add media volume mount)

# 2. Restart proxy container
docker restart websoft9-proxy

# 3. Verify media files accessible
curl http://localhost:9000/media/catalog_en.json
curl http://localhost:9000/media/product_en.json
curl http://localhost:9000/media/logos/  # Should return 404 or index
```

**Development Testing**:
```bash
# 1. Verify static files served by nginx
curl -I http://localhost:9000/media/catalog_en.json
# Should return: Content-Type: application/json
# Should return: Cache-Control: public, immutable

# 2. Start store plugin (with proxy to nginx)
cd plugins/store

# Option A: Add proxy in package.json
echo '"proxy": "http://localhost:9000"' >> package.json
npm start

# Option B: Use .env file
echo 'REACT_APP_MEDIA_URL=http://localhost:9000/media' > .env
npm start

# 3. Verify in browser
# - Open http://localhost:3000
# - Check Network tab - requests go to /media/
# - Verify images load from /media/logos/
# - Check response headers (should have Cache-Control)
```

**Container Testing** (After deployment):
```bash
# Deploy to container
npm run build
sudo bash build.sh

# Access via Cockpit
# http://localhost:9000/store

# Verify:
# - API calls go through Nginx proxy
# - No CORS errors
# - Images load correctly
```

**Test Scenarios**:
- [ ] Load with good network (200ms latency)
- [ ] Load with slow network (2s latency)
- [ ] Load with offline network (should show error)
- [ ] Load with 500 apps (performance test)
- [ ] Refresh page (should use cache if available)
- [ ] Switch language (should refetch data)

### 🚨 Known Issues to Avoid

**1. Nginx Configuration Not Updated**:
- Problem: `/media/` still proxies to apphub instead of serving static files
- Solution: Must update `initproxy.conf` and mount media volume to nginx
- Verify: `curl -I http://localhost:9000/media/catalog_en.json` should NOT include `X-Powered-By: FastAPI`

**2. Volume Mount Missing**:
- Problem: Nginx can't access media files (404 errors)
- Solution: Add `apphub_media:/websoft9/media:ro` to nginx volumes in docker-compose.yml
- Verify: `docker exec websoft9-proxy ls /websoft9/media` should list files

**3. CORS in Development**:
- Problem: `npm start` runs on localhost:3000, nginx on localhost:9000
- Solution: Add `"proxy": "http://localhost:9000"` to package.json or use .env

**4. Image Paths**:
- Problem: Product JSON has paths like `/media/logos/wordpress.png`
- Solution: getMediaUrl() handles both absolute and relative paths

**5. Locale Mismatch**:
- Problem: Cockpit uses `zh_CN`, files are named `catalog_zh.json`
- Solution: Normalize to `zh` or `en` in getLocale() function

**6. Cache Invalidation**:
- Problem: Nginx caches JSON for 1 hour, updates not visible
- Solution: Development: disable cache. Production: version query param `?v=timestamp`

### 📚 Key References

**Nginx Configuration**:
- [docker/proxy/config/initproxy.conf](../../../docker/proxy/config/initproxy.conf#L155) - Current /media/ proxy config
- [docker/docker-compose.yml](../../../docker/docker-compose.yml) - Volume mounts

**Media Data Source**:
- `/websoft9/media/catalog_*.json` - Category data (generated by apphub CLI)
- `/websoft9/media/product_*.json` - Product data (generated by apphub CLI)
- `/websoft9/media/logos/` - Application logos
- `/websoft9/media/screenshots/` - Application screenshots

**Similar Pattern** (for reference only, NOT to use):
- [apphub/src/media.py](../../../apphub/src/media.py) - Old Starlette static mount (can be deprecated)
- [plugins/appstore/src/helpers/api/appHub.js](../../../plugins/appstore/src/helpers/api/appHub.js) - Old API pattern

**Architecture**:
- [Architecture Document](../planning-artifacts/architecture.md) - System architecture
- [Story 5.1](story5.1-core-ui.md) - UI components foundation

---

## Completion Checklist

Before marking this story as done:

**Infrastructure** (Must be deployed first):
- [ ] Nginx `/media/` location updated to serve static files (not proxy to apphub)
- [ ] Media volume mounted to nginx container: `apphub_media:/websoft9/media:ro`
- [ ] Verified: `docker exec websoft9-proxy ls /websoft9/media` lists files
- [ ] Static JSON accessible: `curl http://localhost:9000/media/catalog_en.json` returns JSON
- [ ] Response header check: NO `X-Powered-By: FastAPI` (confirms not proxied)
- [ ] CORS headers added for JSON files
- [ ] Cache headers configured: `Cache-Control: public, immutable, max-age=3600`

**Plugin Code**:
- [ ] `src/utils/api.js` implemented with fetchCatalog() and fetchProducts()
- [ ] `App.js` uses static JSON loading (no mock data)
- [ ] Locale detection works: Cockpit → browser → default 'en'
- [ ] Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)
- [ ] Error messages user-friendly and actionable
- [ ] Loading spinner displays during initial fetch
- [ ] Images load from `/media/logos/` paths correctly
- [ ] getMediaUrl() helper handles all path formats

**Decoupling Validation** (Critical - Primary Goal):
- [ ] Stop apphub: `docker stop websoft9-apphub`
- [ ] Store plugin still loads and displays apps
- [ ] Browser Network tab: ZERO requests to `/api/apps/*`
- [ ] Browser Network tab: ONLY requests to `/media/*.json` and `/media/logos/*`
- [ ] Restart apphub: `docker start websoft9-apphub` (cleanup)

**Performance Benchmarks**:
- [ ] Initial load with 300 apps: < 2 seconds (Network tab timeline)
- [ ] Subsequent loads with cache: < 100ms
- [ ] JSON file size: catalog < 100KB, product < 2MB
- [ ] No memory leaks after multiple navigations

**Testing Environments**:
- [ ] Dev mode (`npm start` with proxy): Works
- [ ] Container mode (`http://localhost:9000/store`): Works
- [ ] No console errors in production build
- [ ] Tested on Chrome and Firefox

**Backward Compatibility**:
- [ ] Existing appstore plugin still works (verify manually)
- [ ] Old nginx proxy config in git history (can rollback)

**Documentation & Handoff**:
- [ ] Nginx config changes committed to git
- [ ] Rollback plan tested and documented
- [ ] Known issues documented in this story
- [ ] Ready for Story 5.3 (category filtering with real data)

---

**Status**: ready-for-dev  
**Architecture Decision**: ✅ Nginx static files (complete apphub decoupling)
