# Epic: Backup & Restore

**Related PRD:** [FR-BACKUP-001]
**Owner:** Product Manager  
**Status:** Planning  
**Priority:** P1 (Important)  
**Estimated Effort:** 3-4 weeks

---

## 1. Epic Overview

### 1.1 Business Objectives

Provide application data and system configuration backup/restore capabilities to ensure data security and business continuity.

### 1.2 Core Value

- Regular automatic application data backups
- Support manual backup and restore
- Encrypted backup data storage
- Backup to local or remote storage (S3)
- One-click restore to specific point in time
- Flexible backup policy configuration

### 1.3 Acceptance Criteria

✅ Application data backup completion time < 5 minutes (10GB)  
✅ Backup files encrypted storage  
✅ Support incremental backups  
✅ Restore success rate > 98%  
✅ Backup space usage < 1.5x original data  
✅ Support remote backup to S3  

---

## 2. Technical Specifications

### 2.1 Architecture Design

#### Backup Architecture

```
Application Data Volumes → Backup Engine → Compress & Encrypt → Local Storage / S3
                                ↓
                    Backup Metadata Records (SQLite/PostgreSQL)
```

#### Restore Workflow

```
Backup File → Verify Integrity → Decrypt & Decompress → Restore to Volumes → Restart App
```

### 2.2 API Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/backup/snapshots` | GET | Get snapshot list (filter by app_id) | API Key |
| `/api/v1/backup/{app_id}` | POST | Create backup snapshot | API Key |
| `/api/v1/backup/snapshots/{snapshot_id}` | DELETE | Delete snapshot | API Key |
| `/api/v1/backup/restore/{app_id}/{snapshot_id}` | POST | Restore snapshot | API Key |

#### Example: Create Backup

**Request:**
```http
POST /api/v1/backup/wordpress001
X-API-Key: <key>
```

**Response:**
```json
{
  "code": 200,
  "message": "Backup created successfully",
  "data": {
    "backup_id": "backup_20260105_103000",
    "app_id": "wordpress001",
    "backup_type": "full",
    "size_bytes": 524288000,
    "created_at": "2026-01-05T10:30:00Z",
    "storage_location": "local",
    "file_path": "/var/websoft9/backups/wordpress001/backup_20260105_103000.tar.gz.enc",
    "status": "completed"
  }
}
```

### 2.3 Data Models

#### Backup Record

```python
class Backup(BaseModel):
    backup_id: str                     # Unique backup identifier
    app_id: str                        # Application ID
    app_name: str                      # Application name
    backup_type: str                   # full, incremental, differential
    description: Optional[str]
    size_bytes: int                    # Backup size
    compressed: bool                   # Compressed
    encrypted: bool                    # Encrypted
    storage_location: str              # local, s3
    file_path: str                     # Backup file path
    s3_bucket: Optional[str]           # S3 bucket name
    s3_key: Optional[str]              # S3 object key
    checksum: str                      # Checksum (SHA256)
    status: str                        # pending, in_progress, completed, failed
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
```

#### Backup Schedule

```python
class BackupSchedule(BaseModel):
    schedule_id: str
    app_id: str
    enabled: bool
    frequency: str                     # daily, weekly, monthly
    time: str                          # HH:MM
    day_of_week: Optional[int]         # 0-6 (Sunday-Saturday)
    day_of_month: Optional[int]        # 1-31
    retention_days: int                # Retention days
    backup_type: str
    include_database: bool
    include_uploads: bool
    storage_location: str
```

### 2.4 Core Service Design

#### backup_manager.py

```python
import tarfile
import hashlib
from cryptography.fernet import Fernet
import subprocess

class BackupManager:
    def __init__(self):
        self.backup_dir = "/var/websoft9/backups"
        self.encryption_key = os.getenv("BACKUP_ENCRYPTION_KEY")
        self.cipher = Fernet(self.encryption_key.encode())
    
    def create_backup(self, app_id: str, config: Dict) -> Backup:
        """
        Backup workflow:
        1. Stop application (optional)
        2. Export Docker data volumes
        3. Export database (if needed)
        4. Compress files
        5. Encrypt backup (if needed)
        6. Calculate checksum
        7. Upload to storage (local/S3)
        8. Record backup metadata
        9. Restart application
        """
        backup_id = self._generate_backup_id(app_id)
        backup = Backup(
            backup_id=backup_id,
            app_id=app_id,
            backup_type=config["backup_type"],
            status="in_progress",
            created_at=datetime.now()
        )
        
        try:
            # 1. Get application data volumes
            volumes = self._get_app_volumes(app_id)
            
            # 2. Export data volumes
            volume_backup_path = self._backup_volumes(app_id, volumes)
            
            # 3. Export database (if needed)
            if config.get("include_database"):
                db_backup_path = self._backup_database(app_id)
                volume_backup_path.append(db_backup_path)
            
            # 4. Compress
            if config.get("compress", True):
                compressed_file = self._compress_files(
                    volume_backup_path, 
                    backup_id
                )
            
            # 5. Encrypt
            if config.get("encrypt", True):
                encrypted_file = self._encrypt_file(compressed_file)
                final_file = encrypted_file
            else:
                final_file = compressed_file
            
            # 6. Calculate checksum
            checksum = self._calculate_checksum(final_file)
            
            # 7. Upload to storage
            if config["storage_location"] == "s3":
                self._upload_to_s3(final_file, backup_id)
            
            # 8. Update backup record
            backup.status = "completed"
            backup.file_path = final_file
            backup.checksum = checksum
            backup.size_bytes = os.path.getsize(final_file)
            backup.completed_at = datetime.now()
            
            self._save_backup_metadata(backup)
            
            logger.info(f"Backup completed: {backup_id}")
            return backup
            
        except Exception as e:
            backup.status = "failed"
            backup.error_message = str(e)
            self._save_backup_metadata(backup)
            logger.error(f"Backup failed: {e}")
            raise
    
    def restore_backup(self, backup_id: str, restore_config: Dict) -> Dict:
        """
        Restore workflow:
        1. Verify backup file integrity
        2. Stop application
        3. Download backup file (if from S3)
        4. Decrypt backup file
        5. Decompress file
        6. Restore data volumes
        7. Restore database
        8. Restart application
        9. Verify restore result
        """
        backup = self._get_backup_metadata(backup_id)
        
        try:
            # 1. Verify checksum
            if not self._verify_checksum(backup.file_path, backup.checksum):
                raise Exception("Backup file corrupted")
            
            # 2. Stop application
            if restore_config.get("stop_app", True):
                self._stop_app(backup.app_id)
            
            # 3. Download from S3 (if needed)
            if backup.storage_location == "s3":
                local_file = self._download_from_s3(backup.s3_bucket, backup.s3_key)
            else:
                local_file = backup.file_path
            
            # 4. Decrypt
            if backup.encrypted:
                decrypted_file = self._decrypt_file(local_file)
            else:
                decrypted_file = local_file
            
            # 5. Extract
            extracted_dir = self._extract_archive(decrypted_file)
            
            # 6. Restore data volumes
            self._restore_volumes(backup.app_id, extracted_dir)
            
            # 7. Restore database
            if restore_config.get("restore_database", True):
                self._restore_database(backup.app_id, extracted_dir)
            
            # 8. Restart application
            self._start_app(backup.app_id)
            
            logger.info(f"Restore completed: {backup_id}")
            return {"status": "success", "backup_id": backup_id}
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            # Try to restore original application
            self._start_app(backup.app_id)
            raise
    
    def _backup_volumes(self, app_id: str, volumes: List[str]) -> List[str]:
        """Export Docker data volumes"""
        backup_paths = []
        
        for volume in volumes:
            output_file = f"{self.backup_dir}/{app_id}/{volume}.tar"
            
            # Use docker run to export data volume
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{volume}:/volume",
                "-v", f"{self.backup_dir}/{app_id}:/backup",
                "busybox",
                "tar", "cvf", f"/backup/{volume}.tar", "-C", "/volume", "."
            ]
            
            subprocess.run(cmd, check=True)
            backup_paths.append(output_file)
        
        return backup_paths
    
    def _backup_database(self, app_id: str) -> str:
        """
        Export database:
        - MySQL: mysqldump
        - PostgreSQL: pg_dump
        - MongoDB: mongodump
        """
        app = self._get_app_info(app_id)
        db_type = app.get("database_type")
        
        if db_type == "mysql":
            return self._backup_mysql(app_id, app)
        elif db_type == "postgres":
            return self._backup_postgres(app_id, app)
        elif db_type == "mongodb":
            return self._backup_mongodb(app_id, app)
        else:
            logger.warning(f"Unknown database type: {db_type}")
            return None
    
    def _compress_files(self, files: List[str], backup_id: str) -> str:
        """Compress backup files"""
        output_file = f"{self.backup_dir}/{backup_id}.tar.gz"
        
        with tarfile.open(output_file, "w:gz") as tar:
            for file in files:
                tar.add(file, arcname=os.path.basename(file))
        
        return output_file
    
    def _encrypt_file(self, file_path: str) -> str:
        """Encrypt backup file"""
        encrypted_file = f"{file_path}.enc"
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        encrypted_data = self.cipher.encrypt(data)
        
        with open(encrypted_file, "wb") as f:
            f.write(encrypted_data)
        
        # Delete original file
        os.remove(file_path)
        
        return encrypted_file
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum"""
        sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()
```

### 2.5 Scheduled Backups

```python
import schedule
import time

class BackupScheduler:
    def __init__(self):
        self.backup_manager = BackupManager()
    
    def start(self):
        """Start scheduled backup service"""
        schedules = self._load_schedules()
        
        for sched in schedules:
            if not sched.enabled:
                continue
            
            if sched.frequency == "daily":
                schedule.every().day.at(sched.time).do(
                    self._run_scheduled_backup, sched
                )
            elif sched.frequency == "weekly":
                schedule.every().week.at(sched.time).do(
                    self._run_scheduled_backup, sched
                )
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def _run_scheduled_backup(self, sched: BackupSchedule):
        """Execute scheduled backup"""
        try:
            backup = self.backup_manager.create_backup(
                sched.app_id,
                {
                    "backup_type": sched.backup_type,
                    "include_database": sched.include_database,
                    "include_uploads": sched.include_uploads,
                    "storage_location": sched.storage_location
                }
            )
            
            # Cleanup old backups
            self._cleanup_old_backups(sched.app_id, sched.retention_days)
            
            logger.info(f"Scheduled backup completed: {backup.backup_id}")
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")
    
    def _cleanup_old_backups(self, app_id: str, retention_days: int):
        """Clean up old backups"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        old_backups = self._get_backups_before(app_id, cutoff_date)
        
        for backup in old_backups:
            self.backup_manager.delete_backup(backup.backup_id)
```

### 2.6 Configuration

```yaml
# config/backup.yaml
backup:
  storage:
    local_path: "/var/websoft9/backups"
    s3_bucket: "${BACKUP_S3_BUCKET}"
    s3_region: "us-east-1"
  
  encryption:
    enabled: true
    key: "${BACKUP_ENCRYPTION_KEY}"
  
  compression:
    enabled: true
    algorithm: "gzip"
    level: 6
  
  defaults:
    backup_type: "full"
    retention_days: 30
    storage_location: "local"
  
  limits:
    max_concurrent_backups: 2
    max_backup_size_gb: 50
```

---

## 3. Story Breakdown

### Story 1: Backup Core Engine
**Priority:** P0 | **Effort:** 5 days

### Story 2: Database Backup
**Priority:** P0 | **Effort:** 3 days

### Story 3: Backup Restore Functionality
**Priority:** P0 | **Effort:** 4 days

### Story 4: Scheduled Backups
**Priority:** P1 | **Effort:** 3 days

### Story 5: S3 Remote Backup
**Priority:** P2 | **Effort:** 3 days

### Story 6: Backup Management API
**Priority:** P1 | **Effort:** 2 days

---

## 4. Dependencies

### Technical Dependencies
- **Docker** - Volume management
- **Cryptography (Fernet)** - File encryption
- **Boto3** - S3 integration
- **schedule** - Scheduled tasks

### Module Dependencies
- **Application Management** - Get application info
- **Logging Module** - Record backup operations

---

## 5. Risks & Challenges

| Risk | Level | Mitigation |
|------|-------|------------|
| Application unavailable during backup | Medium | Support online backup (no downtime) |
| Large backup files | High | Incremental backups, compression optimization |
| Restore failures causing data loss | High | Backup current state before restore |
| S3 upload failures | Medium | Local cache, resumable upload |
| Encryption key loss | High | Key backup plan, recovery procedures |

---

## 6. Testing Strategy

### Unit Tests
- Compress/decompress
- Encrypt/decrypt
- Checksum calculation

### Integration Tests
- Complete backup/restore workflow
- Scheduled backup execution
- S3 upload/download

### Disaster Recovery Drills
- Simulate data corruption
- Complete restore verification

---

## 7. Monitoring Metrics

```python
backup_total                           # Total backups
backup_success_total                   # Successful backups
backup_failed_total                    # Failed backups
backup_duration_seconds                # Backup duration
restore_total                          # Total restores
restore_success_total                  # Successful restores
backup_size_bytes                      # Backup file size
```

---

## Appendix

### A. Error Code Definitions

| Error Code | HTTP | Description |
|------------|------|-------------|
| BACKUP_NOT_FOUND | 404 | Backup not found |
| BACKUP_CREATE_FAILED | 500 | Backup creation failed |
| BACKUP_CORRUPTED | 500 | Backup file corrupted |
| RESTORE_FAILED | 500 | Restore failed |
| BACKUP_QUOTA_EXCEEDED | 507 | Insufficient backup space |

### B. Related Documentation

- [PRD - Backup & Restore](../prd.md#25-备份与恢复)
- [Docker Volume Management](https://docs.docker.com/storage/volumes/)

---

**Document Maintainer:** PM Agent  
**Last Updated:** 2026-01-05
