# Websoft9 AI 集成架构与实施方案

## 1. 目标、范围与关键决策

本文面向产品与研发团队，说明如何为 Websoft9 增加自然语言应用管理与运维能力。**本文是目标设计，不表示规划中的命令、技能和 Agent 集成已经交付。** 全量能力与源码入口见第 6 章，实际开放范围由第 5 章的阶段验收决定。

CLI 编码依据见 [CLI 整体规划与增量实施](./cli-implementation-design.md)：包括全量能力与复用、按成熟度分批交付、必要约定及缺口；参数和字段随命令开发确定，不另做全量详细设计。

### 1.1 关键决策

| 事项 | 采用方式 | 不建设或不作为前置条件 |
| :--- | :--- | :--- |
| Agent | 在 OpenCode、Goose、Hermes 等第三方底座中选型，复用模型、会话、工具调用与确认交互 | 自研推理循环、多 Agent 调度器 |
| 执行 | `websoft9 CLI` 复用现有 AppHub Service，兼容人工终端、脚本和 Cron | 新增 HTTP AI 网关、审批库、平行应用状态系统 |
| 知识 | `AGENTS.md` 放全局规则与技能索引，Skills 按需提供任务 SOP | 将完整命令手册和排障树放入常驻提示 |
| 分类 | 三个能力域、八个任务技能；CLI 按十一顶层组及其子组组织 | 技能与页面、组件或 CLI 一一对应 |
| 交付 | CLI 按成熟度分批交付；AI 先只读、再受控写入，Console 后接 | 全部基础命令等待聚合诊断；一次交付全量命令 |
| MCP | 有远程、无 Shell 客户端需求时再适配 | 本地 CLI 调用的必需层 |

### 1.2 平台定位

Websoft9 是面向单机/自托管的应用管理平台：主容器通过 `supervisord` 管理 AppHub、网关及 Gitea、Portainer、NPM 等进程，业务应用由 Docker/Stack 承载。AI 应围绕**应用实例**完成任务，不让用户自行拼接配置仓库、容器和反代操作，也不另做一套通用主机管理系统。

三个能力域分别覆盖：

- **应用管理**：选型部署、配置与版本变更、启停、访问、数据保护和退出。
- **运行保障**：故障诊断、容量巡检、外部容器维护与空间回收。
- **平台管理**：控制平面状态与日志、既有任务、设置及更新准备。

首期面向可信管理员辅助。工具确认不是 OS 权限隔离，也不能自动构成多用户 Console 的安全委托；界面开放须匹配实际认证、授权和运行身份。不同底座的模型支持、技能加载与权限语法须验证，不能假设通用。

## 2. 架构与平台规则

### 2.1 调用链与职责

```text
Console 场景入口 / AI 抽屉 / Web 终端
                    |
第三方 Agent：模型、会话、任务编排、确认、结果反馈
        AGENTS.md 全局规则 + 按需加载的 Skill
                    |
        websoft9 <group> <command> --json
                    |
CLI：参数校验、输出与错误、脱敏、写入及资源保护
                    |
现有 AppHub Service -> Gitea / Portainer / NPM / Restic
```

| 层 | 职责 | 边界 |
| :--- | :--- | :--- |
| Agent | 理解意图、选择主技能、组织工具调用及确认 | 不代替后端校验或系统授权 |
| `AGENTS.md` | 平台概念、全局约束与技能导航 | 不放完整 SOP、命令参数或秘密 |
| Skills | 输入检查、任务流程、确认点、验收和失败去向 | 不创造缺失命令，不绕过禁用操作 |
| CLI / Service | CLI 适配现有业务、统一输出并落实检查；Service 执行确定性操作 | 不复制安装器、状态机或数据真源；不能将校验只写在提示词里 |
| Console | 携带当前目标，展示会话、影响与结果 | 不向浏览器暴露模型密钥，不扩大执行权限 |

### 2.2 Websoft9 特有规则

下表是全局规则的唯一说明位置，技能和命令矩阵仅补充各自差异。

| 平台特点 | AI 操作规则 |
| :--- | :--- |
| **以应用为管理单元** | 一个实例可含多个容器。纳管应用优先走 `app` / `git`，底层 Docker 命令用于诊断或外部容器维护，不绕过应用状态管理 |
| **现有安装跟踪与任务** | 复用现有参数校验、端口预留、安装跟踪和任务记录，使用实际返回的实例/跟踪标识，不根据用户输入猜最终 ID，不新增平行状态 |
| **Gitea 保存纳管配置** | 编排、环境和挂载配置通过仓库维护，不直接修改 Portainer Compose 临时目录；读取 SHA、形成差异、确认、提交、重建、验证，冲突不能覆盖重试 |
| **访问配置联动** | 域名/反代变更须同步检查应用地址与网络，不能只改 NPM 就视为完成；内部监听端口和宿主机映射端口不可混淆 |
| **停用保留数据** | `Inactive` 应用可能仍保留仓库与卷。未运行、未挂载或 dangling 不代表可删除，清理前检查实例归属与引用 |
| **三类恢复不同** | `app restore` 重新激活，`git rollback` 回退配置，`backup restore` 覆盖恢复数据；配置回退不撤销数据库迁移 |
| **单容器控制平面** | Gitea、Portainer、NPM 等是平台内置进程/引擎，不能假设它们都是独立可删容器；服务维护走现有入口，保护实际进程、容器、网络与数据 |
| **备份有范围** | Restic 针对应用 Docker 数据卷，Bind Mount、外部数据库和配置仓库不自动包含；必须给出覆盖清单，活跃数据库文件快照不等于事务一致备份 |
| **主机接入可能写授权** | SSH/SFTP 会话准备可能触发宿主机授权与提权，不作为只读诊断或 AI 自动补救手段 |

关键变量按平台原义使用：

| 变量 | 含义 |
| :--- | :--- |
| `W9_ID` / `app_id` | 应用实例标识，仍须核对资源归属，不仅凭命名推断 |
| `W9_HTTP_PORT` / `W9_HTTPS_PORT` | 容器内部监听端口，反代目标须与实际监听一致 |
| `W9_HTTP_PORT_SET` / `W9_API_PORT_SET` | 宿主机映射端口，执行安装或变更时检查监听、映射和安装预留 |
| `W9_URL` / `W9_URL_REPLACE` | 应用外部地址及替换能力，切换域名须核对同步和重建影响 |
| `W9_NETWORK=websoft9` | 平台共享网络，按应用访问与跨应用通信需要接入 |

## 3. 三个能力域与八个任务技能

**能力域按“管理什么”组织知识，Skill 按“完成什么任务”组织流程，CLI 按“提供什么动作”组织工具。** 多个技能可复用同一命令，一个技能也可组合多个命令组。应用全生命周期是整个应用管理域的覆盖目标，不是兜底技能。

### 3.1 技能职责

| 能力域 / Skill | 用户任务与主流程 | 特殊边界 |
| :--- | :--- | :--- |
| **应用管理 / `app-deploy`** 应用部署 | 找应用、评估资源、首次部署；解析模板和版本，检查配额/端口/外部库，校验 Compose，确认安装计划并验证 | 已有实例升级归 `app-change`；失败转诊断，不自动清理重装 |
| **应用管理 / `app-change`** 应用变更 | 改端口、环境变量、编排与挂载配置、升级或配置回退；读取现状与 SHA，展示差异、提交重建并验证 | 升级另查兼容、数据库迁移、备份一致性及降级限制；PHP 迁移申请不等于自动迁移 |
| **应用管理 / `app-manage`** 应用运行管理 | 查看实例、启停重启、停用保留数据、重新激活、卸载；检查状态和活跃任务，确认后执行并核对结果 | 删除与错误残留清理须展示实际资源；版本升级和数据恢复分别转变更/数据技能 |
| **应用管理 / `app-access`** 应用访问 | 域名、HTTPS、反代目标、访问控制、登录指引；检查地址/网络/证书，制定联动方案并验证 DNS/TLS/访问 | 自签名证书不是公网可信证书；凭证明文与重置走人工界面；平台入口归平台维护 |
| **应用管理 / `app-data`** 应用数据保护 | 卷内文件、权限、备份恢复与外部数据库连接检查；核对对象、路径、覆盖范围及结果 | 不默认递归改全卷权限，不承诺通用 SQL/迁移；恢复先满足后端整改要求 |
| **运行保障 / `ops-diagnose`** 故障诊断与修复 | 安装失败、退出、访问或性能异常；采集应用/容器/网关/任务/平台证据，给出原因与修复建议 | 区分事实和推测，复用责任技能执行具体修复；不默认无人值守自愈 |
| **运行保障 / `ops-resources`** 资源巡检与维护 | 容量、容器监控、镜像网络、外部容器及空间回收；盘点引用和归属，确认候选，维护后验证 | 具体异常根因先转诊断，纳管实例启停走应用管理，不将保留卷当垃圾 |
| **平台管理 / `platform-maintain`** 平台维护 | 控制平面巡检、服务日志、既有任务、镜像源、SMTP、更新准备与平台网关 | 不扩展为通用主机运维；控制面重启、账号密钥修复和最终平台重建保留人工 |

八个技能是规划目录，按已有 CLI 分批启用，不为凑数量编写不可执行流程。只有真实任务路由冲突或 SOP 明显过大时才拆分。

### 3.2 公共流程与协作

所有技能共用“**识别目标 → 检查现状和依赖 → 展示计划并确认 → 执行 → 验证**”：

- 写清触发/排除条件、必要输入、已交付 CLI、确认与停止条件、完成标准和失败去向。
- 资源归属、活跃任务、冲突及恢复前置条件由 CLI/Service 校验；权限不足、参数缺失或命令未实现须明确停止，不用 Shell 补齐。
- 删除、覆盖、重建展示真实影响；退出成功不能替代状态或健康验证。失败说明已执行步骤、当前状态和下一步，不伪报完成。

一次任务由一个主技能收口，其他技能提供 SOP 或参考资料，不新增多 Agent 调度。域名变更由 `app-access` 主责，涉及仓库修改时复用 `app-change`；日常容量检查归资源维护，突然高负载先归诊断。

**示例：“升级 WordPress”**

```text
app-change：读取当前实例、配置版本、目标版本和兼容性
  -> 复用 app-data：核对备份范围、一致性与可恢复条件
  -> 展示差异、迁移风险和降级限制
  -> 确认后变更、重建并验证
  -> 失败转 ops-diagnose；不自动覆盖恢复业务数据
```

诊断遵循平台证据：镜像 EOF/超时先查镜像源、网络和磁盘；安装超时须查任务与 Stack 实际进度；退出码 137 结合 `OOMKilled`、限制与宿主机内存分析，不能直接建议降低内存上限；502 检查目标状态、共享网络与监听端口。

### 3.3 常驻规则与技能发布

`AGENTS.md` 目标不超过 60 行，仅含平台概念、执行原则、配置真源、敏感信息/资源保护与技能索引，不复制本章完整流程。建议骨架：

```markdown
# Websoft9 AI Operations
- 仅使用已交付的 websoft9 CLI；先查 --help，不用裸 Shell 补齐能力。
- 以应用实例为目标，复用现有服务和任务，不直接拼接底层管理动作。
- 纳管配置通过 Gitea 修改，保留 SHA 检查，不把 ****** 写回配置。
- 保护控制平面与停用应用保留数据；区分三类恢复，不自动恢复数据。
- 查询必须只读；写操作说明影响并确认，执行后检查实际结果。
- 秘密值不进入对话；明文凭证、密钥与高风险平台操作引导人工。
- 按任务加载八个技能中已交付的流程，故障先取证，未实现步骤明确报告。
```

规划随容器发布至 `/websoft9/AGENTS.md`、`/websoft9/skills/<skill>/SKILL.md`；技能名称见 3.1 节。实际发现目录、摘要格式和加载入口按选定底座适配验证，不能仅凭文件存在就宣称可用。技能描述须标注当前可执行范围，不能把只读版预检描述为已支持安装。

## 4. 执行契约与安全边界

### 4.1 CLI 公共契约

新增或适配后的 AI 命令支持 `--help`、`--json`，兼容现有人工和 Cron 入口。统一信封：

下列信封先用于新命令；已有 `--json` 的旧格式和特殊退出码保持兼容，不通过根组包装器强制替换。旧命令后续接入的 opt-in/别名策略按 CLI 实现设计单独验收。

```json
{"ok": true, "code": "OK", "data": {}, "error": null, "meta": {"truncated": false}}
```

| 项目 | 要求 |
| :--- | :--- |
| 错误 | `ok=false`、`data=null`，稳定错误标识及脱敏 `error.message/details`；沿用现有日志，不返回成功形状的兜底 |
| 退出码 | `0` 成功、`1` 执行失败、`2` 参数错误；不把日志混入 JSON 标准输出 |
| 大文本 | 默认按行数或 64KB 截断并标记 `meta.truncated=true`，不能把截断当完整日志 |
| 只读 | 查询不协调过期任务状态、不清理资源、不准备主机授权；应用列表与详情整链支持纯查询，拟议 `reconcile_stale=False` 尚待实现 |
| 异步结果 | 复用现有跟踪/任务标识，区分请求已提交、进行中与实际完成，不自建任务系统或在 CLI 退出后遗留不受管理的后台工作 |
| 能力发现 | 第 6 章是规划矩阵，非已发布手册；调用以当前版本 `--help` 为准，缺失命令明确反馈，不猜测参数 |

### 4.2 权限与人工边界

| 标记 | 要求 | 典型操作 |
| :--- | :--- | :--- |
| `allow` | 已验证无业务状态副作用且输出脱敏的查询 | 状态、列表、日志、诊断、连接检查 |
| `ask` | 说明实际影响、确认后执行 | 安装、启停、配置、域名、备份、资源维护 |
| `ask!` | `ask` 的高风险展示要求，**不是底座新权限类型** | 删除应用/卷/快照、错误残留清理、数据覆盖恢复 |
| `deny` | AI 不执行，提供人工指引 | 任意 Exec、自定义主机 Shell、主机全局文件、明文秘密、平台账号/API Key 管理 |

未声明工具默认拒绝；控制面重启、内部账号密钥修复、SSH 免密/提权准备、私钥上传和最终平台重建均保留人工。禁止通过既有自定义任务的 `run/toggle/sync`、应用预设命令或其他入口绕过限制。

底座匹配顺序、通配符及参数处理须实测，覆盖正常查询、确认拒绝、高危禁用和默认拒绝。不维护声称适用于所有 Agent 的通用配置；工具确认不能替代后端校验与运行身份约束。

### 4.3 脱敏、写入和保护

- **输出面**：结构化字段、`.env`、URI 密码、日志、Diff 和错误均纳入脱敏；`PASSWORD/SECRET/TOKEN/KEY/CREDENTIAL/PRIVATE` 等敏感值掩码，`has_password` 等布尔标记保留。
- **明文**：人工可按权限使用 `--reveal-secrets`，AI 禁止该参数；`WEBSOFT9_FORCE_MASK=1` 可作默认配置，不是不可绕过的授权边界。
- **写入**：优先局部更新环境变量，仓库与卷文件拒绝 `******` 覆写；文件冲突须重读、对比并重新确认。已有文件读写不等于已有提交历史、Diff 或回退能力。
- **控制面**：保护真实容器/进程、核心网络和平台卷；文件入口除 `__docker_volumes_root__`、`platform-gateway-certificates` 哨兵外还须检查真实路径归属，不能只按名称匹配。
- **删除**：列出真实目标及引用，保护停用应用保留数据；`app clean-error` 可能删除 Stack、卷、仓库和反代，执行前核对活跃任务，不能只提示“清理记录”。
- **恢复**：遵守 2.2 节范围与一致性限制。须先整改停止失败仍恢复、固定 `chown 33:33`、重启失败仅告警的问题，再开放 `backup restore`；各失败路径报告实际状态。版本变更不能默认以“配置回退 + 覆盖数据恢复”补救。

## 5. 实施阶段、验收与 Console 入口

### 5.1 复用现有实现

CLI 从 `apphub/src/cli/apphub_cli.py` 注册，沿用现有 Click 模式，按需要拆分命令组，**不先创建全量空壳文件**。公共模块负责输出/错误、脱敏和写入保护；资源、路径、SHA 和状态检查接入实际操作路径，不能只靠公共输出函数。

| 工作面 | 复用与新增要求 |
| :--- | :--- |
| 应用执行 | 复用现有校验、安装跟踪、端口预留、Compose 重建和任务服务，不重新编写安装执行器；停用激活和运行中重建按现有语义处理 |
| 只读与诊断 | 整改列表/详情的纯查询路径，复用安装与运行日志；聚合诊断仅组织已有证据，明确缺失项，不另建状态存储 |
| 配置变更 | 复用 Gitea 文件与 SHA 能力，多键更新、历史、Diff、回退按变更任务需要补齐 |
| 资源与访问 | 复用 Portainer、NPM、Restic 及现有平台任务；只为实际任务补缺失 API，不以完整替代底层工具为目标 |
| 集成资产 | 全局规则与技能按第 3 章发布；底座配置、模型密钥与 Console 适配单独验证，不预先固定函数签名和全部目录 |

已有脚本/任务如商店同步、镜像预热/调度、日志清理、更新准备和任务对账继续复用。旧入口及默认语义保持不变，新增别名不等于自动向 AI 开放。

### 5.2 阶段与依赖

**以下是 AI 开放与验收阶段，不是 CLI 开发的串行顺序。** CLI 按实现规划的 A/B/C 批次独立交付，成熟的安装、启停等能力不等待聚合诊断；提前交付写命令不等于提前授权 AI 执行。AI 诊断可先组合已交付查询和日志，专用聚合工具按需补齐；预检独立验收，Git 历史、Diff、回退不作为诊断前置。

| 阶段 | 交付 | 验收与边界 |
| :--- | :--- | :--- |
| **Phase 1A：应用只读诊断** | 新命令基本输出/错误与脱敏；应用查询只读整改；实例及相关日志；全局规则及 `ops-diagnose` 只读版，平台日志巡检按已交付命令启用；聚合工具可后补 | “查实例 → 查日志 → 给出有证据的原因/下一步”闭环；命令失败或证据不足明确报告，不清理、不重装、不改主机。验证底座加载与工具限制，不依赖全部日志入口、聚合工具或完整资源管理 |
| **Phase 1B：部署预检与巡检** | 搜索模板、资源/配额/端口、Compose 校验及已就绪的数据库连接检查；必要的配置只读入口；启用 `app-deploy` 只读预检和 `platform-maintain` 只读巡检 | 与诊断独立验收：能说明“可部署/条件不足/检查缺失”；未完成外部库或深度环境检查不能给出完整通过结论，不执行安装 |
| **Phase 2：应用核心写操作** | 复用安装、启停、重建与退出；补齐配置变更及必要历史/Diff/回退；访问联动、备份、任务与设置；按依赖开放应用管理技能和诊断修复 | 验证确认拒绝、SHA 冲突、真实影响和操作后健康。恢复先整改；无一致性备份/迁移方案的升级保持受限，未实现步骤不写成执行承诺 |
| **Phase 3：资源维护与 Console** | 按需求扩展 Stats、镜像/网络维护、证书续期和高级网关；启用 `ops-resources` 及长尾流程，接入正式会话、设置和结果展示 | 验证控制面与停用卷保护、巡检/故障路由、认证授权与会话关联。Console 和长尾资源管理不是 Phase 1A 前置 |

以下为 AI 各阶段按需使用的 CLI 范围，不构成 CLI 批次的完整交付门槛。统一省略 `websoft9` 前缀；新命令支持 `--json`，旧命令机器适配显式设计，默认行为保持兼容：

| 批次 | 命令范围 |
| :--- | :--- |
| **1A 只读闭环** | 优先 `app list`、`app inspect <app_id>`、`docker container inspect/logs <name>`；平台问题按需使用 `service list/logs/runtime-logs`。`app diagnose` 聚合工具后补，不要求所有入口齐备才开始诊断；外部/异常容器枚举按需补 `docker container list` |
| **1B 独立预检** | `overview status/edition/readiness`、`appstore search <query>/info <name>/state`、`host ports check <ports>/suggest`、`app validate-compose --file <yml>`；`app database list/test` 与 `git repos/files/cat` 按检查需要交付，深度 `host env-check` 未就绪时明确限制 |
| **2 核心变更** | `app install/install-compose/start/stop/restart/redeploy/uninstall/restore/clean-error/remove`，`git env-set/write/log/diff/rollback`，已就绪的 `gateway proxy/cert`，`backup list/create/delete` 及整改后的 `restore`，必要的 `settings mirrors`；各子操作单独验收，不整组通配放行 |

### 5.3 验收底线

| 验证面 | 必须证明 |
| :--- | :--- |
| 兼容与输出 | 旧人工/Cron 默认行为不变；成功、执行失败、参数错误、截断与非 JSON 行为均覆盖 |
| 查询与秘密 | 列表、详情和诊断不隐式写状态/授权；配置、日志、错误、Diff 不泄露秘密；掩码写回拒绝 |
| 技能与权限 | 主技能选择明确，未实现步骤有反馈；只读阶段不写；确认拒绝后不执行，禁用入口不能间接绕过 |
| 变更与资源 | SHA 冲突不覆盖，删除/覆盖对象可核对，保护控制面与停用卷；变更后检查真实健康 |
| 恢复与集成 | 停止、恢复、重启失败返回真实状态；技能实际可发现；Console 的目标、确认和结果对应同一操作且不扩大权限 |

先运行相关现有测试和针对性新增测试，再验证对应场景。文档格式检查不能代替功能与安全验收。

### 5.4 Console 渐进接入

优先复用现有业务上下文，不另建应用工作台：安装错误或容器异常入口携带实例进入诊断；编排编辑器进入应用变更并展示差异；全局抽屉展示目标、影响、确认和结果；Web 终端按需提供底座 TUI。安装报错按钮不能直接触发错误清理。

Provider/API Key 在服务端管理，浏览器只见脱敏配置。底座原生确认适配为界面卡片，不另建审批状态机；正式 UI 的认证授权、会话与执行关联必须通过验收，不能仅因命令可在管理员终端运行就直接向所有用户开放。

## 6. 附录：CLI 能力矩阵与源码入口

### 6.1 阅读约定

按十一个顶层技术命令组及其子组组织能力，不作为完整参数手册。应用外部数据库归入 `app database`，不管理 Websoft9 内部数据库；新开发且无实际调用的 `db` 不保留别名，历史脚本和 cron 使用的入口继续兼容。表中省略 `websoft9` 前缀，`/` 表示独立动作而非可直接复制的一条命令；参数以实际交付版本 `--help` 为准。**以下是全量规划，不是首期清单，也不承诺对 AI 全部开放。**

| 状态 | 含义 |
| :--- | :--- |
| **已有** | 相同或对应 CLI 已存在，仍需核对别名、参数及统一契约 |
| **封装** | 主要 Service 能力已有，需接入参数、边界、输出及测试 |
| **扩展** | 需新增或整改后端/API，当前不可作为可执行步骤 |

权限见 4.2 节。矩阵内只注明特殊约束：查询按 `allow` 验收，常规写按 `ask`，删除/覆盖按 `ask!`；组合能力必须逐动作判定，不能按整行或整组放行。已有但人工专用的能力不需要为 AI 再做一套封装。

### 6.2 十一个顶层组及其子组能力

#### 1. `overview`：概览与就绪

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 状态、配额、就绪 | `status / edition / readiness` | **封装**；CPU、内存、Swap、磁盘/网络、应用统计、产品版本、`max_apps`、底座和初始化状态；区分未就绪与检查失败，不隐式修复 |

#### 2. `appstore`：模板与同步

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 检索、模板、同步状态 | `search / info / state` | **封装**；应用 key/版本/最低内存、必填设置、Profile、端口、HTTPS 要求与数据集渠道；支持本地模板，不把模板文本视为执行授权 |
| 同步与重建索引 | `sync / refresh` | **已有对应入口**；保留同步渠道、强制刷新和后台选项，现有索引刷新入口为 `app refresh`，新别名不改变语义 |
| 收藏 | `favorites list / add / remove` | **封装**；按真实操作员身份读写，不能默认使用共享管理员收藏 |

#### 3. `app`：应用实例

商店、本地商店、自定义 Compose 与外部容器识别分开处理；状态包括 `Active=1`、`Inactive=2`、`Installing=3`、`Error=4`、`Cancelled`，外部容器不自动成为纳管应用。

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 查询与诊断 | `list / inspect / diagnose` | 前两项**封装 + 只读整改**，聚合诊断**扩展**；包含类型/状态、容器/卷、脱敏配置、安装日志、Stack、退出码、健康和 `OOMKilled`；聚合缺项明确标注 |
| 部署前校验 | `validate-compose` | **封装**；语法、变量插值和字段检查，校验通过不等于安全或可部署保证 |
| 商店/Compose 安装与编辑 | `install / install-compose / update-compose` | 商店安装**已有**基础 `--json` / `--from-json`，本地/版本/Profile 参数按实际支持核对；Compose **封装**，编辑需补 `_list_src_files` 回显并保留冲突/待重建语义 |
| 安装取消与运行 | `cancel / start / stop / restart / redeploy` | **封装**；区分取消请求与实际终止，按应用单元操作，重建遵守仓库真源及实例状态 |
| 停用、激活、退出 | `uninstall --keep-data / restore / clean-error / remove --purge-data` | **封装**；遵守平台保留数据规则，后两项按真实删除范围确认，不因 Error/超时直接清理 |
| 凭证与预设命令 | `credentials / exec-preset` | **封装 + 信任检查**；凭证掩码，明文/密码重置走人工；仓库 `variables.json` 的命令不自动可信，须校验来源、动作与目标，不借预设开放任意 Exec |
| PHP 与元数据 | `php-info / php-migrate-request / custom-fields get/set` | **封装**；分别是信息、迁移申请和元数据读写，不承诺自动 PHP 升级 |
| 应用外部数据库连接 | `database list/test` | **封装**；当前汇总应用外部库并测试 MySQL/MariaDB、PostgreSQL；MongoDB/Redis 等仍需按实际支持交付，秘密用受控输入（如 `--password-stdin`），不执行通用 SQL |

#### 4. `git`：纳管配置

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 仓库与文件读取 | `repos / files / cat` | **封装**；返回提交/目录和文本 SHA，受脱敏与大小限制；现有文件列表不直接保证 `pending_redeploy`，须按实际来源计算 |
| 历史与比较 | `log / diff` | **扩展** Commit/Compare API；新增行与删除行均脱敏，属于变更增强，不阻塞只读诊断 |
| 局部更新与写入 | `env-set / write` | 多键更新**扩展**，文本写入**封装**；保留未改密码/注释、SHA 冲突和掩码保护，环境变量优先局部修改 |
| 删除与回退 | `rm / rollback [--redeploy]` | **扩展**；保护根 `docker-compose.yml`、`.env`，回退产生新提交，不恢复业务数据 |

#### 5. `docker`：诊断与资源维护

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 容器查询 | `container list/inspect/logs/stats` | 前三项**封装**，Stats **扩展**；状态、健康、端口、Mount、网络、退出/重启、日志及采样指标；未知指标不写成零值 |
| 容器控制 | `container start/stop/restart/pause/unpause/exec` | 启停重启**封装**，暂停恢复**扩展**，任意 Exec **deny**；纳管实例优先 `app`，保护平台控制面 |
| 镜像查询与准备 | `image list/pull/prewarm` | List **扩展**，Pull **封装**，Prewarm **已有** `images prewarm`；复用直连/加速器回退和既有预热流程，返回真实结果 |
| 镜像清理 | `image rm/prune` | **扩展**；检查引用，展示候选，考虑回退依赖，不以无容器运行直接认定无用 |
| 卷与文件 | `volume list/inspect/ls/cat/write/mkdir/rm/rename/copy/move/chmod` | **封装**；关联活跃/停用应用、限制真实路径和平台卷，文件读写受脱敏/掩码保护；不通过根目录删除整卷，不默认递归 chmod |
| 卷删除 | `volume delete/prune` | **封装**；核对引用及保留数据，精确展示候选后确认 |
| 网络 | `network list/inspect/connect/disconnect/prune` | **扩展**；检查子网/容器连接，保护共享和控制面必需网络；纳管应用临时连网须说明重建后持久性 |
| Stack 维护 | `stack list/inspect/fix-git-urls/clean-workdir` | **封装**；GitConfig 脱敏，修改前列明目标并核对活跃部署；临时目录不是任意文件入口 |

#### 6. `gateway`：访问与平台入口

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 代理查询与域名联动 | `proxy list/bind/set-target/set-root-url/delete` | **封装**，删除须补一致性校验；转发目标、应用地址和重建按平台规则联动，验证实际访问 |
| 自定义 Nginx | `proxy set-nginx-conf` | **封装**，按高风险变更展示片段和影响，校验实际配置结果 |
| 证书 | `cert list/issue-letsencrypt/renew/upload` | 查询/申请/上传**封装**，续期**扩展**；自签名回退不冒充公网可信证书，发起申请不等于已签发/绑定；私钥上传走人工 |
| 高级网关 | `acl list/create-auth`、`stream list/create`、`redirect list/create` | **扩展**；访问控制秘密不进入模型，四层转发检查端口/开放范围，重定向验证目标与响应 |
| 平台网关 | `platform status/update` | **封装**；更新属于高风险，单独检查失联风险及变更后可达性 |

#### 7. `backup`：Restic 快照

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 查询、创建、删除 | `list / create / delete` | **封装**；快照 ID/实例/时间/覆盖路径清晰，刷新不改变业务状态，删除按覆盖与保留影响确认 |
| 数据恢复 | `restore` | **扩展 / 整改**；按 4.3 节门槛开放，不因已有后端方法就标成可直接执行 |

#### 8. `host`：部署环境与连接元信息

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 端口与环境预检 | `ports check/suggest`、`env-check` | 端口**封装**，环境检查**扩展**；检查监听/映射/安装预留、Swap/Inode/DNS/`vm.max_map_count`；建议端口不永久预留，部署时仍校验 |
| SSH Profile | `ssh-profiles list/test/activate/set-default/delete` | **封装，非首期必需**；只读元信息不导出凭证，变更按身份和影响确认；删除本地连接可能撤销自动建立的凭证 |
| 主机授权与全局文件 | `ssh-prepare`、`fs ls/cat/write/mkdir/rm` | **人工专用 / deny**；不展开通用主机运维 SOP，不为 AI 新增封装，不能自动执行授权或提权准备 |

#### 9. `task`：既有任务与预热队列

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 查询 | `list / runs / log / check-host` | **封装**；任务类型/状态/周期、历史与脱敏输出；查询不重试、不准备主机授权 |
| 调度与执行 | `create/update/toggle/run/sync` | **封装**；允许的内置任务变更需确认，自定义 Shell 创建/修改/间接触发均 **deny** |
| 预热记录与对账 | `prewarm-records list/retry/cancel/delete`、`reconcile-scheduled-tasks` | 记录操作**封装**，对账**已有**顶层入口；保留 `images dispatch`，记录删除不是应用资源清理，AI 开放须检查任务类型 |

#### 10. `service`：平台服务与日志

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 状态与日志 | `list / logs / runtime-logs` | **封装**；复用现有核心服务与 AppHub 日志入口，不将所有平台进程误当独立 Docker 容器 |
| 控制与认证修复 | `control / repair-auth` | 仅现有允许的受控操作考虑封装；控制面重启和凭证修复 **人工专用**，不能绕过保护 |
| 日志清理 | `log-cleanup`（现有顶层入口） | **已有** `--json`，确认清理并报告真实结果，复用轮转机制 |

#### 11. `settings`：平台设置与更新准备

| 能力 | 动作 | 状态与差异要求 |
| :--- | :--- | :--- |
| 摘要、镜像源、邮件 | `summary`、`mirrors list/test/refresh/set`、`smtp get/set/test` | **封装**；查询脱敏，写配置/刷新列表/发测试邮件按实际副作用确认 |
| 更新准备 | `upgrade status/check/prepare/logs` | **封装**；版本检查的缓存刷新与升级包准备分开，最终容器重建保留人工，不以下载完成当升级完成 |
| 配置、账号与密钥 | `getconfig/setconfig/setsysconfig`、`users`、`resetpwd`、`apikey get/rotate` | **已有 / 后续人工能力**；AI **deny**，不因 get 前缀认定安全，不为 AI 扩展该管理面 |

### 6.3 源码入口与缺口

目录缩写：`services/`、`external/` 位于 `apphub/src/`，`routers/` 位于 `apphub/src/api/v1/`；同格裸文件名沿用前述目录，`docker/` 从仓库根目录起算。此表只定位业务复用点，不重复命令功能。

| 命令组 | 主要入口 | 缺口 / 实施重点 |
| :--- | :--- | :--- |
| `overview` | `services/overview_service.py`、`platform_readiness.py`、`product_runtime_state.py`；`routers/setup_wizard.py` | 概览、配额与就绪输出 |
| `appstore` | `services/appstore_sync_manager.py`、`local_app_store.py`、`product_auth.py`；`routers/appstore_sync.py` | 查询/模板/身份封装，同步旧行为兼容 |
| `app` | `services/app_manager.py`、`compose_app_manager.py`、`compose_install.py`、`app_access_manager.py`、`app_status.py`；`routers/app.py`、`compose_app.py` | 查询只读整链、聚合证据、Compose 挂载回显、预设命令信任与真实操作影响 |
| `git` | `services/gitea_manager.py`、`git_manager.py`；`external/gitea_api.py` | 复用文件读写与 SHA，补多键更新、历史/比较/回退/删除 |
| `docker` | `services/portainer_manager.py`、`image_pull.py`、`image_prewarm.py`、`file_manager.py`；`external/portainer_api.py` | 复用容器/卷/Stack/预热，补 Stats/Pause、镜像网络 API 和资源保护 |
| `gateway` | `services/proxy_manager.py`、`proxy_task_manager.py`、`app_access_manager.py`；`external/nginx_proxy_manager_api.py`；`routers/settings.py` | 代理/证书/地址一致性，补续期与高级网关 |
| `backup` | `services/back_manager.py`；`routers/backup.py` | 覆盖范围及恢复停止/权限/重启错误整改 |
| `app database`（子组） | `services/app_manager.py`、`install_profile.py` | 应用外部库聚合与测试，不管理平台内部数据库，秘密输入保护 |
| `host` | `services/host_access.py`、`host_access_prepare.py`、`app_sftp.py`、`port_allocator.py` | 复用端口/连接，隔离授权写入路径，按需补环境检查 |
| `task` | `services/scheduled_tasks.py`、`image_prewarm.py`；`routers/scheduled_tasks.py` | 任务类型校验及既有历史/队列封装 |
| `service` | `services/core_services.py`、`runtime_logs.py`、`log_cleanup.py`、`integration_session_bridge.py`；`docker/scripts/platform-service-control.sh` | 日志适配、真实控制面保护及人工凭证边界 |
| `settings` | `services/settings_manager.py`、`mirror_registry.py`、`smtp_service.py`、`upgrade_manager.py`、`product_auth.py`、`apikey_manager.py` | 设置脱敏与更新状态区分；人工管理面不向 AI 开放 |

旧入口如 `app refresh`、`images prewarm/dispatch`、`reconcile-scheduled-tasks`、`log-cleanup`、`check-update` 和内部配置命令保持兼容；新开发且未被业务使用的命令允许直接调整名称，不增加无必要的兼容别名。新别名、命令组与技能仅组织已交付能力，不能改变旧脚本默认语义或自动获得 AI 执行许可。
