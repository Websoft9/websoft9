# Story 4.4: Configuration Management

**Epic**: Epic 4 - Portainer SSO Integration  
**Priority**: P1  
**Status**: ⚠️ Partially Completed

## User Story
As an administrator, I want to configure the Portainer plugin connection and authentication parameters, so that the plugin can adapt to different deployment environments.

## Acceptance Criteria
- [x] Portainer service URL can be configured
- [x] Authentication credentials can be configured (stored via apphub)
- [ ] Configuration UI interface provided in plugin
- [x] Configuration persists in `portainer.json`
- [ ] Configuration changes take effect without Cockpit restart
- [ ] Sensitive information (passwords, API keys) encrypted in storage

## Current Implementation

### Configuration Storage
**Backend Configuration** (via `apphub`):
```bash
# Portainer credentials
apphub getconfig --section portainer
# Returns: {"user_name": "admin", "user_pwd": "<password>"}

# Nginx proxy port
apphub getconfig --section nginx_proxy_manager
# Returns: {"listen_port": 81}
```

**Plugin Manifest** (`portainer.json`):
```json
{
  "Plugin Name": "Portainer",
  "Repository": "https://github.com/Websoft9/plugin-portainer",
  "Description": "200 application template for you installation.",
  "Version": "0.1.4-rc2",
  "Requires at most": "1.8.20",
  "Requires at least": "0.7.3",
  "Author": "Websoft9 Inc",
  "License": "GPL v2 or later"
}
```

### Configuration Retrieval (`src/App.js`)
```javascript
const getNginxConfig = async () => {
  const script = "apphub getconfig --section nginx_proxy_manager";
  let content = await cockpit.spawn(["/bin/bash", "-c", script], { superuser: "try" });
  content = JSON.parse(content.trim());
  
  if (content && content.listen_port) {
    setListenPort(content.listen_port);
  }
};

const getJwt = async (baseURL) => {
  const script = "apphub getconfig --section portainer";
  let content = await cockpit.spawn(["/bin/bash", "-c", script], { superuser: "try" });
  content = JSON.parse(content.trim());
  
  const userName = content.user_name;
  const userPwd = content.user_pwd;
  // ... use credentials for authentication
};
```

## Gaps & Missing Features

### 🔴 Critical Gaps

#### 1. No Configuration UI
**Problem**: Users cannot configure the plugin through the interface
**Impact**: Must manually edit backend configuration files
**Priority**: High

**Needed Features**:
- Settings page in plugin
- Form to edit Portainer URL
- Credential management (change password, API key)
- Test connection button

#### 2. Hardcoded Configuration Keys
```javascript
// Config sections are hardcoded strings
"apphub getconfig --section portainer"
"apphub getconfig --section nginx_proxy_manager"
```
**Problem**: Not flexible for custom deployments
**Impact**: Cannot easily support alternative proxy managers or Portainer instances

#### 3. No Configuration Validation
**Problem**: No validation of config values before use
**Impact**: Cryptic errors if config is malformed
**Example**:
```javascript
// What if listen_port is not a number?
// What if user_name is empty?
```

#### 4. Credentials Not Encrypted
**Problem**: Credentials stored in plaintext (assumed from apphub)
**Impact**: Security risk if config files are exposed
**Priority**: High

### 🟡 Medium Priority Gaps

#### 5. No Default Configuration
**Problem**: No fallback if config is missing
**Impact**: Plugin fails to load

#### 6. Configuration Changes Require Page Reload
**Problem**: After changing config (in backend), must refresh page
**Impact**: Poor user experience

## Recommended Implementation

### Phase 1: Configuration UI

#### Settings Component
```javascript
// src/components/Settings.js
import { useState } from 'react';
import { Form, Button, Alert } from 'react-bootstrap';

function Settings() {
  const [config, setConfig] = useState({
    portainerUrl: '',
    listenPort: '',
    userName: '',
    password: '',
    authMethod: 'credentials' // or 'api_key'
  });
  const [testResult, setTestResult] = useState(null);

  const loadConfig = async () => {
    const portainerConfig = await getConfig('portainer');
    const nginxConfig = await getConfig('nginx_proxy_manager');
    
    setConfig({
      portainerUrl: portainerConfig.url || '',
      listenPort: nginxConfig.listen_port || 81,
      userName: portainerConfig.user_name || '',
      password: '', // Don't load password for security
      authMethod: portainerConfig.auth_method || 'credentials'
    });
  };

  const saveConfig = async () => {
    try {
      // Validate
      if (!config.portainerUrl || !config.userName) {
        throw new Error('URL and username required');
      }

      // Save via apphub
      await cockpit.spawn([
        'apphub', 'setconfig',
        '--section', 'portainer',
        '--data', JSON.stringify({
          url: config.portainerUrl,
          user_name: config.userName,
          user_pwd: config.password,
          auth_method: config.authMethod
        })
      ], { superuser: "try" });

      setTestResult({ success: true, message: 'Configuration saved' });
    } catch (error) {
      setTestResult({ success: false, message: error.message });
    }
  };

  const testConnection = async () => {
    try {
      const response = await axios.post(`${config.portainerUrl}/api/auth`, {
        username: config.userName,
        password: config.password
      });
      
      if (response.status === 200) {
        setTestResult({ success: true, message: 'Connection successful' });
      }
    } catch (error) {
      setTestResult({ success: false, message: 'Connection failed: ' + error.message });
    }
  };

  return (
    <div className="settings-container">
      <h2>Portainer Configuration</h2>
      
      <Form>
        <Form.Group className="mb-3">
          <Form.Label>Portainer URL</Form.Label>
          <Form.Control
            type="text"
            value={config.portainerUrl}
            onChange={(e) => setConfig({...config, portainerUrl: e.target.value})}
            placeholder="http://localhost:9000"
          />
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Listen Port (Nginx Proxy)</Form.Label>
          <Form.Control
            type="number"
            value={config.listenPort}
            onChange={(e) => setConfig({...config, listenPort: e.target.value})}
          />
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Username</Form.Label>
          <Form.Control
            type="text"
            value={config.userName}
            onChange={(e) => setConfig({...config, userName: e.target.value})}
          />
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Password</Form.Label>
          <Form.Control
            type="password"
            value={config.password}
            onChange={(e) => setConfig({...config, password: e.target.value})}
            placeholder="Enter new password to change"
          />
        </Form.Group>

        <Button variant="secondary" onClick={testConnection} className="me-2">
          Test Connection
        </Button>
        <Button variant="primary" onClick={saveConfig}>
          Save Configuration
        </Button>
      </Form>

      {testResult && (
        <Alert variant={testResult.success ? 'success' : 'danger'} className="mt-3">
          {testResult.message}
        </Alert>
      )}
    </div>
  );
}
```

### Phase 2: Secure Configuration Storage

#### Encrypt Sensitive Data
```bash
# Backend: apphub should encrypt passwords
apphub setconfig --section portainer --encrypt --data '{"user_pwd":"secret123"}'

# When reading, apphub decrypts automatically
apphub getconfig --section portainer --decrypt
# Returns: {"user_name":"admin","user_pwd":"secret123"}
```

**Encryption Strategy**:
- Use system keyring (e.g., `libsecret` on Linux)
- Or encrypt with server-generated key stored in `/etc/websoft9/`
- Never store plaintext passwords in config files

### Phase 3: Configuration Validation

#### Schema Validation
```javascript
const configSchema = {
  portainer: {
    url: { type: 'string', required: true, pattern: /^https?:\/\/.+/ },
    user_name: { type: 'string', required: true, minLength: 3 },
    user_pwd: { type: 'string', required: true, minLength: 8 },
    auth_method: { type: 'string', enum: ['credentials', 'api_key'] }
  },
  nginx_proxy_manager: {
    listen_port: { type: 'number', required: true, min: 1, max: 65535 }
  }
};

const validateConfig = (config, schema) => {
  const errors = [];
  
  for (const [key, rules] of Object.entries(schema)) {
    const value = config[key];
    
    if (rules.required && !value) {
      errors.push(`${key} is required`);
    }
    
    if (rules.type === 'number' && typeof value !== 'number') {
      errors.push(`${key} must be a number`);
    }
    
    if (rules.pattern && !rules.pattern.test(value)) {
      errors.push(`${key} format is invalid`);
    }
    
    // ... more validation rules
  }
  
  return errors;
};
```

### Phase 4: Hot Configuration Reload

```javascript
// Watch for config changes
const watchConfig = () => {
  const configWatcher = setInterval(async () => {
    const newConfig = await getNginxConfig();
    if (newConfig.listen_port !== listenPort) {
      setListenPort(newConfig.listen_port);
      // Trigger re-authentication with new config
      await autoLogin(buildBaseURL(newConfig.listen_port));
    }
  }, 30000); // Check every 30 seconds
  
  return () => clearInterval(configWatcher);
};

useEffect(() => {
  const cleanup = watchConfig();
  return cleanup;
}, []);
```

## Configuration File Locations

### Backend Storage
```
/etc/websoft9/config.json
└── {
      "portainer": {
        "url": "http://localhost:9000",
        "user_name": "admin",
        "user_pwd_encrypted": "...",
        "auth_method": "credentials"
      },
      "nginx_proxy_manager": {
        "listen_port": 81
      }
    }
```

### Plugin Manifest
```
/usr/share/cockpit/portainer/portainer.json
```

## Testing

### Manual Testing
```bash
# 1. Test current config retrieval
sudo apphub getconfig --section portainer
sudo apphub getconfig --section nginx_proxy_manager

# 2. Test config modification
sudo apphub setconfig --section portainer --data '{"user_name":"testuser","user_pwd":"testpass"}'

# 3. Verify plugin reads new config
# Reload plugin in browser, check if new credentials are used

# 4. Test validation
# Try invalid port number (e.g., 99999)
# Expected: Error message displayed

# 5. Test encryption (if implemented)
cat /etc/websoft9/config.json | grep user_pwd
# Expected: Should see encrypted string, not plaintext
```

### Unit Tests
```javascript
describe('Configuration', () => {
  it('should load config from apphub', async () => {
    const config = await getConfig('portainer');
    expect(config).toHaveProperty('user_name');
    expect(config).toHaveProperty('user_pwd');
  });
  
  it('should validate config schema', () => {
    const invalidConfig = { listen_port: 'not_a_number' };
    const errors = validateConfig(invalidConfig, configSchema);
    expect(errors.length).toBeGreaterThan(0);
  });
  
  it('should save config successfully', async () => {
    const newConfig = { user_name: 'admin', user_pwd: 'newpass' };
    await saveConfig('portainer', newConfig);
    const loaded = await getConfig('portainer');
    expect(loaded.user_name).toBe('admin');
  });
});
```

## Definition of Done
- [ ] Configuration UI implemented in plugin
- [ ] Config can be modified through UI
- [ ] Configuration validation working
- [ ] Sensitive data encrypted in storage
- [ ] Configuration changes take effect without restart
- [ ] Test connection feature working
- [ ] Default configuration provided
- [ ] Configuration schema documented
- [ ] Unit tests for config management
- [ ] User documentation for configuration

## References
- [Cockpit Configuration Storage](https://cockpit-project.org/guide/latest/packages.html)
- [React Bootstrap Forms](https://react-bootstrap.github.io/forms/overview/)
- [Linux Keyring (libsecret)](https://wiki.gnome.org/Projects/Libsecret)
