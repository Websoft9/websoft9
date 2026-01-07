# Story 4: Configuration Validation

**Story ID:** SETTINGS-004  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** validate configuration values before they are saved  
**So that** I prevent invalid configurations that could break the system

## Acceptance Criteria

✅ URL format validation  
✅ Port range validation (1-65535)  
✅ Email format validation  
✅ Required field validation  
✅ Clear error messages on validation failure  
✅ Custom validators for specific fields

## Technical Tasks

- [ ] Create ConfigValidator class
- [ ] Implement URL validation with regex
- [ ] Implement port range validation
- [ ] Implement email validation
- [ ] Add required field checks
- [ ] Integrate validators into update flow
- [ ] Write validation tests

## Implementation Notes

```python
class ConfigValidator:
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, str]:
        pattern = r'^https?://[\w\-.]+(:\d+)?(/.*)?$'
        if re.match(pattern, url):
            return True, "Valid URL"
        return False, "Invalid URL format"
    
    @staticmethod
    def validate_port(port: str) -> Tuple[bool, str]:
        try:
            port_num = int(port)
            if 1 <= port_num <= 65535:
                return True, "Valid port"
            return False, "Port must be between 1 and 65535"
        except ValueError:
            return False, "Port must be a number"
```

## Test Scenarios

1. Valid URL passes validation
2. Invalid URL format rejected
3. Port 80 passes validation
4. Port 0 fails validation
5. Port 99999 fails validation
6. Valid email passes validation
7. Invalid email rejected
