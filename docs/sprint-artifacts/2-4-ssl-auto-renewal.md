# Story 4: SSL Certificate Auto-Renewal

**Story ID:** PROXY-004  
**Priority:** P1  
**Estimated Effort:** 2 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** automatically renew SSL certificates before they expire  
**So that** I don't experience downtime due to expired certificates

## Acceptance Criteria

✅ Daily check for certificates expiring within 30 days  
✅ Automatic renewal attempt for expiring certificates  
✅ Notification on renewal failure  
✅ Renewal success rate > 98%  
✅ Zero downtime during renewal

## Technical Tasks

- [ ] Implement scheduled task (cron/celery)
- [ ] Add certificate expiration monitoring
- [ ] Implement automatic renewal logic
- [ ] Add failure notification system
- [ ] Log all renewal attempts
- [ ] Write renewal simulation tests

## Implementation Notes

```python
class CertificateRenewalService:
    async def auto_renew_certificates(self):
        """Daily task to renew expiring certificates"""
        certificates = self.npm_api.get_certificates()
        
        for cert in certificates:
            if cert["provider"] != "letsencrypt":
                continue
            
            days_until_expiry = (cert["expires_at"] - datetime.now()).days
            
            if days_until_expiry <= 30:
                logger.info(f"Renewing certificate for {cert['domain_names']}")
                try:
                    self.npm_api.renew_certificate(cert["id"])
                except Exception as e:
                    logger.error(f"Renewal failed: {e}")
                    self.send_notification(cert, e)
```

## Test Scenarios

1. Certificate expiring in 25 days triggers renewal
2. Certificate expiring in 60 days does not trigger renewal
3. Renewal failure sends notification
4. Multiple certificates renewed in same run
5. Manual certificates (not Let's Encrypt) are skipped
