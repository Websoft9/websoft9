# Epic: Reverse Proxy Management

**Related PRD:** [FR-PROXY-001]
**Owner:** Product Manager  
**Status:** In Development  
**Priority:** P0 (Required)  
**Estimated Effort:** 3-4 weeks

---

## 1. Epic Overview

### 1.1 Business Objectives

Provide reverse proxy configuration and automated SSL certificate management for applications through Nginx Proxy Manager, enabling domain access and HTTPS encryption.

### 1.2 Core Value

- Applications accessible via custom domain names
- Automatic Let's Encrypt SSL certificate requests and renewals
- Support for forced HTTPS redirect
- Access control (IP whitelist/blacklist)
- Support for custom SSL certificate upload
- HTTP Basic Authentication protection

### 1.3 Acceptance Criteria

✅ Proxy host creation time < 30 seconds  
✅ Let's Encrypt certificate auto-request success rate > 95%  
✅ SSL certificates auto-renew (30 days before expiration)  
✅ SSL Labs rating A or higher  
✅ Proxy configuration changes take effect < 5 seconds  
✅ Support wildcard domain certificates

---

## 2. Technical Specifications

### 2.1 Architecture Design

#### System Architecture

```
User Domain Request → Nginx Proxy Manager → Backend Application Container
                              ↓
                      Let's Encrypt (ACME)
```

#### Proxy Workflow

```
Domain Resolution → NPM Reverse Proxy → Docker Network → App Container:Port
                          ↓
                  SSL Certificate Verification & Encryption
```

### 2.2 API Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/proxys/{app_id}` | GET | Get application proxy configuration list | API Key |
| `/api/v1/proxys/{app_id}` | POST | Create proxy host (supports multiple domains) | API Key |
| `/api/v1/proxys/{proxy_id}` | PUT | Update proxy configuration (by proxy_id) | API Key |
| `/api/v1/proxys/{proxy_id}` | DELETE | Delete proxy (by proxy_id) | API Key |
| `/api/v1/proxys/ssl/certificates` | GET | Get SSL certificate list | API Key |

#### Example: Create Proxy Host

**Request:**
```http
POST /api/v1/proxys/wordpress001
X-API-Key: <key>
Content-Type: application/json

{
  "domain_names": ["myblog.example.com", "www.myblog.example.com"]
}
```

**Response:**
```json
{
  "code": 200,
  "message": "Proxy host created successfully",
  "data": {
    "proxy_id": "123",
    "domain_names": ["myblog.example.com", "www.myblog.example.com"],
    "ssl_status": "pending",
    "certificate_expires_at": null,
    "created_at": "2026-01-05T10:30:00Z"
  }
}
```

### 2.3 Data Models

#### NPM Proxy Host Configuration

```python
class ProxyHost(BaseModel):
    proxy_id: int                      # NPM Proxy Host ID
    app_id: str                        # Associated application ID
    domain_names: List[str]            # Domain name list
    forward_host: str                  # Forward target host
    forward_port: int                  # Forward target port
    forward_scheme: str                # http or https
    ssl_enabled: bool                  # SSL enabled
    ssl_forced: bool                   # Force HTTPS
    certificate_id: Optional[int]      # SSL certificate ID
    access_list_id: Optional[int]      # Access control list ID
    enable_websocket: bool             # WebSocket support
    http2_support: bool                # HTTP/2 support
    hsts_enabled: bool                 # HSTS enabled
```

#### SSL Certificate

```python
class SSLCertificate(BaseModel):
    id: int
    provider: str                      # letsencrypt, custom, other
    domain_names: List[str]
    expires_at: datetime
    is_valid: bool
    meta: Dict[str, Any]               # Certificate metadata
```

### 2.4 Core Service Design

#### nginx_proxy_manager.py

```python
class NginxProxyManagerAPI:
    def __init__(self):
        self.base_url = "http://nginx-proxy-manager:81/api"
        self.token = self.get_token()
    
    def get_token(self) -> str:
        """Get NPM API Token"""
        response = requests.post(
            f"{self.base_url}/tokens",
            json={
                "identity": os.getenv("NPM_USER"),
                "secret": os.getenv("NPM_PASSWORD")
            }
        )
        return response.json()["token"]
    
    def create_proxy_host(self, config: Dict) -> Dict:
        """
        Create proxy host:
        1. Validate domain format
        2. Check if domain already used
        3. Create Proxy Host
        4. If SSL enabled, request Let's Encrypt certificate
        5. Return proxy configuration
        """
        url = f"{self.base_url}/nginx/proxy-hosts"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        payload = {
            "domain_names": config["domain_names"],
            "forward_host": config["forward_host"],
            "forward_port": config["forward_port"],
            "forward_scheme": config["forward_scheme"],
            "certificate_id": config.get("certificate_id"),
            "ssl_forced": config.get("ssl_forced", False),
            "meta": {
                "letsencrypt_agree": True,
                "letsencrypt_email": config.get("letsencrypt_email"),
                "dns_challenge": False
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def update_proxy_host(self, proxy_id: int, config: Dict) -> Dict:
        """Update proxy configuration"""
        url = f"{self.base_url}/nginx/proxy-hosts/{proxy_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(url, json=config, headers=headers)
        return response.json()
    
    def delete_proxy_host(self, proxy_id: int) -> None:
        """Delete proxy host"""
        url = f"{self.base_url}/nginx/proxy-hosts/{proxy_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        requests.delete(url, headers=headers)
    
    def request_letsencrypt_cert(self, proxy_id: int, email: str, 
                                  domains: List[str]) -> Dict:
        """Request Let's Encrypt certificate"""
        url = f"{self.base_url}/nginx/certificates"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        payload = {
            "provider": "letsencrypt",
            "domain_names": domains,
            "meta": {
                "letsencrypt_email": email,
                "letsencrypt_agree": True
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        cert = response.json()
        
        # Associate certificate with proxy host
        self.update_proxy_host(proxy_id, {"certificate_id": cert["id"]})
        return cert
```

### 2.5 Let's Encrypt Certificate Auto-Renewal

```python
class CertificateRenewalService:
    def __init__(self):
        self.npm_api = NginxProxyManagerAPI()
    
    async def auto_renew_certificates(self):
        """
        Scheduled task: Auto-renew certificates
        - Daily check
        - Auto-renew 30 days before expiration
        """
        certificates = self.npm_api.get_certificates()
        
        for cert in certificates:
            if cert["provider"] != "letsencrypt":
                continue
            
            days_until_expiry = (cert["expires_at"] - datetime.now()).days
            
            if days_until_expiry <= 30:
                logger.info(f"Renewing certificate for {cert['domain_names']}")
                try:
                    self.npm_api.renew_certificate(cert["id"])
                    logger.info(f"Certificate renewed: {cert['id']}")
                except Exception as e:
                    logger.error(f"Certificate renewal failed: {e}")
```

### 2.6 Configuration

```yaml
# config/proxy.yaml
nginx_proxy_manager:
  url: "http://nginx-proxy-manager:81"
  api_url: "http://nginx-proxy-manager:81/api"
  admin_email: "${NPM_ADMIN_EMAIL}"
  admin_password: "${NPM_ADMIN_PASSWORD}"
  
  ssl:
    provider: "letsencrypt"
    auto_renew: true
    renew_before_days: 30
    challenge_type: "http-01"  # http-01 or dns-01
  
  defaults:
    forward_scheme: "http"
    ssl_forced: true
    http2_support: true
    hsts_enabled: true
    hsts_max_age: 31536000
    websocket_support: false
```

---

## 3. Story Breakdown

### Story 1: NPM API Integration

**Priority:** P0  
**Effort:** 3 days

**Tasks:**
- Implement NPM Token authentication
- Wrap proxy host CRUD interfaces
- Error handling and retry mechanism
- Write API integration tests

### Story 2: Proxy Host Management

**Priority:** P0  
**Effort:** 3 days

**Tasks:**
- Implement create proxy host endpoint
- Domain format validation
- Proxy configuration persistence
- Write functional tests

### Story 3: Let's Encrypt Certificate Request

**Priority:** P0  
**Effort:** 4 days

**Tasks:**
- Integrate Let's Encrypt ACME workflow
- HTTP-01 challenge validation
- Certificate request failure handling
- Write certificate request tests

### Story 4: SSL Certificate Auto-Renewal

**Priority:** P1  
**Effort:** 2 days

**Tasks:**
- Implement scheduled check task
- Certificate expiration monitoring
- Auto-renewal logic
- Renewal failure alerts
- Write renewal tests

### Story 5: Custom SSL Certificate Upload

**Priority:** P1  
**Effort:** 2 days

**Tasks:**
- Certificate file upload interface
- Certificate format validation (PEM)
- Private key secure storage
- Write upload tests

### Story 6: Access Control Lists

**Priority:** P2  
**Effort:** 2 days

**Tasks:**
- IP whitelist/blacklist configuration
- HTTP Basic Authentication
- Access control rule validation
- Write access control tests

---

## 4. Dependencies

### Technical Dependencies

- **Nginx Proxy Manager** 2.10+
- **Let's Encrypt** ACME v2
- **FastAPI** 0.104+
- **Certbot** (built into NPM)

### Module Dependencies

- **Application Management Module** - Get application container info
- **Configuration Module** - Read proxy configuration
- **Logging Module** - Record certificate operations

### External Dependencies

- **DNS Resolution** - Domain must correctly resolve to server
- **Ports 80/443 Open** - Let's Encrypt HTTP-01 validation

---

## 5. Risks & Challenges

| Risk | Level | Mitigation |
|------|-------|------------|
| Let's Encrypt rate limiting | High | Use DNS-01 challenge, avoid repeated requests |
| Certificate request failures | High | Detailed error logs, DNS pre-check |
| Domain not resolving to server | Medium | DNS validation before installation |
| NPM API changes | Medium | API version locking, change monitoring |
| Certificate renewal failures | High | Renew 30 days early, failure alerts |

---

## 6. Testing Strategy

### Unit Tests

- Domain format validation
- Proxy configuration generation
- Token authentication logic
- API response parsing

### Integration Tests

- Complete proxy creation workflow
- Let's Encrypt certificate request (test environment)
- Certificate renewal simulation
- Proxy deletion cleanup

### Manual Tests

- Real domain SSL certificate request
- SSL Labs rating verification
- Browser HTTPS access
- Force HTTPS redirect verification

---

## 7. Monitoring Metrics

```python
# Prometheus metrics
proxy_host_total                       # Total proxy hosts
proxy_host_create_success_total        # Successful creations
proxy_host_create_failed_total         # Failed creations
ssl_certificate_total                  # Total SSL certificates
ssl_certificate_expiring_soon          # Certificates expiring soon
ssl_certificate_renew_success_total    # Successful renewals
ssl_certificate_renew_failed_total     # Failed renewals
proxy_api_request_duration_seconds     # API response time
```

---

## Appendix

### A. Error Code Definitions

| Error Code | HTTP | Description |
|------------|------|-------------|
| PROXY_DOMAIN_INVALID | 400 | Invalid domain format |
| PROXY_DOMAIN_CONFLICT | 409 | Domain already in use |
| PROXY_NOT_FOUND | 404 | Proxy configuration not found |
| SSL_CERT_REQUEST_FAILED | 500 | SSL certificate request failed |
| SSL_CERT_INVALID | 400 | Invalid SSL certificate format |
| NPM_API_ERROR | 502 | NPM API error |
| DNS_RESOLUTION_FAILED | 400 | Domain not resolving to server |

### B. Let's Encrypt Rate Limits

- **Certificates per domain:** 50/week
- **Duplicate certificates:** 5/week
- **Failed validations:** 5/account/hour
- **New accounts:** 10/IP/3 hours

### C. Related Documentation

- [PRD - Reverse Proxy & SSL Management](../prd.md#22-反向代理与-ssl-管理)
- [Nginx Proxy Manager Documentation](https://nginxproxymanager.com/guide/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

---

**Document Maintainer:** PM Agent  
**Last Updated:** 2026-01-05
