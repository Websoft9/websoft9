# Epic: System Settings Management

**Related PRD:** [FR-SYS-001] 
**Owner:** Product Manager  
**Status:** In Development  
**Priority:** P0 (Required)  
**Estimated Effort:** 2-3 weeks

---

## 1. Epic Overview

### 1.1 Business Objectives

Provide system-level configuration management capabilities, including AppHub configuration, Portainer configuration, NPM configuration, and other core component parameter management.

### 1.2 Core Value

- Unified configuration management interface
- Real-time configuration changes
- Configuration validation and verification
- Configuration backup and restore
- Sensitive information encrypted storage

### 1.3 Acceptance Criteria

✅ Configuration read response time < 100ms  
✅ Configuration updates take effect immediately (no restart required)  
✅ Sensitive configuration encrypted storage  
✅ Configuration change audit log recording  
✅ Configuration format validation accuracy 100%  
✅ Support configuration rollback

---

## 2. Technical Specifications

### 2.1 Architecture Design

#### Configuration Storage Architecture

```
Application Config → config.ini (ConfigParser)
System Config → system.ini
Environment Variables → .env file
Sensitive Config → Encrypted Storage (Fernet)
```

#### Configuration Read Workflow

```
API Request → Config Manager → Read INI File → Decrypt Sensitive Values → Return Config
```

### 2.2 API Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/settings` | GET | Get all configuration | API Key |
| `/api/v1/settings/{section}` | GET | Get specific configuration section | API Key |
| `/api/v1/settings/{section}?key=xx&value=yy` | PUT | Update single configuration (using Query parameters) | API Key |

#### Example: Get Configuration

**Request:**
```http
GET /api/v1/settings
X-API-Key: <key>
```

**Response:**
```json
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
    "gitea": {
      "url": "http://gitea:3000",
      "admin_username": "gitea_admin"
    },
    "apphub": {
      "media_url": "https://websoft9.github.io/docker-library/media.json",
      "cache_duration": 3600,
      "max_concurrent_installs": 3
    }
  }
}
```

#### Example: Update Configuration

**Request:**
```http
PUT /api/v1/settings/portainer?key=password&value=new_secure_password_123
X-API-Key: <key>
```

**Response:**
```json
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

### 2.3 Data Models

#### Configuration File Structure (config.ini)

```ini
[portainer]
url = http://portainer:9000
username = admin
password = encrypted:gAAAAABh1234567890...  # Fernet encrypted

[nginx_proxy_manager]
url = http://nginx-proxy-manager:81
admin_email = admin@example.com
admin_password = encrypted:gAAAAABh9876543210...

[gitea]
url = http://gitea:3000
admin_username = gitea_admin
admin_password = encrypted:gAAAAABh5555555555...

[apphub]
media_url = https://websoft9.github.io/docker-library/media.json
cache_duration = 3600
max_concurrent_installs = 3
log_level = INFO

[system]
timezone = Asia/Shanghai
language = zh_CN
```

#### Python Configuration Model

```python
class ConfigItem(BaseModel):
    section: str
    key: str
    value: str
    is_sensitive: bool = False  # Is sensitive configuration
    data_type: str = "string"   # string, int, bool, list
    description: Optional[str]

class ConfigSection(BaseModel):
    name: str
    items: Dict[str, ConfigItem]
    description: Optional[str]
```

### 2.4 Core Service Design

#### config.py

```python
import configparser
from cryptography.fernet import Fernet
import os

class ConfigManager:
    def __init__(self, config_file="config/config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Encryption key (from environment variable)
        self.cipher = Fernet(os.getenv("CONFIG_ENCRYPTION_KEY").encode())
    
    def get_value(self, section: str, key: str, 
                  decrypt: bool = True) -> str:
        """
        Get configuration value
        - Automatically decrypt values starting with 'encrypted:'
        """
        value = self.config.get(section, key)
        
        if decrypt and value.startswith("encrypted:"):
            encrypted_data = value.replace("encrypted:", "")
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        
        return value
    
    def set_value(self, section: str, key: str, value: str, 
                  encrypt: bool = False) -> None:
        """
        Set configuration value
        - Sensitive configuration automatically encrypted
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        
        if encrypt:
            encrypted_value = self.cipher.encrypt(value.encode()).decode()
            value = f"encrypted:{encrypted_value}"
        
        self.config.set(section, key, value)
        self._save_config()
        
        # Record audit log
        self._log_config_change(section, key, "update")
    
    def remove_value(self, section: str, key: str) -> None:
        """Delete configuration item"""
        if self.config.has_option(section, key):
            self.config.remove_option(section, key)
            self._save_config()
            self._log_config_change(section, key, "delete")
    
    def remove_section(self, section: str) -> None:
        """Delete entire configuration section"""
        if self.config.has_section(section):
            self.config.remove_section(section)
            self._save_config()
            self._log_config_change(section, None, "delete_section")
    
    def get_all_config(self, mask_sensitive: bool = True) -> Dict:
        """
        Get all configuration
        - mask_sensitive: Whether to mask sensitive information
        """
        result = {}
        sensitive_keys = ["password", "secret", "token", "key"]
        
        for section in self.config.sections():
            result[section] = {}
            for key, value in self.config.items(section):
                # Mask sensitive configuration
                if mask_sensitive and any(sk in key.lower() for sk in sensitive_keys):
                    result[section][key] = "******"
                elif value.startswith("encrypted:"):
                    result[section][key] = "******"
                else:
                    result[section][key] = value
        
        return result
    
    def validate_config(self, section: str, key: str, 
                       value: str) -> Tuple[bool, str]:
        """
        Validate configuration value
        - URL format validation
        - Port range validation
        - Required field validation
        """
        validators = {
            "url": self._validate_url,
            "port": self._validate_port,
            "email": self._validate_email,
            "int": self._validate_int,
        }
        
        # Determine validation type based on key name
        if "url" in key.lower():
            return validators["url"](value)
        elif "port" in key.lower():
            return validators["port"](value)
        elif "email" in key.lower():
            return validators["email"](value)
        
        return True, "Valid"
    
    def backup_config(self) -> str:
        """
        Backup configuration file
        Return backup file path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"config/backups/config_{timestamp}.ini"
        
        os.makedirs("config/backups", exist_ok=True)
        shutil.copy(self.config_file, backup_file)
        
        logger.info(f"Configuration backed up to {backup_file}")
        return backup_file
    
    def restore_config(self, backup_file: str) -> None:
        """Restore configuration file"""
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        # Backup current configuration
        self.backup_config()
        
        # Restore
        shutil.copy(backup_file, self.config_file)
        self.config.read(self.config_file)
        
        logger.info(f"Configuration restored from {backup_file}")
    
    def _save_config(self) -> None:
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def _log_config_change(self, section: str, key: str, action: str) -> None:
        """Record configuration change audit log"""
        logger.access(
            action="config_change",
            section=section,
            key=key,
            operation=action,
            timestamp=datetime.now().isoformat()
        )
```

### 2.5 Configuration Encryption

```python
from cryptography.fernet import Fernet

class ConfigEncryption:
    @staticmethod
    def generate_key() -> str:
        """Generate new encryption key"""
        return Fernet.generate_key().decode()
    
    @staticmethod
    def encrypt_value(value: str, key: str) -> str:
        """Encrypt configuration value"""
        cipher = Fernet(key.encode())
        encrypted = cipher.encrypt(value.encode())
        return f"encrypted:{encrypted.decode()}"
    
    @staticmethod
    def decrypt_value(encrypted_value: str, key: str) -> str:
        """Decrypt configuration value"""
        cipher = Fernet(key.encode())
        encrypted_data = encrypted_value.replace("encrypted:", "")
        return cipher.decrypt(encrypted_data.encode()).decode()
```

### 2.6 Configuration Validation Rules

```python
class ConfigValidator:
    @staticmethod
    def _validate_url(url: str) -> Tuple[bool, str]:
        """Validate URL format"""
        import re
        pattern = r'^https?://[\w\-.]+(:\d+)?(/.*)?$'
        if re.match(pattern, url):
            return True, "Valid URL"
        return False, "Invalid URL format"
    
    @staticmethod
    def _validate_port(port: str) -> Tuple[bool, str]:
        """Validate port range"""
        try:
            port_num = int(port)
            if 1 <= port_num <= 65535:
                return True, "Valid port"
            return False, "Port must be between 1 and 65535"
        except ValueError:
            return False, "Port must be a number"
    
    @staticmethod
    def _validate_email(email: str) -> Tuple[bool, str]:
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return True, "Valid email"
        return False, "Invalid email format"
```

---

## 3. Story Breakdown

### Story 1: Configuration Read API
**Priority:** P0 | **Effort:** 2 days

### Story 2: Configuration Update API
**Priority:** P0 | **Effort:** 3 days

### Story 3: Configuration Encryption
**Priority:** P0 | **Effort:** 2 days

### Story 4: Configuration Validation
**Priority:** P1 | **Effort:** 2 days

### Story 5: Configuration Backup & Restore
**Priority:** P1 | **Effort:** 2 days

### Story 6: Configuration Audit Logging
**Priority:** P2 | **Effort:** 1 day

---

## 4. Dependencies

### Technical Dependencies
- **Python ConfigParser** - INI file parsing
- **Cryptography (Fernet)** - Configuration encryption
- **FastAPI** 0.104+

### Module Dependencies
- **Logging Module** - Record configuration changes
- **API Key Authentication** - Interface security

---

## 5. Risks & Challenges

| Risk | Level | Mitigation |
|------|-------|------------|
| Configuration file corruption | High | Automatic backup, checksum validation |
| Encryption key leakage | High | Environment variable storage, regular rotation |
| Invalid configuration causing system unavailable | High | Configuration validation, gradual rollout |
| Concurrent write conflicts | Medium | File locking mechanism |

---

## 6. Testing Strategy

### Unit Tests
- Configuration read/write
- Encrypt/decrypt logic
- Validation rules

### Integration Tests
- Complete configuration update workflow
- Configuration backup/restore
- Configuration validation scenarios

---

## 7. Monitoring Metrics

```python
config_read_total                      # Configuration read count
config_update_total                    # Configuration update count
config_validation_failed_total         # Configuration validation failures
config_backup_total                    # Configuration backups
```

---

## Appendix

### A. Error Code Definitions

| Error Code | HTTP | Description |
|------------|------|-------------|
| CONFIG_NOT_FOUND | 404 | Configuration item not found |
| CONFIG_INVALID_FORMAT | 400 | Invalid configuration format |
| CONFIG_VALIDATION_FAILED | 400 | Configuration validation failed |
| CONFIG_BACKUP_FAILED | 500 | Configuration backup failed |

### B. Related Documentation

- [PRD - System Management](../prd.md#23-系统管理)
- [Configuration Management Best Practices](../standards/config-management.md)

---

**Document Maintainer:** PM Agent  
**Last Updated:** 2026-01-05
