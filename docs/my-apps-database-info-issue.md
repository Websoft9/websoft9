# 我的应用「数据 → 数据库」信息问题与优化建议

## 1. 背景

应用详情页「数据 → 数据库」区块用于展示应用内置或外部数据库的连接信息（主机、库名、账号、密码、推荐工具）。当前实现由前端根据环境变量猜测生成，缺少统一的数据来源，导致展示内容不准确，部分应用甚至为空。本文描述已核实的问题及分阶段优化建议，不涉及代码修改。

## 2. 涉及代码

| 位置 | 作用 |
| :--- | :--- |
| `console/src/features/my-apps/my-app-detail-page.tsx:169-176` | 硬编码数据库账号映射 `dbConfig` |
| `console/src/features/my-apps/my-app-detail-page.tsx:399-423` | `getDatabaseRows`：生成数据库行（主机、库名、账号、密码） |
| `console/src/features/my-apps/my-app-detail-page.tsx:1885-1886` | 账号 / 密码列标题 |
| `console/src/shared/i18n/resources.ts` | `tabs.database.columns.account/password` 文案（初始账号 / 密码） |
| `apphub/src/services/install_secrets.py` | 安装密钥生成：只为模板中已存在的字段赋值 |
| `apphub/src/services/app_manager.py:1235-1270` | 仅聚合外部数据库，无内置数据库接口 |

## 3. 已核实问题

### 3.1 密码为空（mattermost、thingsboard）

- 前端密码固定取 `data.env.W9_POWER_PASSWORD`。
- mattermost 模板已移除 `W9_POWER_PASSWORD`（`docker-library/apps/mattermost/CHANGELOG.md`），数据库密码改为 `${W9_RCODE}`（`docker-compose.yml:32`）。
- `install_secrets.py` 只为模板中存在的字段生成值，不会补回已删除变量，因此应用 env 中确实没有该键。
- 全量统计：142 个模板中 49 个声明 `W9_DB_EXPOSE`，其中 mattermost、thingsboard 两个缺少 `W9_POWER_PASSWORD`。

### 3.2 账号为固定值

- `dbConfig` 写死：mysql/mariadb=`root`、postgresql=`postgres`、mongodb=`root`、oracle=`system`、sqlserver=`sa`、redis=`-`。
- 不读取模板中的 `MYSQL_USER`、`POSTGRES_USER` 等变量。
- 实例证据：drupal 存在专用账号 `MYSQL_USER=drupal`，页面仍只显示 `root`。

### 3.3 多账号未被表达

- MySQL / MariaDB 官方镜像会创建两个账号：`root`（`MYSQL_ROOT_PASSWORD`）+ 应用账号（`MYSQL_USER`/`MYSQL_PASSWORD`）。本库有 drupal、moodle、nopcommerce 等 4 个模板使用专用账号，密码多数与 root 相同（同取 `W9_POWER_PASSWORD`）。
- PostgreSQL 仅一个超级用户（`POSTGRES_USER`，默认 `postgres`），部分模板改为专用名（airflow、superset、timescaledb）。
- MongoDB 仅 `MONGO_INITDB_ROOT_USERNAME`。
- 结论：账号数量由数据库类型与模板决定，不能假定只有一个。

### 3.4 主机名拼接不可靠（10/49）

前端用 `${app_id}-${dbType}` 拼接，与实际容器名不一致的模板：

| 模板 | 声明类型 | 实际容器名 |
| :--- | :--- | :--- |
| airflow / ckan / thingsboard / jitsu / budibase / dify / supabase | postgresql | `${W9_ID}-postgres` |
| seafile | mariadb | `${W9_ID}-db` |
| timescaledb | postgresql | 单容器 `${W9_ID}`，无独立数据库容器 |

### 3.5 数据库名称恒为 `-`

内置库未读取 `MYSQL_DATABASE` / `POSTGRES_DB`。实例：mattermost 实际库名 `mattermost`，drupal 实际库名 `drupal`。

### 3.6 密码变量因数据库类型而异

| 模板 | 密码来源 |
| :--- | :--- |
| redis | `W9_LOGIN_PASSWORD`（`--requirepass`） |
| seafile | `REDIS_PASSWORD` |
| zulip | `W9_POWER_PASSWORD` |
| mattermost | `W9_RCODE` |

统一读取 `W9_POWER_PASSWORD` 必然出现空值或错误值。

### 3.7 列标题语义错误

`tabs.database.columns.account/password` 当前为「初始账号 / 密码」（英文 Initial Account / Password）。该表格展示的是数据库连接账号与密码，与应用初始管理员账号不是同一概念。

### 3.8 外部数据库回退只覆盖 WordPress

`getDatabaseRows` 的 external 分支回退键固定为 `WORDPRESS_DB_*`，其他应用使用外部库时取不到库名、账号与密码。

### 3.9 覆盖缺口

93 个模板没有声明 `W9_DB_EXPOSE`，即使包含数据库也不会显示区块。

### 3.10 展示细节

- 密码为 `-` 时仍渲染掩码圆点，复制按钮也会复制 `-`，易误判为有效凭据。
- 数据库容器停止时仍展示连接信息，无运行状态提示。
- 内置库无端口展示（3306/5432），且多数模板未做宿主端口映射，页面未说明仅容器网络内可连。
- 类型名直接展示 `W9_DB_EXPOSE` 原值（`postgresql` / `mariadb`），与镜像实际名称不一致。

### 3.11 敏感信息暴露面

`GET /api/apps` 与详情接口返回完整 env（含 `W9_POWER_PASSWORD`、`W9_RCODE`、应用初始密码明文）。任何可查看详情的用户都能读取这些值，且无审计记录或二次确认。

## 4. 目标形态

数据库区块应展示"一条记录一个可用连接"，字段固定为：

| 字段 | 说明 |
| :--- | :--- |
| 数据库类型 | 规范化名称（MySQL / MariaDB / PostgreSQL / MongoDB / Redis 等） |
| 地址 | 主机 + 端口（内部服务名 + 端口），外部库为真实地址 |
| 数据库名称 | 实际库名，未知时显示 `—` |
| 用户 | 真实账号，并注明用途（超级用户 / 应用用户 / 只读） |
| 密码 | 实际密码，默认掩码，可复制 |
| 来源 | 内置 / 外部 |
| 推荐工具 | 按类型给出 |
| 状态 | 容器运行中 / 已停止 |

## 5. 实施建议

### 5.1 模板元数据（根源）

在应用模板元数据中新增 `database` 声明，明确连接信息来自哪里：

```json
{
  "database": {
    "type": "postgresql",
    "service": "postgres",
    "port": 5432,
    "name": "mattermost",
    "accounts": [
      { "role": "superuser", "username": "postgres", "password_env": "W9_RCODE" }
    ],
    "tools": ["CloudBeaver"]
  }
}
```

- `accounts` 支持多项，覆盖 MySQL 的 root + 应用账号。
- `password_env` 指向真实变量，避免统一猜测。
- 单容器内置数据库（timescaledb 等）声明 `"embedded": true`，只展示说明而不给内网主机。

### 5.2 后端接口（唯一数据来源）

新增 `GET /api/apps/{app_id}/databases`，返回结构：

```json
{
  "databases": [
    {
      "type": "mysql",
      "source": "builtin",
      "host": "drupal_fexsd-mysql",
      "port": 3306,
      "database": "drupal",
      "status": "running",
      "accounts": [
        { "role": "superuser", "username": "root", "password": "..." },
        { "role": "app", "username": "drupal", "password": "..." }
      ],
      "tools": ["phpMyAdmin", "CloudBeaver"]
    }
  ]
}
```

解析顺序：

1. 模板 `database` 声明（首选）；
2. 应用 env 中的 `W9_DB_*_SET`（外部库）；
3. 兼容回退：`W9_POWER_PASSWORD` / `W9_RCODE` / `MYSQL_PASSWORD` / `POSTGRES_PASSWORD` / `REDIS_PASSWORD` 及 `MYSQL_USER` / `POSTGRES_USER`；
4. 主机名以实际容器标签（`com.docker.compose.service`）为准，不拼接。

### 5.3 前端展示

- 删除 `dbConfig` 硬编码，改为渲染接口数据。
- 列标题改为「数据库 / 地址 / 数据库名称 / 用户 / 密码 / 工具」，用户列显示"角色（用户名）"。
- 取不到值时显示 `—` 并提示原因（未声明 / 未运行），不渲染掩码与复制按钮。
- 增加数据库状态标记，容器停止时给出提示。
- 内置库在地址列展示"仅容器网络内可连"，外部库展示真实地址。

### 5.4 模板补齐

- mattermost、thingsboard 声明 `password_env: W9_RCODE`。
- redis 声明 `password_env: W9_LOGIN_PASSWORD`，seafile 声明 `REDIS_PASSWORD`。
- 逐步为无 `W9_DB_EXPOSE` 但有数据库的模板补声明。

### 5.5 安全加固

- 列表接口不再返回敏感 env；详情接口按字段级权限返回数据库凭据。
- 密码查看/复制记录审计日志。
- 敏感字段默认掩码，显式操作后才返回明文。

## 6. 分期计划

| 阶段 | 内容 | 价值 |
| :--- | :--- | :--- |
| P0 | 修正列标题为「数据库用户 / 数据库密码」；空值显示 `—` 且禁用掩码与复制；补 `W9_RCODE` 等回退 | 消除误导，成本最低 |
| P1 | 新增后端 `/databases` 接口；主机名改为读取实际容器服务名；补库名与端口；支持多账号 | 数据准确 |
| P2 | 模板 `database` 声明与覆盖率补齐；安全加固与审计 | 长期可维护 |

## 7. 验收清单

- mattermost：显示类型 PostgreSQL、地址 `<app>-postgres`、库名 `mattermost`、用户 `postgres`、密码非空。
- drupal：显示 root 与 `drupal` 两个账号，库名 `drupal`。
- airflow / ckan / seafile / timescaledb：地址与实际容器名一致，单容器库显示为内嵌说明。
- redis / seafile / zulip：密码与 `docker inspect` 中真实值一致。
- 无数据库声明的应用：不出现空表格，显示 `—` 或明确提示。
- 数据库容器停止：显示状态提示，不误导为可用。
- 安全：列表接口不含敏感 env；密码查看/复制产生审计记录。
