# Epic: 备份与恢复

**关联 PRD:** [FR-BACKUP-001](../prd.md#25-备份与恢复)  
**负责人:** Product Manager  
**状态:** Planning  
**优先级:** P1 (重要)  
**预估工作量:** 3-4 周

---

## 1. Epic 概述

### 1.1 业务目标

提供应用数据和系统配置的备份恢复能力，确保数据安全和业务连续性。

### 1.2 核心价值

- 应用数据定期自动备份
- 支持手动备份和恢复
- 备份数据加密存储
- 备份到本地或远程存储（S3）
- 一键恢复到指定时间点
- 备份策略灵活配置

### 1.3 验收标准

✅ 应用数据备份完成时间 < 5分钟（10GB）  
✅ 备份文件加密存储  
✅ 支持增量备份  
✅ 恢复成功率 > 98%  
✅ 备份空间占用 < 原数据 1.5倍  
✅ 支持远程备份到 S3  

---

## 2. 技术规范

### 2.1 架构设计

#### 备份架构

```
应用数据卷 → 备份引擎 → 压缩加密 → 本地存储 / S3
                ↓
        备份元数据记录 (SQLite/PostgreSQL)
```

#### 恢复流程

```
备份文件 → 验证完整性 → 解密解压 → 恢复到数据卷 → 重启应用
```

### 2.2 API 端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/v1/backups` | GET | 获取备份列表 | API Key |
| `/api/v1/backups/{app_id}` | POST | 创建备份 | API Key |
| `/api/v1/backups/{backup_id}` | GET | 获取备份详情 | API Key |
| `/api/v1/backups/{backup_id}` | DELETE | 删除备份 | API Key |
| `/api/v1/backups/{backup_id}/restore` | POST | 恢复备份 | API Key |
| `/api/v1/backups/schedule` | GET | 获取备份计划 | API Key |
| `/api/v1/backups/schedule` | PUT | 更新备份计划 | API Key |
| `/api/v1/backups/download/{backup_id}` | GET | 下载备份文件 | API Key |

#### 示例：创建备份

**请求:**
```http
POST /api/v1/backups/wordpress001
X-API-Key: <key>
Content-Type: application/json

{
  "backup_type": "full",
  "description": "手动备份",
  "include_database": true,
  "include_uploads": true,
  "compress": true,
  "encrypt": true,
  "storage_location": "local"
}
```

**响应:**
```json
{
  "code": 200,
  "message": "Backup created successfully",
  "data": {
    "backup_id": "backup_20260105_103000",
    "app_id": "wordpress001",
    "backup_type": "full",
    "size_bytes": 524288000,
    "created_at": "2026-01-05T10:30:00Z",
    "storage_location": "local",
    "file_path": "/var/websoft9/backups/wordpress001/backup_20260105_103000.tar.gz.enc",
    "status": "completed"
  }
}
```

### 2.3 数据模型

#### 备份记录

```python
class Backup(BaseModel):
    backup_id: str                     # 备份唯一标识
    app_id: str                        # 应用 ID
    app_name: str                      # 应用名称
    backup_type: str                   # full, incremental, differential
    description: Optional[str]
    size_bytes: int                    # 备份大小
    compressed: bool                   # 是否压缩
    encrypted: bool                    # 是否加密
    storage_location: str              # local, s3
    file_path: str                     # 备份文件路径
    s3_bucket: Optional[str]           # S3 桶名
    s3_key: Optional[str]              # S3 对象键
    checksum: str                      # 校验和（SHA256）
    status: str                        # pending, in_progress, completed, failed
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
```

#### 备份策略

```python
class BackupSchedule(BaseModel):
    schedule_id: str
    app_id: str
    enabled: bool
    frequency: str                     # daily, weekly, monthly
    time: str                          # HH:MM
    day_of_week: Optional[int]         # 0-6 (周日-周六)
    day_of_month: Optional[int]        # 1-31
    retention_days: int                # 保留天数
    backup_type: str
    include_database: bool
    include_uploads: bool
    storage_location: str
```

### 2.4 核心服务设计

#### backup_manager.py

```python
import tarfile
import hashlib
from cryptography.fernet import Fernet
import subprocess

class BackupManager:
    def __init__(self):
        self.backup_dir = "/var/websoft9/backups"
        self.encryption_key = os.getenv("BACKUP_ENCRYPTION_KEY")
        self.cipher = Fernet(self.encryption_key.encode())
    
    def create_backup(self, app_id: str, config: Dict) -> Backup:
        """
        创建备份流程:
        1. 停止应用（可选）
        2. 导出 Docker 数据卷
        3. 导出数据库（如果需要）
        4. 压缩文件
        5. 加密备份（如果需要）
        6. 计算校验和
        7. 上传到存储（本地/S3）
        8. 记录备份元数据
        9. 重启应用
        """
        backup_id = self._generate_backup_id(app_id)
        backup = Backup(
            backup_id=backup_id,
            app_id=app_id,
            backup_type=config["backup_type"],
            status="in_progress",
            created_at=datetime.now()
        )
        
        try:
            # 1. 获取应用数据卷
            volumes = self._get_app_volumes(app_id)
            
            # 2. 导出数据卷
            volume_backup_path = self._backup_volumes(app_id, volumes)
            
            # 3. 导出数据库（如果需要）
            if config.get("include_database"):
                db_backup_path = self._backup_database(app_id)
                volume_backup_path.append(db_backup_path)
            
            # 4. 压缩
            if config.get("compress", True):
                compressed_file = self._compress_files(
                    volume_backup_path, 
                    backup_id
                )
            
            # 5. 加密
            if config.get("encrypt", True):
                encrypted_file = self._encrypt_file(compressed_file)
                final_file = encrypted_file
            else:
                final_file = compressed_file
            
            # 6. 计算校验和
            checksum = self._calculate_checksum(final_file)
            
            # 7. 上传到存储
            if config["storage_location"] == "s3":
                self._upload_to_s3(final_file, backup_id)
            
            # 8. 更新备份记录
            backup.status = "completed"
            backup.file_path = final_file
            backup.checksum = checksum
            backup.size_bytes = os.path.getsize(final_file)
            backup.completed_at = datetime.now()
            
            self._save_backup_metadata(backup)
            
            logger.info(f"Backup completed: {backup_id}")
            return backup
            
        except Exception as e:
            backup.status = "failed"
            backup.error_message = str(e)
            self._save_backup_metadata(backup)
            logger.error(f"Backup failed: {e}")
            raise
    
    def restore_backup(self, backup_id: str, restore_config: Dict) -> Dict:
        """
        恢复备份流程:
        1. 验证备份文件完整性
        2. 停止应用
        3. 下载备份文件（如果在 S3）
        4. 解密备份文件
        5. 解压缩文件
        6. 恢复数据卷
        7. 恢复数据库
        8. 重启应用
        9. 验证恢复结果
        """
        backup = self._get_backup_metadata(backup_id)
        
        try:
            # 1. 验证校验和
            if not self._verify_checksum(backup.file_path, backup.checksum):
                raise Exception("Backup file corrupted")
            
            # 2. 停止应用
            if restore_config.get("stop_app", True):
                self._stop_app(backup.app_id)
            
            # 3. 从 S3 下载（如果需要）
            if backup.storage_location == "s3":
                local_file = self._download_from_s3(backup.s3_bucket, backup.s3_key)
            else:
                local_file = backup.file_path
            
            # 4. 解密
            if backup.encrypted:
                decrypted_file = self._decrypt_file(local_file)
            else:
                decrypted_file = local_file
            
            # 5. 解压
            extracted_dir = self._extract_archive(decrypted_file)
            
            # 6. 恢复数据卷
            self._restore_volumes(backup.app_id, extracted_dir)
            
            # 7. 恢复数据库
            if restore_config.get("restore_database", True):
                self._restore_database(backup.app_id, extracted_dir)
            
            # 8. 重启应用
            self._start_app(backup.app_id)
            
            logger.info(f"Restore completed: {backup_id}")
            return {"status": "success", "backup_id": backup_id}
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            # 尝试恢复原应用
            self._start_app(backup.app_id)
            raise
    
    def _backup_volumes(self, app_id: str, volumes: List[str]) -> List[str]:
        """导出 Docker 数据卷"""
        backup_paths = []
        
        for volume in volumes:
            output_file = f"{self.backup_dir}/{app_id}/{volume}.tar"
            
            # 使用 docker run 导出数据卷
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{volume}:/volume",
                "-v", f"{self.backup_dir}/{app_id}:/backup",
                "busybox",
                "tar", "cvf", f"/backup/{volume}.tar", "-C", "/volume", "."
            ]
            
            subprocess.run(cmd, check=True)
            backup_paths.append(output_file)
        
        return backup_paths
    
    def _backup_database(self, app_id: str) -> str:
        """
        导出数据库
        - MySQL: mysqldump
        - PostgreSQL: pg_dump
        - MongoDB: mongodump
        """
        app = self._get_app_info(app_id)
        db_type = app.get("database_type")
        
        if db_type == "mysql":
            return self._backup_mysql(app_id, app)
        elif db_type == "postgres":
            return self._backup_postgres(app_id, app)
        elif db_type == "mongodb":
            return self._backup_mongodb(app_id, app)
        else:
            logger.warning(f"Unknown database type: {db_type}")
            return None
    
    def _compress_files(self, files: List[str], backup_id: str) -> str:
        """压缩备份文件"""
        output_file = f"{self.backup_dir}/{backup_id}.tar.gz"
        
        with tarfile.open(output_file, "w:gz") as tar:
            for file in files:
                tar.add(file, arcname=os.path.basename(file))
        
        return output_file
    
    def _encrypt_file(self, file_path: str) -> str:
        """加密备份文件"""
        encrypted_file = f"{file_path}.enc"
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        encrypted_data = self.cipher.encrypt(data)
        
        with open(encrypted_file, "wb") as f:
            f.write(encrypted_data)
        
        # 删除原文件
        os.remove(file_path)
        
        return encrypted_file
    
    def _decrypt_file(self, encrypted_file: str) -> str:
        """解密备份文件"""
        decrypted_file = encrypted_file.replace(".enc", "")
        
        with open(encrypted_file, "rb") as f:
            encrypted_data = f.read()
        
        decrypted_data = self.cipher.decrypt(encrypted_data)
        
        with open(decrypted_file, "wb") as f:
            f.write(decrypted_data)
        
        return decrypted_file
    
    def _calculate_checksum(self, file_path: str) -> str:
        """计算文件 SHA256 校验和"""
        sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _upload_to_s3(self, file_path: str, backup_id: str) -> None:
        """上传备份到 S3"""
        import boto3
        
        s3_client = boto3.client("s3")
        bucket = os.getenv("BACKUP_S3_BUCKET")
        key = f"backups/{backup_id}/{os.path.basename(file_path)}"
        
        s3_client.upload_file(file_path, bucket, key)
        logger.info(f"Uploaded to S3: s3://{bucket}/{key}")
```

### 2.5 定时备份

```python
import schedule
import time

class BackupScheduler:
    def __init__(self):
        self.backup_manager = BackupManager()
    
    def start(self):
        """启动定时备份服务"""
        schedules = self._load_schedules()
        
        for sched in schedules:
            if not sched.enabled:
                continue
            
            if sched.frequency == "daily":
                schedule.every().day.at(sched.time).do(
                    self._run_scheduled_backup, sched
                )
            elif sched.frequency == "weekly":
                schedule.every().week.at(sched.time).do(
                    self._run_scheduled_backup, sched
                )
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def _run_scheduled_backup(self, sched: BackupSchedule):
        """执行定时备份"""
        try:
            backup = self.backup_manager.create_backup(
                sched.app_id,
                {
                    "backup_type": sched.backup_type,
                    "include_database": sched.include_database,
                    "include_uploads": sched.include_uploads,
                    "storage_location": sched.storage_location
                }
            )
            
            # 清理过期备份
            self._cleanup_old_backups(sched.app_id, sched.retention_days)
            
            logger.info(f"Scheduled backup completed: {backup.backup_id}")
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")
    
    def _cleanup_old_backups(self, app_id: str, retention_days: int):
        """清理过期备份"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        old_backups = self._get_backups_before(app_id, cutoff_date)
        
        for backup in old_backups:
            self.backup_manager.delete_backup(backup.backup_id)
```

### 2.6 配置

```yaml
# config/backup.yaml
backup:
  storage:
    local_path: "/var/websoft9/backups"
    s3_bucket: "${BACKUP_S3_BUCKET}"
    s3_region: "us-east-1"
  
  encryption:
    enabled: true
    key: "${BACKUP_ENCRYPTION_KEY}"
  
  compression:
    enabled: true
    algorithm: "gzip"
    level: 6
  
  defaults:
    backup_type: "full"
    retention_days: 30
    storage_location: "local"
  
  limits:
    max_concurrent_backups: 2
    max_backup_size_gb: 50
```

---

## 3. Stories 拆分

### Story 1: 备份核心引擎

**优先级:** P0  
**工作量:** 5 天

**任务:**
- 数据卷导出逻辑
- 文件压缩功能
- 文件加密功能
- 校验和计算
- 编写备份测试

### Story 2: 数据库备份

**优先级:** P0  
**工作量:** 3 天

**任务:**
- MySQL 备份集成
- PostgreSQL 备份集成
- MongoDB 备份集成
- 编写数据库备份测试

### Story 3: 备份恢复功能

**优先级:** P0  
**工作量:** 4 天

**任务:**
- 备份文件验证
- 解密解压逻辑
- 数据卷恢复
- 数据库恢复
- 编写恢复测试

### Story 4: 定时备份

**优先级:** P1  
**工作量:** 3 天

**任务:**
- 备份计划配置
- 定时任务调度
- 自动清理过期备份
- 编写调度测试

### Story 5: S3 远程备份

**优先级:** P2  
**工作量:** 3 天

**任务:**
- S3 SDK 集成
- 上传/下载逻辑
- 断点续传支持
- 编写 S3 测试

### Story 6: 备份管理 API

**优先级:** P1  
**工作量:** 2 天

**任务:**
- 备份列表接口
- 备份删除接口
- 备份下载接口
- 编写 API 测试

---

## 4. 依赖关系

### 技术依赖

- **Docker** - 数据卷管理
- **Cryptography (Fernet)** - 文件加密
- **Boto3** - S3 集成
- **schedule** - 定时任务

### 模块依赖

- **应用管理** - 获取应用信息
- **日志模块** - 记录备份操作

---

## 5. 风险与挑战

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 备份过程中应用不可用 | 中 | 支持在线备份（不停机） |
| 备份文件过大 | 高 | 增量备份，压缩优化 |
| 恢复失败导致数据丢失 | 高 | 恢复前备份当前状态 |
| S3 上传失败 | 中 | 本地缓存，断点续传 |
| 加密密钥丢失 | 高 | 密钥备份方案，密钥恢复流程 |

---

## 6. 测试策略

### 单元测试
- 压缩/解压缩
- 加密/解密
- 校验和计算

### 集成测试
- 完整备份恢复流程
- 定时备份执行
- S3 上传下载

### 灾难恢复演练
- 模拟数据损坏
- 完整恢复验证

---

## 7. 监控指标

```python
backup_total                           # 备份总数
backup_success_total                   # 备份成功数
backup_failed_total                    # 备份失败数
backup_duration_seconds                # 备份耗时
restore_total                          # 恢复总数
restore_success_total                  # 恢复成功数
backup_size_bytes                      # 备份文件大小
```

---

## 附录

### A. 错误码定义

| 错误码 | HTTP | 说明 |
|--------|------|------|
| BACKUP_NOT_FOUND | 404 | 备份不存在 |
| BACKUP_CREATE_FAILED | 500 | 备份创建失败 |
| BACKUP_CORRUPTED | 500 | 备份文件损坏 |
| RESTORE_FAILED | 500 | 恢复失败 |
| BACKUP_QUOTA_EXCEEDED | 507 | 备份空间不足 |

### B. 相关文档

- [PRD - 备份与恢复](../prd.md#25-备份与恢复)
- [Docker 数据卷管理](https://docs.docker.com/storage/volumes/)

---

**文档维护:** PM Agent  
**最后更新:** 2026-01-05
