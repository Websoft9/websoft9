# Story 9: Inactive Application Removal

**Story ID:** APP-009  
**Priority:** P2  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** remove empty/inactive applications  
**So that** I can maintain a clean application list

## Acceptance Criteria

✅ Only applications with status=inactive can be removed  
✅ Quick removal operation  
✅ Proper validation before deletion

## Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/remove` DELETE endpoint
- [ ] Verify application status is 'inactive'
- [ ] Remove application record
- [ ] Write inactive removal tests
