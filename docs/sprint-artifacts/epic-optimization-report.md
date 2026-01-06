# Epic 优化总结报告

**日期:** 2026-01-06  
**执行者:** Dev Agent  
**项目:** Websoft9

---

## ✅ 完成的优化

### 1. **API 路径和端点修正**

#### App Management Epic
- ✅ 添加了实际存在的 `/apps/{app_id}/redeploy` API（PUT 方法，支持流式日志）
- ✅ 添加了 `/apps/{app_id}/remove` 和 `/apps/{app_id}/error/remove` API
- ✅ 移除了未实现的 `/apps/{app_id}/logs` API
- ✅ 修正了 install API 的行为说明（异步后台执行）

#### Proxy Management Epic
- ✅ 修正 API 路径: `/api/v1/proxy/` → `/api/v1/proxys/`
- ✅ 修正证书 API: `/proxys/certificates` → `/proxys/ssl/certificates`
- ✅ 更新 API 说明：按 `proxy_id` 而非 `app_id` 删除
- ✅ 移除了未实现的自定义证书上传功能
- ✅ 简化了创建代理的请求体（只需 domain_names）

#### Backup & Restore Epic
- ✅ 修正 API 路径: `/api/v1/backups` → `/api/v1/backup`
- ✅ 移除了未实现的功能：
  - 定时备份 (`/backup/schedule`)
  - 备份下载 (`/backup/download`)
  - 获取单个备份详情
- ✅ 简化了备份请求（只需 app_id，无需复杂配置）
- ✅ 修正了恢复 API 路径格式

#### System Settings Epic
- ✅ 修正 API 参数方式：从路径参数改为 Query 参数
- ✅ 更新端点: `/settings/{section}/{key}` → `/settings/{section}?key=xx&value=yy`
- ✅ 移除了未实现的功能：
  - DELETE 配置
  - 配置验证 API
  - 配置备份/恢复 API

---

## 📊 对比统计

| Epic | 原 API 数量 | 实际 API 数量 | 修正项 |
|------|------------|--------------|--------|
| App Management | 11 | 12 | +2 新增, -1 移除 |
| Proxy Management | 6 | 5 | -1 移除 |
| Backup & Restore | 8 | 4 | -4 简化 |
| System Settings | 8 | 3 | -5 简化 |

---

## 🎯 下一步行动

### 推荐工作流：

1. **生成详细的 User Stories** (使用 BMAD 工作流)
   ```
   @sm *create-epics-and-stories
   ```
   这将从更新后的 Epics 生成可执行的 Stories

2. **初始化 Sprint 跟踪**
   ```
   @sm *sprint-planning
   ```
   生成 `sprint-status.yaml` 来跟踪开发进度

3. **开始开发循环**
   - 使用 `*sprint-status` 查看当前状态
   - 使用 `*dev-story` 实施具体的 story
   - 使用 `*code-review` 审查代码质量

---

## 📝 注意事项

### Epic 保留的"规划性"功能（未实现但可能需要）:

#### App Management
- 应用日志查看功能（Epic 提到但未实现）

#### Proxy Management  
- 自定义 SSL 证书上传
- 访问控制列表 (ACL)
- HTTP 基本认证

#### Backup & Restore
- 定时备份策略
- 备份加密
- S3 远程存储
- 备份文件下载

#### System Settings
- 配置删除功能
- 配置验证
- 配置备份/恢复

**这些功能可以作为未来的增强点，在新的 Epics 或 Stories 中规划。**

---

## ✅ 验证建议

建议对每个 Epic 运行以下验证：

1. **API 测试验证**
   - 使用 Swagger UI (`/api/docs`) 测试所有端点
   - 确认请求/响应格式与 Epic 描述一致

2. **功能完整性检查**
   - 验证每个验收标准是否可测试
   - 确认 Stories 分解是否覆盖所有功能点

3. **代码覆盖率**
   - 检查是否有测试覆盖
   - 识别缺少测试的 API 端点

---

**Epic 优化完成！所有文件已更新以准确反映实际代码实现。**
