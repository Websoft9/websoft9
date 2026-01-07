# Story 3: Application Lifecycle Management

**Story ID:** APP-003  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** start, stop, and restart installed applications  
**So that** I can manage application availability and perform maintenance

## Acceptance Criteria

✅ Start/stop/restart operations complete in < 3 seconds  
✅ Application status reflects changes immediately  
✅ Operations are idempotent (safe to retry)  
✅ Error messages clearly indicate failure reasons  
✅ All containers in app affected simultaneously

## Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/start` POST endpoint
- [ ] Implement `/api/v1/apps/{app_id}/stop` POST endpoint
- [ ] Implement `/api/v1/apps/{app_id}/restart` POST endpoint
- [ ] Integrate Portainer Stack start/stop APIs
- [ ] Add status synchronization with Docker
- [ ] Implement idempotency checks
- [ ] Write functional tests for lifecycle operations

## API Specification

```http
POST /api/v1/apps/wordpress001/start
X-API-Key: <key>

Response:
{
  "code": 200,
  "message": "App started successfully",
  "data": {
    "app_id": "wordpress001",
    "status": "running"
  }
}
```

## Test Scenarios

1. Start stopped application succeeds
2. Start already running application is idempotent
3. Stop running application succeeds
4. Restart application completes successfully
5. Operation on non-existent app returns 404
