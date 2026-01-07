# Story 4: Scheduled Backups

**Story ID:** BACKUP-004  
**Priority:** P1  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** schedule automatic backups  
**So that** I don't have to remember to backup manually

## Acceptance Criteria

✅ Support daily, weekly, monthly schedules  
✅ Configurable time for backup execution  
✅ Automatic cleanup of old backups based on retention policy  
✅ Backup schedule persists across restarts  
✅ Failed backups trigger notifications  
✅ Multiple schedules per application

## Technical Tasks

- [ ] Implement backup schedule configuration API
- [ ] Add cron-like scheduler (or use Celery Beat)
- [ ] Implement automatic old backup cleanup
- [ ] Add schedule persistence (database)
- [ ] Implement failure notification system
- [ ] Write scheduler tests

## API Specification

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

## Implementation Notes

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

## Test Scenarios

1. Daily backup executes at configured time
2. Weekly backup executes on correct day
3. Old backups cleaned up per retention policy
4. Disabled schedules don't execute
5. Failed backup sends notification
6. Schedule persists after service restart
