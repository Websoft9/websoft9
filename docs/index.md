# Websoft9 Project Knowledge Index

- 生成时间: 2026-04-21
- 文档模式: bmad-document-project initial_scan
- 扫描深度: deep
- 项目类型: 多部分 brownfield 仓库（backend + web plugins + infra/install）

## 文档清单

1. [当前架构基线](current-architecture-baseline.md)
   说明当前 Websoft9 的真实运行拓扑、模块边界、宿主机依赖与重构影响面。

2. [插件与交互基线](ui-plugin-baseline.md)
   说明 pluings 目录下 Cockpit 插件的职责、技术栈和强耦合点。

3. [AppHub API 基线](api-contracts-apphub.md)
   汇总当前后端开放的主要 API 能力与现有限制。

4. [项目扫描状态](project-scan-report.json)
   记录本次扫描的模式、步骤、已生成输出和后续恢复上下文。

## 本轮关键结论

- 当前项目的业务中枢是 AppHub，而不是 Cockpit。
- Cockpit 当前承担了三类职责: 宿主机认证与权限放大、插件运行容器、内置系统工具入口。
- pluings 目录是现有前端功能的真实来源，且大量直接依赖 cockpit.js。
- 当前文件管理和终端能力并不属于 Websoft9 自己的产品能力，而是借用了 Cockpit 的宿主机能力。
- 去 Cockpit 化以后，需要把“前端重建”和“能力重建”分开设计，不能只做 UI 迁移。

## 建议后续文档顺序

1. 基于当前基线重写新 PRD，显式删除 Cockpit 作为基础假设。
2. 产出目标架构，明确单容器内部进程模型和宿主机连接方案。
3. 为升级迁移单独设计兼容策略，覆盖配置、数据卷、证书、用户和入口 URL。