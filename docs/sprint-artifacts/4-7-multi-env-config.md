# Story 7: Multi-Environment Configuration

**Story ID:** SETTINGS-007  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 developer  
**I want to** support different configurations for dev/staging/production  
**So that** I can easily switch between environments

## Acceptance Criteria

✅ Support for environment-specific config files  
✅ Environment detection (from ENV variable)  
✅ Default to production if not specified  
✅ Override mechanism (env vars override config file)  
✅ Environment clearly indicated in API responses

## Technical Tasks

- [ ] Add environment detection logic
- [ ] Support config.{env}.ini files
- [ ] Implement config override from environment variables
- [ ] Add environment info to API responses
- [ ] Write multi-environment tests

## Configuration Structure

```
config/
  config.ini             # Default/production
  config.dev.ini         # Development overrides
  config.staging.ini     # Staging overrides
```

## Test Scenarios

1. Production environment uses config.ini
2. Development environment uses config.dev.ini
3. Environment variable overrides config file
4. Missing environment-specific file falls back to default
5. Environment shown in API response headers
