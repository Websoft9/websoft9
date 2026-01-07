# Story 5: Configuration Backup & Restore

**Story ID:** SETTINGS-005  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** backup and restore system configuration  
**So that** I can recover from configuration errors or migrate settings

## Acceptance Criteria

✅ Automatic backup before each update  
✅ Manual backup on demand  
✅ Restore from specific backup version  
✅ List available backups  
✅ Backup retention policy (keep last 10)  
✅ Backup includes timestamp in filename

## Technical Tasks

- [ ] Implement auto-backup on config update
- [ ] Implement manual backup API endpoint
- [ ] Implement restore API endpoint
- [ ] Implement backup listing endpoint
- [ ] Add backup cleanup (retention policy)
- [ ] Write backup/restore tests

## API Specification

```http
POST /api/v1/settings/backup
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "backup_file": "config/backups/config_20260105_103000.ini",
    "created_at": "2026-01-05T10:30:00Z"
  }
}

POST /api/v1/settings/restore
{
  "backup_file": "config/backups/config_20260105_103000.ini"
}

GET /api/v1/settings/backups
Response:
{
  "data": {
    "backups": [
      {
        "file": "config_20260105_103000.ini",
        "created_at": "2026-01-05T10:30:00Z",
        "size_bytes": 2048
      }
    ]
  }
}
```

## Test Scenarios

1. Manual backup creates timestamped file
2. Auto-backup runs before config update
3. Restore replaces current config
4. Restore creates backup of current config first
5. Old backups cleaned up per retention policy
6. List backups returns all available backups
