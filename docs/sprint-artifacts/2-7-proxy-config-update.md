# Story 7: Proxy Configuration Update

**Story ID:** PROXY-007  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** update existing proxy configurations  
**So that** I can modify domains or settings without recreating proxies

## Acceptance Criteria

✅ Update domain names without downtime  
✅ Toggle SSL settings  
✅ Update access control rules  
✅ Changes apply in < 5 seconds  
✅ Configuration history tracked

## Technical Tasks

- [ ] Implement `/api/v1/proxys/{proxy_id}` PUT endpoint
- [ ] Support partial updates (PATCH semantics)
- [ ] Validate updated configuration
- [ ] Track configuration changes (audit log)
- [ ] Write update tests

## Test Scenarios

1. Update domain names succeeds
2. Enable SSL on existing proxy works
3. Disable force HTTPS works
4. Update with invalid data fails validation
5. Configuration history records all changes
