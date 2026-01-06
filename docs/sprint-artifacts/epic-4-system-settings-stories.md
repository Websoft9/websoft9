# Epic 4: 系统设置管理 - User Stories

**Epic ID:** epic-4  
**Epic Title:** 系统设置管理  
**Status:** In Development  
**Priority:** P0

---

## Story 4-1: 获取所有系统设置

**Story ID:** 4-1-get-all-settings  
**Title:** 获取所有配置节的设置信息  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** Websoft9 管理员  
**I want to** 查看所有系统配置  
**So that** 我可以了解当前的系统设置

### Acceptance Criteria

- [x] AC1: GET `/api/v1/settings` 返回所有配置
- [x] AC2: 返回 `AppSettings` 模型
- [x] AC3: 包含所有配置节（portainer, nginx_proxy_manager, gitea, apphub）
- [x] AC4: 敏感信息脱敏（密码显示为 ******）
- [x] AC5: 响应时间 < 100ms

### Tasks

- [x] 实现 `/settings` GET 路由
  - [x] 调用 `SettingsManager.read_all()`
- [x] 实现 `SettingsManager.read_all()` 方法
  - [x] 读取所有 INI 配置节
  - [x] 解析为字典格式
  - [x] 脱敏敏感字段（password）
  - [x] 返回 AppSettings 模型
- [x] 定义 `AppSettings` Pydantic 模型
  - [x] portainer: dict
  - [x] nginx_proxy_manager: dict
  - [x] gitea: dict
  - [x] apphub: dict
- [x] 实现敏感信息脱敏逻辑
  - [x] 识别 password, secret, key 字段
  - [x] 替换为 "******"
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/settings.py`
- `apphub/src/services/settings_manager.py`
- `apphub/src/schemas/appSettings.py`
- `tests/test_settings_get.py`

---

## Story 4-2: 获取指定配置节

**Story ID:** 4-2-get-section  
**Title:** 获取特定配置节的设置  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 0.5 day

### User Story

**As a** Websoft9 管理员  
**I want to** 只查看某个服务的配置  
**So that** 我可以快速定位需要的设置

### Acceptance Criteria

- [x] AC1: GET `/api/v1/settings/{section}` 返回指定配置节
- [x] AC2: section 可以是: portainer, nginx_proxy_manager, gitea, apphub
- [x] AC3: 配置节不存在返回 404
- [x] AC4: 敏感信息脱敏
- [x] AC5: 响应时间 < 50ms

### Tasks

- [x] 实现 `/settings/{section}` GET 路由
  - [x] Path 参数: section
  - [x] 调用 `SettingsManager.read_section()`
- [x] 实现 `read_section()` 方法
  - [x] 验证 section 存在
  - [x] 读取该配置节
  - [x] 脱敏处理
  - [x] 返回配置字典
- [x] 错误处理
  - [x] section 不存在
- [x] 编写测试

### File List

- `apphub/src/api/v1/routers/settings.py`
- `apphub/src/services/settings_manager.py`
- `tests/test_settings_get_section.py`

---

## Story 4-3: 更新配置项

**Story ID:** 4-3-update-setting  
**Title:** 更新指定配置节的单个配置项  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 管理员  
**I want to** 修改系统配置  
**So that** 我可以调整服务参数

### Acceptance Criteria

- [x] AC1: PUT `/api/v1/settings/{section}?key=xx&value=yy` 更新配置
- [x] AC2: 配置立即写入 INI 文件
- [x] AC3: 返回更新后的配置
- [x] AC4: 配置格式验证
- [x] AC5: section 或 key 不存在返回 404
- [x] AC6: 敏感配置（如密码）加密存储

### Tasks

- [x] 实现 `/settings/{section}` PUT 路由
  - [x] Path 参数: section
  - [x] Query 参数: key, value
  - [x] 调用 `SettingsManager.write_section()`
- [x] 实现 `write_section()` 方法
  - [x] 验证 section 存在
  - [x] 验证 key 有效
  - [x] 验证 value 格式
  - [x] 敏感值加密（如果是密码）
  - [x] 写入 INI 文件
  - [x] 返回更新后的配置
- [x] 实现配置验证逻辑
  - [x] URL 格式验证
  - [x] 端口号验证（1-65535）
  - [x] Email 格式验证
- [x] 实现敏感值加密存储
  - [x] 使用 Fernet 加密
  - [x] 密钥管理
- [x] 编写测试
  - [x] 测试更新成功
  - [x] 测试格式验证
  - [x] 测试敏感值加密

### Test Scenarios

**场景 1: 成功更新配置**
```
Given: section "apphub" 存在
And: key "media_url" 有效
When: PUT /api/v1/settings/apphub?key=media_url&value=https://new-url.com
Then: 返回 200
And: INI 文件更新
And: 返回新配置值
```

**场景 2: 无效的配置值**
```
Given: key "port" 期望数字
When: PUT /api/v1/settings/apphub?key=port&value=invalid
Then: 返回 400 "Invalid value format"
```

**场景 3: 密码加密存储**
```
Given: key "password"
When: PUT /api/v1/settings/portainer?key=password&value=secret123
Then: 返回 200
And: INI 文件中存储加密值
And: 读取时可正确解密
```

### File List

- `apphub/src/api/v1/routers/settings.py`
- `apphub/src/services/settings_manager.py`
- `apphub/src/core/config.py`
- `apphub/src/utils/encryption.py`
- `tests/test_settings_update.py`

---

## Story 4-4: SettingsManager 核心服务实现

**Story ID:** 4-4-settings-manager  
**Title:** 实现系统设置管理核心服务  
**Priority:** P0  
**Status:** ready-for-dev  
**Estimated Effort:** 2 days

### User Story

**As a** 开发人员  
**I want to** 封装配置管理的核心逻辑  
**So that** 所有模块可以统一使用配置服务

### Acceptance Criteria

- [x] AC1: SettingsManager 类封装所有配置操作
- [x] AC2: 支持 INI 文件的读写
- [x] AC3: 实现配置缓存机制
- [x] AC4: 提供配置变更通知
- [x] AC5: 线程安全的配置操作

### Tasks

- [x] 创建 `SettingsManager` 类
  - [x] `__init__()` - 初始化 ConfigParser
  - [x] `read_all()` - 读取所有配置
  - [x] `read_section(section)` - 读取配置节
  - [x] `write_section(section, key, value)` - 写配置
  - [x] `get_value(section, key)` - 获取单个值
  - [x] `set_value(section, key, value)` - 设置单个值
- [x] 实现 INI 文件操作
  - [x] 使用 ConfigParser 解析
  - [x] 写入时保持格式
  - [x] 处理特殊字符
- [x] 实现配置缓存
  - [x] 内存缓存配置（避免频繁读文件）
  - [x] 文件修改时刷新缓存
  - [x] TTL 机制（5分钟）
- [x] 实现线程安全
  - [x] 使用锁保护读写操作
- [x] 日志记录
  - [x] 配置读取日志
  - [x] 配置更新日志
- [x] 编写单元测试

### File List

- `apphub/src/services/settings_manager.py` - 主类
- `apphub/src/core/config.py` - 配置路径
- `tests/test_settings_manager.py` - 单元测试

---

## Story 4-5: ConfigManager 增强（现有代码改进）

**Story ID:** 4-5-config-manager-improve  
**Title:** 改进现有的 ConfigManager 类  
**Priority:** P1  
**Status:** ready-for-dev  
**Estimated Effort:** 1 day

### User Story

**As a** 开发人员  
**I want to** 改进现有的配置管理类  
**So that** 提供更好的配置读取性能和错误处理

### Acceptance Criteria

- [x] AC1: 优化 ConfigManager 的性能
- [x] AC2: 添加配置验证逻辑
- [x] AC3: 改进错误处理和日志
- [x] AC4: 向后兼容现有代码

### Tasks

- [x] 审查现有 `ConfigManager` 代码
- [x] 添加配置缓存
- [x] 添加配置验证方法
- [x] 改进错误消息
- [x] 添加单元测试
- [x] 更新文档

### File List

- `apphub/src/core/config.py`
- `tests/test_config_manager.py`

---

## Story 4-6: 配置变更审计日志（未来增强）

**Story ID:** 4-6-config-audit  
**Title:** 记录所有配置变更的审计日志  
**Priority:** P2  
**Status:** backlog  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 管理员  
**I want to** 查看配置的历史变更记录  
**So that** 我可以追溯配置修改和问题排查

### Acceptance Criteria

- [ ] AC1: 所有配置变更记录到审计日志
- [ ] AC2: 日志包含：时间、用户、配置项、旧值、新值
- [ ] AC3: 提供审计日志查询 API
- [ ] AC4: 支持按时间范围过滤

### Tasks

- [ ] 实现审计日志记录
- [ ] 设计审计日志存储（SQLite/PostgreSQL）
- [ ] 实现审计日志查询 API
- [ ] 编写测试

### File List

- `apphub/src/services/config_audit.py`
- `apphub/src/api/v1/routers/settings.py`
- `tests/test_config_audit.py`

---

## Story 4-7: 配置备份和恢复（未来增强）

**Story ID:** 4-7-config-backup  
**Title:** 支持配置的备份和恢复  
**Priority:** P2  
**Status:** backlog  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 管理员  
**I want to** 备份和恢复系统配置  
**So that** 我可以在配置错误时快速恢复

### Acceptance Criteria

- [ ] AC1: POST `/api/v1/settings/backup` 创建配置备份
- [ ] AC2: POST `/api/v1/settings/restore` 恢复配置
- [ ] AC3: 备份包含所有 INI 文件
- [ ] AC4: 恢复前验证配置格式

### Tasks

- [ ] 实现配置备份 API
- [ ] 实现配置恢复 API
- [ ] 配置验证逻辑
- [ ] 编写测试

### File List

- `apphub/src/api/v1/routers/settings.py`
- `apphub/src/services/settings_manager.py`
- `tests/test_config_backup.py`

---

## Story 4-8: 配置导入导出（未来增强）

**Story ID:** 4-8-config-export  
**Title:** 支持配置的导出和导入（JSON/YAML）  
**Priority:** P2  
**Status:** backlog  
**Estimated Effort:** 2 days

### User Story

**As a** Websoft9 管理员  
**I want to** 导出配置为 JSON 或 YAML  
**So that** 我可以在多个环境间迁移配置

### Acceptance Criteria

- [ ] AC1: GET `/api/v1/settings/export` 导出配置为 JSON
- [ ] AC2: POST `/api/v1/settings/import` 导入配置
- [ ] AC3: 支持 JSON 和 YAML 格式
- [ ] AC4: 导入前验证格式

### Tasks

- [ ] 实现导出 API
- [ ] 实现导入 API
- [ ] 格式转换（INI ↔ JSON/YAML）
- [ ] 格式验证
- [ ] 编写测试

### File List

- `apphub/src/api/v1/routers/settings.py`
- `apphub/src/services/settings_manager.py`
- `apphub/src/utils/format_converter.py`
- `tests/test_config_export.py`

---

**Total Stories: 8** (5 ready-for-dev + 3 backlog)  
**Total Estimated Effort: 14.5 days** (ready stories: 6.5 days)  
**Epic Status: Ready for Sprint Planning**
