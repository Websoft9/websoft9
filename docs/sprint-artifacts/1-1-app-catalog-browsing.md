# Story 1: Application Catalog Browsing

**Story ID:** APP-001  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** browse the application catalog with category filtering  
**So that** I can discover and select applications to install

## Acceptance Criteria

✅ Application catalog loads in < 2 seconds  
✅ Support for Chinese (zh) and English (en) locales  
✅ Applications grouped by categories  
✅ Each application displays: name, logo, description, category  
✅ Catalog data cached for 1 hour  
✅ Graceful fallback if media.json unavailable

## Technical Tasks

- [ ] Implement `/api/v1/apps/catalog/{locale}` endpoint
- [ ] Load and parse media.json from GitHub
- [ ] Implement caching mechanism (Redis/in-memory)
- [ ] Add locale-specific category translation
- [ ] Write unit tests for catalog parsing
- [ ] Write integration tests for API endpoint

## API Specification

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

## Test Scenarios

1. Request catalog with `locale=zh` returns Chinese names/descriptions
2. Request catalog with `locale=en` returns English names/descriptions
3. Invalid locale defaults to English
4. Catalog cached response uses cache until expiry
5. Network failure to media.json returns cached data or error
