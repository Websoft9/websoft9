# Story 1: Configuration Read API

**Story ID:** SETTINGS-001  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** retrieve system configuration settings  
**So that** I can view current system parameters and troubleshoot issues

## Acceptance Criteria

✅ Configuration retrieval in < 100ms  
✅ Sensitive values masked (passwords, tokens)  
✅ Support retrieving all settings or specific sections  
✅ JSON response format  
✅ Proper error handling for missing config files

## Technical Tasks

- [ ] Implement `/api/v1/settings` GET endpoint
- [ ] Implement `/api/v1/settings/{section}` GET endpoint
- [ ] Create ConfigManager class with INI file parsing
- [ ] Add sensitive value masking logic
- [ ] Handle missing config files gracefully
- [ ] Write configuration read tests

## API Specification

```http
GET /api/v1/settings
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "portainer": {
      "url": "http://portainer:9000",
      "username": "admin",
      "password": "******"
    },
    "nginx_proxy_manager": {
      "url": "http://nginx-proxy-manager:81",
      "admin_email": "admin@example.com",
      "admin_password": "******"
    },
    "apphub": {
      "media_url": "https://websoft9.github.io/docker-library/media.json",
      "cache_duration": 3600
    }
  }
}
```

## Test Scenarios

1. GET all settings returns complete configuration
2. GET specific section returns only that section
3. Passwords are masked with "******"
4. Encrypted values are masked
5. Missing config file returns appropriate error
6. Invalid section name returns 404
