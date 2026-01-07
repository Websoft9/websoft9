# Story 4: Application Uninstallation

**Story ID:** APP-004  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** uninstall applications I no longer need  
**So that** I can free up system resources and keep my environment clean

## Acceptance Criteria

✅ Uninstallation removes all containers  
✅ Uninstallation removes all networks  
✅ Optional removal of data volumes  
✅ Confirmation required before deletion  
✅ Complete cleanup in < 30 seconds  
✅ No orphaned resources left behind

## Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/uninstall` DELETE endpoint
- [ ] Add `remove_volumes` parameter support
- [ ] Implement resource cleanup logic (containers, networks, volumes)
- [ ] Add confirmation mechanism
- [ ] Verify complete resource removal
- [ ] Write cleanup verification tests

## API Specification

```http
DELETE /api/v1/apps/wordpress001/uninstall?remove_volumes=true
X-API-Key: <key>

Response:
{
  "code": 200,
  "message": "App uninstalled successfully",
  "data": {
    "app_id": "wordpress001",
    "removed_containers": 2,
    "removed_networks": 1,
    "removed_volumes": 3
  }
}
```

## Test Scenarios

1. Uninstall with `remove_volumes=false` keeps data volumes
2. Uninstall with `remove_volumes=true` deletes all volumes
3. Verify all containers removed from Docker
4. Verify all networks removed from Docker
5. Uninstalling non-existent app returns error
