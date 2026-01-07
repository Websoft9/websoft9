# Story 8: Proxy List and Query

**Story ID:** PROXY-008  
**Priority:** P0  
**Estimated Effort:** 1 day (included in Story 2)  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** view all proxy configurations for an application  
**So that** I can see what domains are configured

## Acceptance Criteria

✅ List all proxies for specific application  
✅ Show SSL status for each proxy  
✅ Display certificate expiration dates  
✅ Fast query response (< 500ms)

## Technical Tasks

- [ ] Implement `/api/v1/proxys/{app_id}` GET endpoint
- [ ] Fetch proxy hosts from NPM
- [ ] Aggregate SSL certificate information
- [ ] Write query tests

## API Specification

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
