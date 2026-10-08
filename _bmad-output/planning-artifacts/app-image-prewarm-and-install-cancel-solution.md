# 应用镜像预拉与安装取消实施规格

**状态：** 已实施（含调度与历史保留优化）
**日期：** 2026-10-08

本文定义应用镜像预拉与安装取消的目标行为、数据契约和验收条件。除标为【待验】的 Docker daemon 行为外，规则均为实施要求。

## 1. 目标与边界

| 能力 | 目标 |
|---|---|
| 镜像预拉 | 用户可提前下载指定应用版本的全部默认镜像；安装时复用本地镜像层。 |
| 安装取消 | 用户只能在拉取镜像阶段请求取消；取消不自动删除已创建的资源。 |

**范围内：** 计划任务扩展、镜像拉取 CLI、安装状态与取消通道、API、控制台和测试。

**范围外：** 通用安装编排重构、Portainer 内部取消、镜像清理/回收、预拉优先级和百分比进度。

### 关键事实

- 安装的耗时主要在 Step 3：`pull_images_from_yml` 调用 `pull_with_fallback` 拉取镜像。
- Step 1/2（Gitea）和 Step 4/5（建栈、域名）不可取消；仅 Step 3 可取消。
- Docker SDK 停止消费拉取生成器只会**请求**中止。连接无输出时，取消延迟受 60 秒读超时约束。【待验】daemon 是否立即停止下载。
- 计划任务调度器由 cron 独立启动；进程内 `threading.RLock()` 不能跨 tick 互斥。

## 2. 不可变决策

| 项 | 决策 |
|---|---|
| 队列 | 全局 FIFO，最多 5 个未完成预拉任务；同一时间只运行 1 个。 |
| 调度 | 入队、重试、完成和取消后主动接续；启动恢复与每分钟内部 cron 检查兜底，每次最多派发 1 个任务。 |
| 互斥 | 使用 `flock` 文件锁；认领使用 SQLite 条件更新。 |
| 任务 | 每个应用版本 1 个内部 `@once` 任务，`timeout_seconds=7200`、`retry_count=0`。 |
| 去重 | 按 `category + subject_app + subject_version`，不得解析任务名或命令。 |
| 任务终态 | 预拉以 `queue_state` 为唯一业务状态；不以 `last_status` 驱动控制台显示。 |
| 历史 | 预拉与普通计划任务使用相同规则：执行索引最近 20 次／3 天；JSON 和日志由 runner 收尾按最近 50 次／七天清理。任务不自动过期，删除任务时一并删除历史和日志。 |
| 就绪 | 查询本地 Docker 镜像，不能仅依据预拉任务成功记录。 |
| 取消 | 仅 `phase='pulling'` 时接受；保持 `status=3` 至工作线程退出，最终写 `status=6`。 |
| 资源 | 取消保留仓库、栈、卷和日志；用户选择“移除”时复用错误应用的清理逻辑。 |
| 权限 | 预拉任务归属已认证 operator；内部恢复检查不作为用户可见任务。 |
| `latest` | 允许预拉，但界面只表示“缓存候选”，不得承诺版本一致。 |

## 3. 镜像预拉

### 3.1 任务和周期

预拉任务由平台创建，命令固定为：

```text
/usr/local/bin/websoft9 images prewarm --app <app> --version <version>
```

`@once` 只允许内部预拉任务使用：

- 不写入容器或主机 crontab，不计算 `next_run_at`。
- `_normalize_payload` 放行 `@once` 并拒绝 `target='host'`。
- `_sync_tasks`、`_list_enabled_host_tasks` 和 `_sync_host_tasks` 跳过 `@once`。
- `_next_run('@once')` 返回 `null`；控制台显示“一次性”。
- 用户点击“重跑”仅将任务重新入队，不能调用通用 `run_task()`。

### 3.2 队列状态和流程

`queue_state` 仅用于 `category='prewarm'`：

| 状态 | 含义 | 下一步 |
|---|---|---|
| `queued` | 等待调度 | 调度器原子认领 |
| `running` | runner 已启动或正在启动 | 下个 tick 收敛或恢复 |
| `success` | 全部镜像拉取成功 | 保留任务；执行历史按公共策略清理 |
| `failed` | 拉取失败 | 用户可重跑或删除 |
| `cancelled` | 用户取消 | 用户可重跑或删除 |

创建和重跑必须在同一个 `BEGIN IMMEDIATE` 事务内完成：

1. 按 `category`、`subject_app`、`subject_version` 查询当前 operator 的任务。
2. `queued`/`running` 返回既有任务；`success` 返回已就绪；`failed`/`cancelled` 重置为 `queued`。
3. 不存在时，确认全局 `queued + running < 5`，再插入任务。

调度器执行以下步骤：

1. 获取 `state/prewarm-dispatch.lock` 的非阻塞 `flock`；未获取即退出。
2. 收敛已有 `running` 任务：读取 runner state 和运行记录，将成功、失败写入 `queue_state`。若任务已是 `cancelled`，不得被 runner 后续写出的结果覆盖。runner 的 `skipped` 不代表成功，应回退 `queued`。
3. 对无进程、无有效 state 且超过 2 分钟启动宽限的任务回退 `queued`；其他失联任务在租约 `timeout_seconds + 5 分钟` 后回收。
4. 原子认领最早的 `queued` 任务：`UPDATE ... WHERE queue_state='queued'`，且仅在受影响行数为 1 时继续。
5. `start_new_session=True` 启动 runner，立即保存 `runner_pgid`，然后退出。

容器启动脚本在 `/run/websoft9/prewarm-instance-id` 生成一次实例标识；API 和 cron 读取同一标识。实例变化时必须先检查旧 runner 是否存活，不得重复启动存活的拉取进程。API 启动后台恢复统一 cron 配置与 runner 后主动调度一次。

### 3.3 生命周期和取消

- `queued` 取消：直接写 `cancelled`。
- `running` 取消：与调度共用文件锁，先写 `cancelled`，再终止同一 session 的全部进程；失败时保留 `runner_pgid`，阻止新派发、重试和删除。确认退出后解除阻塞并接续。
- 终态任务不自动删除。执行索引保留最近 20 次且不超过 3 天；JSON 和日志沿用公共 runner 的最近 50 次／七天策略，在后续执行收尾时清理。删除任务时删除 runner、state、索引和文件，不删除镜像。
- runner 完成后先写终态并关闭执行锁描述符，再调用内部调度；接续失败不改变原执行退出码，由 cron 恢复。
- 预拉任务不能编辑、启停或修改命令；服务层必须拒绝这些通用操作。

### 3.4 镜像解析和日志

预拉必须复用安装的镜像解析链路：复制应用模板，物化默认 profile，写入 `W9_ID`、`W9_APP_NAME`、`W9_VERSION`、`W9_DIST`，再调用 `collect_compose_images` 与 `pull_with_fallback`。

预拉按默认 profile 解析；安装使用其他 profile 时，未命中的镜像仍由安装流程拉取。CLI 输出每个镜像的开始和完成行，复用计划任务运行日志，不提供百分比进度。

### 3.5 系统任务和控制台

内部恢复检查写入统一生成的 `/etc/cron.d/websoft9-tasks`，不使用普通任务 runner：

```text
* * * * * root /usr/local/bin/websoft9 images dispatch --quiet
```

- 从 `SYSTEM_TASKS` 移除旧 `system:image-prewarm-dispatch`，迁移清理其专属记录与产物，不影响真实预拉任务。
- 空闲与已有下载的检查不输出常规信息、不生成执行历史；调度异常写平台日志。
- 计划任务页面按 `category='prewarm'` 展示 `queue_state`、一次性周期和日志；隐藏编辑和启用开关。
- 安装对话框提供“预拉镜像”按钮；未选版本时禁用，已排队或已就绪时显示对应状态。队列提示不得暴露其他 operator 的应用信息。

## 4. 安装取消

### 4.1 状态和原子边界

`install_tasks` 新增 `phase` 与 `cancel_requested`：

| 时机 | `phase` | 状态 |
|---|---|---|
| Step 3 开始 | `pulling` | `status=3` |
| 接受取消 | `pulling` + `cancel_requested=1` | 保持 `status=3`，UI 显示“正在取消” |
| 拉取结束进入建栈 | `deploying` | `status=3` |
| 取消工作线程退出 | 终态 | `status=6` |

取消接口执行条件更新：`UPDATE ... SET cancel_requested=1 WHERE app_id=? AND status=3 AND phase='pulling'`。受影响行数为 0 时返回 409。工作线程在拉取结束、进入 Step 4 前条件更新 `phase='deploying'` 并重读取消标记；两个操作竞争同一边界，先到者生效。

路径参数使用 `app_id`，服务端解析对应的 `tracking_id` 后写状态；不得混用两种标识符。

### 4.2 中断实现

1. 取消端点写数据库标记，并设置 `_prewarm_cancel_events[tracking_id]`。
2. `pull_images_from_yml` 在每张镜像开始前和每条进度回调中检查 Event。
3. 回调发现取消时抛出 `InstallCancelled`；拉取流以 `stream.close()` 显式关闭。
4. `_pull`、`pull_with_fallback` 及其异步路径必须先 `except InstallCancelled: raise`，不得把取消当成镜像源失败并继续回退。
5. `install_app` 的 Step 3 在通用异常处理之前透传 `InstallCancelled`；最外层将任务写为 cancelled，不调用 `remove_repo`、`modify_app_information` 或资源清理。

取消日志写入独立的 `Installation cancelled` stage，避免被拉取阶段 30 行窗口挤掉。进程重启时，将 `status=3 AND cancel_requested=1` 收敛为 cancelled；stale 清理必须排除 `status=6`。

### 4.3 已取消应用

`status=6` 是已取消。后端新增 `appCancelled` 集合并将其合并到 `get_apps`；删除逻辑同时接受 4 和 6，包含 `remove_app_from_errors_by_app_id` 的状态筛选。前端补齐筛选、计数、状态标签、徽标和 `RemoveType='cancelled'`。

取消仅停止安装并保留资源。用户点击“移除”后，复用 `_cleanup_error_app_resources` 清理仓库、栈、卷和代理；重新安装创建新任务并复用已下载镜像层。

## 5. 数据、接口与前端

### 5.1 数据迁移

| 表 | 变更 |
|---|---|
| `install_tasks` | `cancel_requested INTEGER DEFAULT 0`、`phase TEXT`；通过版本化 `schema_version` 迁移。 |
| `scheduled_tasks` | `category`、`subject_app`、`subject_version`、`queue_state`、`claimed_at`、`claimed_by`、`runner_pgid`；复用现有补列机制。为 `(category, subject_app, subject_version, operator_id)` 建索引。 |

`claimed_by` 为本次容器启动生成的实例 id；`runner_pgid` 用于终止进程组。预拉任务只以 `queue_state` 表示业务状态，避免 `last_status` 与队列状态双真相；`cancelled` 为不可逆终态。

### 5.2 API

| 接口 | 行为 |
|---|---|
| `POST /apps/images/prewarm` | 创建、复用或重新入队预拉任务；返回任务 ID、`queue_state` 和匿名队列位次。 |
| `GET /apps/images/prewarm/status` | 按应用和版本检查本地 Docker 镜像是否齐全。 |
| `POST /apps/{app_id}/install/cancel` | 仅拉取阶段接受；成功时写取消标记，其他阶段返回 409。 |
| `DELETE /apps/{app_id}/error/remove` | 同时支持 error 和 cancelled。 |
| 计划任务接口 | 公开 `category`、`queue_state`；预拉重跑走入队，不走通用立即执行。 |

预拉相关端点必须接收并传递认证会话；认证关闭时沿用现有 403 约定。

### 5.3 UI

- 安装对话框：版本选择、预拉按钮、已排队/已就绪/失败状态和本地缓存提示。
- 我的应用：仅 `phase='pulling'` 显示“取消安装”；取消后显示“已取消”和“移除”。
- 计划任务：预拉任务可查看日志、重跑、删除和筛选；内部恢复检查不显示为任务。

## 6. 实施清单

1. 扩展 `scheduled_tasks` schema、`@once` 支持、内部预拉任务创建/清理和权限保护。
2. 实现预拉 CLI、镜像解析复用和结构化日志。
3. 实现 dispatcher、文件锁、原子认领、进程组管理、租约与实例恢复。
4. 增加内部 cron 恢复检查、主动接续与启动恢复，不新增 worker。
5. 为 `install_tasks` 实施版本化迁移，增加 phase、取消标记和 cancelled 状态集合。
6. 在镜像拉取链路实现 Event 检查、异常透传和流关闭。
7. 扩展删除与 stale 清理逻辑，使 status=6 可见、可删且不被改写为错误。
8. 实施 API、控制台预拉入口、取消确认、状态展示和计划任务分组。
9. 补齐单元、集成和手工验收测试。

## 7. 验收与发布前验证

### 自动化验收

- `@once` 不进入任意 crontab，且列表、创建和 `next_run_at` 不调用 `croniter('@once')`。
- 多个预拉按 FIFO 串行；调度器派发即返回；锁竞争时不产生认领或回收。
- 同一应用版本并发创建只生成一个任务；全局未完成数不会超过 5。
- `skipped` 不会被标记为预拉成功；进程、state 或实例丢失后任务可恢复；runner 的后续结果不会覆盖 `cancelled`。
- 容器重建后生成新的实例标识，原 `running` 任务被 API 启动恢复逻辑回收。
- 预拉成功后安装复用本地镜像；失败、取消可重跑；任务不自动过期，历史和日志保留／删除与普通计划任务一致，不显示额外保留提示。
- 拉取中取消后不进入 Step 4，资源保留；非拉取阶段取消返回 409。
- 取消后的应用可见、可移除；重新安装不受旧 `tracking_id` 影响。
- 计划任务和 My Apps 的中英状态、系统任务名称、筛选和日志入口正确。

### 手工验证【待验】

1. 断网或阻塞拉取时，测量从取消请求到安装线程退出的延迟。
2. 确认客户端停止消费后 Docker daemon 是否停止拉取，以及已下载层是否保留。
3. 故意遗漏一张镜像，确认 Portainer 建栈是否补拉及其可见日志。
4. 平台容器重建后，确认运行中预拉立即回收、队列继续。

已知基线：`tests/test_scheduled_tasks.py` 中 `test_list_tasks_refreshes_ssh_task_execution_status` 与 `test_switching_away_from_unreachable_host_is_rejected` 在本方案实施前已失败，不能作为本次回归依据。

## 8. 风险与非目标

| 风险 | 处理 |
|---|---|
| 取消不是 daemon 级保证 | UI 使用“正在取消”，不承诺秒级或强制停止。 |
| `latest` 与 profile 差异 | 标记为缓存候选；未命中镜像由安装按正常流程拉取。 |
| 磁盘增长 | 只做弱校验；Docker root 不可见时依赖 daemon 返回的真实错误。 |
| 预拉与安装重叠 | 允许 Docker 层幂等复用；安装可等待或提示。 |

不提供恢复安装、跨应用缓存管理界面、优先级插队、镜像自动回收或 Portainer 内部取消。