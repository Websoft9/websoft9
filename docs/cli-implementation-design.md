# Websoft9 CLI 整体规划与增量实施

## 1. 目标与实施原则

本文承接 [AI 集成架构](./ai-integration-architecture.md)，回答 CLI 做哪些、复用什么、缺什么、如何分批交付。**整体规划完整，按现有能力成熟度开发，不整体重写，也不把聚合诊断作为全部命令的前置。**

本文保留整体设计与验收边界。A/B/C 批次已有命令实现，正在按实际行为验收；命令已注册或单测通过不代表全部能力已经交付。CLI 先作为可信本地管理员工具独立使用，后续 AI 只调用已验收、获准开放的命令。

基本原则：

- **复用平台，不另造引擎**：CLI 接入现有 AppHub Service，沿用安装校验、跟踪、Compose、端口预留、Gitea、Portainer、NPM、Restic 和任务机制。
- **成熟能力先交付**：查询、安装、启停等分别验收，不必等待全部日志、诊断、预检或 Git 历史完成。
- **缺口随命令解决**：只整改当前命令必需的后端路径，不先重构所有服务或创建全量空壳模块。
- **按调用历史决定兼容**：新增且未被实际调用的命令可直接改名，不为旧草案增加别名；已有脚本、cron、安装和升级流程使用的入口继续保留协议兼容。
- **细节随开发确定**：本文保留能力、依赖与边界；参数枚举、字段清单、内部函数和具体限额在对应命令开发时确定，写入帮助和测试。

## 2. 现有 CLI：保留，而非迁移重写

入口为 [apphub_cli.py](../apphub/src/cli/apphub_cli.py) 和 [app_commands.py](../apphub/src/cli/app_commands.py)。[包安装入口](../apphub/setup.py) 与 [容器包装脚本](../docker/Dockerfile) 均保留；配置路径复用 [runtime_paths.py](../apphub/src/core/runtime_paths.py)，不再建立 CLI 专用配置体系。

以下命令已存在，继续保留参数、默认值、输出、交互和退出语义。表内 `/` 仅表示独立命令，不是可复制的命令路径。

| 已有命令 | 兼容重点 |
| :--- | :--- |
| `app install` / `app refresh` | 安装复用验证、跟踪与执行顺序；旧安装 JSON 保留 `{app_id, tracking_id}`，以服务实际返回标识为准；刷新报告及部分错误退出 `2` 保留 |
| `appstore sync` | 保留渠道、默认等待、后台与跳过选项；目前输出文本，不强行加统一 JSON |
| `images prewarm` / `images dispatch` | 保留预热流程、进度与最终结果、quiet、队列和跳过语义；预热 stdout 目前不是单个 JSON |
| `check-update` / `log-cleanup` | 更新检查含镜像源刷新和升级包准备，不是只读；保留本机派发与已有清理器、JSON 和退出行为 |
| `reconcile-scheduled-tasks`（隐藏） | 保留任务对账入口，不另建调度器 |
| `getconfig` / `setconfig` / `setsysconfig` | 保留人工配置入口及部署脚本调用；全量配置可能含秘密，不向 AI 直接开放 |
| `setedition`（隐藏） / `resetpwd` | 保留内部/人工管理用途和密码确认，不改成 AI 无确认接口 |
| `upgrade apps` | 保留已废弃的成功 no-op 和指引，不重新接回升级或同步 |

[scheduled_tasks.py](../apphub/src/services/scheduled_tasks.py) 和 [platform-sync-config.sh](../docker/scripts/platform-sync-config.sh) 已依赖这些入口。尤其跳过退出码 `75`、`app refresh` 的退出 `2` 不得被公共包装器重新解释；没有发现仓库内调用，也不等于没有外部脚本使用。

### 2.1 命令导航与使用约定

顶层帮助按 **Applications / Infrastructure / Platform** 展示十一个主题组，不增加 `manage` 等无业务意义的中间层，也不为缩短列表将容器、主机、服务等不同权限能力强行合并。配置、账户、预热及维护操作的推荐入口归入现有主题；已有调用历史的旧路径继续可调用，但从顶层帮助隐藏，避免重复入口干扰新用户。

新开发的 `db list/test` 直接更名为 `app database list/test`，不保留无业务调用的 `db` 别名。该子组只汇总应用绑定的外部数据库及测试 MySQL/MariaDB、PostgreSQL 连接，不管理 Websoft9 内部数据库，也不提供通用 SQL 执行。

| 命令组 | 管理对象与边界 |
| :--- | :--- |
| `git` | 应用在 Gitea 中的配置仓库，不是通用 Git 客户端；除显式请求外，修改仓库不自动重新部署 |
| `backup` | 应用卷的 Restic 快照，不是平台全量备份或数据库原生 SQL 备份 |
| `gateway` | 应用域名、反向代理和证书，不是平台网关进程控制 |
| `service` | Websoft9 核心平台服务及日志；应用实例用 `app`，容器资源用 `docker container` |
| `host` | 端口、本地执行环境及 SSH 配置元数据，不是通用远程主机管理；容器内 `env-check` 反映其可见环境 |

| 推荐入口 | 兼容旧路径 | 保留的行为 |
| :--- | :--- | :--- |
| `settings config get` | `getconfig` | 原始配置读取，可能含明文秘密，仅可信管理员使用 |
| `settings config set` | `setconfig` | 原参数写入应用配置 |
| `settings config set-system` | `setsysconfig` | 原参数写入系统配置 |
| `settings auth reset-password` | `resetpwd` | 隐藏输入、重复输入与最终确认 |
| `settings upgrade check-and-prepare` | `check-update` | 刷新版本/镜像源，并按原策略自动准备升级；不是只读检查 |
| `service cleanup-logs` | `log-cleanup` | 保留 verbose、原始 JSON 与跳过退出码 |
| `appstore prewarm` | `images prewarm` | 保留镜像预热进度与最终结果 |
| `task dispatch-prewarm` | `images dispatch` | 保留队列锁、quiet、跳过退出码 `75` |

隐藏的 `upgrade apps` 兼容 no-op、`setedition` 和内部任务对账入口仍然保留。以上只是导航别名，共用原回调和参数，不复制业务逻辑，不改变旧脚本输出、退出码或安全确认。新增别名沿用原权限边界，不因归组而自动允许 AI 使用。

- 全部命令层级支持 `-h` 与 `--help`，包括隐藏的旧路径；显式请求帮助退出 `0`。直接执行 `websoft9` 沿用原 Click 行为，显示帮助并退出 `2`，避免改变已有脚本的失败判断。
- 八个因归组而隐藏的旧入口仅从帮助列表隐藏，仍保留 Shell 补全，包括旧子命令和参数；原本隐藏的 `setedition`、`reconcile-scheduled-tasks` 不新增补全暴露。
- 对已有调用的旧路径，新路径是推荐入口，旧路径继续保留；不批量迁移现有 cron、升级或安装脚本，也不向旧命令 stdout/stderr 添加弃用提示。新增且无实际调用的命令允许直接改名。帮助布局和说明文本不作为机器接口；自动化应使用明确的命令路径及该命令约定的输出、退出码。
- `websoft9 --version` 读取平台版本文件并退出，不连接后端或初始化数据库；版本不可读时明确报错。它与安装等子命令的 `--version` 参数相互独立。
- 保留完整的 `websoft9 <主题> <动作>` 路径，不引入模糊缩写或含义不明确的单字母操作。已有 `-y` 等短选项不变，结构化命令继续使用 `--json`。

```bash
websoft9 -h
websoft9 app install -h
websoft9 app database -h
websoft9 settings config -h
websoft9 --version
websoft9 overview status --json
websoft9 settings config get --section example --key value
```

帮助树、兼容别名、版本、参数错误与退出语义回归见 [CLI 使用体验测试](../apphub/tests/test_cli_usability.py)。

命名及兼容性收敛后的使用体验及相关回归 **317 项通过**：在 `apphub/` 执行以下命令；旧升级测试保持独立进程，避免其全局模块替身影响其他测试。

```bash
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_cli_usability.py tests/test_apphub_cli_apps.py tests/test_apphub_cli_check_update.py tests/test_cli_batch_a.py tests/test_cli_batch_b.py tests/test_cli_batch_c.py tests/test_cli_contract_regressions.py tests/test_cli_restore_regressions.py tests/test_compose_app_classification.py
# 287 passed
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_apphub_cli_upgrade.py
# 8 passed
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_log_cleanup.py
# 22 passed
```

[Python CI](../.github/workflows/ci-pr.yml) 单独执行 CLI 使用体验、更新检查和协议回归测试，使用独立 pytest 进程，失败直接阻断 CI，不依赖全量测试步骤的警告回退。兼容测试覆盖根命令退出码、帮助与补全、新旧路径共享参数/回调、配置纯文本/JSON 输出、静默写入、系统配置目标、跳过退出码和密码隐藏输入及最终确认。

## 3. 全量能力与复用表

十一个顶层组及其子组覆盖 Websoft9 的应用生命周期、运行保障和平台管理。下表给出主要入口与工程缺口，长尾动作和权限以 [架构第 6 章](./ai-integration-architecture.md#6-附录cli-能力矩阵与源码入口) 为准，不再复制一份完整参数手册。

**已有**表示对应 CLI 已存在；**封装**表示主要 Service 已有，仍需参数、保护和测试；**扩展**表示需要补后端能力。一个组可以跨批次交付，不按整组宣布完成或向 AI 放行。

| 命令组与主要能力 | 复用入口 | 新增 / 整改重点 |
| :--- | :--- | :--- |
| `overview`：状态、版本/配额、就绪 | [overview_service.py](../apphub/src/services/overview_service.py)、[platform_readiness.py](../apphub/src/services/platform_readiness.py) | **封装**；未就绪、检查失败与正常结果分开，不隐式修复 |
| `appstore`：检索/模板/同步状态、同步/索引、收藏 | [local_app_store.py](../apphub/src/services/local_app_store.py)、[appstore_sync_manager.py](../apphub/src/services/appstore_sync_manager.py) | 同步/刷新**已有**；查询**封装**；收藏依赖实际操作员身份，不默认共享管理员 |
| `app`：实例查询、预检、安装/Compose 编辑、启停/取消/重建、退出、诊断及元数据 | [app_manager.py](../apphub/src/services/app_manager.py)、[compose_app_manager.py](../apphub/src/services/compose_app_manager.py)、[app_status.py](../apphub/src/services/app_status.py) | 安装**已有**；多数操作**封装**；查询只读、Compose 挂载回显与退出保护按需整改，聚合诊断**扩展**；预设命令不默认可信 |
| `git`：配置仓库/文件读取、局部更新、写入、历史/Diff/回退 | [gitea_manager.py](../apphub/src/services/gitea_manager.py)、[gitea_api.py](../apphub/src/external/gitea_api.py) | 复用文件/SHA；多键更新、历史/比较/回退/删除**扩展**；不阻塞无关命令 |
| `docker`：容器、镜像、卷/文件、网络、Stack | [portainer_manager.py](../apphub/src/services/portainer_manager.py)、[portainer_api.py](../apphub/src/external/portainer_api.py)、[file_manager.py](../apphub/src/services/file_manager.py) | 预热**已有**，多数查询/控制/文件能力**封装**；指标、部分镜像/网络操作**扩展**；纳管实例优先 `app`，任意 Exec 不向 AI 开放 |
| `gateway`：应用代理/地址联动、证书、Nginx、高级网关、平台入口 | [proxy_manager.py](../apphub/src/services/proxy_manager.py)、[app_access_manager.py](../apphub/src/services/app_access_manager.py) | 代理/证书主要**封装**；删除一致性、证书续期和高级能力按需补齐；检查变更后实际访问 |
| `backup`：快照查询/创建/删除、数据恢复 | [back_manager.py](../apphub/src/services/back_manager.py) | 前三项**封装**；恢复先整改停止、权限和重启错误，不因已有方法就直接开放 |
| `app database`：应用外部数据库分组与连接测试 | [app_manager.py](../apphub/src/services/app_manager.py)、[install_profile.py](../apphub/src/services/install_profile.py) | **封装**；真实类型/权限检查、受控秘密输入，不管理平台内部数据库，不做通用数据库管理工具 |
| `host`：端口预检、环境检查、SSH Profile | [port_allocator.py](../apphub/src/services/port_allocator.py)、[host_access.py](../apphub/src/services/host_access.py) | 端口/连接元信息**封装**，深度环境检查**扩展**；主机授权、提权和全局文件保留人工 |
| `task`：任务/历史/日志、允许的调度、预热记录 | [scheduled_tasks.py](../apphub/src/services/scheduled_tasks.py)、[image_prewarm.py](../apphub/src/services/image_prewarm.py) | 对账/派发**已有**，其余主要**封装**；复用锁与跟踪，不借任务触发任意 Shell |
| `service`：平台服务状态、服务/运行日志、受控维护 | [core_services.py](../apphub/src/services/core_services.py)、[runtime_logs.py](../apphub/src/services/runtime_logs.py) | 日志清理**已有**；状态/日志**封装并适配鉴权与读取边界**；控制面不是业务容器，重启/认证修复保留人工 |
| `settings`：脱敏摘要、镜像源、邮件、更新准备 | [settings_manager.py](../apphub/src/services/settings_manager.py)、[upgrade_manager.py](../apphub/src/services/upgrade_manager.py) | 部分顶层命令**已有**，其余主要**封装**；区分查询、刷新、下载、实际升级；账号/API Key 管理不因 CLI 补全自动向 AI 开放 |

## 4. 分批交付：不让复杂能力阻塞基础命令

以下是 **CLI 开发批次，不是 AI 权限开放阶段**。A/B/C 表示交付优先级，不要求所有 A 完成才能开发某个已具备条件的 B；每个命令的真实依赖和保护通过后即可独立交付。

| 批次 | 主要交付 | 依赖与验收 |
| :--- | :--- | :--- |
| **A：基础可用** | 验证旧命令兼容；增加必要的新命令输出/错误处理；优先封装概览、商店查询、应用列表/详情、`app start/stop/restart`、端口检查及直接可用的容器查询/日志 | 只解决本命令所需缺口；查询不改状态，启停准确定位并检查实际结果；不等完整日志体系或聚合诊断。已有安装继续可用，不重新开发 |
| **B：常用流程补齐** | 按任务补 Compose 安装/编辑、配置读取/局部更新、访问联动、快照查询/创建、数据库检查、平台服务/日志及允许的任务/设置 | 复用安装跟踪、SHA、代理和任务机制；写前说明目标/影响并确认，失败与部分结果明确；身份依赖未解决的操作不开放 |
| **C：扩展与高风险能力** | 聚合诊断、深度环境/指标、Git 历史/Diff/回退、镜像/网络等扩展、删除/清理与数据恢复 | 按真实需求补后端；先完成相应引用/保留数据/恢复保护；能力之间不捆绑验收。基础诊断可由已交付查询和日志人工组合，不等待聚合工具 |

安排工作时，从表中选择一个具体命令：**确认现有 Service → 补必要边界 → 注册 CLI → 定向测试 → 实例验收**。命令按需拆模块，共用输出和校验，不先建立通用工作流框架、平行状态库或新任务系统。

Skills/Agent 可在所需 CLI 已交付后接入，不必等待全部组齐全；其初次开放仍限只读，后续写操作需单独通过确认与权限验收。管理员 CLI 提前具有写能力，不等于 AI 可提前执行。

## 5. 必要公共约定与已知缺口

### 5.1 输出、错误和兼容

- 新命令提供 `--help`、文本摘要与 `--json`，参数和字段以实际帮助/测试为准。旧命令默认格式不变；以后适配机器输出须显式 opt-in 或新增别名，不用根组统一替换。
- 新命令业务结果使用同一信封；stdout 只含一个完整 JSON，进度和脱敏日志到 stderr。先处理相关 logger 的 stdout 路由，不以重构整套日志系统为前置。

```json
{"ok": true, "code": "OK", "data": {}, "error": null, "meta": {"truncated": false}}
```

- 失败为 `ok=false`、`data=null`，给稳定错误码和脱敏 `error.message/details`；新命令退出 `0/1/2` 分别表示完成、执行失败、参数错误。解析阶段沿用 Click 参数错误文本及 stderr/`2`，不先开发覆盖所有解析场景的 JSON 框架。
- 不把应用故障等同于查询失败：采集成功但容器异常，仍返回真实状态；必要来源不可用则明确失败并可附安全部分结果，可选来源缺失给警告，不能空成功或伪报“目标不存在”。
- 日志有条数、输入读取和超时边界，大文本默认按 64 KiB 预算裁剪并标记；脱敏先于展示裁剪，JSON 始终完整。具体读取上限随命令实现测试，不预先固化一套多源调度限额。
- `task log` 的 CLI 输入扫描最多 1 MiB。小日志保留按行 `--before` 翻页；超过扫描预算只返回有界尾部，标记 `meta.truncated=true` 且 `next_before=null`，不伪造绝对行号；此时显式传入 `--before` 会返回错误。HTTP 日志分页语义不变。

### 5.2 不能靠“薄包装”跳过的整改

以下只在相关命令落地时处理，**不是全部开发的统一前置**：

| 涉及能力 | 必须解决的问题 |
| :--- | :--- |
| 应用列表/详情 | `get_apps` 会协调过期安装状态，详情会回调列表；新查询须整链关闭协调并保留 HTTP 默认行为。核实真实存在性，不沿用空 Inactive 占位或将依赖失败当不存在；状态与类型沿用平台，不另建真源 |
| 安装状态读取 | `app_status.py` 导入会初始化/迁移 SQLite；分离查询与业务初始化，读取既有库和活动 WAL，不创建/迁移业务库；缺库/不兼容明确报错。保留现有写入和跨进程跟踪机制 |
| 容器日志 | 复用 [现有解码逻辑](../apphub/src/services/app_access_manager.py) 和引擎接口；正确处理 TTY/复用帧、读取边界、404/超时，不把 OverflowError 或不可读转为空日志 |
| 平台服务/日志 | 现有公开方法要求会话；提取可共用的本地采集逻辑，HTTP 认证保持，不传 None 绕过、不伪造会话。Supervisor/日志读取失败不得变成正常空结果；只用无状态健康探测 |
| 写入与恢复 | 保留安装校验、跟踪、冲突和状态检查；配置写入保留 SHA、拒绝掩码覆盖；删除保护控制面及停用数据。恢复先解决停止失败仍恢复、固定属主和重启失败被弱化的问题 |

### 5.3 权限与保护

CLI 初期只面向已部署平台的可信本地管理员，缺配置或凭证明确反馈，不自动创建账户、同步密钥或准备主机授权。本地权限不能代替 Console 多用户授权，HTTP 认证也不因 CLI 复用而削弱。

查询不改业务数据、schema、资源或授权；允许正常运行日志和既有引擎认证。结构化输出按字段白名单，日志/错误/文件覆盖秘密脱敏；不能可靠处理的内容省略并说明，不提供新命令的明文秘密开关。

新增写命令在 CLI 说明目标和影响并确认；自动化调用须显式采用受支持的非交互确认，Agent 工具确认另行适配，旧命令交互不强制迁移。删除/覆盖列出真实范围与引用，纳管实例优先走应用业务链。任意 Exec、自定义 Shell、主机授权、控制面凭证及最终平台重建不向 AI 开放。

## 6. 轻量验收与下一步

- **开始前**核对当前命令及调用方基线，不要求先跑完全项目测试。
- **每个命令**覆盖成功、参数/依赖失败、真实状态、输出和相关权限保护；查询补无业务写入测试，修改共用服务时回归对应 HTTP/旧 CLI 行为。
- **按改动选测试**：复用现有 `CliRunner`、fake Service、临时库和日志，不在真实平台运行安装/清理/改密码来测兼容。例如改应用 CLI 时，从 `apphub/` 运行：

```bash
python3 -m pytest -q -o addopts='' tests/test_apphub_cli_apps.py tests/test_apphub_cli_upgrade.py tests/test_apphub_cli_check_update.py
```

调度、应用状态、Portainer 或平台日志有改动时，再增加对应的 `test_scheduled_tasks.py`、`test_app_manager_stack_state.py`、`test_portainer_manager.py`、`test_core_services.py`、`test_runtime_logs.py` 等定向测试，不把全部矩阵变成每个命令的前置。

交付记录包含实际命令、结果、未验证项和脱敏输出样例；在测试平台按具体命令验证真实行为。

### 2026-10-20 代码复核整改

- 显式升级准备经固定 loopback 接口和既有内部凭证派发至长驻 AppHub；自动更新检查保留原入口与策略，不在 CLI 进程中启动会随退出消失的下载线程。
- Git 回退产生完整目标文件树的新提交，并检查推送结果；推送失败不进入重部署。补齐文件删除 JSON 请求体、真实区间 Diff，以及重复键和特殊字符环境变量更新。
- `clean-error` 不处理仍有同名部署的应用；无法从跟踪记录证明部署归属时，要求先通过显式卸载/删除处理。任何资源清理失败均保留跟踪记录并报错。
- 数据恢复在停止前验证快照路径和当前卷映射，拒绝无容器的停用实例；恢复前确认停止，恢复后验证运行态，不将启动调用成功等同于恢复完成。
- 安装状态、自定义字段、CLI 任务采集使用只读数据库；缺库、损坏或不兼容明确失败，不初始化/迁移、不协调任务状态。数据库连接列表关闭旧应用状态协调并传递依赖错误；HTTP 原默认行为保留。
- 容器指标从指定 Portainer Endpoint 获取。文件/日志字符串覆盖 YAML、JSON、环境赋值和多行秘密脱敏；任务日志按上述扫描边界读取。

新增回归测试集中在 [输出与只读契约](../apphub/tests/test_cli_contract_regressions.py)、[Git 操作](../apphub/tests/test_cli_git_regressions.py) 和 [清理与恢复](../apphub/tests/test_cli_restore_regressions.py)，使用临时 SQLite、实际本地 Git 仓库及外部接口替身，不操作真实应用。

本轮定向回归 **219 项通过**；升级兼容测试 [test_apphub_cli_upgrade.py](../apphub/tests/test_apphub_cli_upgrade.py) **8 项通过**，同步测试 [test_appstore_sync_manager_versions.py](../apphub/tests/test_appstore_sync_manager_versions.py) **3 项通过**。后两组会在收集时替换/重载全局模块，须分别在独立 pytest 进程运行。调度测试独立运行 **88 项通过、2 项失败**，这两项在干净 HEAD 同样失败，作为原有问题保留，不算作本次修复通过项。

**自动回归不替代测试平台验收。** 现场结果与未验证的发布边界见下文；本轮不继续开发 Skills/Agent，不宣称全部 CLI 能力已获准开放。

### 测试平台只读验收

在现有 `websoft9-dev` 平台中，以临时源码连接真实 Gitea、Portainer、平台服务和业务库；Python 源码及版本文件经哈希核对。未覆盖部署文件或重启服务，**不是新版正式 CLI 包装入口的部署验收**。

- 最终 **45 项通过、0 项失败**：覆盖概览、应用查询与诊断、应用商店、主机端口、容器及资源列表、仓库文件与单提交统一格式 Diff、网关、数据库连接列表、已有任务执行记录与日志、平台日志、设置摘要及参数/确认失败路径。数据库连接列表为空，不代表真实数据库连通性已验收。
- 验收补发现并修复产品版本、概览、设置摘要查询仍初始化产品状态库的问题；CLI 显式使用只读分支，缺库、缺表或未初始化状态明确报错，HTTP 原默认初始化/写入行为保留。Readiness 数据库探测改为真正的只读 URI。
- 18 个涉及 SQLite 的用例中，CLI 进程观察到的连接全部为 `mode=ro`；安装跟踪（含产品状态）、计划任务、主机访问三个库的表结构与行内容摘要在验收前后一致。这不替代其他业务引擎的写入审计。
- 容器测试从所选 Portainer Endpoint 的实际列表发现目标，不假定宿主容器名可见。本轮应用目标已停止，指标字段返回空值，**没有验证运行中应用的实时数值**。控制面容器在该列表不可见，未将“容器不存在”算作控制面保护验证。
- 平台概览仍报告 3 条应用/安装任务错误告警；查询通过不表示平台业务全部健康。

补充回归在 `apphub/` 目录分别执行：

```bash
python3 -m pytest -q -o addopts='' tests/test_product_metadata.py tests/test_platform_readiness.py tests/test_overview.py tests/test_cli_batch_a.py tests/test_cli_batch_c.py tests/test_cli_contract_regressions.py
# 82 passed
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_settings_internal_product_edition.py
# 22 passed
```

只读库连接及缺库/损坏/缺表回归见 [产品状态测试](../apphub/tests/test_product_metadata.py) 与 [Readiness 测试](../apphub/tests/test_platform_readiness.py)。

以上为只读阶段的范围；写入生命周期、正式包装入口、运行中容器指标及保护逻辑由下一阶段在一次性资源中验证，不以修改或重启共享业务作为测试前提。

### 隔离写入与升级派发补充验收

**当前测试平台的可控范围验收通过，共 120 项检查通过、0 项失败。** 不将此结论扩大为所有命令、所有云环境或生产升级发布认证。

| 范围 | 结果 | 实际验证 |
| :--- | :--- | :--- |
| 真实后端只读查询 | 45 通过 | 修复后重新运行，源码哈希一致，三个业务库逻辑快照不变 |
| 隔离生命周期 | 60 通过 | Compose 安装、容器及应用启停/重启、运行中容器数值、Git 写入/过期 SHA 拒绝/特殊值/删除/区间 Diff/完整树回退、备份创建/数据恢复/删除、保留数据卸载/恢复/最终删除 |
| 升级准备 HTTP 链路 | 15 通过 | 实际 AppHub HTTP 与 UpgradeManager；鉴权、确认、CLI 退出后后台继续、并发锁、坏校验和及非新版本拒绝、失败暂存清理和重试 |

- 一次性运行容器使用镜像内的正式 `/usr/local/bin/websoft9`，逐字核对其内容与 Dockerfile 生成模板一致；Python 源码和版本文件与当前工作区哈希一致。没有覆盖或重启共享平台，这不是重新构建完整发布镜像的认证。
- 创建的仓库、Compose 应用、容器、卷及 Restic 仓库均限定为本轮唯一测试资源；共享配置与凭证只读挂载，业务状态库和安装秘密目录使用隔离数据根。恢复后真实校验文件内容及属主 `1001:1002`，不是只检查成功退出码。
- 控制面保护使用具有受保护名称的临时容器，验证 `--yes` 也被拒绝且容器继续运行；没有对真实控制面容器执行停机操作。
- 现场发现保留数据卸载后 Compose 恢复失败：原类型判断依赖运行容器，错误分支还引用未定义的 `dist`。改为复用平台统一的应用类型，支持无运行容器的保留实例，并显式传递依赖错误。回归见 [Compose 类型测试](../apphub/tests/test_compose_app_classification.py)，实际卸载、恢复及删除链路已重测通过。
- 升级测试在无外网、无 Docker Socket 的独立容器中运行，仅将制品源构造参数指向本地测试 HTTP 服务；没有替换真实下载、校验、后台线程或状态持久化方法。**未验证外网制品及镜像成功准备到 `ready` 的完整链路，也未执行最终升级。**
- 结束时测试仓库、栈、卷清单恢复；现有运行容器启动时间不变。临时运行容器、备份仓库、缓存及测试目录均清理。

本阶段相关自动回归 **192 项通过**，在 `apphub/` 分别运行：

```bash
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_product_metadata.py tests/test_platform_readiness.py tests/test_overview.py tests/test_cli_batch_a.py tests/test_cli_batch_c.py tests/test_cli_contract_regressions.py tests/test_compose_app_classification.py tests/test_cli_restore_regressions.py
# 128 passed
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_cli_git_regressions.py
# 30 passed
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_settings_internal_product_edition.py
# 22 passed
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_backup_restore.py
# 12 passed
```

旧备份测试在收集时替换 `git` 等全局模块，与其他测试混跑会产生导入或替身冲突，因此独立执行，不通过修改业务代码适配测试污染。

**发布边界**：远端云服务器/Endpoint、外网升级制品成功暂存及完整镜像重新构建不在此次已验证范围；本地容器后续部署结果见下文。最终平台重建、现有应用破坏性操作、任意 Shell、主机授权和明文秘密输出仍不开放。后续发布验证按实际环境执行，不将本轮通过项替代这些边界。

### 本地容器部署记录（2026-10-20）

用户确认后，已将验收通过的当前 AppHub 后端源码及版本文件部署到常驻容器 `websoft9-dev`，正式 `websoft9` 包装入口已生效。部署标识：`cli-20261020T022323Z-892f3e8c`。未构建镜像、部署 Console 或执行最终平台升级。

- 部署前备份完整旧源码与版本文件，暂存代码通过 Python 语法及 CLI 导入检查；正式部署源码哈希与验收版本一致：`9f72a4e25251d8954def21b583b2a534b1ac65346b042fe8347ad216b386d280`。
- 仅停止/启动 `apphub-api`，其余七个 Supervisor 服务 PID 不变；现有平台及业务容器未重启，未进行业务应用写入操作。
- 通过容器内正式 `/usr/local/bin/websoft9` 重跑 **45 项查询与错误路径，全部通过**；新版手动/自动升级派发接口无凭证均返回 HTTP 403，未触发下载。健康与就绪接口均返回 HTTP 200；部署前置、源码、入口、服务及容器保护检查合计 **64 项通过**。
- 容器内回退源码为 `/websoft9/apphub/src.before-cli-20261020T022323Z-892f3e8c`，旧版本文件为 `/websoft9/version.before-cli-20261020T022323Z-892f3e8c.json`。旧源码归档另存于部署会话目录，临时上传包及暂存目录已清理。

**持久性说明**：本次修改保存在当前容器可写层，停止/启动或重启该容器后仍在；删除并重建容器、拉取原镜像重建或执行平台升级时可能被覆盖。需要可重复发布的镜像时，应另行构建并部署包含这些源码的新镜像，不将本次本地部署误记为镜像发布。

#### CLI 使用体验更新

2026-10-20 后续已将上述分组、兼容别名、`-h` 与 `--version` 更新同步到同一个本地容器。仅更新 [CLI 入口](../apphub/src/cli/apphub_cli.py) 和 [帮助导航](../apphub/src/cli/cli_help.py)，所有平台服务 PID 不变，无须重启 AppHub。部署源码哈希为 `1a69f3729266803bdd6dcefe82a1dda66b8a666b18ec91ae85e4ea7a1068e171`；此哈希替代上一次部署哈希。

通过正式 `websoft9` 包装入口完成 **57 项检查**：根及新旧路径短/长帮助等价、版本输出，以及此前 45 项查询/错误路径均通过；健康与就绪接口均为 HTTP 200。更新前的 CLI 源码已在部署会话目录归档，暂存文件已清理；容器可写层的持久性边界不变。

#### CLI 兼容性收敛

2026-10-20 完成调用方评估后，恢复无参数调用退出 `2`，显式帮助仍退出 `0`；恢复八个归组隐藏入口的 Shell 补全，保持分类帮助和原本内部隐藏入口的边界。没有修改既有 cron、任务脚本、安装或升级调用方。

已再次仅更新本地容器的上述两个 CLI 文件，无须重启服务，所有服务 PID 保持不变。该轮部署源码哈希为 `3475bfb15233cc137bb0c073c5bddd77e9cdf2a5c14cc961e1399e89d91a36aa`，替代上一轮哈希。更新前 CLI 已归档，暂存文件已清理；未构建或发布新镜像。

正式包装入口原有 **57 项检查**再次通过，健康与就绪接口均为 HTTP 200；另以真实 Bash 补全协议和包装入口验证 **24 项兼容性检查**，覆盖无参数退出、显式帮助、八个旧入口隐藏及前缀补全、内部入口不暴露、旧子命令和新旧参数补全。验收不执行真实同步、清理、密码重置或升级。

#### CLI 命名与管理对象收敛

2026-10-20 按“新命令直接调整，历史调用才兼容”的边界，将 `db list/test` 直接移到 `app database list/test`，不保留 `db` 入口。顶层由十二组变为十一组，可执行能力未删除；Git、备份、应用网关、平台服务及主机检查帮助明确各自管理对象和非目标。

本地容器已同步八个 CLI 文件，更新前均已归档，无服务重启，所有服务 PID 不变，健康与就绪接口均为 HTTP 200。最新源码哈希为 `75f2183266497cda5d4cd362a3609e55cebedb190539315aa0c9f2db1c46c1c7`，替代前述部署哈希。该轮仅热更新，未修改既有业务调用脚本、未构建新镜像；后续镜像发布见下一节。

正式包装入口 **60 项检查**通过；旧验收用例中的数据库查询按新路径执行，仍验证原输出及退出契约。另有 **24 项命名与补全检查**通过，覆盖十一组、旧调用入口补全、`db` 不再存在、新数据库路径及参数补全、帮助边界和无参数退出码。外部数据库成功连接仍只使用受控替身验证，不将其计为真实远端数据库验收。

#### CLI 镜像化与独立容器验收

2026-10-20 已基于原产品镜像构建本地派生镜像，打包当前已验收的 AppHub 后端源码和版本文件；前端及其他运行时沿用基础镜像，不包含工作区尚未发布的前端变更。不是 `docker commit`，也不是启动后再覆盖源码。真实生命周期测试发现问题后已重新构建；下表为最终镜像，最终源码哈希见下一节。

| 项目 | 当前值 |
| :--- | :--- |
| 本地镜像 | `websoft9dev/websoft9:cli-20261020t035537z` |
| 新容器 | `websoft9-cli-acceptance` |
| Console | `http://127.0.0.1:19000` |
| 应用代理端口 | `127.0.0.1:18080` / `127.0.0.1:18443`，分别映射容器 80 / 443 |
| 独立宿主机数据目录 | `/opt/websoft9-cli-acceptance-20261020/data` |
| 容器内数据目录 | `/opt/websoft9/data` |

独立宿主机目录挂载到容器标准数据路径，避免基础镜像中 Gitea 用户固定主目录与非标准容器内路径冲突。新实例不复制原平台的业务数据或账号，首次访问需要初始化管理员。端口仅绑定回环地址；远程访问需端口转发，不直接开放公网。

已通过 **50 项镜像/运行验收检查**：包括 30 项正式 CLI 查询及错误/拒绝契约、镜像与源码核对、端口及数据挂载边界、补全、实际就绪、重启后源码与数据持久性、原容器及八个服务 PID 不变。另验证 **138 条新旧命令路径**短/长帮助一致。新容器重启后健康及就绪均通过，Console 返回 HTTP 200。构建暂存目录、上下文归档及首次失败启动的临时数据/镜像标签均已清理。

**验收边界**：镜像只保存在本机，未推送仓库，也未替换原 `websoft9-dev`。新旧实例仍共用 Docker 引擎，不是完全隔离的业务测试环境；首次镜像检查仅执行只读操作，后续真实写入验收见下一节。新实例关闭自动升级下载及备份镜像预拉取，防止验收期间启动额外写入。镜像可用于重建保留 CLI，业务数据仍依赖上述独立目录，不能误用原数据挂载。

#### 新镜像原生端到端生命周期验收（2026-10-20）

**最终镜像的可控范围端到端验收通过：175 项检查通过、0 项失败，并遍历 138 条帮助路径。** 不将本结论扩大为所有命令、所有环境或生产升级发布认证。

此次直接使用新平台的正式 `websoft9` 包装入口、原生配置、实际安装状态库及默认 Restic 仓库；没有替换为隔离配置或临时源码。每次产品修复后均重新构建镜像，再保留该实例的数据目录重建容器，最终又完成完整生命周期和重启检查。

真实测试发现并修复三个问题：

1. **Compose 更新假成功**：[更新服务](../apphub/src/services/compose_app_manager.py) 原来把所有 Git 提交错误当作无变更，干净镜像缺少全局作者时会重部署旧内容。现在使用集成凭据中的显式作者；仅真正无差异时跳过提交。提交或推送失败明确返回错误，不继续重部署。
2. **环境变量字面值损坏**：Compose 安装、更新原来裸写 `.env`，会截断含空格及 `#` 的值；原 Git 写入方式重复转义反斜杠，也与实际 Compose 语义不一致。[共享读写函数](../apphub/src/utils/env_file.py) 已接入安装、更新和 Git 环境变量修改；写入时正确处理引号、反斜杠、换行和字面 `$`，读取时不展开宿主机变量，并兼容单引号内容。环境变量值不再去除首尾空白；无效赋值明确报错，不回显变量内容。
3. **商店安装 JSON 被日志污染**：[安装命令](../apphub/src/cli/app_commands.py) 复用现有日志路由，将后端安装日志输出到 stderr。stdout 保留原有 `{app_id, tracking_id}` JSON，不改成新 envelope，也不丢弃日志。

| 范围 | 结果 | 实际验证 |
| :--- | :--- | :--- |
| 新镜像原生生命周期 | 79 通过 | Compose 安装、应用/容器启停、真实指标、控制面保护、Git 冲突/特殊值/删除/完整树回退、显式重部署、Compose 更新实际生效、自定义字段、Restic 创建/覆盖恢复/删除、文件属主 `1001:1002`、保留数据卸载/恢复、最终清除 |
| 扩展真实服务 | 46 通过 | MySQL 8.4 和 PostgreSQL 17 的连接/版本/特殊字符密码/错误密码拒绝/不可达错误及脱敏；官方 Redis 7.4 商店安装、原 JSON 契约、认证、实际写入及启停后数据保留、卸载清除；网关目标设置、域名绑定、实际 HTTP 响应和绑定删除 |
| 最终镜像及重启 | 50 通过 | 镜像源码哈希、正式入口、错误/拒绝契约、138 条路径的 `-h`/`--help` 一致性、补全、独立数据和回环端口、实际就绪、重启后源码和凭据持久性、原容器及八个服务 PID 不变 |
| Compose 字面值额外验证 | 9 通过 | 使用真实 Docker Compose 容器逐字节核对空值、`$`/`#`/空格、`${HOME}`、单双引号、首尾空格、LF/CRLF、反斜杠及末尾反斜杠 |

最终镜像 ID：`sha256:28010a628e2e272d07c75eadb610bd201c2e00c3a54337547ac010a024387b07`。镜像内源码及版本文件的联合 SHA-256：`0910739532e56306899a072f6be559e909b928777d8850ba25502e2772c492c3`。

相关回归命令及结果（在 `apphub/` 执行；不同命令包含重叠用例，不相加计数）：

```bash
# 61 passed；此集合已加入独立阻断式 CI 步骤。
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_cli_git_regressions.py tests/test_app_compose_install.py tests/test_compose_app_classification.py tests/test_apphub_cli_apps.py

# 288 passed
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_cli_usability.py tests/test_apphub_cli_apps.py tests/test_apphub_cli_check_update.py tests/test_cli_batch_a.py tests/test_cli_batch_b.py tests/test_cli_batch_c.py tests/test_cli_contract_regressions.py tests/test_cli_restore_regressions.py tests/test_compose_app_classification.py

# 12 passed；独立进程，避免旧测试的全局模块替身影响其他测试。
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_backup_restore.py

# 8 passed；独立进程。
python3 -m pytest -q -o addopts='' --disable-warnings tests/test_apphub_cli_upgrade.py
```

最终两组真实写入测试的清理错误均为零，原有容器未被重启，仓库、Stack、卷及代理绑定清单恢复测试前状态；临时测试容器、快照、上传脚本及工作文件已清理。验收结果保留在新实例数据目录的 `cli-image-e2e/lifecycle-result.json` 和 `cli-image-e2e/extended-result.json`，生命周期结果同时保留前面失败轮次，便于追溯问题及复测。

**仍未覆盖**：真实公网 Let's Encrypt 签发、外部 SMTP 投递、异机 SSH/SFTP、最终整个平台版本升级，以及所有命令的所有破坏性分支。本轮不伪造这些链路成功，也没有发布工作区前端变更。

新镜像端到端生命周期阶段已完成。下一步可固化 CLI 发布基线，再按 [AI 阶段计划](./ai-integration-architecture.md#52-阶段与依赖) 进入 Phase 1A：核对全局规则、接入 `ops-diagnose` 只读技能，验证“查应用 → 查日志 → 给出有证据的诊断”，暂不开放写操作。
