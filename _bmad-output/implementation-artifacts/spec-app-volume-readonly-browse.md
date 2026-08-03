---
title: '应用详情卷文件只读浏览并移除旧 Volume 挂载链路'
type: 'refactor'
created: '2026-08-03'
status: 'in-progress'
baseline_commit: '4afe6cef'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前“我的应用 → 应用详情 → 数据”的卷文件弹窗复用未接入的 `/api/files/*` 全功能 Docker Volume 管理链路。该链路依赖将整个宿主机 Docker volumes 根目录挂载进 product 容器，超出所需权限边界；现有可见的终端文件功能则独立走 SSH/SFTP，不依赖该挂载。

**Approach:** 移除未接入的旧 Docker Volume 文件页面、API、files-agent 与 volumes-root 配置；新增仅用于当前应用详情的 Docker exec 只读浏览接口和精简 UI。通过当前应用 ID 限定 volume 与运行容器，支持目录浏览和小型 UTF-8 文本预览。

## Boundaries & Constraints

**Always:** 保留 SSH/SFTP Host Access 文件管理、`/var/run/docker.sock` 挂载及所有无关功能；新增 API 必须验证 volume 的 Compose project 归属当前 app；只读链路不得创建容器、写入文件或访问未归属当前应用的 volume；路径必须后端规范化且不得直接拼入 shell；目录和文本结果必须有条目/大小/超时边界。

**Ask First:** 若发现 `/api/files/*`、files-agent 或 Docker volumes-root 配置被未扫描到的运行时入口、发布脚本或外部契约使用，暂停并确认处置方式；若当前应用 ID 无法可靠匹配 Docker Compose project label，暂停确认映射规则。

**Never:** 不修改 Host Access 的 SSH/SFTP 后端和终端文件 UI；不保留写操作、下载或编辑能力于新的应用卷浏览；不通过 bind mount、helper 容器、host agent 或 docker cp 实现新浏览功能；不修改无关页面或业务流程。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| 浏览目录 | 当前应用的运行容器挂载目标 named volume | 返回目录、普通文件、来源容器及当前路径 | 最多 500 项并标记截断 |
| 预览文本 | 常规 UTF-8 文件且不超过 1 MiB | 返回只读文本内容 | 二进制、非 UTF-8、超限文件返回受控错误 |
| 归属校验 | volume label 不属于 URL app_id | 拒绝访问 | 403，不泄露文件内容 |
| 容器不可用 | 应用未运行、未挂卷、无 shell 或 exec 超时 | 不返回数据 | 明确的 409/422/504 错误 |
| 多容器共享卷 | 多个当前应用运行容器匹配同一 volume | 按稳定容器名选择并返回 source_container | 同一容器同卷多挂载点拒绝，不猜测 |

</frozen-after-approval>

## Code Map

- `console/src/features/my-apps/my-app-detail-page.tsx` -- 现有应用详情和卷浏览弹窗入口，持有 `appId`。
- `console/src/features/my-apps/volume-file-manager-dialog.tsx` -- 当前全功能卷文件弹窗，需收缩为只读并改接专用 API。
- `console/src/features/files/` -- 未接入导航的旧 Docker volume 全功能页面，需移除。
- `console/src/app/router/index.tsx` -- 含不可达 FilesPage import、预加载和路由分支，需清理。
- `apphub/src/api/v1/routers/files.py` -- 旧 `/api/files/*` API，需移除。
- `apphub/src/services/file_manager.py` -- 旧 Docker volume 文件服务，需移除。
- `apphub/src/files_agent.py` -- 旧 files-agent 与 helper 容器实现，需移除。
- `apphub/src/main.py` -- 注册新只读 router，并移除旧 router。
- `docker/docker-compose.yml`, `docker/docker-compose.dev.yml` -- 移除 Docker volumes-root 环境变量和 bind mount。
- `docker/supervisord.conf`, `scripts/`, `docker/scripts/`, `install/lib/common.sh` -- 清理 files-agent 及 Docker volumes-root 配置残留。
- `apphub/tests/test_file_manager.py`, `apphub/tests/test_files_agent.py` -- 移除旧链路测试。

## Tasks & Acceptance

**Execution:**
- [ ] 新增应用卷只读浏览 schema、service、router 和单元测试；通过 Docker SDK 定位当前应用运行容器中的目标 named-volume mount，并以固定 Docker exec 协议返回安全的目录/文本结果。
- [ ] 注册新 router，移除旧 `/api/files/*` router、FileManagerService 与 files-agent；清理仅服务于该链路的测试和运行配置。
- [ ] `console/src/features/my-apps/my-app-detail-page.tsx` -- 将当前 `appId` 传入浏览弹窗。
- [ ] `console/src/features/my-apps/volume-file-manager-dialog.tsx` -- 改接只读 API，移除所有 mutation UI/状态，显示来源容器与截断/不可预览反馈。
- [ ] `console/src/app/router/index.tsx` 和 `console/src/features/files/` -- 移除不可达旧 FilesPage 页面与路由残留。
- [ ] Compose、安装、同步、supervisor、服务控制脚本 -- 移除 volumes-root bind mount、环境变量及 files-agent 生命周期管理。
- [ ] 执行定向后端测试、前端构建、遗留引用扫描及运行时 Playwright 验证。

**Acceptance Criteria:**
- Given 已运行且挂载应用 volume 的 Compose 应用, when 从数据页打开查看文件, then 用户只能浏览目录和预览符合限制的文本，且显示实际来源容器。
- Given 目标 volume 不属于当前应用, when 直接调用新 API, then 请求被拒绝且不泄露文件数据。
- Given 应用停止、无兼容 Shell、目录超限或文件不可预览, when 用户尝试浏览, then UI 显示明确的受控错误或截断状态。
- Given 部署配置已更新, when 启动 product 容器, then 不再挂载或配置 Docker volumes root，且不再运行 files-agent。
- Given 终端文件功能, when 使用 SSH/SFTP 浏览与编辑主机文件, then 现有能力保持可用。

## Design Notes

新 API 采用 `/myapps/{app_id}/volumes/{volume_id}/browse/*`，与旧 `/files` 和 `/host-access/files` 明确隔离。目录协议不解析 `ls -l`，固定 Shell 脚本以 NUL 分隔传回 `name/type/size`；用户路径作为参数传入脚本。

## Verification

**Commands:**
- `cd apphub && pytest tests/test_app_volume_browse.py` -- 新 API 的归属、安全与边界测试通过。
- `cd apphub && pytest` -- 后端全套通过。
- `cd console && npm run build` -- TypeScript production build 通过。
- `rg 'WEBSOFT9_DOCKER_VOLUMES_ROOT|files-agent|/api/files|FilesPage' docker install scripts apphub console/src` -- 仅允许文档或明确保留项，无遗留运行时引用。
- Playwright 运行时检查 -- 数据页文件浏览只读可用；终端 SSH/SFTP 文件功能可用；product 容器未挂 volumes root 且 supervisor 无 files-agent。
