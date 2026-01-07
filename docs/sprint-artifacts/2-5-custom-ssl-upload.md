# Story 5: Custom SSL Certificate Upload

**Story ID:** PROXY-005  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 user  
**I want to** upload my own SSL certificates  
**So that** I can use wildcard certificates or certificates from other providers

## Acceptance Criteria

✅ Support PEM format certificate upload  
✅ Validate certificate format before acceptance  
✅ Secure storage of private keys  
✅ Certificate chain validation  
✅ Display expiration date after upload

## Technical Tasks

- [ ] Implement certificate file upload endpoint
- [ ] Add PEM format validation
- [ ] Validate certificate chain completeness
- [ ] Secure private key storage (encryption)
- [ ] Parse certificate metadata (expiry, domains)
- [ ] Write upload validation tests

## API Specification

```http
POST /api/v1/proxys/ssl/certificates/upload
X-API-Key: <key>
Content-Type: multipart/form-data

certificate: <file>
private_key: <file>
intermediate_cert: <file> (optional)

Response:
{
  "code": 200,
  "message": "Certificate uploaded successfully",
  "data": {
    "certificate_id": "cert_123",
    "domain_names": ["*.example.com"],
    "expires_at": "2027-01-01T00:00:00Z",
    "issuer": "DigiCert Inc"
  }
}
```

## Test Scenarios

1. Valid certificate upload succeeds
2. Invalid PEM format rejected
3. Expired certificate rejected
4. Private key mismatch detected
5. Wildcard certificate accepted
