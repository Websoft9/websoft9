# Epic 1: Application Management - User Stories

**Epic:** [Application Management Epic](../epics/app-management-epic.md)  
**Total Stories:** 9  
**Total Estimated Effort:** 21 days  
**Priority Distribution:** P0 (6), P1 (2), P2 (1)

---

## Story 1: Application Catalog Browsing

**Story ID:** APP-001  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** browse the application catalog with category filtering  
**So that** I can discover and select applications to install

### Acceptance Criteria

✅ Application catalog loads in < 2 seconds  
✅ Support for Chinese (zh) and English (en) locales  
✅ Applications grouped by categories  
✅ Each application displays: name, logo, description, category  
✅ Catalog data cached for 1 hour  
✅ Graceful fallback if media.json unavailable

### Technical Tasks

- [ ] Implement `/api/v1/apps/catalog/{locale}` endpoint
- [ ] Load and parse media.json from GitHub
- [ ] Implement caching mechanism (Redis/in-memory)
- [ ] Add locale-specific category translation
- [ ] Write unit tests for catalog parsing
- [ ] Write integration tests for API endpoint

### API Specification

```http
GET /api/v1/apps/catalog/en
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "categories": ["CMS", "Database", "Development"],
    "apps": [
      {
        "key": "wordpress",
        "name": "WordPress",
        "category": "CMS",
        "description": "Popular blog and CMS platform",
        "logo_url": "https://...",
        "default_port": 80
      }
    ]
  }
}
```

### Test Scenarios

1. Request catalog with `locale=zh` returns Chinese names/descriptions
2. Request catalog with `locale=en` returns English names/descriptions
3. Invalid locale defaults to English
4. Catalog cached response uses cache until expiry
5. Network failure to media.json returns cached data or error

---

## Story 2: Application Installation Workflow

**Story ID:** APP-002  
**Priority:** P0  
**Estimated Effort:** 4 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** install an application from the catalog with custom parameters  
**So that** I can quickly deploy applications without manual Docker configuration

### Acceptance Criteria

✅ Installation completes in < 2 minutes for typical apps  
✅ Support custom environment variables  
✅ Support custom domain configuration  
✅ Async installation with status updates  
✅ Automatic rollback on failure  
✅ Success rate > 95%

### Technical Tasks

- [ ] Implement `/api/v1/apps/install` POST endpoint
- [ ] Generate docker-compose.yml from template
- [ ] Integrate Portainer Stack creation API
- [ ] Implement parameter validation (app_name, app_id, env)
- [ ] Add error handling and rollback logic
- [ ] Implement async background job execution
- [ ] Write integration tests with real Docker environment

### API Specification

```http
POST /api/v1/apps/install
X-API-Key: <key>
Content-Type: application/json

{
  "app_name": "wordpress",
  "app_id": "wordpress001",
  "endpointId": 1,
  "domain": "myblog.example.com",
  "env": {
    "MYSQL_ROOT_PASSWORD": "secret123",
    "WORDPRESS_DB_NAME": "wp_db"
  }
}

Response:
{
  "code": 200,
  "message": "App installed successfully",
  "data": {
    "app_id": "wordpress001",
    "app_name": "wordpress",
    "status": "running",
    "domain": "myblog.example.com",
    "created_at": "2026-01-05T10:30:00Z"
  }
}
```

### Test Scenarios

1. Install WordPress with default parameters succeeds
2. Install with custom environment variables applies correctly
3. Install with duplicate app_id returns error
4. Install with invalid app_name returns error
5. Installation failure triggers automatic cleanup
6. Installation status can be queried during process

---

## Story 3: Application Lifecycle Management

**Story ID:** APP-003  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** start, stop, and restart installed applications  
**So that** I can manage application availability and perform maintenance

### Acceptance Criteria

✅ Start/stop/restart operations complete in < 3 seconds  
✅ Application status reflects changes immediately  
✅ Operations are idempotent (safe to retry)  
✅ Error messages clearly indicate failure reasons  
✅ All containers in app affected simultaneously

### Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/start` POST endpoint
- [ ] Implement `/api/v1/apps/{app_id}/stop` POST endpoint
- [ ] Implement `/api/v1/apps/{app_id}/restart` POST endpoint
- [ ] Integrate Portainer Stack start/stop APIs
- [ ] Add status synchronization with Docker
- [ ] Implement idempotency checks
- [ ] Write functional tests for lifecycle operations

### API Specification

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

### Test Scenarios

1. Start stopped application succeeds
2. Start already running application is idempotent
3. Stop running application succeeds
4. Restart application completes successfully
5. Operation on non-existent app returns 404

---

## Story 4: Application Uninstallation

**Story ID:** APP-004  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** uninstall applications I no longer need  
**So that** I can free up system resources and keep my environment clean

### Acceptance Criteria

✅ Uninstallation removes all containers  
✅ Uninstallation removes all networks  
✅ Optional removal of data volumes  
✅ Confirmation required before deletion  
✅ Complete cleanup in < 30 seconds  
✅ No orphaned resources left behind

### Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/uninstall` DELETE endpoint
- [ ] Add `remove_volumes` parameter support
- [ ] Implement resource cleanup logic (containers, networks, volumes)
- [ ] Add confirmation mechanism
- [ ] Verify complete resource removal
- [ ] Write cleanup verification tests

### API Specification

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

### Test Scenarios

1. Uninstall with `remove_volumes=false` keeps data volumes
2. Uninstall with `remove_volumes=true` deletes all volumes
3. Verify all containers removed from Docker
4. Verify all networks removed from Docker
5. Uninstalling non-existent app returns error

---

## Story 5: Application Log Viewing

**Story ID:** APP-005  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** view real-time logs of running applications  
**So that** I can troubleshoot issues and monitor application behavior

### Acceptance Criteria

✅ Log streaming with < 500ms latency  
✅ Support for tail (last N lines)  
✅ Support for live streaming (follow mode)  
✅ Filter logs by container  
✅ Search within logs  
✅ Download logs as file

### Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/logs` GET endpoint
- [ ] Integrate Docker logs API
- [ ] Implement streaming response (SSE or WebSocket)
- [ ] Add tail and follow parameters
- [ ] Implement log filtering and search
- [ ] Write streaming tests

### API Specification

```http
GET /api/v1/apps/wordpress001/logs?tail=100&follow=true
X-API-Key: <key>

Response (Server-Sent Events):
data: [2026-01-05 10:30:00] WordPress initialized
data: [2026-01-05 10:30:01] Database connection established
data: ...
```

### Test Scenarios

1. Request last 100 lines returns correct number of logs
2. Follow mode streams new logs in real-time
3. Filter by specific container shows only that container's logs
4. Non-running app returns appropriate error

---

## Story 6: Installed Applications List

**Story ID:** APP-006  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** see a list of all installed applications with their status  
**So that** I can monitor and manage my deployments

### Acceptance Criteria

✅ List loads in < 1 second  
✅ Shows application name, status, created date  
✅ Status accurately reflects Docker container state  
✅ Support filtering and sorting  
✅ Pagination for large lists

### Technical Tasks

- [ ] Implement `/api/v1/apps` GET endpoint
- [ ] Fetch Stack list from Portainer API
- [ ] Aggregate container status for each app
- [ ] Format response with application metadata
- [ ] Add filtering and pagination
- [ ] Write query tests

### API Specification

```http
GET /api/v1/apps?status=running&page=1&limit=20
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "total": 15,
    "apps": [
      {
        "app_id": "wordpress001",
        "app_name": "wordpress",
        "status": "running",
        "containers": 2,
        "created_at": "2026-01-05T10:30:00Z"
      }
    ]
  }
}
```

### Test Scenarios

1. List all applications returns complete list
2. Filter by status=running shows only running apps
3. Pagination works correctly
4. Empty list returns empty array (not error)

---

## Story 7: Application Redeployment

**Story ID:** APP-007  
**Priority:** P1  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** redeploy an application with latest images  
**So that** I can update applications to their newest versions

### Acceptance Criteria

✅ Pull latest images before redeployment  
✅ Stream pull progress to user  
✅ Minimal downtime during update  
✅ Rollback on failure  
✅ Preserve data volumes

### Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/redeploy` PUT endpoint
- [ ] Implement image pull with progress streaming
- [ ] Add container recreation logic
- [ ] Ensure volume preservation
- [ ] Add rollback on failure
- [ ] Write redeployment tests

### Test Scenarios

1. Redeploy pulls new image version
2. Redeploy preserves existing data volumes
3. Stream logs show pull progress
4. Failure during redeploy triggers rollback

---

## Story 8: Error Application Removal

**Story ID:** APP-008  
**Priority:** P0  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** remove applications in error state  
**So that** I can clean up failed installations

### Acceptance Criteria

✅ Only applications with status=error can be removed  
✅ Removal cleans up all related resources  
✅ Fast operation (< 10 seconds)

### Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/error/remove` DELETE endpoint
- [ ] Verify application status is 'error'
- [ ] Clean up partial resources
- [ ] Write error cleanup tests

---

## Story 9: Inactive Application Removal

**Story ID:** APP-009  
**Priority:** P2  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 user  
**I want to** remove empty/inactive applications  
**So that** I can maintain a clean application list

### Acceptance Criteria

✅ Only applications with status=inactive can be removed  
✅ Quick removal operation  
✅ Proper validation before deletion

### Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/remove` DELETE endpoint
- [ ] Verify application status is 'inactive'
- [ ] Remove application record
- [ ] Write inactive removal tests

---

## Summary

This Epic encompasses the complete application lifecycle from discovery to removal. The stories are prioritized to deliver core functionality first (P0), followed by enhancements (P1) and nice-to-have features (P2).

**Development Sequence:**
1. Stories 1, 6 (Read operations)
2. Story 2 (Installation - most complex)
3. Stories 3, 4, 8 (Lifecycle management)
4. Stories 5, 7, 9 (Enhancement features)

**Dependencies:**
- All stories depend on Portainer API integration
- Stories 2-9 depend on Story 1 (catalog data)
- Story 7 depends on Stories 2-3 (install + lifecycle)

**Risk Mitigation:**
- Implement comprehensive error handling in Story 2
- Add detailed logging throughout all operations
- Create rollback mechanisms for destructive operations
