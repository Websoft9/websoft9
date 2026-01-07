# Story 6: Backup Management API

**Story ID:** BACKUP-006  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** view, download, and delete backups  
**So that** I can manage backup storage and retrieve backups when needed

## Acceptance Criteria

✅ List backups in < 1 second  
✅ Filter backups by application  
✅ Sort by date, size  
✅ Download backup files  
✅ Delete individual backups  
✅ Show storage space used

## Technical Tasks

- [ ] Implement `/api/v1/backup/snapshots` GET endpoint
- [ ] Add filtering and sorting
- [ ] Implement snapshot deletion endpoint
- [ ] Add backup download endpoint
- [ ] Calculate storage usage
- [ ] Write API tests

## API Specification

```http
GET /api/v1/backup/snapshots?app_id=wordpress001&sort=created_at
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "total": 15,
    "total_size_bytes": 5368709120,
    "snapshots": [
      {
        "backup_id": "backup_20260105_103000",
        "app_id": "wordpress001",
        "size_bytes": 524288000,
        "created_at": "2026-01-05T10:30:00Z",
        "status": "completed",
        "storage_location": "local"
      }
    ]
  }
}
```

## Test Scenarios

1. List all backups returns complete list
2. Filter by app_id works correctly
3. Sort by date works (newest first)
4. Delete backup removes file and metadata
5. Download backup returns correct file
6. Storage usage calculation accurate
