# Story 4.6: Testing & Documentation

**Epic**: Epic 4 - Portainer SSO Integration  
**Priority**: P2  
**Status**: ⚠️ Needs Completion

## User Story
As a developer and user, I want comprehensive test coverage and usage documentation, so that the SSO functionality is reliable and users know how to configure and use it.

## Acceptance Criteria
- [ ] Unit tests cover authentication flow
- [ ] Integration tests verify Portainer API interaction
- [ ] Tests cover various failure scenarios (network errors, auth failures, token expiry)
- [ ] User documentation explains configuration and usage
- [ ] Troubleshooting guide created
- [ ] README.md includes build, deployment, and configuration guide
- [ ] All tests run automatically in CI/CD

## Current State

### Documentation
**Existing Docs**:
- ✅ `README.md` - Basic installation and build instructions
- ✅ `docs/developer.md` - Technology stack and build commands
- ✅ `docs/PRD.md` - Link to design prototype
- ⚠️ CHANGELOG.md - Exists but minimal content

**Missing Docs**:
- ❌ Configuration guide (how to set credentials)
- ❌ Troubleshooting guide
- ❌ API documentation
- ❌ Architecture diagram
- ❌ User manual

### Testing
**Current State**:
- ❌ No unit tests
- ❌ No integration tests
- ❌ No E2E tests
- ❌ No CI/CD pipeline for tests

**package.json Test Script**:
```json
{
  "scripts": {
    "test": "react-app-rewired test"
  }
}
```
(Configured but no test files exist)

## Required Test Coverage

### Unit Tests

#### 1. Configuration Loading Tests
```javascript
// tests/config.test.js
import { getNginxConfig, getPortainerConfig } from '../src/utils/config';

describe('Configuration Loading', () => {
  it('should load nginx config successfully', async () => {
    const config = await getNginxConfig();
    expect(config).toHaveProperty('listen_port');
    expect(typeof config.listen_port).toBe('number');
  });

  it('should load portainer config successfully', async () => {
    const config = await getPortainerConfig();
    expect(config).toHaveProperty('user_name');
    expect(config).toHaveProperty('user_pwd');
  });

  it('should handle missing configuration gracefully', async () => {
    // Mock apphub to return empty config
    await expect(getNginxConfig()).rejects.toThrow('Configuration not found');
  });

  it('should validate configuration format', () => {
    const invalidConfig = { listen_port: 'not_a_number' };
    expect(() => validateConfig(invalidConfig)).toThrow();
  });
});
```

#### 2. Authentication Tests
```javascript
// tests/auth.test.js
import { getJwt, checkTokenExpiry } from '../src/utils/auth';
import axios from 'axios';

jest.mock('axios');

describe('Authentication', () => {
  beforeEach(() => {
    axios.post.mockReset();
  });

  it('should authenticate successfully with valid credentials', async () => {
    axios.post.mockResolvedValue({
      status: 200,
      data: { jwt: 'mock_jwt_token' }
    });

    const token = await getJwt('http://localhost:81');
    expect(token).toBe('mock_jwt_token');
    expect(axios.post).toHaveBeenCalledWith(
      'http://localhost:81/w9deployment/api/auth',
      expect.objectContaining({ username: expect.any(String) })
    );
  });

  it('should throw error on authentication failure', async () => {
    axios.post.mockRejectedValue(new Error('401 Unauthorized'));
    await expect(getJwt('http://localhost:81')).rejects.toThrow('401');
  });

  it('should detect expired tokens', () => {
    const expiredTime = Math.floor(Date.now() / 1000) - 100;
    sessionStorage.setItem('portainer_token_expiry', expiredTime);
    expect(checkTokenExpiry()).toBe(true);
  });

  it('should detect valid tokens', () => {
    const futureTime = Math.floor(Date.now() / 1000) + 3600;
    sessionStorage.setItem('portainer_token_expiry', futureTime);
    expect(checkTokenExpiry()).toBe(false);
  });
});
```

#### 3. Component Tests
```javascript
// tests/App.test.js
import { render, screen, waitFor } from '@testing-library/react';
import App from '../src/App';

describe('App Component', () => {
  it('should render loading spinner initially', () => {
    render(<App />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('should render iframe after successful authentication', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTitle('portainer')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('should display error message on authentication failure', async () => {
    // Mock failed authentication
    jest.spyOn(global, 'fetch').mockRejectedValue(new Error('Auth failed'));
    
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  it('should handle permission denied errors', async () => {
    // Mock permission denied error
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Docker permissions/i)).toBeInTheDocument();
    });
  });
});
```

### Integration Tests

#### 4. Portainer API Integration Tests
```javascript
// tests/integration/portainer-api.test.js
describe('Portainer API Integration', () => {
  const portainerUrl = process.env.TEST_PORTAINER_URL || 'http://localhost:9000';

  it('should authenticate to real Portainer instance', async () => {
    const response = await axios.post(`${portainerUrl}/api/auth`, {
      username: 'admin',
      password: 'testpassword'
    });
    
    expect(response.status).toBe(200);
    expect(response.data).toHaveProperty('jwt');
  });

  it('should access system info with JWT', async () => {
    const { jwt } = await authenticate();
    
    const response = await axios.get(`${portainerUrl}/api/system/status`, {
      headers: { Authorization: `Bearer ${jwt}` }
    });
    
    expect(response.status).toBe(200);
    expect(response.data).toHaveProperty('Version');
  });

  it('should handle expired JWT gracefully', async () => {
    const expiredJwt = 'expired_token';
    
    await expect(
      axios.get(`${portainerUrl}/api/system/status`, {
        headers: { Authorization: `Bearer ${expiredJwt}` }
      })
    ).rejects.toThrow();
  });
});
```

### End-to-End Tests

#### 5. E2E Tests with Playwright
```javascript
// tests/e2e/sso-flow.spec.js
const { test, expect } = require('@playwright/test');

test.describe('Portainer SSO Flow', () => {
  test('should complete full SSO flow', async ({ page }) => {
    // 1. Navigate to Cockpit
    await page.goto('http://localhost:9000');
    
    // 2. Login to Cockpit (if needed)
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'password');
    await page.click('button[type="submit"]');
    
    // 3. Click Portainer plugin
    await page.click('a[href="/portainer"]');
    
    // 4. Wait for loading to complete
    await page.waitForSelector('iframe[title="portainer"]', { timeout: 5000 });
    
    // 5. Verify iframe loaded
    const iframe = page.frameLocator('iframe[title="portainer"]');
    await expect(iframe.locator('text=Dashboard')).toBeVisible({ timeout: 10000 });
  });

  test('should handle authentication errors', async ({ page }) => {
    // Mock failed authentication
    await page.route('**/api/auth', route => {
      route.fulfill({ status: 401, body: 'Unauthorized' });
    });
    
    await page.goto('http://localhost:9000/portainer');
    
    // Should show error message
    await expect(page.locator('text=/error/i')).toBeVisible();
  });

  test('should support browser back/forward with hash routing', async ({ page }) => {
    await page.goto('http://localhost:9000/portainer');
    await page.waitForSelector('iframe[title="portainer"]');
    
    // Navigate within Portainer
    const iframe = page.frameLocator('iframe[title="portainer"]');
    await iframe.locator('a[href*="containers"]').click();
    await page.waitForTimeout(1000);
    
    // Check URL hash changed
    expect(page.url()).toContain('containers');
    
    // Browser back button
    await page.goBack();
    await page.waitForTimeout(1000);
    
    // URL should revert
    expect(page.url()).not.toContain('containers');
  });
});
```

## Required Documentation

### 1. User Guide (`docs/user-guide.md`)
```markdown
# Portainer Plugin User Guide

## Overview
The Portainer plugin provides seamless access to Portainer from the Websoft9 Cockpit interface.

## Features
- Single Sign-On (no need to remember Portainer credentials)
- Embedded Portainer interface
- Deep linking to specific Portainer pages

## Getting Started

### Accessing Portainer
1. Log in to Websoft9 Cockpit
2. Click "Portainer" from the left menu
3. Wait 1-2 seconds for automatic authentication
4. Portainer dashboard will appear

### Configuration
[Credentials are managed automatically. For advanced configuration, see Configuration Guide]

## Troubleshooting
[See Troubleshooting Guide]
```

### 2. Configuration Guide (`docs/configuration-guide.md`)
```markdown
# Portainer Plugin Configuration Guide

## Configuration Files

### Portainer Credentials
Location: Managed by `apphub`

View current configuration:
\`\`\`bash
sudo apphub getconfig --section portainer
\`\`\`

Update configuration:
\`\`\`bash
sudo apphub setconfig --section portainer --data '{
  "user_name": "admin",
  "user_pwd": "your_password"
}'
\`\`\`

### Nginx Proxy Configuration
\`\`\`bash
sudo apphub getconfig --section nginx_proxy_manager
\`\`\`

## Security Recommendations
1. Use strong passwords (min 12 characters)
2. Change default admin password
3. Enable HTTPS in production
4. Regularly rotate credentials

## Advanced Configuration
[Details on API keys, custom URLs, etc.]
```

### 3. Troubleshooting Guide (`docs/troubleshooting.md`)
```markdown
# Portainer Plugin Troubleshooting Guide

## Common Issues

### Plugin shows "Permission Denied" error

**Symptom**: Error message about Docker permissions

**Cause**: User does not have Docker group membership

**Solution**:
\`\`\`bash
sudo usermod -aG docker <username>
# Log out and log back in
\`\`\`

### Plugin shows loading spinner forever

**Possible Causes**:
1. Portainer service not running
2. Network connectivity issues
3. Incorrect configuration

**Debugging Steps**:
\`\`\`bash
# Check if Portainer is running
docker ps | grep portainer

# Check configuration
sudo apphub getconfig --section portainer
sudo apphub getconfig --section nginx_proxy_manager

# Test Portainer API directly
curl -X POST http://localhost:<port>/w9deployment/api/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<password>"}'
\`\`\`

### Authentication fails

**Symptoms**: "Auth Portainer Error" message

**Solutions**:
1. Verify credentials are correct
2. Check Portainer logs: `docker logs <portainer_container>`
3. Ensure Portainer is accessible on expected port

[More issues and solutions...]
```

### 4. Architecture Diagram
```markdown
# Architecture Documentation

## SSO Flow Diagram

\`\`\`
┌─────────────────┐
│  User Browser   │
└────────┬────────┘
         │ 1. Access /portainer
         ↓
┌─────────────────┐
│ Cockpit Plugin  │
│    (React)      │
└────────┬────────┘
         │ 2. apphub getconfig
         ↓
┌─────────────────┐
│    Apphub       │  (Config Storage)
└────────┬────────┘
         │ 3. Returns credentials
         ↓
┌─────────────────┐
│ Plugin (Auth)   │
└────────┬────────┘
         │ 4. POST /api/auth
         ↓
┌─────────────────┐
│ Nginx Proxy     │  (Port 81)
└────────┬────────┘
         │ 5. Forward to Portainer
         ↓
┌─────────────────┐
│   Portainer     │  (Port 9000)
│   /w9deployment/│
└────────┬────────┘
         │ 6. Returns JWT
         ↓
┌─────────────────┐
│ Plugin (iframe) │
└────────┬────────┘
         │ 7. Load Portainer UI
         ↓
┌─────────────────┐
│  User sees UI   │
└─────────────────┘
\`\`\`

## Component Diagram
[Detailed component interactions]
```

## CI/CD Integration

### GitHub Actions Workflow
```yaml
# .github/workflows/test.yml
name: Test Plugin

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: yarn install
      - run: yarn test --coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      portainer:
        image: portainer/portainer-ce:latest
        ports:
          - 9000:9000
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: yarn install
      - run: yarn test:integration

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: yarn install
      - run: npx playwright install
      - run: yarn test:e2e
```

## Definition of Done
- [ ] Unit test coverage > 80%
- [ ] Integration tests pass with real Portainer instance
- [ ] E2E tests cover critical user flows
- [ ] User guide written and reviewed
- [ ] Configuration guide complete
- [ ] Troubleshooting guide covers common issues
- [ ] Architecture documentation created
- [ ] CI/CD pipeline runs all tests automatically
- [ ] Test results visible in PR checks
- [ ] Documentation reviewed by 2+ team members

## References
- [Jest Testing Framework](https://jestjs.io/)
- [React Testing Library](https://testing-library.com/react)
- [Playwright E2E Testing](https://playwright.dev/)
- [Documentation Best Practices](https://www.writethedocs.org/guide/)
