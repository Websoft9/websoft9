# Epic 4: System Settings Management - User Stories

**Epic:** [System Settings Management Epic](../epics/system-settings-epic.md)  
**Total Stories:** 8  
**Total Estimated Effort:** 15 days  
**Priority Distribution:** P0 (4), P1 (3), P2 (1)

---

## Story 1: Configuration Read API

**Story ID:** SETTINGS-001  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** retrieve system configuration settings  
**So that** I can view current system parameters and troubleshoot issues

### Acceptance Criteria

✅ Configuration retrieval in < 100ms  
✅ Sensitive values masked (passwords, tokens)  
✅ Support retrieving all settings or specific sections  
✅ JSON response format  
✅ Proper error handling for missing config files

### Technical Tasks

- [ ] Implement `/api/v1/settings` GET endpoint
- [ ] Implement `/api/v1/settings/{section}` GET endpoint
- [ ] Create ConfigManager class with INI file parsing
- [ ] Add sensitive value masking logic
- [ ] Handle missing config files gracefully
- [ ] Write configuration read tests

### API Specification

```http
GET /api/v1/settings
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "portainer": {
      "url": "http://portainer:9000",
      "username": "admin",
      "password": "******"
    },
    "nginx_proxy_manager": {
      "url": "http://nginx-proxy-manager:81",
      "admin_email": "admin@example.com",
      "admin_password": "******"
    },
    "apphub": {
      "media_url": "https://websoft9.github.io/docker-library/media.json",
      "cache_duration": 3600
    }
  }
}
```

### Test Scenarios

1. GET all settings returns complete configuration
2. GET specific section returns only that section
3. Passwords are masked with "******"
4. Encrypted values are masked
5. Missing config file returns appropriate error
6. Invalid section name returns 404

---

## Story 2: Configuration Update API

**Story ID:** SETTINGS-002  
**Priority:** P0  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** update system configuration settings  
**So that** I can modify system behavior without manually editing config files

### Acceptance Criteria

✅ Configuration updates apply immediately  
✅ Input validation before saving  
✅ Atomic updates (all or nothing)  
✅ Configuration backup before update  
✅ Audit log of all changes  
✅ Support for query parameter-based updates

### Technical Tasks

- [ ] Implement `/api/v1/settings/{section}?key=xx&value=yy` PUT endpoint
- [ ] Add configuration validation logic
- [ ] Implement atomic file write (write to temp, then rename)
- [ ] Add automatic configuration backup
- [ ] Implement audit logging
- [ ] Write configuration update tests

### API Specification

```http
PUT /api/v1/settings/portainer?key=password&value=new_password_123
X-API-Key: <key>

Response:
{
  "code": 200,
  "message": "Configuration updated successfully",
  "data": {
    "section": "portainer",
    "key": "password",
    "value": "******",
    "updated_at": "2026-01-05T10:30:00Z"
  }
}
```

### Test Scenarios

1. Update valid configuration succeeds
2. Invalid value fails validation
3. Update creates backup of old config
4. Audit log records the change
5. Update with missing section creates section
6. Concurrent updates handled safely

---

## Story 3: Configuration Encryption

**Story ID:** SETTINGS-003  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** automatically encrypt sensitive configuration values  
**So that** passwords and secrets are not stored in plaintext

### Acceptance Criteria

✅ Passwords automatically encrypted on write  
✅ Encrypted values prefixed with "encrypted:"  
✅ Decryption transparent on read  
✅ Encryption key stored securely (environment variable)  
✅ Support for key rotation  
✅ Fernet encryption standard

### Technical Tasks

- [ ] Integrate Cryptography library (Fernet)
- [ ] Implement encrypt/decrypt functions
- [ ] Auto-detect sensitive keys (password, secret, token, key)
- [ ] Add encryption on config write
- [ ] Add decryption on config read
- [ ] Write encryption tests

### Implementation Notes

```python
from cryptography.fernet import Fernet

class ConfigManager:
    def __init__(self):
        self.cipher = Fernet(os.getenv("CONFIG_ENCRYPTION_KEY").encode())
    
    def _encrypt_value(self, value: str) -> str:
        encrypted = self.cipher.encrypt(value.encode()).decode()
        return f"encrypted:{encrypted}"
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        data = encrypted_value.replace("encrypted:", "")
        return self.cipher.decrypt(data.encode()).decode()
```

### Test Scenarios

1. Password saved as encrypted in config file
2. Encrypted value decrypted correctly on read
3. Non-encrypted values pass through unchanged
4. Auto-detection of sensitive keys works
5. Invalid encryption key fails gracefully
6. Re-encryption with new key works

---

## Story 4: Configuration Validation

**Story ID:** SETTINGS-004  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** validate configuration values before they are saved  
**So that** I prevent invalid configurations that could break the system

### Acceptance Criteria

✅ URL format validation  
✅ Port range validation (1-65535)  
✅ Email format validation  
✅ Required field validation  
✅ Clear error messages on validation failure  
✅ Custom validators for specific fields

### Technical Tasks

- [ ] Create ConfigValidator class
- [ ] Implement URL validation with regex
- [ ] Implement port range validation
- [ ] Implement email validation
- [ ] Add required field checks
- [ ] Integrate validators into update flow
- [ ] Write validation tests

### Implementation Notes

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

### Test Scenarios

1. Valid URL passes validation
2. Invalid URL format rejected
3. Port 80 passes validation
4. Port 0 fails validation
5. Port 99999 fails validation
6. Valid email passes validation
7. Invalid email rejected

---

## Story 5: Configuration Backup & Restore

**Story ID:** SETTINGS-005  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** backup and restore system configuration  
**So that** I can recover from configuration errors or migrate settings

### Acceptance Criteria

✅ Automatic backup before each update  
✅ Manual backup on demand  
✅ Restore from specific backup version  
✅ List available backups  
✅ Backup retention policy (keep last 10)  
✅ Backup includes timestamp in filename

### Technical Tasks

- [ ] Implement auto-backup on config update
- [ ] Implement manual backup API endpoint
- [ ] Implement restore API endpoint
- [ ] Implement backup listing endpoint
- [ ] Add backup cleanup (retention policy)
- [ ] Write backup/restore tests

### API Specification

```http
POST /api/v1/settings/backup
X-API-Key: <key>

Response:
{
  "code": 200,
  "data": {
    "backup_file": "config/backups/config_20260105_103000.ini",
    "created_at": "2026-01-05T10:30:00Z"
  }
}

POST /api/v1/settings/restore
{
  "backup_file": "config/backups/config_20260105_103000.ini"
}

GET /api/v1/settings/backups
Response:
{
  "data": {
    "backups": [
      {
        "file": "config_20260105_103000.ini",
        "created_at": "2026-01-05T10:30:00Z",
        "size_bytes": 2048
      }
    ]
  }
}
```

### Test Scenarios

1. Manual backup creates timestamped file
2. Auto-backup runs before config update
3. Restore replaces current config
4. Restore creates backup of current config first
5. Old backups cleaned up per retention policy
6. List backups returns all available backups

---

## Story 6: Configuration Audit Logging

**Story ID:** SETTINGS-006  
**Priority:** P2  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 administrator  
**I want to** see audit logs of all configuration changes  
**So that** I can track who changed what and when

### Acceptance Criteria

✅ All config changes logged  
✅ Log includes: timestamp, section, key, action, user (if available)  
✅ Log stored securely  
✅ Log rotation to prevent disk fill  
✅ Query logs by date range  
✅ Query logs by section

### Technical Tasks

- [ ] Implement audit log writer
- [ ] Add logging to all config update operations
- [ ] Implement log query API
- [ ] Add log rotation (by size or date)
- [ ] Write audit log tests

### Log Format

```json
{
  "timestamp": "2026-01-05T10:30:00Z",
  "action": "config_change",
  "section": "portainer",
  "key": "password",
  "operation": "update",
  "user": "admin",
  "ip_address": "192.168.1.100"
}
```

### Test Scenarios

1. Config update creates audit log entry
2. Query logs by date range works
3. Query logs by section works
4. Old logs rotated automatically
5. Log format is valid JSON

---

## Story 7: Multi-Environment Configuration

**Story ID:** SETTINGS-007  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 developer  
**I want to** support different configurations for dev/staging/production  
**So that** I can easily switch between environments

### Acceptance Criteria

✅ Support for environment-specific config files  
✅ Environment detection (from ENV variable)  
✅ Default to production if not specified  
✅ Override mechanism (env vars override config file)  
✅ Environment clearly indicated in API responses

### Technical Tasks

- [ ] Add environment detection logic
- [ ] Support config.{env}.ini files
- [ ] Implement config override from environment variables
- [ ] Add environment info to API responses
- [ ] Write multi-environment tests

### Configuration Structure

```
config/
  config.ini             # Default/production
  config.dev.ini         # Development overrides
  config.staging.ini     # Staging overrides
```

### Test Scenarios

1. Production environment uses config.ini
2. Development environment uses config.dev.ini
3. Environment variable overrides config file
4. Missing environment-specific file falls back to default
5. Environment shown in API response headers

---

## Story 8: Configuration Schema Definition

**Story ID:** SETTINGS-008  
**Priority:** P0  
**Estimated Effort:** 1 day  
**Status:** ready-for-dev

### User Story

**As a** Websoft9 developer  
**I want to** define expected configuration schema  
**So that** I can validate configuration completeness and correctness

### Acceptance Criteria

✅ Schema defines all expected sections and keys  
✅ Schema includes data types for each field  
✅ Schema indicates required vs optional fields  
✅ Validation against schema on startup  
✅ Schema serves as documentation

### Technical Tasks

- [ ] Create configuration schema (JSON Schema or Pydantic)
- [ ] Implement schema validation on read
- [ ] Generate documentation from schema
- [ ] Add schema validation to update flow
- [ ] Write schema validation tests

### Schema Example

```python
class PortainerConfig(BaseModel):
    url: HttpUrl
    username: str
    password: str
    
class NginxProxyManagerConfig(BaseModel):
    url: HttpUrl
    admin_email: EmailStr
    admin_password: str
    
class SystemConfig(BaseModel):
    portainer: PortainerConfig
    nginx_proxy_manager: NginxProxyManagerConfig
    apphub: AppHubConfig
```

### Test Scenarios

1. Valid config passes schema validation
2. Missing required field fails validation
3. Invalid data type fails validation
4. Extra fields allowed (for extensibility)
5. Schema documentation generated correctly

---

## Summary

This Epic provides comprehensive system configuration management with security (encryption), reliability (validation, backup), and auditability (logging). The focus is on making configuration changes safe and traceable.

**Development Sequence:**
1. Stories 1, 8 (Read API + Schema foundation)
2. Story 2 (Update API - core functionality)
3. Story 3 (Encryption - security critical)
4. Stories 4, 5 (Validation + Backup - safety features)
5. Stories 6, 7 (Advanced features)

**Dependencies:**
- Story 2 depends on Story 1 (need read before write)
- Story 3 should be implemented with Story 2 (encryption on write)
- Story 4 should be integrated into Story 2 (validation on update)
- Story 5 should trigger on Story 2 operations (auto-backup)
- Story 8 provides foundation for Story 4 (schema for validation)

**Risk Mitigation:**
- Always backup before updates (Story 5)
- Validate before saving (Story 4)
- Encrypt sensitive data (Story 3)
- Audit all changes (Story 6)
- Test restore process regularly
- Monitor for invalid configurations
- Implement configuration rollback on service failure
