# DevOps 发布治理文档包

创建时间：2026-06-08
状态：可实施入口
适用对象：开发、发布负责人、值班同学、DevOps

## 1. 目录定位

本目录用于承载本轮 Websoft9 发布治理与仓库交付相关中文文档，不再把这批文件散放在 `docs/standards` 同级目录。

从现在开始，这一批文档统一在本目录内维护、相互引用和验证，并以中文文档作为单一事实来源。

当前状态：应用商店数据发布治理主文档已经达到可实施阶段；仓库门禁、GitHub 手工配置与 Hotfix 文档也已经具备执行入口，可以按批次直接推进。

当前制品目录策略也已明确：旧兼容链路继续保留在 `artifact/<channel>/websoft9/...`，新版应用商店数据制品统一并行发布到 `artifact/websoft9/v2/<channel>/appstore/...`。

## 2. 阅读入口

建议固定按下面顺序阅读：

1. [roadmap_cn.md](./roadmap_cn.md)
2. [entry-baseline_cn.md](./entry-baseline_cn.md)
3. 当前阶段对应的执行文档

如果你现在就是要开始实施，直接看下面三处：

1. [roadmap_cn.md](./roadmap_cn.md) 的“后续推进顺序”，先确认当前先做哪一批
2. [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 的“17.1 实施顺序”，这里是当前第一优先级的主实施步骤
3. [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 的“17.4 第一批实施文件清单”，这里是第一批真正要改的文件面

## 3. 文档分工

| 文件 | 角色 | 说明 |
|---|---|---|
| [roadmap_cn.md](./roadmap_cn.md) | 总控 | 维护整体目标、主干基线、阶段状态和推进顺序 |
| [entry-baseline_cn.md](./entry-baseline_cn.md) | 入口 | 固定阅读顺序和最小制度基线 |
| [branching-and-artifacts_cn.md](./branching-and-artifacts_cn.md) | 说明 | 解释分支、通道、制品和兼容思路 |
| [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) | 执行 | 处理应用商店数据制品治理、兼容、R2 布局和发布规则 |
| [incident-hotfix-runbook_cn.md](./incident-hotfix-runbook_cn.md) | 执行 | 处理代码 Hotfix、数据 Hotfix、回滚和值班 |
| [repo-protection-and-checks_cn.md](./repo-protection-and-checks_cn.md) | 执行 | 处理仓库门禁与 required checks |
| [github-manual-configuration_cn.md](./github-manual-configuration_cn.md) | 执行 | 处理 GitHub 平台侧手工配置 |

## 4. 使用规则

1. 这批 DevOps 文档只在本目录新增和维护
2. 需要更新阶段状态时，只改总控文档
3. 需要更新执行细节时，只改对应执行文档
4. 新增文档前，先判断能否归入当前这组中文 DevOps 文档之一
5. 顶层 [../README.md](../README.md) 只保留索引，不再承载这批文档的细节
6. 平台安装、升级、卸载与迁移兼容不再放在本目录，统一转到 [../../platform-lifecycle/README.md](../../platform-lifecycle/README.md)

## 5. 已确认旧模式

基于 `main` 分支重新检索后，本轮文档必须继续锚定以下旧模式：

1. 主干 workflow 仍以 `media.yml`、`media_dev.yml` 为展示数据主链路
2. 主干运行时仍直接消费 `/websoft9/media/json/*.json` 与 `/websoft9/library/...`
3. 主干平台仍通过 `cron -> update.sh -> update_zip.sh` 每天自动拉取 `media-latest.zip` 和 `library-latest.zip`
4. 当前生产基线仍然是 `media + library` 双包全量更新模式

## 6. 本轮明确需求

本轮收口后的需求边界统一如下：

1. 所有 DevOps 重构文档统一以 `main` 分支旧模式为基线
2. 旧的 `media-latest.zip` / `library-latest.zip` 自动更新链路不能被破坏
3. 已运行旧版本应用商店和平台不能因为新制品模型受影响
4. 新需求的核心是补齐应用商店数据制品治理、兼容、回滚和门禁，而不是改写旧运行方式
5. 平台本身的安装、升级、卸载与兼容迁移单独归入平台生命周期文档包
6. 应用商店作为平台能力本身单独归入平台专题文档包
7. 中文文档作为唯一执行依据，避免中英文双轨继续漂移
8. 新版应用商店数据制品统一规划到 `artifact/websoft9/v2/<channel>/appstore` 数据域，旧 `websoft9` 根目录只承担 legacy 兼容契约

## 7. 当前结论

这次重构的目的不是新增更多文档，而是把已经存在的 DevOps 说明、主控和执行包收敛成一个可读、可维护、可验证的目录。