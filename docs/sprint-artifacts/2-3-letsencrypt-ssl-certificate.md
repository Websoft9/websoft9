# Story 3: Let's Encrypt SSL Certificate Request

**Story ID:** PROXY-003  
**Priority:** P0  
**Estimated Effort:** 4 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** automatically obtain free SSL certificates for my domains  
**So that** I can secure my applications with HTTPS without manual certificate management

## Acceptance Criteria

✅ Certificate request completes in < 2 minutes  
✅ HTTP-01 challenge verification works automatically  
✅ Success rate > 95% for properly configured domains  
✅ Clear error messages for failed requests  
✅ Automatic force HTTPS after certificate obtained

## Technical Tasks

- [ ] Integrate Let's Encrypt ACME protocol via NPM
- [ ] Implement HTTP-01 challenge verification
- [ ] Add certificate request error handling
- [ ] Enable force SSL redirect after cert obtained
- [ ] Add DNS pre-validation check
- [ ] Write certificate request tests

## API Enhancement

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

## Test Scenarios

1. Certificate request succeeds for valid domain
2. Certificate request fails if domain not pointing to server
3. HTTP-01 challenge verification succeeds
4. Certificate properly attached to proxy host
5. Force HTTPS redirect works after certificate obtained
6. Error message clear when Let's Encrypt rate limit hit
