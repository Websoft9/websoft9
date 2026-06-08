# 发布治理路线图

创建时间：2026-06-05
最后更新：2026-06-08
状态：执行中
负责人：Platform/DevOps

## 1. 文档定位

这份文档是本轮 Websoft9 发布治理重构的总控文档。

它只负责三类事情：

1. 说明这轮重构的目标边界
2. 说明当前基于 `main` 分支的真实状态
3. 说明后续按什么顺序推进

它不负责展开每一类执行细节。执行细节统一下沉到对应规范：

1. 分支、通道与制品解释： [branching-and-artifacts_cn.md](./branching-and-artifacts_cn.md)
2. 应用商店数据治理： [app-store-release-governance_cn.md](./app-store-release-governance_cn.md)
3. Hotfix 与数据 Hotfix： [incident-hotfix-runbook_cn.md](./incident-hotfix-runbook_cn.md)
4. 仓库门禁与手工配置： [repo-protection-and-checks_cn.md](./repo-protection-and-checks_cn.md)、 [github-manual-configuration_cn.md](./github-manual-configuration_cn.md)

不属于本目录、但与发布治理协同的专题：

1. 平台安装、升级、卸载与迁移兼容： [../../platform-lifecycle/platform-lifecycle-governance_cn.md](../../platform-lifecycle/platform-lifecycle-governance_cn.md)
2. 应用商店作为平台能力本身： [../../platform/app-store-foundation_cn.md](../../platform/app-store-foundation_cn.md)

## 2. 单一事实来源规则

从本版开始，文档分工固定如下：

1. 本文档只维护整体目标、整体状态、推进顺序
2. `branching-and-artifacts_cn.md` 只解释分支、通道、制品模型
3. `app-store-release-governance_cn.md` 作为应用商店数据治理的主执行文档
4. 其他文档只作为专项执行包，不再承担总控职责

控制规则：

1. 不再新增同级“既像总控又像执行细则”的混合文档
2. 阶段状态统一在本文档更新
3. 具体实施方法统一在对应专项文档更新

## 3. `main` 分支基线判断

后续所有判断和方案，先以 `main` 分支为基线。

### 3.1 当前主干已确认事实

1. 主干的应用商店展示数据仍由 `media.yml` / `media_dev.yml` 生成
2. 主干的安装元数据仍由独立 `docker-library` 项目提供
3. 主干运行时仍直接依赖 `/websoft9/media/json/*.json` 与 `/websoft9/library/...`
4. 主干平台仍通过 `cron -> update.sh -> update_zip.sh` 每天自动全量更新 `media-latest.zip` 和 `library-latest.zip`
5. 主干当前还没有统一 `datasetVersion`、统一 manifest、历史 manifest、数据 hotfix 脚本这些能力

### 3.2 当前主干的核心约束

1. 旧的每日自动全量更新链路不能断
2. 已运行旧版本应用商店不能受影响
3. 已运行平台不能受影响
4. 新制品模型只能并行增加，不能先替代旧链路
5. 旧 `websoft9` 根继续作为 legacy 契约保留，新版应用商店数据统一收敛到 `artifact/websoft9/v2/<channel>/appstore`

## 4. 本轮目标

这轮 DevOps 重构的真实目标不是“把所有流程都改成新样子”，而是：

1. 用更清晰的分支和通道模型统一认知
2. 把应用程序制品和应用商店数据制品分开治理
3. 在不破坏主干旧链路的前提下，为应用商店数据补齐制品化、版本化、校验、回滚和兼容机制
4. 让后续实施能按文档直接落地，而不是继续靠临时判断推进
5. 为新版应用商店数据制品建立独立数据域 `artifact/websoft9/v2/<channel>/appstore/...`，避免继续绑定旧 `artifact/<channel>/websoft9/...` 语义

## 5. 本轮范围与非范围

### 5.1 纳入范围

1. 分支模型与发布通道说明
2. 仓库治理与 PR 门禁
3. 应用程序制品职责边界
4. 应用商店数据发布治理方案
5. 数据 Hotfix 与回滚执行规范
6. 旧链路兼容与不破坏验证

### 5.2 暂不纳入范围

1. 完整多环境平台建设
2. Kubernetes 全量迁移
3. 完整供应链安全体系
4. 大规模运行时架构重构

## 6. 当前阶段状态

### Phase 0：文档基线

目标：建立以 `main` 为基线的文档体系。

状态：已完成

结果：

1. 总控文档角色已明确
2. 解释型文档角色已明确
3. 应用商店数据主执行文档已明确

### Phase 1：仓库治理与 PR 门禁

目标：把仓库内可自动落地的规则收进 CI。

状态：部分完成

说明：

1. 文档和部分仓库规则已有基础
2. 是否完全落地，仍应以 `main` 分支当前有效配置和后台配置为准

### Phase 2：应用程序制品治理

目标：明确应用程序制品职责边界和最小发布规则。

状态：部分完成

说明：

1. 应用程序制品与数据制品的边界已经能说明清楚
2. 主干上的全链路程序制品治理尚未完全收口

### Phase 3：应用商店数据升级与兼容

目标：在不破坏主干旧链路的前提下，补齐应用商店数据制品能力。

状态：文档已可实施，主干实现未完成

说明：

1. 这部分现在统一由 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 承接
2. 文档中已经包含主干旧流程基线、不可破坏约束、第一阶段产物、实施顺序、仓库落地映射、第一批实施文件清单和验收标准
3. `main` 分支当前尚未具备这些新能力
4. 当前执行策略已经收敛为双轨根目录：legacy 继续发布到 `artifact/<channel>/websoft9/...`，新版并行发布到 `artifact/websoft9/v2/<channel>/appstore/...`

### Phase 4：数据 Hotfix 与回滚执行

目标：把数据 Hotfix 从原则变成可执行流程。

状态：文档基线已形成，主干实现未完成

说明：

1. 主干尚未具备完整 Hotfix 工具链
2. 当前重点应先完成应用商店数据主链路与兼容治理，再进入 Hotfix 实施

### Phase 5：平台侧配置与远端演练

目标：完成后台门禁配置与一次真实不破坏验证。

状态：未完成

说明：

1. GitHub 平台配置仍需后台实际落地
2. 远端真实演练尚未执行

## 7. 当前完成度总览

| 模块 | 按 `main` 基线判断 | 当前结论 |
|---|---|---|
| 文档分工 | 已完成 | 总控、解释、执行三层边界已清楚 |
| 仓库治理 | 部分完成 | 需要继续核对主干有效规则和后台配置 |
| 应用程序制品治理 | 部分完成 | 边界清楚，但全链路未收口 |
| 应用商店数据治理 | 未完成 | 文档已可实施，legacy + `artifact/websoft9/v2/<channel>/appstore` 双轨发布已开始落地，但远端实跑未完成 |
| 数据 Hotfix | 未完成 | 文档有原则，主干没有完整工具链 |
| rc / release 数据治理 | 未完成 | 路径策略已收敛到 `artifact/websoft9/v2/<channel>/appstore`，仍需远端真实发布验证 |
| 平台手工配置与远端演练 | 未完成 | 还没有实际落地 |

## 8. 后续推进顺序

后续统一按下面顺序推进，不再零散推进：

1. 先按 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 完成 Phase 3 的第一阶段实现
2. 再进入数据 Hotfix 与回滚入口实现
3. 再补 rc / release 通道的数据治理
4. 最后做平台手工配置与远端演练收尾

如果现在立刻进入实施，不要再继续扩写总控或解释型文档，直接按下面入口执行：

1. 第一步看 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 的“17.1 实施顺序”
2. 第二步看 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 的“17.4 第一批实施文件清单”
3. 当前这一批做完后，再切到 [incident-hotfix-runbook_cn.md](./incident-hotfix-runbook_cn.md)
4. 最后一批再执行 [repo-protection-and-checks_cn.md](./repo-protection-and-checks_cn.md) 和 [github-manual-configuration_cn.md](./github-manual-configuration_cn.md)

与本路线图并行但不归入本目录的专题：

1. 平台生命周期与升级迁移：见 [../../platform-lifecycle/platform-lifecycle-governance_cn.md](../../platform-lifecycle/platform-lifecycle-governance_cn.md)
2. 应用商店平台归属与主干事实：见 [../../platform/app-store-foundation_cn.md](../../platform/app-store-foundation_cn.md)

## 9. 当前最重要的控制点

1. 不允许把当前改造分支中的原型能力误写成 `main` 现状
2. 不允许先替换旧的 `media-latest.zip` / `library-latest.zip` 链路
3. 不允许在没有完成不破坏验证前，宣称应用商店升级已经落地
4. 不允许再新增更多总控类文档，继续稀释单一事实来源

## 10. 批次交付规则

从本版开始，后续交付统一按批次推进，每一批必须同时回写：

1. 本批目标
2. 影响的主干文件面
3. 实际代码或 workflow 改动
4. 验证结果
5. 是否影响旧链路

## 11. 最终结论

当前 DevOps 相关文档确实需要继续优化，而且优化方式必须和应用商店执行文档保持一致：

1. 先看 `main` 分支真实基线
2. 再定义目标模型
3. 再定义不可破坏约束
4. 最后给出实施顺序

这轮优化之后：

1. 本文档负责总控
2. `branching-and-artifacts_cn.md` 负责解释
3. `app-store-release-governance_cn.md` 负责应用商店数据治理执行

平台安装、升级、卸载与迁移兼容，不再混入本目录，统一转入 [../../platform-lifecycle/platform-lifecycle-governance_cn.md](../../platform-lifecycle/platform-lifecycle-governance_cn.md)。

后续推进时，执行人员不需要再在多个同级文档之间来回猜测。