# Story 2: Application Installation Workflow

**Story ID:** APP-002  
**Priority:** P0  
**Estimated Effort:** 4 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** install an application from the catalog with custom parameters  
**So that** I can quickly deploy applications without manual Docker configuration

## Acceptance Criteria

✅ Installation completes in < 2 minutes for typical apps  
✅ Support custom environment variables  
✅ Support custom domain configuration  
✅ Async installation with status updates  
✅ Automatic rollback on failure  
✅ Success rate > 95%

## Technical Tasks

- [ ] Implement `/api/v1/apps/install` POST endpoint
- [ ] Generate docker-compose.yml from template
- [ ] Integrate Portainer Stack creation API
- [ ] Implement parameter validation (app_name, app_id, env)
- [ ] Add error handling and rollback logic
- [ ] Implement async background job execution
- [ ] Write integration tests with real Docker environment

## API Specification

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

## Test Scenarios

1. Install WordPress with default parameters succeeds
2. Install with custom environment variables applies correctly
3. Install with duplicate app_id returns error
4. Install with invalid app_name returns error
5. Installation failure triggers automatic cleanup
6. Installation status can be queried during process
