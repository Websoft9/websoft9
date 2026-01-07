# Story 6: Installed Applications List

**Story ID:** APP-006  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** see a list of all installed applications with their status  
**So that** I can monitor and manage my deployments

## Acceptance Criteria

✅ List loads in < 1 second  
✅ Shows application name, status, created date  
✅ Status accurately reflects Docker container state  
✅ Support filtering and sorting  
✅ Pagination for large lists

## Technical Tasks

- [ ] Implement `/api/v1/apps` GET endpoint
- [ ] Fetch Stack list from Portainer API
- [ ] Aggregate container status for each app
- [ ] Format response with application metadata
- [ ] Add filtering and pagination
- [ ] Write query tests

## API Specification

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

## Test Scenarios

1. List all applications returns complete list
2. Filter by status=running shows only running apps
3. Pagination works correctly
4. Empty list returns empty array (not error)
