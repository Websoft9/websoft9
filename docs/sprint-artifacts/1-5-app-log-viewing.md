# Story 5: Application Log Viewing

**Story ID:** APP-005  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** view real-time logs of running applications  
**So that** I can troubleshoot issues and monitor application behavior

## Acceptance Criteria

✅ Log streaming with < 500ms latency  
✅ Support for tail (last N lines)  
✅ Support for live streaming (follow mode)  
✅ Filter logs by container  
✅ Search within logs  
✅ Download logs as file

## Technical Tasks

- [ ] Implement `/api/v1/apps/{app_id}/logs` GET endpoint
- [ ] Integrate Docker logs API
- [ ] Implement streaming response (SSE or WebSocket)
- [ ] Add tail and follow parameters
- [ ] Implement log filtering and search
- [ ] Write streaming tests

## API Specification

```http
GET /api/v1/apps/wordpress001/logs?tail=100&follow=true
X-API-Key: <key>

Response (Server-Sent Events):
data: [2026-01-05 10:30:00] WordPress initialized
data: [2026-01-05 10:30:01] Database connection established
data: ...
```

## Test Scenarios

1. Request last 100 lines returns correct number of logs
2. Follow mode streams new logs in real-time
3. Filter by specific container shows only that container's logs
4. Non-running app returns appropriate error
