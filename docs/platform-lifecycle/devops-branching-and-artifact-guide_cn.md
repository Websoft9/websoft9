# 新版本分支与制品引导

创建时间：2026-06-12
状态：说明入口
适用对象：发布负责人、平台维护者、安装脚本维护者

这份文件只做生命周期目录下的阅读引导，不单独维护一套新的分支与制品规范。

如果你现在关注的是新版本发布机制、`dev/main` 两分支模型、制品通道和发布门禁，统一看：

1. [../standards/devops/branching-and-artifacts_cn.md](../standards/devops/branching-and-artifacts_cn.md)

当前新版本基线已经收敛为：

1. 长期分支只有 `dev` 和 `main`
2. `dev` 用于日常集成与候选验证
3. `main` 用于正式发布
4. 程序制品推荐只保留 `dev` 和 `release` 两层通道
5. 旧平台兼容约束仍以旧链路继续可用为前提

如果你关注的是平台安装、升级、卸载和跨代迁移本身，继续看：

1. [platform-lifecycle-governance_cn.md](./platform-lifecycle-governance_cn.md)