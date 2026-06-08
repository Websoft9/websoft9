# Hotfix 与数据 Hotfix 操作手册

创建时间：2026-06-05
最后更新：2026-06-08
状态：可执行基线
适用对象：开发、发布负责人、值班同学、DevOps
所属阶段：Phase 4 / Phase 7 Hotfix 与值班执行包

## 1. 文档定位

这份文档给出“出了问题以后怎么做”的标准步骤。

它已经达到可执行基线状态：代码 Hotfix 流程可以直接执行，数据 Hotfix 需要与 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md) 当前已落地的数据制品能力配合推进。

完整路径、当前完成度、阶段顺序与后续推进优先级，统一以 [roadmap_cn.md](./roadmap_cn.md) 为准。

它覆盖两类紧急处理：

1. 代码 Hotfix：程序本体出错
2. 数据 Hotfix：应用商店数据出错

本文件只负责“出问题以后怎么处理”。

如果需要理解这套模型为什么这样设计，先看 [branching-and-artifacts_cn.md](./branching-and-artifacts_cn.md)。

如果需要执行应用商店数据制品升级和兼容方案，先看 [app-store-release-governance_cn.md](./app-store-release-governance_cn.md)。

## 2. 判断入口

### 2.1 代码 Hotfix 适用场景

例如：

1. 登录失败
2. 镜像启动失败
3. 安装脚本回归
4. API 异常
5. 发布 zip 包存在严重问题

### 2.2 数据 Hotfix 适用场景

例如：

1. catalog 错误
2. library 变量错误
3. manifest 错误
4. 图片 URL 错误
5. 数据格式兼容性错误

## 3. 总原则

1. 先判断问题属于代码还是数据
2. 代码问题优先走 `hotfix/*` 分支
3. 数据问题优先走数据修复流水线，不强迫发布代码版本
4. 修复必须最小化，避免顺手夹带额外需求
5. 所有 Hotfix 都必须留痕、可追踪、可回滚

## 4. 代码 Hotfix 标准流程

```mermaid
flowchart LR
    A[确认生产故障] --> B[从 main 拉 hotfix/*]
    B --> C[实现最小修复]
    C --> D[快速验证]
    D --> E[发布修复制品]
    E --> F[验证恢复]
    F --> G[回合并到 dev]
    G --> H[复盘]
```

### 4.1 创建分支

必须从 `main` 拉分支：

```bash
git checkout main
git pull origin main
git checkout -b hotfix/<issue-id>-<short-desc>
```

禁止从 `dev` 拉 hotfix。

### 4.2 实施规则

1. 只做与故障直接相关的最小修复
2. 不顺带加入新功能
3. 不顺带做无关重构
4. 变更范围必须尽可能小

### 4.3 快速验证

至少应完成：

1. 语法/构建检查
2. 关键路径验证
3. 受影响功能回归检查
4. 制品可生成检查

### 4.4 发布动作

1. 生成修复制品
2. 如需要，先走 `rc` 通道快速验证
3. 确认无误后晋升到正式制品

### 4.5 发布后动作

1. 验证核心故障已恢复
2. 将相同修复回合并到 `dev`
3. 记录本次 hotfix 的原因、范围、验证、回滚点

## 5. 数据 Hotfix 标准流程

```mermaid
flowchart LR
    A[确认数据故障] --> B[修复数据源]
    B --> C[生成修复数据制品]
    C --> D[更新 manifest]
    D --> E[上传到 R2]
    E --> F[验证客户端恢复]
    F --> G[保留回滚点]
    G --> H[复盘]
```

### 5.1 实施规则

1. 数据修复优先不发布代码版本
2. 数据修复必须保留上一个可回滚版本
3. 数据修复必须更新 manifest 和版本号
4. 不得覆盖历史版本而不留痕

### 5.2 最小检查项

1. 目标文件存在
2. checksum 正确
3. manifest 指向正确
4. 兼容性字段未破坏旧客户端
5. 至少验证一个旧兼容路径和一个新兼容路径

### 5.3 当前可用工具

当前仓库内已经具备一组可直接执行的本地辅助脚本：

1. `scripts/validate_appstore_catalog_artifact.sh`
2. `scripts/validate_appstore_library_artifact.sh`
3. `scripts/validate_appstore_library_metadata.sh`
4. `scripts/validate_appstore_dataset_manifests.sh`
5. `scripts/list_appstore_dataset_versions.sh`
6. `scripts/switch_appstore_dataset_manifest.sh`
7. `scripts/appstore_dataset_hotfix_helper.sh`

推荐用途：

1. 发布前校验单个 catalog 制品
2. 发布前校验单个 library 制品
3. 校验 catalog/library 双 manifest 是否属于同一数据集
4. 列出当前 catalog/library 共同可用的历史 `datasetVersion`
5. 将 `manifest-<datasetVersion>.json` 切回当前 `manifest.json`，用于本地演练或数据回滚操作
6. 用统一入口脚本对本地镜像目录或 R2 风格目录做 list / switch 预演，必要时显式 `--apply`
7. 用 `plan` 模式先输出当前版本与目标版本摘要，再决定是否执行切换

### 5.4 当前边界

截至本轮文档重构完成时，应明确下面这条边界：

1. 本手册定义了标准流程，但不代表 `main` 分支已经具备全部远端自动化能力
2. 对真实远端通道执行数据切换前，仍应先按主控文档确认当前阶段状态
3. 没有完成不破坏验证前，不应把本手册理解为“已经可以直接在生产远端全自动切换”

## 6. 决策表

| 情况 | 处理方式 |
|---|---|
| 登录、安装、启动等程序故障 | 代码 Hotfix |
| 应用商店元数据错误 | 数据 Hotfix |
| library 变量错误导致安装异常 | 数据 Hotfix，必要时配合代码 Hotfix |
| manifest 指向错误 | 数据 Hotfix |
| 客户端逻辑和数据格式同时不兼容 | 先定主故障来源，必要时代码和数据双修 |

## 7. 回滚规则

### 7.1 代码 Hotfix 回滚

回滚条件：

1. 修复制品引入新故障
2. 修复未解决原故障
3. 修复导致更大范围异常

回滚动作：

1. 恢复上一版稳定应用程序制品
2. 恢复对应版本说明与发布记录
3. 记录失败原因

### 7.2 数据 Hotfix 回滚

回滚条件：

1. 新数据继续导致异常
2. manifest 指向错误版本
3. 旧客户端兼容性被破坏

回滚动作：

1. manifest 指回上一份稳定数据版本
2. 恢复上一版 catalog / library
3. 保留失败数据制品做审计

当前仓库内可直接使用：

```bash
bash scripts/list_appstore_dataset_versions.sh \
    --catalog-dir <catalog目录> \
    --library-dir <library目录>

bash scripts/switch_appstore_dataset_manifest.sh \
    --catalog-dir <catalog目录> \
    --library-dir <library目录> \
    --dataset-version <目标datasetVersion>

bash scripts/appstore_dataset_hotfix_helper.sh \
    --mode list \
    --channel dev \
    --local-root <本地镜像根目录>

bash scripts/appstore_dataset_hotfix_helper.sh \
    --mode plan \
    --channel dev \
    --dataset-version <目标datasetVersion> \
    --local-root <本地镜像根目录>

bash scripts/appstore_dataset_hotfix_helper.sh \
    --mode switch \
    --channel dev \
    --dataset-version <目标datasetVersion> \
    --local-root <本地镜像根目录> \
    --apply
```

推荐顺序：

1. 先列出 catalog 和 library 共同可回退的数据版本
2. 选定目标 `datasetVersion`
3. 先执行 `--mode plan` 确认 current/target 摘要
4. 再执行 manifest 切换脚本

默认规则：

1. `appstore_dataset_hotfix_helper.sh` 默认只做 dry-run
2. `--mode plan` 只输出切换摘要，不改任何文件
3. 只有显式加上 `--apply` 才会写回最新 `manifest.json`
4. 没有完成远端验证前，不建议直接对真实通道执行 `--apply`

执行前提：

1. catalog 和 library 的历史 manifest 已存在
2. 目标 `datasetVersion` 的 catalog/library manifest 能通过一致性校验

## 8. 必须留存的记录

每次 hotfix 或数据 hotfix 后，至少记录：

1. 问题编号
2. 故障类型（代码 / 数据）
3. 影响范围
4. 修复分支或数据版本
5. 发布通道
6. 验证方式
7. 回滚点
8. 是否已回合并到 `dev`

## 9. 最小检查清单

### 9.1 代码 Hotfix 发布前

- [ ] 从 `main` 拉出 `hotfix/*`
- [ ] 修复范围最小化
- [ ] 完成关键路径验证
- [ ] 制品生成成功
- [ ] 已确认回滚点

### 9.2 数据 Hotfix 发布前

- [ ] 已修复数据源
- [ ] 已生成新数据版本
- [ ] 已更新 manifest
- [ ] 已验证兼容性
- [ ] 已确认回滚点

## 10. 最终要求

1. Hotfix 必须小而快
2. 数据 Hotfix 必须独立治理
3. 代码问题和数据问题不能混在一起模糊处理
4. 所有紧急修复都必须可回滚、可审计、可复盘
