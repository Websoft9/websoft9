# Epic 2: Proxy Management - User Stories

**Epic:** [Proxy Management Epic](../epics/proxy-management-epic.md)  
**Total Stories:** 8  
**Total Estimated Effort:** 18 days  
**Priority Distribution:** P0 (3), P1 (3), P2 (2)

---

## Story 1: NPM API Integration

**Story ID:** PROXY-001  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 developer  
**I want to** integrate with Nginx Proxy Manager API  
**So that** I can programmatically manage proxy hosts and SSL certificates

### Acceptance Criteria

✅ Successful token-based authentication with NPM  
✅ CRUD operations for proxy hosts work reliably  
✅ Error handling with automatic retry (3 attempts)  
✅ API response time < 1 second  
✅ Connection pooling for efficiency

### Technical Tasks

- [ ] Implement NPM token authentication
- [ ] Create NginxProxyManagerAPI class
- [ ] Implement proxy host CRUD methods
- [ ] Add error handling and retry logic
- [ ] Write API integration tests
- [ ] Document API wrapper usage

### Implementation Notes

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

### Test Scenarios

1. Token authentication succeeds with valid credentials
2. Token authentication fails with invalid credentials
3. API call retries on network error
4. API call fails after max retries
5. Token refresh works on expiration

---

## Story 2: Proxy Host Management

**Story ID:** PROXY-002  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** create reverse proxy configurations for my applications  
**So that** I can access applications via custom domain names

### Acceptance Criteria

✅ Proxy host created in < 30 seconds  
✅ Support multiple domain names per proxy  
✅ Automatic domain format validation  
✅ Check for domain conflicts before creation  
✅ Support for WebSocket applications

### Technical Tasks

- [ ] Implement `/api/v1/proxys/{app_id}` POST endpoint
- [ ] Add domain name validation (regex)
- [ ] Check domain uniqueness across all proxies
- [ ] Persist proxy configuration
- [ ] Add WebSocket support option
- [ ] Write functional tests

### API Specification

```http
POST /api/v1/proxys/wordpress001
X-API-Key: <key>
Content-Type: application/json

{
  "domain_names": ["myblog.example.com", "www.myblog.example.com"]
}

Response:
{
  "code": 200,
  "message": "Proxy host created successfully",
  "data": {
    "proxy_id": "123",
    "domain_names": ["myblog.example.com", "www.myblog.example.com"],
    "ssl_status": "pending",
    "created_at": "2026-01-05T10:30:00Z"
  }
}
```

### Test Scenarios

1. Create proxy with single domain succeeds
2. Create proxy with multiple domains succeeds
3. Create proxy with invalid domain format fails
4. Create proxy with duplicate domain fails
5. Domain validation catches common errors (missing TLD, spaces)

---

## Story 3: Let's Encrypt SSL Certificate Request

**Story ID:** PROXY-003  
**Priority:** P0  
**Estimated Effort:** 4 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** automatically obtain free SSL certificates for my domains  
**So that** I can secure my applications with HTTPS without manual certificate management

### Acceptance Criteria

✅ Certificate request completes in < 2 minutes  
✅ HTTP-01 challenge verification works automatically  
✅ Success rate > 95% for properly configured domains  
✅ Clear error messages for failed requests  
✅ Automatic force HTTPS after certificate obtained

### Technical Tasks

- [ ] Integrate Let's Encrypt ACME protocol via NPM
- [ ] Implement HTTP-01 challenge verification
- [ ] Add certificate request error handling
- [ ] Enable force SSL redirect after cert obtained
- [ ] Add DNS pre-validation check
- [ ] Write certificate request tests

### API Enhancement

```http
POST /api/v1/proxys/wordpress001
{
  "domain_names": ["myblog.example.com"],
  "ssl": {
    "enabled": true,
    "force": true,
    "email": "admin@example.com"
  }
}

Response:
{
  "data": {
    "proxy_id": "123",
    "ssl_status": "active",
    "certificate_expires_at": "2026-04-05T10:30:00Z",
    "ssl_rating": "A"
  }
}
```

### Test Scenarios

1. Certificate request succeeds for valid domain
2. Certificate request fails if domain not pointing to server
3. HTTP-01 challenge verification succeeds
4. Certificate properly attached to proxy host
5. Force HTTPS redirect works after certificate obtained
6. Error message clear when Let's Encrypt rate limit hit

---

## Story 4: SSL Certificate Auto-Renewal

**Story ID:** PROXY-004  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** automatically renew SSL certificates before they expire  
**So that** I don't experience downtime due to expired certificates

### Acceptance Criteria

✅ Daily check for certificates expiring within 30 days  
✅ Automatic renewal attempt for expiring certificates  
✅ Notification on renewal failure  
✅ Renewal success rate > 98%  
✅ Zero downtime during renewal

### Technical Tasks

- [ ] Implement scheduled task (cron/celery)
- [ ] Add certificate expiration monitoring
- [ ] Implement automatic renewal logic
- [ ] Add failure notification system
- [ ] Log all renewal attempts
- [ ] Write renewal simulation tests

### Implementation Notes

```python
class CertificateRenewalService:
    async def auto_renew_certificates(self):
        """Daily task to renew expiring certificates"""
        certificates = self.npm_api.get_certificates()
        
        for cert in certificates:
            if cert["provider"] != "letsencrypt":
                continue
            
            days_until_expiry = (cert["expires_at"] - datetime.now()).days
            
            if days_until_expiry <= 30:
                logger.info(f"Renewing certificate for {cert['domain_names']}")
                try:
                    self.npm_api.renew_certificate(cert["id"])
                except Exception as e:
                    logger.error(f"Renewal failed: {e}")
                    self.send_notification(cert, e)
```

### Test Scenarios

1. Certificate expiring in 25 days triggers renewal
2. Certificate expiring in 60 days does not trigger renewal
3. Renewal failure sends notification
4. Multiple certificates renewed in same run
5. Manual certificates (not Let's Encrypt) are skipped

---

## Story 5: Custom SSL Certificate Upload

**Story ID:** PROXY-005  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** upload my own SSL certificates  
**So that** I can use wildcard certificates or certificates from other providers

### Acceptance Criteria

✅ Support PEM format certificate upload  
✅ Validate certificate format before acceptance  
✅ Secure storage of private keys  
✅ Certificate chain validation  
✅ Display expiration date after upload

### Technical Tasks

- [ ] Implement certificate file upload endpoint
- [ ] Add PEM format validation
- [ ] Validate certificate chain completeness
- [ ] Secure private key storage (encryption)
- [ ] Parse certificate metadata (expiry, domains)
- [ ] Write upload validation tests

### API Specification

```http
POST /api/v1/proxys/ssl/certificates/upload
X-API-Key: <key>
Content-Type: multipart/form-data

certificate: <file>
private_key: <file>
intermediate_cert: <file> (optional)

Response:
{
  "code": 200,
  "message": "Certificate uploaded successfully",
  "data": {
    "certificate_id": "cert_123",
    "domain_names": ["*.example.com"],
    "expires_at": "2027-01-01T00:00:00Z",
    "issuer": "DigiCert Inc"
  }
}
```

### Test Scenarios

1. Valid certificate upload succeeds
2. Invalid PEM format rejected
3. Expired certificate rejected
4. Private key mismatch detected
5. Wildcard certificate accepted

---

## Story 6: Access Control Lists

**Story ID:** PROXY-006  
**Priority:** P2  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** restrict access to applications by IP address or authentication  
**So that** I can control who can access sensitive applications

### Acceptance Criteria

✅ IP whitelist blocks unauthorized IPs  
✅ IP blacklist blocks specific IPs  
✅ HTTP Basic Authentication works correctly  
✅ Access rules apply immediately  
✅ Rules can be updated without downtime

### Technical Tasks

- [ ] Implement access list configuration API
- [ ] Add IP whitelist/blacklist support
- [ ] Add HTTP Basic Authentication support
- [ ] Integrate with NPM access list feature
- [ ] Write access control tests

### API Specification

```http
PUT /api/v1/proxys/123/access-control
{
  "whitelist_ips": ["192.168.1.0/24"],
  "blacklist_ips": ["10.0.0.5"],
  "basic_auth": {
    "enabled": true,
    "username": "admin",
    "password": "secure123"
  }
}
```

### Test Scenarios

1. Whitelisted IP can access application
2. Non-whitelisted IP is blocked
3. Blacklisted IP is always blocked
4. Basic auth prompts for credentials
5. Correct credentials grant access

---

## Story 7: Proxy Configuration Update

**Story ID:** PROXY-007  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** update existing proxy configurations  
**So that** I can modify domains or settings without recreating proxies

### Acceptance Criteria

✅ Update domain names without downtime  
✅ Toggle SSL settings  
✅ Update access control rules  
✅ Changes apply in < 5 seconds  
✅ Configuration history tracked

### Technical Tasks

- [ ] Implement `/api/v1/proxys/{proxy_id}` PUT endpoint
- [ ] Support partial updates (PATCH semantics)
- [ ] Validate updated configuration
- [ ] Track configuration changes (audit log)
- [ ] Write update tests

### Test Scenarios

1. Update domain names succeeds
2. Enable SSL on existing proxy works
3. Disable force HTTPS works
4. Update with invalid data fails validation
5. Configuration history records all changes

---

## Story 8: Proxy List and Query

**Story ID:** PROXY-008  
**Priority:** P0  
**Estimated Effort:** 1 day (included in Story 2)  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** view all proxy configurations for an application  
**So that** I can see what domains are configured

### Acceptance Criteria

✅ List all proxies for specific application  
✅ Show SSL status for each proxy  
✅ Display certificate expiration dates  
✅ Fast query response (< 500ms)

### Technical Tasks

- [ ] Implement `/api/v1/proxys/{app_id}` GET endpoint
- [ ] Fetch proxy hosts from NPM
- [ ] Aggregate SSL certificate information
- [ ] Write query tests

### API Specification

```http
GET /api/v1/proxys/wordpress001
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": [
    {
      "proxy_id": "123",
      "domain_names": ["myblog.example.com"],
      "ssl_enabled": true,
      "ssl_forced": true,
      "certificate_expires_at": "2026-04-05T10:30:00Z"
    }
  ]
}
```

---

## Summary

This Epic provides comprehensive proxy and SSL management capabilities through Nginx Proxy Manager integration. The focus is on automation (auto-SSL, auto-renewal) while providing flexibility for advanced users (custom certificates, access control).

**Development Sequence:**
1. Story 1 (NPM API foundation)
2. Stories 2, 8 (Basic proxy CRUD)
3. Story 3 (SSL automation - highest value)
4. Story 4 (Auto-renewal - critical for production)
5. Stories 5, 6, 7 (Advanced features)

**Dependencies:**
- All stories depend on Story 1 (NPM API integration)
- Story 4 depends on Story 3 (SSL certificate management)
- Stories 6-7 enhance Story 2 (proxy management)

**Risk Mitigation:**
- Implement DNS validation before SSL request (Story 3)
- Add comprehensive error handling for Let's Encrypt rate limits
- Test renewal process in staging environment before production
- Monitor certificate expiration with alerts
