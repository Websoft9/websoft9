# Epic 3: Backup & Restore - User Stories

**Epic:** [Backup & Restore Epic](../epics/backup-restore-epic.md)  
**Total Stories:** 8  
**Total Estimated Effort:** 25 days  
**Priority Distribution:** P0 (4), P1 (3), P2 (1)

---

## Story 1: Backup Core Engine

**Story ID:** BACKUP-001  
**Priority:** P0  
**Estimated Effort:** 5 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** create full backups of application data  
**So that** I can protect against data loss and disasters

### Acceptance Criteria

✅ Backup completes in < 5 minutes for 10GB data  
✅ Compressed backup file size < 1.5x original data  
✅ File integrity verified with SHA256 checksum  
✅ Support for encryption (optional)  
✅ Atomic backup operation (all or nothing)  
✅ Minimal impact on running applications

### Technical Tasks

- [ ] Implement Docker volume export logic
- [ ] Add file compression (gzip, tar.gz)
- [ ] Implement file encryption with Fernet
- [ ] Add SHA256 checksum calculation
- [ ] Create backup metadata database
- [ ] Write backup engine tests
- [ ] Optimize for large files (streaming)

### Implementation Notes

```python
class BackupManager:
    def create_backup(self, app_id: str, config: Dict) -> Backup:
        """
        Backup workflow:
        1. Get application volumes
        2. Export volumes to tar files
        3. Compress files
        4. Encrypt (if enabled)
        5. Calculate checksum
        6. Store metadata
        """
```

### Test Scenarios

1. Backup 1GB application completes successfully
2. Compressed backup is smaller than original
3. Checksum verification passes
4. Encrypted backup can be decrypted
5. Backup fails gracefully on disk full
6. Concurrent backups handled correctly

---

## Story 2: Database Backup Integration

**Story ID:** BACKUP-002  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** backup application databases separately  
**So that** I can ensure database consistency and enable point-in-time recovery

### Acceptance Criteria

✅ Support MySQL/MariaDB (mysqldump)  
✅ Support PostgreSQL (pg_dump)  
✅ Support MongoDB (mongodump)  
✅ Database backup is consistent (transaction-safe)  
✅ Minimal downtime during backup  
✅ Backup includes schema and data

### Technical Tasks

- [ ] Implement MySQL backup integration
- [ ] Implement PostgreSQL backup integration
- [ ] Implement MongoDB backup integration
- [ ] Add database connection detection
- [ ] Handle database credentials securely
- [ ] Write database backup tests

### Implementation Notes

```python
def _backup_mysql(self, app_id: str, app: Dict) -> str:
    """Execute mysqldump via Docker exec"""
    cmd = [
        "docker", "exec", container_name,
        "mysqldump",
        "-u", username,
        f"-p{password}",
        "--single-transaction",
        "--routines",
        "--triggers",
        database_name
    ]
    return self._execute_dump(cmd, output_file)
```

### Test Scenarios

1. MySQL database backed up successfully
2. PostgreSQL database backed up successfully
3. MongoDB database backed up successfully
4. Backup includes all tables and data
5. Restored database is consistent
6. Credentials handled securely (not logged)

---

## Story 3: Backup Restore Functionality

**Story ID:** BACKUP-003  
**Priority:** P0  
**Estimated Effort:** 4 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** restore applications from backups  
**So that** I can recover from data loss or migrate applications

### Acceptance Criteria

✅ Restore completes in < 10 minutes for 10GB backup  
✅ Application automatically restarted after restore  
✅ Data integrity verified before restore  
✅ Rollback on restore failure  
✅ Restore success rate > 98%  
✅ Preserve original permissions

### Technical Tasks

- [ ] Implement backup file validation
- [ ] Add decryption logic
- [ ] Implement decompression
- [ ] Add volume restore functionality
- [ ] Implement database restore
- [ ] Add application restart after restore
- [ ] Write restore tests with real backups

### API Specification

```http
POST /api/v1/backup/restore/wordpress001/{snapshot_id}
X-API-Key: <key>
Content-Type: application/json

{
  "stop_app": true,
  "restore_database": true,
  "backup_before_restore": true
}

Response:
{
  "code": 200,
  "message": "Restore completed successfully",
  "data": {
    "app_id": "wordpress001",
    "snapshot_id": "backup_20260105_103000",
    "restored_volumes": 3,
    "database_restored": true,
    "duration_seconds": 245
  }
}
```

### Test Scenarios

1. Restore from valid backup succeeds
2. Checksum verification prevents corrupt restore
3. Application stopped during restore
4. Application restarted after successful restore
5. Restore fails if backup file missing
6. Current state backed up before restore (safety)

---

## Story 4: Scheduled Backups

**Story ID:** BACKUP-004  
**Priority:** P1  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** schedule automatic backups  
**So that** I don't have to remember to backup manually

### Acceptance Criteria

✅ Support daily, weekly, monthly schedules  
✅ Configurable time for backup execution  
✅ Automatic cleanup of old backups based on retention policy  
✅ Backup schedule persists across restarts  
✅ Failed backups trigger notifications  
✅ Multiple schedules per application

### Technical Tasks

- [ ] Implement backup schedule configuration API
- [ ] Add cron-like scheduler (or use Celery Beat)
- [ ] Implement automatic old backup cleanup
- [ ] Add schedule persistence (database)
- [ ] Implement failure notification system
- [ ] Write scheduler tests

### API Specification

```http
POST /api/v1/backup/schedules
{
  "app_id": "wordpress001",
  "enabled": true,
  "frequency": "daily",
  "time": "02:00",
  "retention_days": 30,
  "backup_type": "full",
  "storage_location": "local"
}
```

### Implementation Notes

```python
class BackupScheduler:
    def start(self):
        """Start scheduled backup service"""
        schedules = self._load_schedules()
        
        for sched in schedules:
            if sched.frequency == "daily":
                schedule.every().day.at(sched.time).do(
                    self._run_scheduled_backup, sched
                )
```

### Test Scenarios

1. Daily backup executes at configured time
2. Weekly backup executes on correct day
3. Old backups cleaned up per retention policy
4. Disabled schedules don't execute
5. Failed backup sends notification
6. Schedule persists after service restart

---

## Story 5: S3 Remote Backup

**Story ID:** BACKUP-005  
**Priority:** P2  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** store backups on Amazon S3 or compatible storage  
**So that** I have off-site backups for disaster recovery

### Acceptance Criteria

✅ Upload to S3 in < 10 minutes for 5GB backup  
✅ Support S3-compatible storage (MinIO, Wasabi)  
✅ Resumable uploads for large files  
✅ Automatic retry on network failure  
✅ Backup encrypted before upload  
✅ Download from S3 for restore

### Technical Tasks

- [ ] Integrate Boto3 SDK
- [ ] Implement multipart upload for large files
- [ ] Add upload progress tracking
- [ ] Implement resumable upload
- [ ] Add S3 download for restore
- [ ] Write S3 integration tests (with mocked S3)

### Configuration

```yaml
backup:
  storage:
    s3_bucket: "websoft9-backups"
    s3_region: "us-east-1"
    s3_access_key: "${AWS_ACCESS_KEY_ID}"
    s3_secret_key: "${AWS_SECRET_ACCESS_KEY}"
    s3_endpoint: "https://s3.amazonaws.com"  # Or MinIO endpoint
```

### Test Scenarios

1. Upload to S3 succeeds
2. Large file uses multipart upload
3. Network failure triggers retry
4. Download from S3 for restore works
5. S3-compatible storage (MinIO) works
6. Invalid credentials fail gracefully

---

## Story 6: Backup Management API

**Story ID:** BACKUP-006  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** view, download, and delete backups  
**So that** I can manage backup storage and retrieve backups when needed

### Acceptance Criteria

✅ List backups in < 1 second  
✅ Filter backups by application  
✅ Sort by date, size  
✅ Download backup files  
✅ Delete individual backups  
✅ Show storage space used

### Technical Tasks

- [ ] Implement `/api/v1/backup/snapshots` GET endpoint
- [ ] Add filtering and sorting
- [ ] Implement snapshot deletion endpoint
- [ ] Add backup download endpoint
- [ ] Calculate storage usage
- [ ] Write API tests

### API Specification

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

### Test Scenarios

1. List all backups returns complete list
2. Filter by app_id works correctly
3. Sort by date works (newest first)
4. Delete backup removes file and metadata
5. Download backup returns correct file
6. Storage usage calculation accurate

---

## Story 7: Incremental Backup

**Story ID:** BACKUP-007  
**Priority:** P1  
**Estimated Effort:** 4 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** perform incremental backups  
**So that** I can reduce backup time and storage space

### Acceptance Criteria

✅ Incremental backup only includes changed files  
✅ Backup time < 50% of full backup  
✅ Storage space < 30% of full backup (for typical changes)  
✅ Restore from incremental requires base backup  
✅ Automatic base backup after N incremental backups

### Technical Tasks

- [ ] Implement file change detection (modified time, hash)
- [ ] Add incremental backup logic
- [ ] Track backup chain (base + incrementals)
- [ ] Implement restore from incremental chain
- [ ] Add automatic full backup after N incrementals
- [ ] Write incremental backup tests

### Test Scenarios

1. First backup is always full
2. Incremental backup smaller than full
3. Restore from base + incremental works
4. Change detection accurate
5. Auto full backup after 7 incrementals

---

## Story 8: Backup Verification

**Story ID:** BACKUP-008  
**Priority:** P0  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** verify backup integrity without full restore  
**So that** I can ensure backups are valid for disaster recovery

### Acceptance Criteria

✅ Verification completes in < 1 minute  
✅ Checksum validation catches corrupted backups  
✅ Archive structure validation  
✅ Verification doesn't modify backup file  
✅ Verification report shows what's included

### Technical Tasks

- [ ] Implement checksum verification
- [ ] Add archive structure validation
- [ ] Create verification report
- [ ] Add verification API endpoint
- [ ] Write verification tests

### API Specification

```http
POST /api/v1/backup/snapshots/{snapshot_id}/verify
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "snapshot_id": "backup_20260105_103000",
    "valid": true,
    "checksum_match": true,
    "contains": {
      "volumes": 3,
      "databases": 1,
      "config_files": 5
    }
  }
}
```

---

## Summary

This Epic provides comprehensive backup and disaster recovery capabilities. The focus is on reliability and automation while supporting both local and remote storage options.

**Development Sequence:**
1. Stories 1, 8 (Core backup engine + verification)
2. Story 2 (Database backup)
3. Story 3 (Restore capability - critical)
4. Story 6 (Management API)
5. Story 4 (Automation)
6. Stories 5, 7 (Advanced features)

**Dependencies:**
- Story 3 depends on Stories 1, 2 (backup must exist to restore)
- Story 4 depends on Story 1 (scheduled backups use core engine)
- Story 5 can be developed in parallel with Story 4
- Story 7 depends on Story 1 (incremental builds on full backup)

**Risk Mitigation:**
- Implement thorough verification (Story 8) before allowing restore
- Always backup current state before restore (Story 3)
- Test restore process regularly in non-production environment
- Monitor backup success/failure rates
- Implement alerting for backup failures
- Encrypt backups before S3 upload for security
