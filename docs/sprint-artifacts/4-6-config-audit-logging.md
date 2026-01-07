# Story 6: Configuration Audit Logging

**Story ID:** SETTINGS-006  
**Priority:** P2  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** see audit logs of all configuration changes  
**So that** I can track who changed what and when

## Acceptance Criteria

✅ All config changes logged  
✅ Log includes: timestamp, section, key, action, user (if available)  
✅ Log stored securely  
✅ Log rotation to prevent disk fill  
✅ Query logs by date range  
✅ Query logs by section

## Technical Tasks

- [ ] Implement audit log writer
- [ ] Add logging to all config update operations
- [ ] Implement log query API
- [ ] Add log rotation (by size or date)
- [ ] Write audit log tests

## Log Format

```json
{
  "timestamp": "2026-01-05T10:30:00Z",
  "action": "config_change",
  "section": "portainer",
  "key": "password",
  "operation": "update",
  "user": "admin",
  "ip_address": "192.168.1.100"
}
```

## Test Scenarios

1. Config update creates audit log entry
2. Query logs by date range works
3. Query logs by section works
4. Old logs rotated automatically
5. Log format is valid JSON
