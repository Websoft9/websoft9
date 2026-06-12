# 应用商店平台基础规范

创建时间：2026-06-08
状态：可实施
适用对象：平台负责人、产品维护者、客户端开发者、架构与运维

## 1. 文档定位

这份文档负责说明 Websoft9 应用商店作为平台能力本身的定义、主干事实和边界。

它回答的是下面这些问题：

1. 应用商店在平台里到底属于什么能力
2. `main` 分支上的应用商店当前怎么生产、怎么被运行时消费
3. 应用商店与 Contentful、docker-library、AppHub 的关系是什么
4. 哪些部分属于平台能力，哪些部分属于发布治理，哪些部分属于平台生命周期

如果需要处理应用商店数据的发布、版本、manifest、回滚与兼容窗口，统一看 [../standards/devops/app-store-release-governance_cn.md](../standards/devops/app-store-release-governance_cn.md)。

如果需要处理平台安装、升级、卸载和迁移兼容，统一看 [../platform-lifecycle/platform-lifecycle-governance_cn.md](../platform-lifecycle/platform-lifecycle-governance_cn.md)。

## 2. 平台归属

应用商店本身属于平台能力，而不是 DevOps 能力。

原因如下：

1. 它直接决定平台向用户展示什么应用、暴露什么元数据、如何提供安装入口
2. 它在运行时由 AppHub API 与平台静态目录共同消费，不是纯构建产物
3. 它与 Contentful、docker-library、图片资源、安装变量之间存在长期数据关系
4. DevOps 只负责它的发布治理，不负责定义它作为平台模块的业务归属

## 3. `main` 分支平台基线

以下事实只以 `main` 分支为准。

### 3.1 数据来源

1. 展示数据当前由 `.github/workflows/media.yml` 与 `.github/workflows/media_dev.yml` 从 Contentful 拉取
2. 安装元数据当前由独立的 `docker-library` 项目提供
3. 图片资源当前仍和 `media` 包一起交付

### 3.2 运行时消费

1. AppHub 当前直接读取 `/websoft9/media/json/catalog_{locale}.json`
2. AppHub 当前直接读取 `/websoft9/media/json/product_{locale}.json`
3. AppHub 同时结合 `/websoft9/library` 下的安装模板与变量数据生成可安装视图
4. `/apps/catalog/{locale}` 与 `/apps/available/{locale}` 仍是平台对外接口的一部分

### 3.3 平台关系

1. Contentful 负责展示侧主数据
2. docker-library 负责安装与 edition 真相
3. AppHub 负责运行时组装、读取与 API 暴露
4. 应用商店前端与平台前端消费的是同一平台能力输出，而不是独立产品

## 4. 模块边界

### 4.1 属于平台专题的内容

1. 应用商店属于平台哪个模块
2. 主干当前有哪些数据源和消费路径
3. 平台 API 和静态目录如何消费应用商店数据
4. 平台内其他模块如何依赖应用商店能力

### 4.2 属于 DevOps 的内容

1. 应用商店数据制品如何分通道发布
2. manifest、checksum、历史版本和回滚规则
3. R2 路径、命名规范、保留策略和 hotfix 流程
4. RC、正式版、兼容窗口与不破坏验证

### 4.3 属于平台生命周期的内容

1. 平台如何安装
2. 平台如何升级与迁移旧数据
3. 平台如何卸载以及如何保留数据

## 5. 当前控制点

1. 不能把应用商店作为平台能力的定义继续混写进 DevOps 文档
2. 不能把应用商店发布治理误写成平台业务定义
3. 不能把安装、升级、迁移问题再混回应用商店专题

## 6. 实施责任矩阵

如果现在开始实施，责任先按下面划分，不再临时讨论：

| 主题 | 负责人角色 | 主要关注点 |
|---|---|---|
| 应用商店平台定义 | 平台负责人 | 模块边界、运行时关系、API 与静态消费面 |
| 展示数据生产 | 前端/平台协同 | Contentful 输出、media 构建、静态资源组织 |
| 安装元数据真相 | docker-library 维护者 | variables、env、edition、安装模板 |
| 运行时消费 | AppHub 维护者 | catalog/product 读取、library 结合、兼容 API |
| 数据发布治理 | DevOps/发布负责人 | R2、版本、manifest、checksum、回滚 |
| 升级迁移与卸载 | 平台运维/安装脚本维护者 | 安装、升级、数据迁移、卸载 |

## 7. 第一批实施文件落点

第一批实施时，先盯下面这些文件，不要扩散：

| 目的 | 文件 |
|---|---|
| 应用商店数据发布 workflow | `docker-library` 仓库中的 `appstore-publish.yml` |
| 运行时 catalog 读取 | `apphub/src/services/app_manager.py` |
| 兼容 API 暴露 | `apphub/src/api/v1/routers/app.py` |
| 运行时升级入口 | `apphub/src/cli/apphub_cli.py` |
| 平台发布时附带安装脚本 | `.github/workflows/release.yml` |

说明：

1. 这份文档负责告诉实施人员“先改哪几层”
2. 制品路径、版本、manifest 细节不在这里展开，统一转到 DevOps 文档
3. 升级、迁移、卸载的动作步骤不在这里展开，统一转到平台生命周期文档

## 8. 平台专题实施顺序

平台专题这条线的实施顺序固定如下：

1. 先冻结应用商店的平台边界，不再把平台定义混进发布治理
2. 核对 `app_manager.py` 与兼容 API 是否仍以 `/websoft9/media/json/*.json` 和 `/websoft9/library` 为主消费面
3. 核对 workflow 输出与运行时消费是否一一对应
4. 明确 Contentful、docker-library、AppHub 三方责任，不再在实现中相互覆盖真相来源
5. 输出一次平台侧验证记录，确认“应用商店作为平台能力”这条线的边界已经稳定

## 9. 平台专题完成标准

只有同时满足下面条件，平台专题才算进入可实施状态：

1. 实施人员知道应用商店属于平台能力，不再把它整体归到 DevOps
2. 实施人员知道展示数据、安装元数据、运行时消费分别落在哪些文件和系统里
3. 当前实施分支中的 `docker-library/appstore-publish.yml`、`app_manager.py`、兼容 API 的关系已经讲清楚
4. 后续改制品规则时，不会误改平台模块定义

## 10. 当前结论

应用商店应该留在平台目录下作为平台专题维护；DevOps 目录只保留它的数据发布治理文档。