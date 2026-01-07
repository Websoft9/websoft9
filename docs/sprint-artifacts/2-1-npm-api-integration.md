# Story 1: NPM API Integration

**Story ID:** PROXY-001  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 developer  
**I want to** integrate with Nginx Proxy Manager API  
**So that** I can programmatically manage proxy hosts and SSL certificates

## Acceptance Criteria

✅ Successful token-based authentication with NPM  
✅ CRUD operations for proxy hosts work reliably  
✅ Error handling with automatic retry (3 attempts)  
✅ API response time < 1 second  
✅ Connection pooling for efficiency

## Technical Tasks

- [ ] Implement NPM token authentication
- [ ] Create NginxProxyManagerAPI class
- [ ] Implement proxy host CRUD methods
- [ ] Add error handling and retry logic
- [ ] Write API integration tests
- [ ] Document API wrapper usage

## Implementation Notes

```python
class NginxProxyManagerAPI:
    def __init__(self):
        self.base_url = "http://nginx-proxy-manager:81/api"
        self.token = self.get_token()
    
    def get_token(self) -> str:
        """Authenticate with NPM and get JWT token"""
        
    def create_proxy_host(self, config: Dict) -> Dict:
        """Create a new proxy host"""
        
    def update_proxy_host(self, proxy_id: int, config: Dict) -> Dict:
        """Update existing proxy host"""
        
    def delete_proxy_host(self, proxy_id: int) -> None:
        """Delete proxy host"""
```

## Test Scenarios

1. Token authentication succeeds with valid credentials
2. Token authentication fails with invalid credentials
3. API call retries on network error
4. API call fails after max retries
5. Token refresh works on expiration
