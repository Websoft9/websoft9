# Docker Library 发布治理规范

创建时间：2026-06-08
状态：可实施草案
适用对象：docker-library 仓库维护者、发布负责人、DevOps、应用模板维护者

## 1. 文档目的

本文档是独立面向 `docker-library` 仓库的发布治理规范。

它不讨论 `websoft9` 仓库中的应用商店组装细节，而是只定义 `docker-library` 作为安装真相源时，必须如何产出、命名、校验、发布和回滚 `library` 制品。

如果要在 `docker-library` 项目中实施流程改造，应以本文作为直接执行依据。

## 2. 适用范围

本文档只约束以下对象：

1. `docker-library` 仓库中的 legacy workflow，例如 `release.yml`、`release-dev.yml`
2. `docker-library` 仓库中的新统一发布 workflow，例如 `appstore-library-publish.yml`
3. `docker-library` 仓库中负责生成 library 制品的脚本
4. 发布到 R2 的 `plugin/library` 兼容路径
5. 发布到新制品模型中的 app 级目录制品与数据制品

本文档不负责以下内容：

1. Contentful 展示数据拉取
2. `websoft9` 仓库中的 catalog 组装
3. AppHub 运行时激活逻辑
4. Console 前端刷新逻辑

## 3. 角色边界

`docker-library` 的职责必须固定为安装真相源。

它至少负责：

1. 维护 `apps/<app>/variables.json`
2. 维护 `apps/<app>/.env`
3. 维护应用模板、安装脚本和其他安装相关文件
4. 产出 `library` 全量包
5. 产出 app 级目录制品与数据制品
6. 产出可校验、可版本化、可回滚的发布元数据

`docker-library` 不负责：

1. 组装 catalog 与 library 为统一 dataset
2. 绑定 Contentful 数据版本
3. 对外暴露应用商店 API
4. 替代平台运行时做快照激活

## 4. 当前兼容基线

在迁移期内，以下旧链路必须继续成立：

1. 开发通道继续提供 `library-dev.zip`
2. 正式通道继续提供 `library-latest.zip`
3. 旧平台仍可通过 `plugin/library` 路径获取上述全量包
4. 旧平台每天自动更新 `library-latest.zip` 的能力不能被破坏

结论：第一阶段允许新增新制品，但不能先删除旧全量包发布。

## 4.1 Workflow 治理原则

`docker-library` 的发布流程应采用双轨治理，而不是继续把新需求叠加到旧 workflow 上。

规则如下：

1. 旧的 `release.yml`、`release-dev.yml` 归入 legacy 维护面
2. legacy workflow 只继续服务旧版本平台和旧兼容包发布
3. 新的 library 制品模型必须使用独立的新 workflow 实施
4. 新体系优先采用一个统一主 workflow，通过 `channel=dev|rc|release` 参数分流
5. 只有当审批、权限或触发机制完全不同，才允许在统一主 workflow 外面再套很薄的 wrapper workflow

结论：新体系不推荐再新增三个独立 workflow 分别对应 dev、rc、release，而是推荐一个主 workflow 管三条通道。

## 5. 输入真相面

发布前的最小输入事实如下：

1. `apps/<app>/variables.json`
2. `apps/<app>/.env`
3. `apps/<app>/docker-compose.yml` 或等效模板文件
4. `apps/<app>/scripts` 或等效安装辅助文件
5. 其他运行安装所需的静态模板资源

要求：

1. 这些输入只能由 `docker-library` 维护
2. 发布时不允许从 `websoft9` 仓库反向推导安装真相
3. edition、变量、默认值、模板内容必须以 `docker-library` 为准

## 6. 强制输出物

每次发布至少必须产出以下两类制品。

### 6.1 兼容层全量包

必须继续发布：

1. 开发通道：`library-dev.zip`
2. 正式通道：`library-latest.zip` 或 `library-<version>.zip`
3. 对应 `.sha256`

### 6.2 新制品层

每次发布还必须产出以下内容：

1. app 级目录全量包：`apps/<app>/bundle-<datasetVersion>.zip`
2. app 级变量快照：`apps/<app>/variables-<datasetVersion>.json`
3. app 级环境快照：`apps/<app>/env-<datasetVersion>.env`
4. app 级差异包：`apps/<app>/delta-<fromVersion>-to-<toVersion>.zip`
5. 全局应用索引：`apps-index-<datasetVersion>.json`
6. library 级增量索引：`library-delta-<fromVersion>-to-<toVersion>.json`
7. app 级增量索引：`apps-delta-<fromVersion>-to-<toVersion>.json`
8. library manifest
9. 所有可下载文件的 checksum

说明：第一阶段如果暂时无法生成真正的 app 级 zip 差异包，允许先产出 app 级变更清单和全量 app bundle，但目录结构和命名位必须预留好。

## 7. R2 发布路径规范

迁移期同时维护两层路径。

### 7.1 兼容路径

必须继续写入：

1. `artifact/<channel>/websoft9/plugin/library/library-dev.zip`
2. `artifact/<channel>/websoft9/plugin/library/library-latest.zip`
3. `artifact/<channel>/websoft9/plugin/library/manifest.json`
4. `artifact/<channel>/websoft9/plugin/library/apps-index.json`
5. `artifact/<channel>/websoft9/plugin/library/app-store-install-metadata.json`
6. `artifact/<channel>/websoft9/plugin/library/library-delta-<from>-to-<to>.json`
7. `artifact/<channel>/websoft9/plugin/library/apps-delta-<from>-to-<to>.json`
8. 上述文件对应 checksum

### 7.2 新制品路径

建议新增：

1. `artifact/websoft9/v2/<channel>/appstore/library/manifest.json`
2. `artifact/websoft9/v2/<channel>/appstore/library/apps-index-<datasetVersion>.json`
3. `artifact/websoft9/v2/<channel>/appstore/library/apps/<app>/bundle-<datasetVersion>.zip`
4. `artifact/websoft9/v2/<channel>/appstore/library/apps/<app>/variables-<datasetVersion>.json`
5. `artifact/websoft9/v2/<channel>/appstore/library/apps/<app>/env-<datasetVersion>.env`
6. `artifact/websoft9/v2/<channel>/appstore/library/apps/<app>/delta-<from>-to-<to>.zip`
7. 对应 checksum

要求：

1. 兼容路径和新路径可以并行发布
2. 第一阶段不能只发布新路径而丢掉兼容路径
3. 所有路径必须能通过 manifest 追溯到具体 datasetVersion

## 8. 命名规范

推荐规则如下：

1. 开发通道主包：`library-dev.zip`
2. 开发通道版本化主包：`library-dev-<date>.<seq>.zip`
3. RC 主包：`library-<version>-rc.<n>.zip`
4. 正式主包：`library-latest.zip` 或 `library-<version>.zip`
5. library 增量索引：`library-delta-<fromVersion>-to-<toVersion>.json`
6. app 增量索引：`apps-delta-<fromVersion>-to-<toVersion>.json`
7. app bundle：`bundle-<datasetVersion>.zip`
8. app variables：`variables-<datasetVersion>.json`
9. app env：`env-<datasetVersion>.env`
10. app delta：`delta-<fromVersion>-to-<toVersion>.zip`

要求：

1. 第一阶段允许保留 `library-dev.zip` 和 `library-latest.zip`
2. 新命名要表达领域职责，而不是历史脚本名
3. 如果主包仍使用固定名，manifest 中必须同时提供版本化信息

## 9. Manifest 契约

每次发布都必须产出稳定的 `manifest.json`，至少包含以下字段：

1. `schemaVersion`
2. `datasetVersion`
3. `channel`
4. `libraryPackage`
5. `appsIndex`
6. `deltaFiles.library`
7. `deltaFiles.apps`
8. `checksum.libraryPackage`
9. `checksum.appsIndex`
10. `checksum.libraryDelta`
11. `checksum.appsDelta`
12. `generatedAt`
13. `compatibility.legacyPluginPaths`
14. `compatibility.appLevelArtifacts`

建议样例如下：

```json
{
  "schemaVersion": "1",
  "datasetVersion": "2026.06.08.120000",
  "channel": "release",
  "libraryPackage": "library-latest.zip",
  "appsIndex": "apps-index-2026.06.08.120000.json",
  "deltaFiles": {
    "library": "library-delta-2026.06.07.120000-to-2026.06.08.120000.json",
    "apps": "apps-delta-2026.06.07.120000-to-2026.06.08.120000.json"
  },
  "checksum": {
    "libraryPackage": "library-latest.zip.sha256",
    "appsIndex": "apps-index-2026.06.08.120000.json.sha256",
    "libraryDelta": "library-delta-2026.06.07.120000-to-2026.06.08.120000.json.sha256",
    "appsDelta": "apps-delta-2026.06.07.120000-to-2026.06.08.120000.json.sha256"
  },
  "compatibility": {
    "legacyPluginPaths": true,
    "appLevelArtifacts": true,
    "schemaVersion": "1"
  },
  "generatedAt": "2026-06-08T12:00:00Z"
}
```

## 10. Workflow 改造要求

`docker-library` 的发布流程应拆成 legacy 面和 new 面。

### 10.1 Legacy workflow

legacy workflow 指当前已存在的 `release.yml`、`release-dev.yml`。

职责：

1. 继续服务旧版本平台
2. 继续提供旧兼容包
3. 在迁移期内为旧运行时保底

要求：

1. 不再把新模型主逻辑持续叠加到 legacy workflow 中
2. 如果必须修复旧链路，只允许做兼容性维护和必要修复
3. legacy workflow 可以继续存在，但不再作为新体系主入口

### 10.2 新统一主 workflow

新体系建议新增一个统一主 workflow，例如 `appstore-library-publish.yml`。

职责：

1. 统一处理 `dev`、`rc`、`release` 三个通道
2. 统一生成 library 主包、app 级制品、delta、manifest、checksum
3. 统一写入兼容路径和新制品路径

必须完成：

1. 接收 `channel` 输入，允许值至少包括 `dev`、`rc`、`release`
2. 按 `channel` 选择主包命名和目标 R2 路径
3. 生成 `apps-index-<datasetVersion>.json`
4. 生成 `library-delta-<from>-to-<to>.json`
5. 生成 `apps-delta-<from>-to-<to>.json`
6. 生成 app 级 bundle、env、variables 制品
7. 生成 checksum
8. 写入该通道 manifest
9. 上传到 R2
10. 保证三个通道产物结构一致，禁止格式漂移

### 10.3 通道分流规则

统一主 workflow 内部必须只在少数必要点按 channel 分流。

推荐分流项：

1. 主包文件名
2. 目标 R2 通道路径
3. 触发条件与审批策略
4. 是否允许高频自动发布

不推荐分流项：

1. manifest 结构
2. delta 格式
3. checksum 规则
4. app 级制品目录布局

### 10.4 可选 wrapper workflow

如果 `dev`、`rc`、`release` 三个通道在审批、权限、触发入口上差异很大，可以额外保留很薄的 wrapper workflow。

要求：

1. wrapper workflow 只负责传参和触发
2. 真正的产物生成逻辑只能放在统一主 workflow 中
3. 不允许为三个通道维护三份独立的完整发布实现

### 10.5 `sync_contentful.yml`

职责：可选的反向同步辅助。

要求：

1. 它不能替代正式发布流程
2. 它只负责把需要同步的结构化字段回写到 Contentful
3. 它不能作为 `library` 包发布的唯一入口

## 11. 数据变更识别规范

发布流程必须能识别以下三类变更：

1. 新 app 增加
2. 已有 app 的 variables、env 或模板内容变化
3. app 删除或下线

最低要求：

1. `apps-delta` 要能标识 `addedApps`、`removedApps`、`changedApps`
2. `library-delta` 要能标识本次 library 视角的整体变化摘要
3. 不能只靠整个 zip 的二进制差异判断更新

## 12. 校验门禁

每次发布前至少必须执行以下校验：

1. library 根目录结构校验
2. 所有 app 的 `variables.json` JSON 结构校验
3. 所有 app 的 `.env` 文件存在性和格式校验
4. app bundle 能被解压
5. manifest 字段完整性校验
6. checksum 对应关系校验
7. R2 上传后的可访问性抽样校验

建议 CI 至少有以下失败门禁：

1. 任一 app 缺少 `variables.json`
2. 任一 app 缺少 `.env`
3. manifest 缺关键字段
4. checksum 与文件不一致
5. 产物命名不符合规范

## 13. 回滚规范

`docker-library` 发布必须支持回滚，不允许只有“覆盖最新包”一种行为。

最低要求：

1. 每次发布都保留历史 manifest
2. 每次发布都保留历史 `apps-index-<datasetVersion>.json`
3. app 级 bundle、env、variables 必须带版本号
4. 回滚时能根据 manifest 找回上一版完整可用集合

## 14. 与 websoft9 仓库的契约

`docker-library` 发布链路与 `websoft9` 的契约必须固定为：

1. `docker-library` 负责安装真相与 library 制品发布
2. `websoft9` 负责把 catalog 与 library 绑定为统一 dataset
3. `websoft9` 可以补充 install metadata、索引兼容层和运行时消费面
4. `websoft9` 不应成为 `variables.json`、`.env`、模板文件的权威维护方

## 15. 第一阶段最小改造清单

如果要在 `docker-library` 仓库先完成第一批可落地改造，最少做下面五件事：

1. 冻结 `release.yml` 和 `release-dev.yml` 的角色，只保留 legacy 维护职责
2. 新增一个统一主 workflow，用 `channel=dev|rc|release` 管理三条通道
3. 为每次发布补充 `manifest.json` 与历史 manifest
4. 为每次发布补充 `apps-index`、`library-delta`、`apps-delta`
5. 为每个 app 补充版本化的 bundle、env、variables 制品
6. 为全部可下载文件补充 checksum 和发布校验

## 16. 第二阶段增强项

完成第一阶段后，再考虑：

1. 真正的 app 级 zip 差异包
2. 更严格的 schema 校验器
3. 自动回滚 workflow
4. 多通道制品复制与升格策略
5. 发布后自动通知 `websoft9` 组装流程

## 17. 实施输出要求

每次对 `docker-library` 发布流程做批量改造，都应留下交付记录，至少包括：

1. 目标：本批要补齐哪些产物和门禁
2. 文件：改动了哪些 workflow、脚本、校验器
3. 产物：新增或变更了哪些 R2 路径和 manifest 字段
4. 验证：跑了哪些 CI、smoke、R2 抽样验证
5. 风险：是否影响 `library-dev.zip` / `library-latest.zip` 兼容链路

## 18. 结论

如果只保留一个全量 `library.zip`，那仍然属于旧模式。

满足本规范的 `docker-library` 发布链路，必须同时具备：

1. 旧全量包兼容
2. app 级制品可追踪
3. manifest 可校验
4. 版本可回滚
5. 与 `websoft9` 的职责边界清晰