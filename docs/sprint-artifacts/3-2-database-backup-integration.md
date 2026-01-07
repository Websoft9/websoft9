# Story 2: Database Backup Integration

**Story ID:** BACKUP-002  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** backup application databases separately  
**So that** I can ensure database consistency and enable point-in-time recovery

## Acceptance Criteria

✅ Support MySQL/MariaDB (mysqldump)  
✅ Support PostgreSQL (pg_dump)  
✅ Support MongoDB (mongodump)  
✅ Database backup is consistent (transaction-safe)  
✅ Minimal downtime during backup  
✅ Backup includes schema and data

## Technical Tasks

- [ ] Implement MySQL backup integration
- [ ] Implement PostgreSQL backup integration
- [ ] Implement MongoDB backup integration
- [ ] Add database connection detection
- [ ] Handle database credentials securely
- [ ] Write database backup tests

## Implementation Notes

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

## Test Scenarios

1. MySQL database backed up successfully
2. PostgreSQL database backed up successfully
3. MongoDB database backed up successfully
4. Backup includes all tables and data
5. Restored database is consistent
6. Credentials handled securely (not logged)
