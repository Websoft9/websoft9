# Websoft9 统一日志管理方案

**版本：** 1.0  
**日期：** 2026-09-28  
**状态：** Draft（待决策，未实施）

> 本文基于当前代码、容器运行时日志样本和轮转行为验证形成。它是后续决策与实施的设计基线，不代表任何日志改造已经上线。

## 1. 目标与边界

目标是在持久数据卷内统一管理平台运行日志，使日志可轮转、按天保留、可压缩、可安全查询，并保证现有两个入口不回归：

- 菜单「日志」继续展示平台结构化 runtime 事件。
- 「服务 -> 查看日志」继续展示服务原始日志，并保留 `7d` 与 `all` 的历史查询语义。

本期只管理平台服务运行日志。安装跟踪 SQLite、计划任务运行历史、升级过程日志和备份工具日志维持各自的保留策略，不能由通用日志清理任务删除。

## 2. 当前事实与关键风险

| 主题 | 当前事实 | 风险 |
|---|---|---|
| Runtime 菜单 | 仅读取一个 JSON runtime 文件 | 只轮转压缩会使历史查询失效 |
| 服务日志弹窗 | 递归读取 raw log，明确跳过 `.gz` | `7d`/`all` 会退化为当前文件 |
| NPM | 镜像自带 logrotate，cron.daily 自动执行 | 与平台任务双重轮转；`su npm npm` 对当前 root 文件会失败 |
| AppHub | 自身使用 `TimedRotatingFileHandler` | 外部 logrotate 会与应用轮转竞争 |
| Supervisor | 多个程序 stdout/stderr 与自身活动共写一个文件 | 无法按服务治理，轮转归属不清 |
| 自定义日志根 | entrypoint 与 AppHub runtime 默认路径计算不一致 | runtime 事件会分裂，菜单无声漏日志 |

**硬性原则：每一个活动日志文件只能有一个轮转器。**

## 3. 目标布局

根目录固定在持久卷：`/opt/websoft9/data/logs`。`/var/log/websoft9` 保持为兼容链接，但不是新的真实写入根。

```text
logs/
  runtime/platform-runtime.jsonl
  services/gateway/access.log
  services/gateway/error.log
  services/apphub/app.log
  services/apphub/access.log
  services/apphub/error.log
  services/apphub/install.log
  services/apphub/media.log
  services/gitea/service.log
  services/portainer/service.log
  services/npm/backend.log
  services/npm/nginx.log
  services/npm/fallback_access.log
  services/npm/fallback_error.log
  supervisor/supervisord.log
  .state/logrotate.status
  .state/log-cleanup.lock
```

归档与当前文件同目录，例如 `access.log-20260928-013000.gz`。文件名使用 UTC 时间，作为历史查询和清理的权威时间来源。

## 4. 写入与轮转设计

| 日志类别 | 写入方 | 平台轮转后的恢复方式 |
|---|---|---|
| Gateway、NPM Nginx | Nginx | rename 后发送 `USR1` |
| Gitea、Portainer、NPM backend | Supervisor 捕获 stdout/stderr | `supervisorctl reopen` |
| AppHub 文件日志 | 可感知文件替换的 Python handler | 下一条日志自动重新打开 |
| Runtime JSON | 可感知文件替换的 JSON handler；entrypoint 每次追加时重新打开 | 下一条日志自动重新打开 |
| Supervisor 自身日志 | 独立文件 | `supervisorctl reopen` |

实施后，所有平台受管文件由平台专属 logrotate 规则管理。NPM 镜像自带的 `/etc/logrotate.d/nginx-proxy-manager` 必须禁用，不能与平台规则共存。

不将 `copytruncate` 作为常规策略；它存在并发写入丢行窗口。若某个写入者无法安全 reopen，必须先增加安全重开能力，不能以静默丢日志换取快速上线。

## 5. 保留、压缩与执行模型

- 默认保留期：14 天；设置范围建议为 1-90 天。
- 默认执行频率：每小时。每日一次无法应对短时间错误风暴。
- 轮转按天执行，同时允许 `maxsize` 提前触发。
- 使用 `dateext` 和秒级日期格式，避免同一天多次轮转覆盖归档。
- 归档 gzip 压缩；独立清理逻辑按归档文件名时间删除过期文件。
- 不依赖 logrotate `maxage`，因为空文件与 `notifempty` 时它不会严格清除过期归档。
- 规则、state 文件和锁全部放在 data volume，避免容器重建后失去状态。
- 手动与定时执行复用同一 runner，使用 `flock` 串行化；已运行时返回 `skipped`。

设置页面名称为「日志」，只提供保留天数、最近执行结果和“立即执行清理”。计划任务页以只读系统任务「日志清理」展示调度与运行历史，不开放任意目录、任意命令或任意 cron 表达式。

## 6. 日志读取兼容层

### 6.1 菜单「日志」

runtime 文件仍是唯一数据源，格式保持 JSON Lines，不能混入 Gitea、NPM 或其他服务原始日志。entrypoint、AppHub runtime handler 和 `RuntimeLogsService` 必须共享同一个 `WEBSOFT9_PLATFORM_RUNTIME_LOG_PATH`。

历史查询读取活动 `.jsonl` 加符合时间范围的 `.gz` 归档。SSE 只跟踪活动文件；发现 inode、设备号或文件长度变化时下发完整快照。

### 6.2 服务「查看日志」

`ServiceDefinition` 更新到目标目录。历史查询读取活动 raw log 加归档 gzip 文件；SSE 仅跟踪活动文件。`all` 表示当前保留窗口内全部可读取历史，而非无限制扫描磁盘。

归档读取必须：

- 拒绝符号链接，且确认解析路径仍位于服务日志根目录内。
- 限制单文件、总解压字节、归档数与返回行数。
- 损坏归档局部跳过并产生 warning，不使接口失败。
- 在受限结果时返回 `truncated=true`，由界面明确提示。
- 统一使用 UTC；无时区的第三方日志按已定义的容器时区解析。

## 7. 迁移与回滚

迁移必须幂等，顺序固定：

1. 创建新目录、权限、平台规则、state 与锁目录。
2. 禁用 NPM 原规则，验证不会再被 cron.daily 触发。
3. 复制旧日志到新目录，记录并校验结果；此时不删除源文件。
4. 同时切换写入路径、服务定义、runtime 路径和读取 API。
5. 重启受影响服务，确认每类日志都在新路径产生新行。
6. 手动执行一次受控轮转，验证写入恢复、gzip 查询和 SSE 刷新。
7. 保留旧路径兼容链接至少一个发布周期；验证后才清理旧副本。

回滚只切换写入与读取路径，不删除迁移期的日志。迁移失败必须保留旧路径可用，不能先清理再尝试恢复。

## 8. 源头治理

### 应立即纳入

- Gateway 的 `/api/healthz`、`/api/healthz/ready`、`/api/healthz/setup-ready` 禁用 access log，与现有 `/w9gateway/healthz` 保持一致。
- 入口脚本将重复成功 bootstrap/wait 事件汇总为启动摘要；保留错误、警告、状态变化和失败原因。

### 必须修根因，禁止降级日志

- NPM `fallback_error.log` 中的 `proxy_temp Permission denied`。
- NPM `worker_connections are not enough`。
- upstream prematurely closed 和 timeout 的上游异常。

### 暂不默认调整

Gitea、NPM backend、Portainer 的全局日志级别保持不变。Gitea router 成功请求降噪可作为二期灰度优化，前提是确认访问审计仍可从 NPM access log 获得。

## 9. 分期建议

| 阶段 | 内容 | 可交付结果 |
|---|---|---|
| 一：安全基础 | 禁用旧 NPM 规则、统一路径、拆 Supervisor 混写、唯一轮转/state/锁 | 磁盘膨胀和双轮转风险消除 |
| 二：读取兼容 | gzip 历史读取、SSE 轮转恢复、安装错误兜底兼容 | 两个现有日志 UI 不退化 |
| 三：源头治理 | 健康检查降噪、NPM 根因修复、runtime 摘要化 | 日志增长恢复到可控水平 |

## 10. 发布门槛

上线前必须自动验证：

1. runtime 与每个服务的当前文件和 gzip 归档均可按时间、级别、关键字查询。
2. `7d`、`all`、结果截断与损坏 gzip 的 API 行为稳定。
3. Gateway/NPM rename 后继续写入；Supervisor reopen 后托管服务继续写入。
4. runtime 和服务 SSE 在 rename、truncate、文件新增/删除后恢复且不报错。
5. `apphub_error.log` 当前和近期历史仍能支持安装失败详情回溯。
6. 自定义 `WEBSOFT9_SERVICE_LOG_ROOT` 下 entrypoint 与 AppHub runtime 进入同一文件。
7. 手动与定时清理并发时仅执行一次，第二次记录为 skipped。
8. 14 天保留期后仅过期归档被删除，活动文件和非日志数据不受影响。

当前 `test_runtime_logs.py` 与 `test_core_services.py` 基线为 27 项通过；实施时应在其上增加上述回归覆盖。

## 11. 非目标

首版不引入集中式日志平台、远程日志存储、全文检索、无限历史、日志告警规则编辑器或第三方服务日志级别的大范围重写。优先确保本地持久化、可诊断性和现有 UI 契约正确。