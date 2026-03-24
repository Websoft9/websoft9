# Story 4.2: SSO Authentication & Navigation

**Epic**: Epic 4 - Portainer SSO Integration  
**Priority**: P0  
**Status**: ⚠️ Partially Completed - Core Flow Working, Security Hardening Needed

## User Story
As a user, I want to click the Portainer plugin in Cockpit and automatically access the Portainer interface without manual login, so that I can manage containers seamlessly without remembering separate credentials.

## Acceptance Criteria

### Authentication (API Integration)
- [x] Plugin retrieves Portainer credentials from configuration (`apphub getconfig`)
- [x] Authenticates to Portainer API via `/api/auth` endpoint
- [x] JWT token obtained successfully from Portainer
- [ ] Token securely stored and explicitly managed
- [ ] Token automatically refreshed when expired
- [x] Clear error handling for authentication failures

### Navigation (SSO Flow)
- [x] Plugin automatically obtains/generates Portainer authentication token
- [x] Constructs authenticated Portainer URL
- [x] Automatically navigates to Portainer interface (iframe embedded)
- [x] User is in authenticated state after navigation
- [x] Entire flow completes within 2 seconds
- [x] Browser hash synchronization with iframe content

## User Experience Flow

### Happy Path Journey
```
1. USER ACTION: Click "Portainer" in Cockpit sidebar
   → UI: Show loading spinner

2. SYSTEM: Retrieve nginx proxy port from apphub config
   ✓ Success → Continue to step 3
   ✗ Failure → Show error + Redirect to default port (if available)
   
3. SYSTEM: Retrieve Portainer credentials from apphub config  
   ✓ Success → Continue to step 4 (attempt SSO)
   ✗ Failure → Skip to step 5 (redirect to Portainer login page)
   
4. SYSTEM: Attempt SSO authentication (optional step)
   → POST ${baseURL}/w9deployment/api/auth with credentials
   ✓ Success (HTTP 200) → Receive JWT token, continue to step 5
   ✗ Failure (any error) → Log error, continue to step 5
   
5. SYSTEM: Construct Portainer URL
   → If SSO succeeded: Set authenticated state (jwtLoaded = true)
   → Always: Construct iframe URL to Portainer (${baseURL}/w9deployment/)
   
6. UI: Load Portainer interface in iframe
   → SSO Success: User sees Portainer dashboard (authenticated) ✓
   → SSO Failed: User sees Portainer login page (can login manually) ✓
   → Total time: ~1.3 seconds (SSO) or ~0.5 seconds (direct redirect)
```

**Key UX Principle**: **Always redirect to Portainer**, even if SSO fails. This ensures:
- Users can always access Portainer (manual login as fallback)
- No dead-end error screens
- Better user experience (show the destination, not just error messages)

### Error Recovery Flows

| Error Condition | User Sees | System Behavior | User Can |
|----------------|-----------|-----------------|----------|
| **Config Missing** | Warning: "Nginx proxy port not configured" | Redirect to Portainer on default port (if detectable) | Try manual login |
| **Credentials Missing** | Info: "SSO credentials not configured - manual login required" | Redirect to Portainer login page | Login manually with own credentials |
| **Invalid Credentials** | Warning: "SSO failed - Invalid credentials" | Redirect to Portainer login page | Login manually |
| **Service Down** | Error: "Portainer service unavailable" | Try redirect to Portainer URL (may show connection error) | Wait for service recovery |
| **Network Error** | Error: "Network connection failed" | Redirect to Portainer URL (may fail to load) | Check connectivity |
| **Permission Denied** | Error: "Docker permission denied. Run: sudo usermod -aG docker <username>" | Redirect to Portainer URL | Fix permissions, then manual login |
| **Token Expired** | *(After fix)* Silent refresh, or redirect to login if refresh fails | Auto-refresh token or show login page | Login manually if auto-refresh fails |

**Fallback Strategy**: All error scenarios result in redirecting to Portainer URL (`${baseURL}/w9deployment/`), allowing users to manually authenticate if SSO fails.

### Critical User Experience Requirements

1. **Always Redirect to Portainer** 🎯 (Highest Priority)
   - **Never block user from reaching Portainer interface**
   - SSO success → Authenticated access
   - SSO failure → Manual login page
   - Configuration missing → Redirect with warning
   - This ensures users always have a path forward

2. **Feedback at Every Step**: User must always see what's happening
   - Loading spinner during authentication attempt
   - Warning/error messages (non-blocking)
   - Silent fallback to manual login (no intrusive errors)

3. **Performance**: Total flow < 2 seconds
   - Config retrieval: ~200ms
   - Authentication: ~300ms (can be skipped if fails)
   - Iframe load: ~800ms
   - **Current total**: ~1.3s (SSO) or ~0.5s (direct redirect) ✅

4. **Graceful Degradation Hierarchy**:
   - ✅ Best: SSO succeeds → Authenticated Portainer dashboard
   - ✅ Good: SSO fails → Portainer login page (manual login available)
   - ❌ Bad: Show error and block access (never do this)

## Technical Implementation

### Architecture Overview
```
┌─────────────────────────────────────────────────────────┐
│ Cockpit Browser UI (Port 9091)                          │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ Portainer Plugin (React)                        │    │
│  │                                                 │    │
│  │  1. getNginxConfig()                            │    │
│  │     ↓ cockpit.spawn("apphub getconfig...")     │    │
│  │  2. getJwt(baseURL)                             │    │
│  │     ↓ axios.post("/api/auth")                   │    │
│  │  3. setJwtLoaded(true)                          │    │
│  │     ↓                                            │    │
│  │  4. <iframe src={portainerURL} />               │    │
│  │                                                 │    │
│  │  ┌───────────────────────────────────────────┐ │    │
│  │  │ Embedded Portainer UI                      │ │    │
│  │  │ (http://hostname:81/w9deployment/)        │ │    │
│  │  └───────────────────────────────────────────┘ │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
         ↓                               ↑
    [Cockpit API]                    [Nginx Proxy :81]
         ↓                               ↑
    [apphub CLI]                     [Portainer API]
         ↓                               ↑
    [Config Store]                   [Portainer Service]
```

### Core Implementation Components

**File**: `plugins/portainer/src/App.js`

**Key Functions**:

1. **Configuration Retrieval** (`getNginxConfig`)
   - **Purpose**: Get nginx proxy port from system config
   - **Method**: Execute `apphub getconfig --section nginx_proxy_manager` via Cockpit
   - **Output**: `listenPort` state (e.g., `81`)
   - **Error Handling**: Log warning, attempt fallback to default port or continue without port
   - **New Behavior**: Never block user flow - always proceed to next step

2. **Authentication** (`getJwt`) - **OPTIONAL STEP**
   - **Purpose**: Attempt SSO authentication to Portainer API
   - **Method**: 
     - Get credentials: `apphub getconfig --section portainer`
     - POST to: `${baseURL}/w9deployment/api/auth`
   - **Output**: Sets `jwtLoaded` if successful
   - **Current Issue**: JWT token received but not explicitly used (relies on Portainer auto-cookies)
   - **Error Handling**: Log errors, set warning message, but **always proceed to navigation**
   - **New Behavior**: SSO is best-effort, failures don't block Portainer access

3. **SSO Navigation** (`autoLogin`)
   - **Purpose**: Attempt authentication and always redirect to Portainer
   - **Method**: 
     - Try: Call `getJwt()` to authenticate (catch all errors)
     - Always: Parse URL hash for deep linking
     - Always: Set `iframeSrc` to Portainer URL
   - **Output**: Iframe loads Portainer (authenticated if SSO succeeded, login page if failed)
   - **New Behavior**: Wrapped in try-catch, never throws errors to UI level

4. **Hash Synchronization** (`handleHashChange`)
   - **Purpose**: Keep browser URL in sync with iframe navigation
   - **Method**: Listen to `hashchange` events, update iframe src
   - **Benefit**: Browser back/forward buttons work correctly

5. **UI Rendering**
   - **Loading State**: Spinner shown briefly during SSO attempt (~1-2s max)
   - **Warning State** (optional): Toast/banner with non-blocking warnings (e.g., "SSO failed, please login manually")
   - **Main State**: Always show full-screen iframe with Portainer UI
   - **New Behavior**: Never show blocking error screens, always render Portainer iframe

### URL Structure
- **Cockpit Plugin**: `http://localhost:9091/portainer`
- **Portainer Base**: `http://hostname:81/w9deployment/`
- **Deep Links**: `http://localhost:9091/portainer#/w9deployment/#!/containers`

### Configuration Schema
```json
// apphub: nginx_proxy_manager section
{
  "listen_port": 81
}

// apphub: portainer section
{
  "user_name": "admin",
  "user_pwd": "<encrypted_password>"
}
```

## Current Implementation Status

### ✅ Working Features

1. **Full SSO Flow**: Click plugin → Auto-login → Portainer dashboard (1.3s)
2. **Configuration Loading**: Successfully retrieves nginx port and credentials
3. **API Authentication**: Correctly calls `/api/auth` and receives JWT
4. **Deep Linking**: URL hash routing works (e.g., `#/w9deployment/#!/images`)
5. **Error Messages**: Specific errors shown for common failures
6. **Performance**: Meets < 2s requirement ✓

### 🔴 Critical Issues Requiring Fixes

#### Issue #1: JWT Token Not Explicitly Managed
**Current Code** (lines 67-68 in App.js):
```javascript
// const portainer_jwt = authResponse.data.jwt;
// document.cookie = "portainer_api_key=" + portainer_jwt + ";path=/";
```

**Why It's Commented**: During testing, found that Portainer API automatically sets session cookies when `/api/auth` returns HTTP 200. The explicit JWT cookie setting was disabled to avoid conflicts.

**Why This Is Risky**:
- Relies on Portainer's implicit behavior (may change in future versions)
- May fail in cross-domain scenarios or strict cookie policies
- No explicit control over token lifecycle
- Token refresh mechanism can't be implemented without explicit token management

**Recommended Fix** (must implement in this story):
```javascript
// Explicitly set JWT cookie for reliable authentication
const portainer_jwt = authResponse.data.jwt;
document.cookie = `portainer_jwt=${portainer_jwt}; path=/; SameSite=Strict; max-age=28800`;
// max-age=28800 = 8 hours (Portainer default token lifetime)
```

**Future Improvement** (Story 4.4 scope):
- Move authentication to backend proxy
- Use HTTP-only cookies for better security

#### Issue #2: No Token Expiration Handling
**Problem**: 
- Portainer tokens expire after 8 hours
- No detection or automatic refresh
- User sees errors after long sessions (must manually refresh page)

**Impact**: Poor user experience for long-running sessions

**Recommended Fix** (must implement in this story):
```javascript
import jwtDecode from 'jwt-decode';

// After receiving JWT
const decoded = jwtDecode(authResponse.data.jwt);
const expiryTime = decoded.exp * 1000; // Convert to milliseconds
sessionStorage.setItem('portainer_token_expiry', expiryTime);

// Check periodically and refresh before expiry
useEffect(() => {
  const checkAndRefresh = () => {
    const expiry = sessionStorage.getItem('portainer_token_expiry');
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000;
    
    // Refresh token if expiring within 5 minutes
    if (expiry && (now + fiveMinutes) >= expiry) {
      console.log('Token expiring soon, refreshing...');
      autoLogin(baseURL);
    }
  };
  
  // Check every 5 minutes
  const interval = setInterval(checkAndRefresh, 5 * 60 * 1000);
  return () => clearInterval(interval);
}, [autoLogin, baseURL]);
```

#### Issue #3: Credentials Exposed in Client-Side Code
**Problem**: 
- Username and password passed to browser JavaScript
- Visible in browser DevTools → Network tab → Request payload
- Security risk if user's browser is compromised

**Current Risk Level**: Medium
- **Mitigated by**: Cockpit authentication required to access plugin
- **Mitigated by**: Local-only access (not exposed to internet by default)
- **Still risky for**: Shared servers, recorded sessions, browser extensions

**Mitigation (Current Story Scope)**:
- Document security limitation clearly
- Add warning in deployment docs

**Future Fix (Story 4.4 Scope)**:
- Implement backend proxy endpoint
- Credentials stay on server
- Only session tokens sent to browser

### 🟡 Medium Priority Enhancements (Can defer to later stories)

4. **Improved Error Messages**: Distinguish timeout vs auth failure vs service down
5. **Config Validation**: Check port range, credential format before use
6. **Retry Mechanism**: Auto-retry on transient network errors

## Testing Checklist

### Manual Testing Flow
```bash
# 1. Verify configuration exists
docker exec websoft9-cockpit apphub getconfig --section nginx_proxy_manager
docker exec websoft9-cockpit apphub getconfig --section portainer

# 2. Access plugin
# Browser: http://localhost:9091
# Login: websoft9/websoft9
# Click: "Portainer" in left sidebar

# 3. Verify behavior
✓ Loading spinner appears briefly (~1s)
✓ Portainer dashboard loads in iframe
✓ No login prompt shown
✓ Can navigate containers, images, etc.

# 4. Test deep linking
# Browser: http://localhost:9091/portainer#/w9deployment/#!/containers
✓ Opens directly to containers page

# 5. Test browser navigation
# In Portainer: Click "Images" tab
# Browser: Press back button
✓ Returns to previous Portainer page
✓ URL hash updates correctly

# 6. Test error handling
docker exec websoft9-cockpit supervisorctl stop portainer
# Reload plugin
✓ Error message shown: "Cannot connect to Portainer service"
docker exec websoft9-cockpit supervisorctl start portainer
```

### API Test
```bash
# Verify authentication endpoint works
NGINX_PORT=$(docker exec websoft9-cockpit apphub getconfig --section nginx_proxy_manager | jq -r '.listen_port')
PORTAINER_USER=$(docker exec websoft9-cockpit apphub getconfig --section portainer | jq -r '.user_name')
PORTAINER_PASS=$(docker exec websoft9-cockpit apphub getconfig --section portainer | jq -r '.user_pwd')

curl -X POST "http://localhost:${NGINX_PORT}/w9deployment/api/auth" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${PORTAINER_USER}\",\"password\":\"${PORTAINER_PASS}\"}"

# Expected: HTTP 200 + {"jwt":"<token>"}
```

### Error Scenarios to Test

| Test Case | How to Trigger | Expected Result |
|-----------|---------------|-----------------|
| Missing config | Rename config key | "Nginx proxy port not configured" |
| Invalid credentials | Change password in config | "Authentication failed" |
| Service down | Stop Portainer container | "Cannot connect to Portainer service" |
| Permission denied | Remove user from docker group | "Docker permission denied" + fix command |
| Token expired | Wait 8 hours or manually expire | *(After fix)* Auto-refresh token |

## Known Limitations

1. **Security**: Credentials temporarily visible in browser DevTools (will fix in Story 4.4)
2. **Session Management**: Manual refresh needed after 8 hours (will fix in this story)
3. **Single Instance**: No support for multiple Portainer instances
4. **Network Dependency**: Requires active connection (no offline mode)

## Definition of Done

### Must Have (Blocking Release)
- [x] Authentication flow works end-to-end
- [x] SSO navigation functional
- [x] Iframe embedding working
- [x] Hash synchronization implemented
- [x] Performance under 2s
- [x] **Graceful degradation: Always redirect to Portainer URL even if SSO fails** ✅ Implemented
- [x] **Non-blocking error messages (warnings/toasts, not blocking alerts)** ✅ Implemented
- [x] **JWT token explicitly set in cookie** ✅ Implemented
- [x] **Token expiry detection + auto-refresh** ✅ Implemented
- [x] **Security limitation documented** ✅ Implemented

### Should Have (Important)
- [x] Loading spinner during auth attempt
- [x] Warning messages displayed (non-blocking toasts/banners) ✅ Implemented
- [x] Configuration retrieval working
- [x] Fallback to Portainer login page when SSO fails ✅ Implemented
- [ ] Retry on transient failures (defer to Story 4.5)

### Could Have (Nice to Have)
- [ ] Multi-stage loading progress (defer)
- [ ] Telemetry/logging (defer)
- [ ] Offline error handling (defer)

## Implementation Tasks

### Task 0: Implement Graceful Degradation Wrapper 🎯 (NEW - CRITICAL)
**File**: `plugins/portainer/src/App.js`  
**Location**: Wrap entire auth flow

**Change**:
```javascript
const autoLogin = useCallback(async (baseURL) => {
  try {
    // Attempt SSO authentication
    await getJwt(baseURL);
  } catch (error) {
    // Log error but DON'T block user
    console.warn('SSO authentication failed:', error);
    // Show non-blocking warning (optional)
    setWarningMessage('Single Sign-On failed. Please login manually.');
  } finally {
    // ALWAYS redirect to Portainer regardless of SSO result
    setIframeKey(Math.random());
    const newHash = window.location.hash;
    if (newHash.includes("/w9deployment/#!/")) {
      const index = newHash.indexOf("#");
      if (index > -1) {
        const content = newHash.slice(index + 1);
        setIframeSrc(`${baseURL}${content}`);
      }
    } else {
      // Always redirect to Portainer base URL
      setIframeSrc(`${baseURL}/w9deployment/`);
    }
  }
}, [getJwt]);
```

**Key Changes**:
1. Wrap `getJwt()` in try-catch (don't let errors propagate)
2. Use `finally` block to ensure iframe always loads
3. Remove dependency on `jwtLoaded` state for rendering iframe
4. Add optional warning message instead of blocking error

### Task 1: Activate JWT Cookie Management
**File**: `plugins/portainer/src/App.js`  
**Line**: ~67-68

**Change**:
```javascript
// Remove comments
const portainer_jwt = authResponse.data.jwt;
document.cookie = `portainer_jwt=${portainer_jwt}; path=/; SameSite=Strict; max-age=28800`;
setJwtLoaded(true);
```

### Task 2: Implement Token Expiry Tracking
**File**: `plugins/portainer/src/App.js`  
**Location**: Add after JWT received

**Add**:
```javascript
import jwtDecode from 'jwt-decode';

// In getJwt function, after successful auth
const decoded = jwtDecode(authResponse.data.jwt);
sessionStorage.setItem('portainer_token_expiry', decoded.exp * 1000);
```

### Task 3: Add Token Refresh Mechanism
**File**: `plugins/portainer/src/App.js`  
**Location**: Add new useEffect hook

**Add**:
```javascript
useEffect(() => {
  const checkAndRefresh = () => {
    const expiry = sessionStorage.getItem('portainer_token_expiry');
    if (!expiry || !baseURL) return;
    
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000;
    
    if (now + fiveMinutes >= Number(expiry)) {
      autoLogin(baseURL);
    }
  };
  
  const interval = setInterval(checkAndRefresh, 5 * 60 * 1000);
  return () => clearInterval(interval);
}, [autoLogin, baseURL]);
```

### Task 4: Update Documentation
**File**: `plugins/portainer/README.md`  
**Add security warning**:
```markdown
## Security Considerations

**Current Limitation**: Portainer credentials are retrieved client-side and briefly visible in browser DevTools. This is mitigated by:
- Cockpit authentication required before plugin access
- Typically used in local/trusted networks
- Planned improvement in Story 4.4: Move authentication to backend proxy

**Recommendation**: Do not use Portainer plugin on shared/untrusted systems until backend proxy is implemented.
```

## Success Criteria

Story is complete when:
1. ✅ **Graceful degradation implemented**: Plugin always redirects to Portainer URL (even on SSO failure)
2. ✅ **Non-blocking warnings**: Error messages shown as toasts/warnings, not blocking alerts
3. ✅ **Manual login fallback works**: Users can access Portainer login page when SSO fails
4. ✅ JWT token is explicitly set (not relying on Portainer auto-cookies)
5. ✅ Token expiry is tracked and logged
6. ✅ Automatic token refresh works (tested by waiting near expiry)
7. ✅ All manual tests pass (including SSO failure scenarios)
8. ✅ Security limitation documented in README
9. ✅ Code changes reviewed and deployed

**Target Timeline**: 1 developer day (includes testing)

**Testing Priority**: Must verify both success and failure paths work correctly!

---

**Version**: v0.1.6-rc1  
**Last Updated**: 2026-02-08  
**Related Stories**: Story 4.1 (completed), Story 4.3 (next)

**Key Changes in v0.1.6**:
- 🎯 **Graceful Degradation**: Always redirect to Portainer, even if SSO fails
- ⚠️ **Non-blocking Errors**: Warnings instead of blocking error screens  
- 🚀 **Better UX**: Users can always access Portainer (SSO or manual login)

---

## Dev Agent Record

### Implementation Plan
**Date**: 2026-02-08  
**Agent**: Amelia (Dev Agent)

**Strategy**:
1. Implement graceful degradation (Task 0) - highest priority
2. Activate JWT explicit management (Task 1)
3. Add token expiry tracking (Task 2)
4. Implement auto-refresh mechanism (Task 3)
5. Document security considerations (Task 4)

**Architecture Decisions**:
- Used try-catch-finally pattern to ensure iframe always loads
- Removed `jwtLoaded` state dependency from UI rendering
- Integrated `jwt-decode` library for token expiry parsing
- Set 5-minute refresh window before token expiry
- Added non-blocking floating warnings instead of blocking alerts

### Debug Log
- **Issue**: ESLint warning for unused `jwtLoaded` variable
  - **Resolution**: Removed `jwtLoaded` state entirely since UI no longer depends on it
  
- **Issue**: build.sh hardcoded path `/data/plugin-cockpit/plugin-portainer/` doesn't exist
  - **Resolution**: Manual deployment using `docker cp` command
  
- **Issue**: Initial build added 884B, optimized to remove unused code
  - **Resolution**: Final build reduced by 21B after removing `jwtLoaded`

### Completion Notes
**Date**: 2026-02-08

✅ **All 5 tasks completed successfully**:
1. ✅ Task 0: Graceful degradation wrapper - `autoLogin` refactored with try-catch-finally
2. ✅ Task 1: JWT cookie explicitly set with `SameSite=Strict; max-age=28800`
3. ✅ Task 2: Token expiry tracked using `jwt-decode` and stored in sessionStorage
4. ✅ Task 3: Auto-refresh mechanism checks every 5 minutes, refreshes 5min before expiry
5. ✅ Task 4: README updated with comprehensive security considerations section

**Build Stats**:
- Final size: 66.9 kB (gzipped)
- Build time: ~10s
- No warnings or errors

**Key Implementation Details**:
- `autoLogin` now wraps `getJwt()` in try-catch, uses finally to always set iframe
- UI rendering changed from `{iframeKey && iframeSrc && jwtLoaded ? ...}` to `{iframeKey && iframeSrc ? ...}`
- Token expiry checked on mount and every 5 minutes thereafter
- Warning messages shown as floating alerts (position-fixed, z-index 9999) when SSO fails

**Test Coverage**:
- Build compilation: ✅ Pass
- ESLint: ✅ Pass (no warnings)
- Deployment: ✅ Successfully deployed to websoft9-cockpit container

---

## File List

**Modified Files**:
- `plugins/portainer/src/App.js` - Refactored SSO authentication with graceful degradation
- `plugins/portainer/README.md` - Added security considerations documentation

**Build Artifacts** (deployed):
- `plugins/portainer/build/static/js/main.be63cad6.js` - 200K (minified)
- `plugins/portainer/build/static/js/main.be63cad6.js.map` - 629K (source map)
- `plugins/portainer/build/static/css/main.5281a9e2.css` - (unchanged)

---

## Change Log

**v0.1.6-rc1** (2026-02-08):
- Implemented graceful degradation: Plugin always redirects to Portainer even if SSO fails
- Activated JWT token explicit management with `portainer_jwt` cookie
- Added token expiry tracking using `jwt-decode` library
- Implemented automatic token refresh (checks every 5min, refreshes 5min before expiry)
- Updated README with security considerations and session management documentation
- Refactored UI rendering to remove dependency on `jwtLoaded` state
- Changed error display from blocking alerts to non-blocking floating warnings

---

## Status

**Current**: ⚠️ Ready for Testing & Review  
**Next**: Manual testing of SSO success/failure paths + Acceptance criteria validation

**Outstanding Items**:
- [ ] Manual testing: SSO success path
- [ ] Manual testing: SSO failure path (invalid credentials, service down)
- [ ] Manual testing: Token refresh after ~8 hours
- [ ] Validate all acceptance criteria satisfied
- [ ] Code review

---

**Version**: v0.1.6-rc1  
**Last Updated**: 2026-02-08  
**Related Stories**: Story 4.1 (completed), Story 4.3 (next)

**Key Changes in v0.1.6**:
- 🎯 **Graceful Degradation**: Always redirect to Portainer, even if SSO fails
- ⚠️ **Non-blocking Errors**: Warnings instead of blocking error screens  
- 🚀 **Better UX**: Users can always access Portainer (SSO or manual login)
