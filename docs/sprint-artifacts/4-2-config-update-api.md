# Story 2: Configuration Update API

**Story ID:** SETTINGS-002  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** update system configuration settings  
**So that** I can modify system behavior without manually editing config files

## Acceptance Criteria

✅ Configuration updates apply immediately  
✅ Input validation before saving  
✅ Atomic updates (all or nothing)  
✅ Configuration backup before update  
✅ Audit log of all changes  
✅ Support for query parameter-based updates

## Technical Tasks

- [ ] Implement `/api/v1/settings/{section}?key=xx&value=yy` PUT endpoint
- [ ] Add configuration validation logic
- [ ] Implement atomic file write (write to temp, then rename)
- [ ] Add automatic configuration backup
- [ ] Implement audit logging
- [ ] Write configuration update tests

## API Specification

```http
PUT /api/v1/settings/portainer?key=password&value=new_password_123
X-API-Key: <key>

Response:
{
  "code": 200,
  "message": "Configuration updated successfully",
  "data": {
    "section": "portainer",
    "key": "password",
    "value": "******",
    "updated_at": "2026-01-05T10:30:00Z"
  }
}
```

## Test Scenarios

1. Update valid configuration succeeds
2. Invalid value fails validation
3. Update creates backup of old config
4. Audit log records the change
5. Update with missing section creates section
6. Concurrent updates handled safely
