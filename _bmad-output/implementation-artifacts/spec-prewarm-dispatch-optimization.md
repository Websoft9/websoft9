---
title: '镜像预拉调度优化：主动接续与内部恢复检查'
type: 'refactor'
created: '2026-10-08'
status: 'done'
baseline_commit: '38c92084f2a963122b6fe896b9555ad08409a474'
context:
  - '_bmad-output/planning-artifacts/app-image-prewarm-and-install-cancel-solution.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 每分钟的系统调度任务产生大量空转历史，runner 完成或取消后不能及时接续；预拉任务应复用普通计划任务的历史管理规则，不需要额外保留提示。

**Approach:** 不新增 worker。复用 SQLite 队列、runner、文件锁和 cron，以完成／取消后的主动接续为主，以内部每分钟检查和启动恢复兜底。只记录真实预拉执行。

## Boundaries & Constraints

**Always:** 保持 operator 权限、单任务串行、已有队列与取消语义。预拉与普通计划任务共用保留策略：执行索引最近 20 次／3 天；磁盘 JSON 和日志由 runner 收尾按最近 50 次／七天清理。任务本身不自动过期，删除任务时一并删除历史和日志。界面不显示额外保留提示。迁移只移除旧内部调度任务及其专属产物。本规格覆盖旧方案中与调度、历史保留冲突的条款。

**Ask First:** 扩展为通用后台队列、改变并发数／容量、增加独立服务或外部依赖、删除真实预拉任务或镜像。

**Never:** 修改安装取消、镜像拉取回退或现有 UI 风格；新增 worker；真实拉取镜像作为自动化测试；自动提交或推送。

## I/O & Edge-Case Matrix

| 场景 | 输入／状态 | 预期行为 | 异常处理 |
|---|---|---|---|
| 入队／重试 | 队列无活跃下载 | 立即尝试调度 | 保留持久化队列供兜底恢复 |
| 正常完成 | 成功或失败，仍有排队项 | 写终态、释放锁后立即尝试接续 | 接续失败不修改原执行结果 |
| 取消 | 已排队或正在下载 | 旧进程确认退出后接续 | 终止失败保留进程标识并阻止所有调度入口启动下一项；后续检查确认退出后解除阻塞 |
| 内部检查 | 空闲／已有下载 | 直接退出，不产生业务历史／文件 | 异常进入平台诊断日志 |
| 并发触发 | API、完成回调、cron 同时调用 | 至多一个认领和执行 | 使用跨进程锁与原子认领 |
| 平台重启 | 队列与旧 runner 状态持久化 | 恢复配置、升级旧 runner、收敛状态并调度一次 | 不重复启动仍存活的拉取进程 |
| 历史保留 | 超过公共数量／时间限制 | 任务保留；索引与文件分别沿用普通任务的公共规则 | 取消的运行记录不得被旧 JSON 复活 |
| 升级迁移 | 存在旧系统调度任务 | 从任务库和统一 cron 配置移除，换为内部命令 | 不触碰其他系统任务、用户任务和预拉历史 |

</frozen-after-approval>

## Code Map

- `apphub/src/services/scheduled_tasks.py`：队列派发、取消、runner 生成、cron 配置、迁移、历史清理。
- `apphub/src/cli/apphub_cli.py`：`images dispatch`，内部安静执行和异常诊断。
- `apphub/src/main.py`：启动时后台恢复计划配置。
- `apphub/tests/test_scheduled_tasks.py`：复用现有队列／取消／runner 测试。
- `console/src/features/scheduled-tasks/scheduled-tasks-page.tsx`、`console/src/shared/i18n/resources.ts`：移除预拉历史保留提示，保持原有日志入口与布局。
- `_bmad-output/planning-artifacts/app-image-prewarm-and-install-cancel-solution.md`：更新过时调度和保留条款。

## Tasks & Acceptance

**Execution:**
- [x] `apphub/src/services/scheduled_tasks.py`：移除系统调度定义，迁移旧内部记录；统一 cron 文件加入直接调度命令，避免普通 runner 的空转产物。
- [x] `apphub/src/services/scheduled_tasks.py`、`apphub/src/cli/apphub_cli.py`：完成后接续；取消保留必要的存活阻塞；内部调度安静执行、异常可诊断。
- [x] `apphub/src/main.py`、`apphub/src/services/scheduled_tasks.py`：恢复配置及旧 runner 后主动调度；保持跨进程互斥。
- [x] `apphub/src/services/scheduled_tasks.py`：预拉复用普通计划任务的索引和文件保留规则，删除任务时一并清理历史与日志。
- [x] `console/src/features/scheduled-tasks/scheduled-tasks-page.tsx`、`console/src/shared/i18n/resources.ts`：移除预拉保留说明及中英资源。
- [x] `apphub/tests/test_scheduled_tasks.py`：覆盖矩阵，使用临时数据目录和替身命令，不操作真实 Docker。
- [x] `_bmad-output/planning-artifacts/app-image-prewarm-and-install-cancel-solution.md`：同步实际实现和新的验收要求。

**Acceptance Criteria:**
- Given 现有部署，when 升级恢复配置，then 页面保留真实任务且不再显示内部调度任务。
- Given 连续排队，when 首项结束，then 无需等待 cron 即接续；所有入口的并发执行上限仍为一。
- Given 完成通知遗漏，when 下一次 cron 检查，then 队列可继续且检查本身不产生任务历史。
- Given 删除预拉任务，when 删除成功，then 其历史／日志一起删除，镜像和缓存层不受影响。

## Spec Change Log

- 2026-10-08 用户明确调整：取消预拉专属保留策略和 UI 提示，复用普通计划任务的数量／时间规则。保留已验证的主动接续、取消安全锁、启动恢复与内部 cron 检查。

## Design Notes

回调必须在终态落盘与执行锁释放之后发生，不能继承持锁描述符给下一 runner。取消中的存活进程必须被所有调度入口识别，不能仅在取消函数里跳过一次接续。空转不记业务历史，不等于吞掉异常。

## Verification

**Commands:**
- `cd apphub && python3 -m pytest tests/test_scheduled_tasks.py -k 'prewarm or cancel or reconcile_local_schedule' -q`：聚焦行为测试通过。
- `cd apphub && python3 -m pytest tests/test_scheduled_tasks.py -q`：新改动无回归；两项既有 SSH 失败单独说明。
- 复用 CLI 相关测试覆盖安静执行；以临时 runner 集成测试验证接续、退出码与锁释放。
- 如修改前端：`cd console && npm run build`，并检查历史提示已移除。
- 检查开发容器恢复后的 cron、任务列表和空闲产物数量；不触发真实镜像下载。

**Results (2026-10-08):**
- 预拉／取消／本地恢复聚焦测试：22 passed。
- 计划任务全模块排除两项已知 SSH 失败：60 passed, 2 deselected；完整运行仍只有这两项既有失败。
- 前端 TypeScript 与生产构建通过，编辑器未报告新错误。
- 三层独立审查完成；补强迟到成功 JSON 的取消终态保护、回调 30 秒上限和取消收尾期间的进程内锁。
- 开发容器已部署；旧系统调度行删除，统一 cron 内直接检查生效；空闲调度无 stdout、无新增运行／日志文件；五条真实预拉任务保留，磁盘现存历史已恢复到索引。
- 浏览器未登录，测试响应拦截未正常完成；已清理拦截，不声称完成视觉验收。历史提示已通过构建验证。
- 未执行真实镜像拉取，未提交或推送 Git。

**Follow-up Results (2026-10-08):**
- 公共保留／删除参数化测试：8 passed，覆盖普通任务与预拉的索引数量、时间期限、runner 文件清理及删除。
- 计划任务全模块排除两项已知 SSH 失败：66 passed, 2 deselected；前端生产构建通过。
- runner 升至 v7，预拉不再跳过公共文件清理；取消与接续逻辑保持不变。
- 开发容器已部署；五个预拉 runner 均确认 v7 与公共清理规则。已登录页面打开预拉执行记录，确认提示移除并截图验证；过期记录按公共三天索引规则清理。

## Suggested Review Order

**调度与取消边界**
- 统一认领、取消存活阻塞和历史同步。
  [scheduled_tasks.py:441](../../apphub/src/services/scheduled_tasks.py#L441)
- 取消确认退出后接续，收尾期间锁定操作。
  [scheduled_tasks.py:493](../../apphub/src/services/scheduled_tasks.py#L493)
- runner 释放执行锁，限时触发下一项。
  [scheduled_tasks.py:1224](../../apphub/src/services/scheduled_tasks.py#L1224)

**恢复与保留**
- API 启动恢复配置后尝试派发。
  [main.py:127](../../apphub/src/main.py#L127)
- 预拉复用公共索引保留规则。
  [scheduled_tasks.py:1187](../../apphub/src/services/scheduled_tasks.py#L1187)
- 迁移旧内部任务，不触碰真实预拉。
  [scheduled_tasks.py:1343](../../apphub/src/services/scheduled_tasks.py#L1343)

**辅助验证**
- CLI 安静执行，同时保留异常诊断。
  [apphub_cli.py:158](../../apphub/src/cli/apphub_cli.py#L158)
- 临时跨进程队列验证无需 cron 接续。
  [test_scheduled_tasks.py:414](../../apphub/tests/test_scheduled_tasks.py#L414)