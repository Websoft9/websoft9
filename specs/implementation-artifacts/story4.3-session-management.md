# Story 4.3: Session Management & Security

**Epic**: Epic 4 - Portainer SSO Integration  
**Priority**: P1  
**Status**: ⚠️ Needs Improvement

## User Story
As an administrator, I want to ensure the SSO process is secure and reliable, so that authentication information doesn't leak and sessions are properly managed.

## Acceptance Criteria
- [ ] Authentication tokens not exposed in client-side JavaScript
- [ ] Token transmission uses secure methods (HTTP-only cookies or backend proxy)
- [ ] Automatic re-authentication or user prompt when session expires
- [ ] CSRF protection implemented
- [ ] Authentication events logged (success/failure)
- [ ] Complies with OWASP security best practices

## Current Security Assessment

### ✅ What's Working

1. **Secure Communication**
   - HTTPS can be enforced (depends on nginx proxy configuration)
   - Credentials retrieved from backend config (not hardcoded in client)

2. **Error Handling**
   - Permission denied errors detected
   - Authentication failures caught and displayed

3. **Cockpit Integration**
   - Uses Cockpit's `superuser: "try"` mode for privilege escalation
   - Inherits Cockpit's session management

### 🔴 Critical Security Gaps

#### 1. Credentials Exposed in Client Code
```javascript
// Current implementation - credentials visible in browser
const userName = content.user_name;
const userPwd = content.user_pwd;

const authResponse = await axios.post(`${baseURL}/w9deployment/api/auth`, {
  username: userName,
  password: userPwd,
});
```
**Risk**: High  
**Impact**: Credentials visible in browser DevTools/Network tab  
**Mitigation**: Move authentication to backend proxy

#### 2. JWT Token Not Properly Managed
```javascript
// Token obtained but not used
// const portainer_jwt = authResponse.data.jwt;
// document.cookie = "portainer_api_key=" + portainer_jwt + ";path=/";
```
**Risk**: Medium  
**Impact**: Relying on Portainer's automatic cookie setting (may fail)  
**Mitigation**: Explicitly set JWT with proper cookie attributes

#### 3. No Session Expiration Handling
**Risk**: Medium  
**Impact**: Users stuck with expired sessions, must manually refresh  
**Mitigation**: Implement token lifetime tracking and auto-refresh

#### 4. No CSRF Protection
**Risk**: Medium  
**Impact**: Vulnerable to cross-site request forgery  
**Mitigation**: Implement CSRF tokens or SameSite cookie policy

#### 5. No Audit Logging
**Risk**: Low  
**Impact**: No visibility into authentication attempts  
**Mitigation**: Log auth events to system log or database

## Recommended Security Enhancements

### Phase 1: Immediate Fixes (P0)

#### 1.1 Secure Token Storage
```javascript
const getJwt = async (baseURL) => {
  const config = await getPortainerConfig();
  const authResponse = await axios.post(`${baseURL}/w9deployment/api/auth`, {
    username: config.user_name,
    password: config.user_pwd,
  });
  
  const jwt = authResponse.data.jwt;
  
  // Set cookie with security attributes
  const cookieOptions = [
    `portainer_jwt=${jwt}`,
    'path=/',
    'SameSite=Strict',
    'Secure'  // Requires HTTPS
  ].join('; ');
  
  document.cookie = cookieOptions;
  
  // Track token expiry
  const decoded = jwtDecode(jwt);
  sessionStorage.setItem('portainer_token_expiry', decoded.exp);
  
  return jwt;
};
```

#### 1.2 Session Expiration Detection
```javascript
const checkTokenExpiry = () => {
  const expiry = sessionStorage.getItem('portainer_token_expiry');
  if (!expiry) return false;
  
  const expiryTime = parseInt(expiry) * 1000;
  const now = Date.now();
  
  // Token expires in less than 5 minutes
  if (expiryTime - now < 5 * 60 * 1000) {
    return true;
  }
  return false;
};

const refreshTokenIfNeeded = async () => {
  if (checkTokenExpiry()) {
    await getJwt(baseURL);
  }
};

// Check every minute
useEffect(() => {
  const interval = setInterval(refreshTokenIfNeeded, 60 * 1000);
  return () => clearInterval(interval);
}, []);
```

### Phase 2: Backend Proxy (P1 - Recommended Long-term Solution)

#### 2.1 Backend Proxy Architecture
```
Client (React Plugin)
    ↓ HTTP GET /cockpit/portainer/auth
Backend Proxy (Cockpit Handler)
    ↓ Uses stored credentials
Portainer API (/api/auth)
    ↓ Returns JWT
Backend Proxy
    ↓ Sets HTTP-only cookie
Client (No token visibility)
```

**Implementation** (pseudo-code):
```python
# cockpit/portainer-auth-proxy.py
@app.route('/cockpit/portainer/auth')
def authenticate():
    # Get credentials from secure storage
    config = get_secure_config('portainer')
    
    # Authenticate to Portainer
    response = requests.post(f'{portainer_url}/api/auth', json={
        'username': config['user_name'],
        'password': config['user_pwd']
    })
    
    jwt = response.json()['jwt']
    
    # Set HTTP-only cookie
    resp = make_response({'status': 'ok'})
    resp.set_cookie(
        'portainer_jwt', 
        jwt,
        httponly=True,  # Not accessible to JavaScript
        secure=True,     # HTTPS only
        samesite='Strict'
    )
    
    return resp
```

**Client Code** (simplified):
```javascript
const autoLogin = async () => {
  // No credentials in client code
  await axios.get('/cockpit/portainer/auth');
  // Backend sets cookie automatically
  setIframeSrc(`${baseURL}/w9deployment/`);
};
```

### Phase 3: Enhanced Security (P2)

#### 3.1 CSRF Protection
```javascript
// Generate CSRF token on plugin load
const csrfToken = generateRandomToken();
sessionStorage.setItem('csrf_token', csrfToken);

// Include in API requests
axios.post('/api/auth', data, {
  headers: { 'X-CSRF-Token': csrfToken }
});
```

#### 3.2 Audit Logging
```javascript
const logAuthEvent = async (event, status, error = null) => {
  const logData = {
    timestamp: new Date().toISOString(),
    event,
    status,
    user: getCurrentUser(),
    error
  };
  
  // Log to cockpit journal
  await cockpit.spawn([
    'logger',
    '-t', 'portainer-plugin',
    JSON.stringify(logData)
  ]);
};

// Usage
try {
  await getJwt(baseURL);
  await logAuthEvent('portainer_auth', 'success');
} catch (error) {
  await logAuthEvent('portainer_auth', 'failure', error.message);
  throw error;
}
```

#### 3.3 Content Security Policy
```html
<!-- Add to public/index.html -->
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; 
               frame-src 'self' http://localhost:*; 
               script-src 'self' 'unsafe-inline'; 
               style-src 'self' 'unsafe-inline';">
```

## Security Testing Checklist

### Authentication Security
- [ ] Credentials not visible in browser DevTools Network tab
- [ ] JWT not accessible via JavaScript (`document.cookie`)
- [ ] Token transmission over HTTPS only (in production)
- [ ] Failed auth attempts don't leak information (generic error messages)

### Session Management
- [ ] Token expiry properly detected
- [ ] Auto-refresh works before expiry
- [ ] User prompted appropriately when session expires
- [ ] Multiple tabs/windows share session state

### CSRF Protection
- [ ] CSRF token generated and validated
- [ ] SameSite cookie policy enforced
- [ ] Cross-origin requests blocked

### Logging & Monitoring
- [ ] Successful authentications logged
- [ ] Failed authentications logged
- [ ] Suspicious activity detected (repeated failures)
- [ ] Logs contain no sensitive data (passwords, tokens)

### OWASP Top 10 Compliance
- [ ] A01: Broken Access Control - ✓ Uses Cockpit's access control
- [ ] A02: Cryptographic Failures - ⚠️ Credentials in transit
- [ ] A03: Injection - ✓ Using axios (parameterized requests)
- [ ] A04: Insecure Design - ⚠️ Client-side auth flow
- [ ] A05: Security Misconfiguration - ⚠️ No CSP, no security headers
- [ ] A07: XSS - ✓ React escapes by default
- [ ] A08: Software Integrity - ⚠️ No SRI for dependencies

## Testing

### Manual Security Tests
```bash
# 1. Test credential exposure
# Open browser DevTools → Network tab
# Click Portainer plugin
# Check POST /api/auth request
# EXPECTED: Body should be hidden or encrypted

# 2. Test token accessibility
# Open browser Console
# Run: document.cookie
# EXPECTED: Portainer JWT should NOT be visible (if HTTP-only)

# 3. Test session expiry
# Authenticate to Portainer
# Wait for token to expire (8+ hours or adjust Portainer settings)
# Try to use plugin
# EXPECTED: Auto-refresh or prompt to re-login

# 4. Test CSRF
# Create malicious page trying to call auth endpoint
# EXPECTED: Request should be blocked

# 5. Check logs
sudo journalctl -t portainer-plugin
# EXPECTED: Auth events logged
```

### Automated Security Tests
```javascript
describe('Security', () => {
  it('should not expose JWT in JavaScript', () => {
    const cookies = document.cookie;
    expect(cookies).not.toContain('portainer_jwt');
  });
  
  it('should detect token expiry', () => {
    sessionStorage.setItem('portainer_token_expiry', Math.floor(Date.now() / 1000) - 100);
    expect(checkTokenExpiry()).toBe(true);
  });
  
  it('should refresh token before expiry', async () => {
    jest.useFakeTimers();
    render(<App />);
    jest.advanceTimersByTime(60 * 1000);
    await waitFor(() => expect(getJwt).toHaveBeenCalled());
  });
});
```

## Definition of Done
- [ ] Credentials not exposed in client-side code
- [ ] JWT token properly secured (HTTP-only cookie)
- [ ] Session expiration detection implemented
- [ ] Auto-refresh or re-authentication flow working
- [ ] CSRF protection in place
- [ ] Audit logging implemented
- [ ] Security tests passing
- [ ] OWASP compliance review completed
- [ ] Penetration testing performed
- [ ] Security documentation written

## References
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Portainer API Security](https://docs.portainer.io/api/access)
- [Cockpit Authentication](https://cockpit-project.org/guide/latest/authentication.html)
