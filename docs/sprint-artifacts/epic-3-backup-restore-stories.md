# Epic 3: 备份与恢复 - User Stories

**Epic ID:** epic-3  
**Epic Title:** 备份与恢复  
**Status:** Planning  
**Priority:** P1

---

## Story 3-1: 创建应用备份

**Story ID:** 3-1-create-backup  
**Title:** 为指定应用创建备份快照  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 用户  
**I want to** 为应用创建数据备份  
**So that** 我可以在数据丢失时恢复

### Acceptance Criteria

- [x] AC1: POST `/api/v1/backup/{app_id}` 创建备份
- [x] AC2: 备份应用的数据卷（volumes）
- [x] AC3: 生成唯一的 snapshot_id
- [x] AC4: 备份元数据包含：app_id, 创建时间, 大小
- [x] AC5: 备份完成时间 < 5分钟（10GB数据）
- [x] AC6: 返回备份成功消息和 snapshot_id
- [x] AC7: 应用不存在返回 404

### Tasks

- [x] 实现 `/backup/{app_id}` POST 路由
  - [x] Path 参数: app_id
  - [x] 调用 `BackupManager.create_backup()`
- [x] 实现 `BackupManager.create_backup()` 方法
  - [x] 验证 app_id 存在
  - [x] 获取应用的数据卷路径
  - [x] 生成 snapshot_id（timestamp格式）
  - [x] 执行备份操作（tar/rsync）
  - [x] 保存备份元数据
  - [x] 返回备份结果
- [x] 备份存储逻辑
  - [x] 创建备份目录 `/var/websoft9/backups/{app_id}/`
  - [x] 压缩数据卷为 tar.gz
  - [x] 记录备份元数据（JSON）
- [x] 编写测试
  - [x] 测试备份创建流程
  - [x] 测试备份文件生成
  - [x] 测试元数据记录

### Test Scenarios

**场景 1: 成功备份 WordPress**
```
Given: WordPress 应用正在运行
When: POST /api/v1/backup/wordpress001
Then: 返回 200 "Backup created successfully"
And: 生成备份文件 /var/websoft9/backups/wordpress001/snapshot_xxx.tar.gz
And: 元数据记录到 snapshots.json
```

**场景 2: 应用不存在**
```
Given: app_id "invalid" 不存在
When: POST /api/v1/backup/invalid
Then: 返回 404 "Application not found"
```

### File List

- `apphub/src/api/v1/routers/backup.py`
- `apphub/src/services/back_manager.py`
- `apphub/src/utils/backup_utils.py`
- `tests/test_backup_create.py`

---

## Story 3-2: 列出备份快照

**Story ID:** 3-2-list-snapshots  
**Title:** 获取所有备份快照或按应用过滤  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 用户  
**I want to** 查看所有可用的备份快照  
**So that** 我可以选择合适的快照进行恢复

### Acceptance Criteria

- [x] AC1: GET `/api/v1/backup/snapshots` 返回所有快照列表
- [x] AC2: 支持 app_id Query 参数过滤
- [x] AC3: 返回 `List[BackupSnapshot]` 格式
- [x] AC4: 快照信息包含：snapshot_id, app_id, size, created_at
- [x] AC5: 按创建时间倒序排列（最新的在前）
- [x] AC6: 响应时间 < 1秒

### Tasks

- [x] 实现 `/backup/snapshots` GET 路由
  - [x] Query 参数: app_id (可选)
  - [x] 调用 `BackupManager.list_snapshots()`
- [x] 实现 `list_snapshots()` 方法
  - [x] 读取所有备份元数据
  - [x] 如果提供 app_id，过滤
  - [x] 按时间倒序排序
  - [x] 返回快照列表
- [x] 定义 `BackupSnapshot` Pydantic 模型
  - [x] snapshot_id: str
  - [x] app_id: str
  - [x] size_bytes: int
  - [x] created_at: datetime
  - [x] file_path: str
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/backup.py`
- `apphub/src/services/back_manager.py`
- `apphub/src/schemas/backupsnapshot.py`
- `tests/test_backup_list.py`

---

## Story 3-3: 删除备份快照

**Story ID:** 3-3-delete-snapshot  
**Title:** 删除不需要的备份快照释放空间  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 用户  
**I want to** 删除旧的备份快照  
**So that** 我可以释放磁盘空间

### Acceptance Criteria

- [x] AC1: DELETE `/api/v1/backup/snapshots/{snapshot_id}` 删除快照
- [x] AC2: 删除备份文件（tar.gz）
- [x] AC3: 从元数据中移除快照记录
- [x] AC4: 删除成功返回 204
- [x] AC5: snapshot_id 不存在返回 404
- [x] AC6: 删除失败返回 500 和错误详情

### Tasks

- [x] 实现 `/backup/snapshots/{snapshot_id}` DELETE 路由
  - [x] Path 参数: snapshot_id
  - [x] 调用 `BackupManager.delete_snapshot()`
- [x] 实现 `delete_snapshot()` 方法
  - [x] 验证 snapshot_id 存在
  - [x] 获取备份文件路径
  - [x] 删除文件
  - [x] 从元数据中移除
  - [x] 保存更新的元数据
- [x] 错误处理
  - [x] snapshot 不存在
  - [x] 文件删除失败
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/backup.py`
- `apphub/src/services/back_manager.py`
- `tests/test_backup_delete.py`

---

## Story 3-4: 恢复备份快照

**Story ID:** 3-4-restore-snapshot  
**Title:** 从快照恢复应用数据  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 3 days

### User Story

**As a** Websoft9 用户  
**I want to** 从备份快照恢复应用数据  
**So that** 我可以在数据丢失或错误操作后恢复应用

### Acceptance Criteria

- [x] AC1: POST `/api/v1/backup/restore/{app_id}/{snapshot_id}` 恢复快照
- [x] AC2: 停止应用容器
- [x] AC3: 解压备份文件到数据卷
- [x] AC4: 重启应用容器
- [x] AC5: 恢复成功率 > 98%
- [x] AC6: 恢复失败时不影响原数据
- [x] AC7: 返回恢复成功消息

### Tasks

- [x] 实现 `/backup/restore/{app_id}/{snapshot_id}` POST 路由
  - [x] Path 参数: app_id, snapshot_id
  - [x] 调用 `BackupManager.restore_backup()`
- [x] 实现 `restore_backup()` 方法
  - [x] 验证 app_id 和 snapshot_id 存在
  - [x] 验证快照属于该应用
  - [x] 停止应用容器
  - [x] 备份当前数据（临时备份）
  - [x] 解压快照到数据卷
  - [x] 重启容器
  - [x] 验证恢复成功
  - [x] 失败时回滚到临时备份
- [x] 错误处理和回滚逻辑
  - [x] 解压失败回滚
  - [x] 容器启动失败处理
- [x] 编写测试
  - [x] 测试完整恢复流程
  - [x] 测试回滚机制
  - [x] 测试错误场景

### Test Scenarios

**场景 1: 成功恢复**
```
Given: WordPress 应用和有效的 snapshot
When: POST /api/v1/backup/restore/wordpress001/snapshot_20260105
Then: 应用停止
And: 数据从快照恢复
And: 应用重启
And: 返回 200 "Snapshot restored successfully"
```

**场景 2: 快照不属于该应用**
```
Given: snapshot_id 属于另一个应用
When: POST /api/v1/backup/restore/app001/snapshot_other
Then: 返回 400 "Snapshot does not belong to this app"
```

**场景 3: 恢复失败回滚**
```
Given: 解压过程中失败
When: 恢复操作执行
Then: 自动回滚到临时备份
And: 应用数据保持原状
And: 返回 500 "Restore failed, rolled back"
```

### File List

- `apphub/src/api/v1/routers/backup.py`
- `apphub/src/services/back_manager.py`
- `apphub/src/utils/backup_utils.py`
- `tests/test_backup_restore.py`

---

## Story 3-5: BackupManager 核心服务实现

**Story ID:** 3-5-backup-manager  
**Title:** 实现备份管理核心服务类  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** 开发人员  
**I want to** 封装备份操作的核心逻辑  
**So that** 所有备份相关功能有统一的实现

### Acceptance Criteria

- [x] AC1: BackupManager 类封装所有备份操作
- [x] AC2: 支持备份元数据的持久化（JSON）
- [x] AC3: 实现备份文件的压缩和解压
- [x] AC4: 提供备份空间统计功能
- [x] AC5: 记录详细的操作日志

### Tasks

- [x] 创建 `BackupManager` 类
  - [x] `__init__()` - 初始化配置、备份路径
  - [x] `create_backup(app_id)` - 创建备份
  - [x] `list_snapshots(app_id)` - 列出快照
  - [x] `delete_snapshot(snapshot_id)` - 删除快照
  - [x] `restore_backup(app_id, snapshot_id)` - 恢复
  - [x] `get_backup_stats()` - 备份统计
- [x] 实现元数据管理
  - [x] 读取 snapshots.json
  - [x] 保存 snapshots.json
  - [x] 更新快照记录
- [x] 实现压缩/解压工具
  - [x] tar.gz 压缩
  - [x] tar.gz 解压
  - [x] 进度回调（可选）
- [x] 日志记录
  - [x] 备份开始/完成日志
  - [x] 恢复操作日志
  - [x] 错误日志
- [x] 配置管理
  - [x] 备份存储路径
  - [x] 最大保留快照数
  - [x] 压缩级别
- [x] 编写单元测试

### File List

- `apphub/src/services/back_manager.py` - 主类
- `apphub/src/utils/backup_utils.py` - 工具函数
- `apphub/src/core/config.py` - 配置
- `tests/test_backup_manager.py` - 单元测试

---

## Story 3-6: 备份空间管理（未来增强）

**Story ID:** 3-6-backup-quota  
**Title:** 实现备份空间配额和自动清理  
**Priority:** P2  
**Status:** backlog  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 管理员  
**I want to** 限制备份占用的磁盘空间  
**So that** 备份不会耗尽服务器存储

### Acceptance Criteria

- [ ] AC1: 配置最大备份空间限制
- [ ] AC2: 达到限制时自动删除最旧的快照
- [ ] AC3: 保留最近 N 个快照（可配置）
- [ ] AC4: 提供备份空间使用统计 API

### Tasks

- [ ] 实现空间配额检查
- [ ] 实现自动清理策略
- [ ] 添加备份统计 API
- [ ] 编写测试

### File List

- `apphub/src/services/back_manager.py`
- `apphub/src/utils/storage_utils.py`
- `tests/test_backup_quota.py`

---

## Story 3-7: 定时备份任务（未来增强）

**Story ID:** 3-7-scheduled-backup  
**Title:** 实现应用的定时自动备份  
**Priority:** P2  
**Status:** backlog  
**Estimated Effort:** 3 days

### User Story

**As a** Websoft9 用户  
**I want to** 配置应用的自动备份计划  
**So that** 我不用手动创建备份

### Acceptance Criteria

- [ ] AC1: 支持配置备份计划（每天/每周）
- [ ] AC2: 定时任务自动执行备份
- [ ] AC3: 备份失败发送告警
- [ ] AC4: 支持备份保留策略

### Tasks

- [ ] 实现备份计划配置 API
- [ ] 实现定时任务调度器
- [ ] 集成备份执行逻辑
- [ ] 告警通知机制
- [ ] 编写测试

### File List

- `apphub/src/services/backup_scheduler.py`
- `apphub/src/api/v1/routers/backup.py`
- `tests/test_scheduled_backup.py`

---

## Story 3-8: 远程备份存储（未来增强）

**Story ID:** 3-8-remote-backup  
**Title:** 支持备份到 S3 等远程存储  
**Priority:** P2  
**Status:** backlog  
**Estimated Effort:** 4 days

### User Story

**As a** Websoft9 用户  
**I want to** 将备份存储到云端（S3）  
**So that** 即使服务器故障也能恢复数据

### Acceptance Criteria

- [ ] AC1: 支持配置 S3 存储凭据
- [ ] AC2: 备份时同步上传到 S3
- [ ] AC3: 恢复时从 S3 下载
- [ ] AC4: 支持增量备份

### Tasks

- [ ] 集成 boto3 (AWS SDK)
- [ ] 实现 S3 上传/下载
- [ ] 配置管理
- [ ] 编写测试

### File List

- `apphub/src/services/s3_backup.py`
- `apphub/src/core/config.py`
- `tests/test_s3_backup.py`

---

**Total Stories: 8** (5 ready-for-dev + 3 backlog)  
**Total Estimated Effort: 17 days** (ready stories: 9 days)  
**Epic Status: Ready for Sprint Planning**
