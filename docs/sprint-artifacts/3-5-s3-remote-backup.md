# Story 5: S3 Remote Backup

**Story ID:** BACKUP-005  
**Priority:** P2  
**Estimated Effort:** 3 days  
**Status:** ready-for-dev

## User Story

**As a** Websoft9 administrator  
**I want to** store backups on Amazon S3 or compatible storage  
**So that** I have off-site backups for disaster recovery

## Acceptance Criteria

✅ Upload to S3 in < 10 minutes for 5GB backup  
✅ Support S3-compatible storage (MinIO, Wasabi)  
✅ Resumable uploads for large files  
✅ Automatic retry on network failure  
✅ Backup encrypted before upload  
✅ Download from S3 for restore

## Technical Tasks

- [ ] Integrate Boto3 SDK
- [ ] Implement multipart upload for large files
- [ ] Add upload progress tracking
- [ ] Implement resumable upload
- [ ] Add S3 download for restore
- [ ] Write S3 integration tests (with mocked S3)

## Configuration

```yaml
backup:
  storage:
    s3_bucket: "websoft9-backups"
    s3_region: "us-east-1"
    s3_access_key: "${AWS_ACCESS_KEY_ID}"
    s3_secret_key: "${AWS_SECRET_ACCESS_KEY}"
    s3_endpoint: "https://s3.amazonaws.com"  # Or MinIO endpoint
```

## Test Scenarios

1. Upload to S3 succeeds
2. Large file uses multipart upload
3. Network failure triggers retry
4. Download from S3 for restore works
5. S3-compatible storage (MinIO) works
6. Invalid credentials fail gracefully
