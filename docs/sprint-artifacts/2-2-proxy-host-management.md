# Story 2: Proxy Host Management

**Story ID:** PROXY-002  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** create reverse proxy configurations for my applications  
**So that** I can access applications via custom domain names

## Acceptance Criteria

✅ Proxy host created in < 30 seconds  
✅ Support multiple domain names per proxy  
✅ Automatic domain format validation  
✅ Check for domain conflicts before creation  
✅ Support for WebSocket applications

## Technical Tasks

- [ ] Implement `/api/v1/proxys/{app_id}` POST endpoint
- [ ] Add domain name validation (regex)
- [ ] Check domain uniqueness across all proxies
- [ ] Persist proxy configuration
- [ ] Add WebSocket support option
- [ ] Write functional tests

## API Specification

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

## Test Scenarios

1. Create proxy with single domain succeeds
2. Create proxy with multiple domains succeeds
3. Create proxy with invalid domain format fails
4. Create proxy with duplicate domain fails
5. Domain validation catches common errors (missing TLD, spaces)
