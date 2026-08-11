---
title: 'WordPress 外部 MySQL 安装模式'
type: 'feature'
created: '2026-08-06'
status: 'in-progress'
baseline_commit: 'a1748d3a'
context:
  - '{project-root}/docs/wordpress-external-mysql-pilot.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** App Store 已能从 Docker Library 发现 WordPress 的 `external-mysql` profile，但 Console 无法选择该模式，AppHub 也无法安全物化模板或初始化外部数据库。

**Approach:** 保持默认安装请求、模板和下游 Gitea/Portainer 流程不变；为可选 profile 增加通用前端选择、受限后端解析和 WordPress 外部 MySQL 初始化。

## Boundaries & Constraints

**Always:** 默认模式不发送 profile 字段且使用原始 `docker-compose.yml`/`.env`；profile 必须由本地完整模板对重新验证；最终仓库固定只有 `docker-compose.yml` 和 `.env`；管理员密码不得写入日志、状态、响应或最终 `.env`；运行账号使用现有 `W9_POWER_PASSWORD` 生成逻辑。

**Ask First:** 支持远程 Endpoint、其他数据库引擎、TLS、已安装应用迁移、外部资源自动清理、持久化管理员凭据。

**Never:** 为 WordPress 在 Console 硬编码字段或模式；信任客户端 profile 字段白名单；修改默认 WordPress 的安装与部署语义；删除外部数据库或账号。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| 默认安装 | 无 `profile` | 原请求与默认模板保持不变 | 沿用现有安装错误 |
| 外部 MySQL | 完整 profile 对及合规参数 | 物化外部模板，建库和低权限账号，部署 WordPress | 管理员密码不持久化 |
| 伪造 profile | profile 缺失、名称非法或字段超出 `.env.<profile>` | 在启动异步安装前拒绝 | 400，不回显秘密 |
| 数据库失败 | 无法连接、同名数据库、权限不足 | 不创建 Git/Stack，返回可操作的无秘密错误 | 不清理已创建外部资源 |

</frozen-after-approval>

## Code Map

- `console/src/features/app-store/app-store-model.ts` -- App Store 前端模型。
- `console/src/features/app-store/use-app-store-apps.ts` -- 合并静态安装 metadata。
- `console/src/features/app-store/app-store-page.tsx` -- 通用安装表单和请求。
- `apphub/src/schemas/appInstall.py` -- 安装 API 请求模型。
- `apphub/src/services/install_profile.py` -- profile 白名单解析、模板物化和敏感字段处理。
- AppHub 不连接外部 MySQL；用户负责预先创建目标数据库及可用账号。
- `apphub/src/services/common_check.py` -- 同步请求校验。
- `apphub/src/services/app_manager.py` -- 临时工作区物化与 provision 调用。

## Tasks & Acceptance

**Execution:**
- [ ] `console/src/features/app-store/*` -- 读取 profiles、选择模式、按命名约定隐藏密码，并仅在选择 profile 时提交 profile 和 profile_settings。
- [ ] `apphub/src/schemas/appInstall.py`、`apphub/src/services/common_check.py` -- 增加可选 profile 契约，并在异步任务前校验本地模板白名单和本地 Endpoint。
- [ ] `apphub/src/services/install_profile.py` -- 以 profile 配对文件覆盖临时工作区的固定 compose/.env，且移除管理员凭据。
- [x] 外部 MySQL 仅物化用户提供的已有数据库连接信息；不新增数据库驱动、不建库、不建用户或授权。
- [ ] `apphub/src/services/app_manager.py` -- 仅在 profile 存在时执行物化和 provision，之后复用既有推送/部署流程。
- [ ] `apphub/tests/` 与 Console 测试 -- 覆盖默认兼容、profile 白名单、模板归一化、秘密剔除和请求负载。

**Acceptance Criteria:**
- Given 默认 WordPress 安装，when 用户提交，then 请求、生成文件和部署行为与改动前一致。
- Given `external-mysql`，when 用户填写合规参数，then 最终 `.env` 含运行连接信息与新生成的 `W9_POWER_PASSWORD`，但不含管理员账号或密码。
- Given 未知 profile 或额外 profile 字段，when 请求安装，then API 在创建安装任务前以 400 拒绝。
- Given 外部 MySQL 初始化失败，when 后端报告错误，then 错误、日志和状态中不含管理员密码。

## Design Notes

`settings` 继续表示默认模板字段；`profile_settings` 只表示选择 profile 后的模板字段。profile 物化发生在复制整个应用目录之后、初始化 `.env` 之前，因此后续 Git、镜像拉取和 Portainer 无需识别额外文件名。

## Verification

**Commands:**
- `cd apphub && pytest tests/test_install_profiles.py` -- profile 校验和物化通过。
- `cd console && npm run build` -- TypeScript 构建通过。
- `docker compose -f docker/docker-compose.dev.yml up -d --build` -- 运行容器包含改动。
- `docker exec websoft9-dev ...` -- 真实 App Store 入口验证默认及外部模式。