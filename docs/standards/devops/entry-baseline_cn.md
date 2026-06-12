# 发布治理文档包入口与制度基线

**Websoft9 项目 - DevOps 入口文档**

**创建时间**：2026-01-04  
**重构时间**：2026-06-05  
**版本**：3.0  
**状态**：Active

## 1. 文档角色

这份文档只做两件事：

1. 定义 DevOps 文档包的固定阅读入口
2. 固定最小制度基线，避免执行时标准漂移

完整路径、当前完成度、阶段顺序、验收口径与下一批计划，统一以 [roadmap_cn.md](./roadmap_cn.md) 为准。

## 2. DevOps 文档包结构

| 层级 | 文件 | 固定角色 | 什么时候看 |
|---|---|---|---|
| 目录入口 | [README.md](./README.md) | DevOps 文档包统一入口 | 第一次进入目录或需要快速定位时 |
| 主控 | [roadmap_cn.md](./roadmap_cn.md) | 单一事实来源，负责整体路径、阶段、完成度、验收和推进顺序 | 每次开始或结束一批工作时 |
| 说明 | [branching-and-artifacts_cn.md](./branching-and-artifacts_cn.md) | 解释为什么采用当前模型 | 需要理解设计 rationale 时 |
| 入口 | [entry-baseline_cn.md](./entry-baseline_cn.md) | 固定阅读顺序和制度基线 | 执行前快速对齐时 |
| 执行包 | [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) | 数据制品规范 | 处理 catalog/library/manifest 时 |
| 执行包 | [incident-hotfix-runbook_cn.md](./incident-hotfix-runbook_cn.md) | 值班与回滚操作 | 处理代码或数据 Hotfix 时 |
| 执行包 | [repo-protection-and-checks_cn.md](./repo-protection-and-checks_cn.md) | 仓库门禁执行 | 配置 main/dev 门禁时 |
| 执行包 | [github-manual-configuration_cn.md](./github-manual-configuration_cn.md) | GitHub 平台侧手工配置 | 配置 Rulesets、Secrets、Pages 时 |

不在本目录、但与发布治理协同的专题：

| 外部专题 | 文件 | 什么时候看 |
|---|---|---|
| 平台生命周期 | [../../platform-lifecycle/platform-lifecycle-governance_cn.md](../../platform-lifecycle/platform-lifecycle-governance_cn.md) | 处理安装、升级、卸载、迁移兼容时 |
| 应用商店平台专题 | [../../platform/app-store-foundation_cn.md](../../platform/app-store-foundation_cn.md) | 处理应用商店归属、主干运行事实、模块边界时 |

## 3. 固定阅读顺序

后续所有人统一按下面顺序进入 DevOps 文档：

1. 先看主控文档，确认当前执行阶段
2. 再看本文件，确认制度边界和阅读顺序
3. 然后只进入与当前阶段对应的执行包
4. 不允许跳过主控文档直接在多个细则文档之间反复切换

## 4. 最小制度基线

### 4.1 分支基线

1. 长期分支只有 `main` 和 `dev`
2. 日常开发使用 `feature/*` 和 `bugfix/*`
3. 紧急生产修复直接基于 `main` 处理，再回合并到 `dev`
4. 不再把 `release/*` 和 `hotfix/*` 作为长期治理基线

### 4.2 合并基线

1. 日常功能和普通修复合回 `dev`
2. `main` 不接收日常功能直接合并
3. 正式发布通过 `dev` 合并到 `main` 完成
4. 紧急修复完成后必须回合并到 `dev`

### 4.3 通道基线

1. `dev` 是开发制品通道
2. `release` 是正式制品通道
3. 当前阶段两者首先是“制品通道”，不是固定环境名
4. `rc` 不再作为当前默认常设通道

### 4.4 制品基线

1. 应用程序制品与应用商店数据制品分开治理
2. 应用程序制品必须可追踪，正式版必须可回滚
3. 数据制品必须具备版本、校验、历史和回滚能力
4. 兼容窗口内不得提前删除旧路径和旧数据

### 4.5 Hotfix 基线

1. 代码紧急问题优先直接基于 `main` 修复
2. 修复发布后必须立即回合并到 `dev`
2. 数据问题优先走数据 Hotfix
3. 数据错误不应强迫发布完整应用版本
4. 任何 Hotfix 都必须留痕、可验证、可回滚

### 4.6 门禁基线

1. 必须逐步落实 Rulesets / branch protection
2. 必须落实 required checks
3. 必须保留 PR 质量检查与版本一致性检查
4. 数据制品 smoke gate 不能退回到无校验状态

## 5. 执行逻辑

从现在开始，不再按零散点推进，而是按“批次交付”推进：

1. 每一轮只做一个阶段内的一整批内容
2. 每一轮必须同时交付文档、逻辑和验证结果
3. 每一轮结束都要回写主控文档中的完成度和未完成项

## 6. 当前默认顺序

默认顺序以主控文档为准，当前建议是：

1. 先按 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 完成应用商店数据治理第一阶段实现
2. 再进入 [incident-hotfix-runbook_cn.md](./incident-hotfix-runbook_cn.md) 处理数据 Hotfix 与回滚入口
3. 再补 `rc / release` 数据治理
4. 最后执行 [repo-protection-and-checks_cn.md](./repo-protection-and-checks_cn.md) 与 [github-manual-configuration_cn.md](./github-manual-configuration_cn.md) 完成平台侧配置和远端演练收尾

如果你现在直接开始实施，不要从平台侧手工配置开工，先从 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 的 Step 1 到 Step 8 顺序执行。

## 7. 文档维护规则

1. 新增 DevOps 文档前，必须先判断能否归入现有文件之一
2. 只有在现有角色无法承载时，才允许新增文件
3. 新增文件后，必须同步更新 [README.md](./README.md) 和 [../README.md](../README.md)
4. 如果某份文档只剩导航作用，应收缩，不再继续承载新细则
