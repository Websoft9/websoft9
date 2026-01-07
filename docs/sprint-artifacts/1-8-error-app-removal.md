# Story 8: Error Application Removal

**Story ID:** APP-008  
**Priority:** P0  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** remove applications in error state  
**So that** I can clean up failed installations

## Acceptance Criteria

✅ Only applications with status=error can be removed  
✅ Removal cleans up all related resources  
✅ Fast operation (< 10 seconds)

## Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/error/remove` DELETE endpoint
- [ ] Verify application status is 'error'
- [ ] Clean up partial resources
- [ ] Write error cleanup tests
