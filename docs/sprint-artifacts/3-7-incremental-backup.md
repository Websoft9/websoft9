# Story 7: Incremental Backup

**Story ID:** BACKUP-007  
**Priority:** P1  
**Estimated Effort:** 4 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** perform incremental backups  
**So that** I can reduce backup time and storage space

## Acceptance Criteria

✅ Incremental backup only includes changed files  
✅ Backup time < 50% of full backup  
✅ Storage space < 30% of full backup (for typical changes)  
✅ Restore from incremental requires base backup  
✅ Automatic base backup after N incremental backups

## Technical Tasks

- [ ] Implement file change detection (modified time, hash)
- [ ] Add incremental backup logic
- [ ] Track backup chain (base + incrementals)
- [ ] Implement restore from incremental chain
- [ ] Add automatic full backup after N incrementals
- [ ] Write incremental backup tests

## Test Scenarios

1. First backup is always full
2. Incremental backup smaller than full
3. Restore from base + incremental works
4. Change detection accurate
5. Auto full backup after 7 incrementals
