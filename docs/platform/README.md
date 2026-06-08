# 平台专题文档包

创建时间：2026-06-08
状态：当前统一入口
适用对象：平台负责人、产品维护者、客户端开发者、架构与运维

## 1. 目录定位

本目录用于承载 Websoft9 平台本身的专题能力文档。

这里描述的是“平台有什么能力、主干当前怎么运行、能力边界在哪里”，而不是“这些能力如何发布、回滚和做仓库治理”。

当前状态：目录内主文档已达到可实施阶段，实施人员可以直接按责任矩阵、文件落点和验证口径推进。

## 2. 阅读入口

当前统一从下面文档进入：

1. [app-store-foundation_cn.md](./app-store-foundation_cn.md)

## 3. 当前边界

本目录负责：

1. 平台能力定义
2. 主干运行事实
3. 模块边界与依赖关系
4. 平台能力与其他专题的协同边界

本目录不负责：

1. 分支、通道与发布门禁
2. 数据制品发布治理
3. 安装、升级、卸载、迁移兼容执行

这些内容分别转到：

1. [../standards/devops/README.md](../standards/devops/README.md)
2. [../standards/devops/app-store-release-governance_cn.md](../standards/devops/app-store-release-governance_cn.md)
3. [../platform-lifecycle/README.md](../platform-lifecycle/README.md)