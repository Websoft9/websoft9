# Websoft9 版本收敛与升级方案

创建时间：2026-06-15
最后更新：2026-06-16
状态：正式方案

## 1. 目标

本轮只解决下面四件事：

1. 明确版本定义信息应该存在哪里
2. 明确当前机器实际开通版本应该存在哪里
3. 明确概览页和设置页的读取链路
4. 明确新装、升级、旧版迁移时如何保持版本状态

本轮不引入 license、远程授权、机器绑定、签名校验等机制。

## 2. 版本模型

当前版本固定为四档：

| 版本键 | 中文名 | 英文名 | 默认 `max_apps` |
|---|---|---|---|
| `free` | 免费版 | Free | 2 |
| `starter` | 入门版 | Starter | 3 |
| `standard` | 标准版 | Standard | 10 |
| `enterprise` | 企业版 | Enterprise | 不限制 |

对外和对内都统一使用这四个版本键，不再引入额外命名。

## 3. 存储职责划分

版本相关信息拆成三类，不再混在一个文件里：

### 3.1 发布版本

作用：标识当前程序产物自身的版本号，例如 `3.0.0`。

建议落点：

1. `version.json`
2. 或镜像构建时注入的只读发布元数据

它回答的问题是：当前运行的这套程序是什么版本。

### 3.2 版本定义表

作用：定义每个版本键对应的中英文名称、兼容别名、默认 `max_apps`。

建议落点：

1. `apphub/src/core/product_catalog.py`

它回答的问题是：每个版本本来应该长什么样。

### 3.3 当前机器运行时版本状态

作用：记录这台机器当前被开通成哪个版本，以及当前最终生效的 `max_apps`。

建议落点：

1. 复用现有 SQLite
2. 不新增新的 SQLite 文件
3. 在现有 `install-tracking.sqlite` 中新增一张表

它回答的问题是：这台机器当前实际启用了哪个版本。

## 4. 现有持久化载体

当前系统已经有现成且持久化的 SQLite 载体：

1. `apphub/src/services/app_status.py`
2. 默认数据库目录为 `/data/config/apphub`
3. 数据库文件为 `/data/config/apphub/install-tracking.sqlite`
4. 当前运行时将该目录统一收敛在 `product_data:/data` 下

因此：

1. 容器重建不会导致该 SQLite 丢失
2. 不需要为了版本状态再新建一个 SQLite 文件
3. 只需要在现有库中新增一个表即可

## 5. 正式存储方案

### 5.1 版本定义信息存储位置

版本定义信息继续保留在：

1. `apphub/src/core/product_catalog.py`

这里负责保存：

1. `edition_key`
2. 中文名
3. 英文名
4. 兼容别名
5. 默认 `max_apps`

这是静态产品常量，不属于运行时状态，不需要放进 SQLite。

### 5.2 运行时版本状态存储位置

运行时版本状态统一存到：

1. `/data/config/apphub/install-tracking.sqlite`
2. 新增表名：`product_runtime_state`

推荐字段如下：

| 字段 | 含义 |
|---|---|
| `id` | 固定单行主键，建议固定为 `1` |
| `edition_key` | 当前机器实际开通的版本键 |
| `max_apps` | 当前最终生效的应用上限，企业版可为 `NULL` |
| `state_source` | 来源，例如 `install`、`legacy-migration`、`manual-support` |
| `updated_by` | 更新人或更新主体 |
| `updated_at` | 最后更新时间 |
| `note` | 人工处理备注，可选 |

这张表只表达一个事实：当前机器的最终运行时版本状态。

### 5.3 `product_metadata.json` 的处理

`apphub/src/config/product_metadata.json` 不再作为正式机制的一部分。

后续策略应为：

1. 退出正式读取链路
2. 不再作为真相源
3. 过渡期如需兼容，可以仅用于旧逻辑迁移
4. 最终应从版本机制中移除

## 6. 读取链路

### 6.1 概览页

概览页继续通过：

1. `/api/overview`
2. `/api/overview/stream`

后端服务层应改为：

1. 从发布元数据读取 `version`
2. 从 `product_runtime_state` 读取 `edition_key` 和 `max_apps`
3. 从 `product_catalog.py` 读取中英文名称和默认定义
4. 组装后返回前端

也就是说，概览页不直接依赖任何版本 JSON 文件。

### 6.2 设置页

设置页继续通过：

1. `/api/settings/summary`

后端服务层应改为：

1. 从发布元数据读取 `version`
2. 从 `product_runtime_state` 读取 `edition_key` 和 `max_apps`
3. 从 `product_catalog.py` 读取显示名称
4. 拼出设置页展示用的产品版本字段

也就是说，设置页也不直接依赖任何版本 JSON 文件。

### 6.3 运行时读取原则

服务层统一遵循下面顺序：

1. 当前机器启用哪个版本：以 `product_runtime_state` 为准
2. 当前版本显示名称：以 `product_catalog.py` 为准
3. 当前版本号：以 `version.json` 或镜像发布元数据为准
4. 当前最终 `max_apps`：优先用 `product_runtime_state.max_apps`，缺失时回退到版本定义表默认值

## 7. 人工升级入口

### 7.1 原则

人工升级必须有稳定入口，但不应采用公开 CLI 作为正式机制。

原因：

1. CLI 不适合作为长期人工处理标准入口
2. CLI 容易被误解成对外公开能力
3. 版本升级本质上是受保护的运维操作，不是普通用户自助能力

### 7.2 正式入口建议

建议采用受保护的内部入口：

1. 内部 API
2. 或内部支持页面

建议能力如下：

1. 写入 `edition_key`
2. 自动推导 `max_apps`
3. 写入 `state_source`
4. 写入 `updated_by`
5. 写入 `updated_at`
6. 允许填写处理备注

### 7.3 访问控制

该入口不对普通用户开放，应受下面能力保护：

1. 管理员身份校验
2. 内部支持权限控制
3. 必要时增加仅内部网络可访问等限制

## 8. 安装与升级流程

### 8.1 新装

新装时应执行：

1. 初始化 `product_runtime_state`
2. 默认写入 `free`
3. 默认写入 `max_apps = 2`
4. `state_source = install`

这保证公开安装永远落到 Free。

### 8.2 现代版本升级

现代版本升级时应执行：

1. 保留现有 `install-tracking.sqlite`
2. 保留现有 `product_runtime_state`
3. 不因容器重建重置版本状态

这保证人工处理后的高级版本不会因升级丢失。

### 8.3 旧版迁移升级

旧版迁移时，必须以旧版真实链路为准：

1. 读取 `system.ini` 的 `[max_apps].key`

固定映射如下：

| 旧版 `max_apps` | 新版目标版本 |
|---|---|
| 2 | `free` |
| 3 | `starter` |
| 10 | `standard` |
| 空、`None`、超大值或等价不限额 | `enterprise` |

迁移写入规则：

1. 命中标准值时，自动写入 `product_runtime_state`
2. `state_source = legacy-migration`
3. 非标准值例如 7、8、13 时，不自动迁移，改为人工处理

## 9. 最终口径

当前正式方案统一收口为：

1. `version.json` 负责程序版本号
2. `apphub/src/core/product_catalog.py` 负责版本定义表
3. 现有 `install-tracking.sqlite` 新增 `product_runtime_state` 表负责当前机器运行时版本状态
4. `product_metadata.json` 退出正式版本机制
5. 概览页和设置页都通过服务层读取发布版本 + 运行时状态 + 版本定义表的合成结果
6. 默认公开安装永远是 Free
7. 高级版本升级由人工处理
8. 人工处理通过受保护的内部入口完成，不通过公开 CLI 完成
9. 现代升级保留现有 SQLite，旧版升级按 `system.ini max_apps` 映射迁移