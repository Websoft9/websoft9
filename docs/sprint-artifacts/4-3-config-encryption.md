# Story 3: Configuration Encryption

**Story ID:** SETTINGS-003  
**Priority:** P0  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** automatically encrypt sensitive configuration values  
**So that** passwords and secrets are not stored in plaintext

## Acceptance Criteria

✅ Passwords automatically encrypted on write  
✅ Encrypted values prefixed with "encrypted:"  
✅ Decryption transparent on read  
✅ Encryption key stored securely (environment variable)  
✅ Support for key rotation  
✅ Fernet encryption standard

## Technical Tasks

- [ ] Integrate Cryptography library (Fernet)
- [ ] Implement encrypt/decrypt functions
- [ ] Auto-detect sensitive keys (password, secret, token, key)
- [ ] Add encryption on config write
- [ ] Add decryption on config read
- [ ] Write encryption tests

## Implementation Notes

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

## Test Scenarios

1. Password saved as encrypted in config file
2. Encrypted value decrypted correctly on read
3. Non-encrypted values pass through unchanged
4. Auto-detection of sensitive keys works
5. Invalid encryption key fails gracefully
6. Re-encryption with new key works
