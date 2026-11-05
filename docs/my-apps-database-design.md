# 我的应用「数据 → 数据库」模板优化方案

> 状态：讨论后的设计稿，未实施。2026-10-27 更新。
> 模板依据：本地 `/root/workspace/docker-library`，`main` 分支，提交 `a00baaf7`；未联网更新，不等同于远端最新版本。
> 问题清单见 [问题说明](my-apps-database-info-issue.md)，UI 备选见 [预览](my-apps-database-ui-preview.html)。预览未随本次文档修改，示例与本文冲突时以本文为准。

## 1. 要解决什么

让每个应用模板明确告诉 Websoft9：它依赖什么数据库、数据库在哪、有哪些库、使用什么账号，以及密码从哪里读取。Websoft9 按声明读取已安装实例的信息，不再根据数据库类型猜主机名、用户名和密码。

本次重点是 docker-library 模板规范及逐应用补齐，平台只做必要的读取和展示适配。

- 只展示业务应用依赖的数据库，如 WordPress 的 MySQL、Seafile 的 MariaDB。
- PostgreSQL、MongoDB、Redis、TimescaleDB 等数据库产品本身不纳入本次展示范围，不能因为没有 `W9_DB_EXPOSE` 就判为漏配。
- 外部数据库现有安装、取值和显示方式保持不变。
- 密码继续直接返回，前端默认掩码；不新增按需下发、审计或列表脱敏工作。
- 不展示数据库运行状态，不处理用户自行修改密码或权限。
- 不改变应用建库方式、密码生成规则、备份功能或现有配色与按钮样式。
- 不承诺已覆盖全部应用。需要逐应用验证，未知信息不猜测。

## 2. 当前实际情况

### 2.1 模板已有内容

模板仓库已有以下约定，实施时应在其基础上扩展，而不是另起一套：

- `apps/<app>/variables.json` 中的 `database`：应用数据库说明。
- `metadata/database-defaults.json`：按数据库类型保存的公共默认配置。
- `metadata/variables.schema.json`：元数据格式校验。
- `docs/database-contract.md`：数据库声明契约。
- `cli/tests/test_consistency.py`：包含全仓库元数据校验。

当前 143 个模板中，50 个有非空 `W9_DB_EXPOSE`，其中只有 activepieces、affine、litellm、lobehub 四个有详细 `database` 声明。该统计不是本期业务应用覆盖率，也不能用于推导实际数据库实例数量。缺少声明的完整名单见问题说明。

已有声明使用对象形式及 `bundled.service/database_env/username_env/password_env` 等字段。现有 Schema 不接受本文提出的数组形式，数据库类型枚举也未包含 ClickHouse、CouchDB；新增结构必须与 Schema、契约、测试一并调整。

公共默认配置中的外部库字段使用 `W9_DB_HOST` 等名字，而 Websoft9 当前使用 `W9_DB_HOST_SET` 等名字。不得直接把这套默认外部映射接入现有外部库流程。公共默认配置也尚不等于已落地的平台读取能力。

### 2.2 Websoft9 当前实现

- [详情页](../console/src/features/my-apps/my-app-detail-page.tsx)的 `getDatabaseRows` 依赖 `W9_DB_EXPOSE`；内置库地址拼接为 `${app_id}-${dbType}`，库名固定 `-`，账号按类型硬编码，密码统一取 `W9_POWER_PASSWORD`。
- 外部库优先读取 `W9_DB_*_SET`，回退 `WORDPRESS_DB_*`；这是需要保留的现有行为，不表示其他应用使用标准字段也一定取不到值。
- [应用服务](../apphub/src/services/app_manager.py)已有外部数据库聚合，浏览器访问路径为 `GET /api/databases`，目前没有本文的新读取接口。
- 活跃实例的详情可返回主容器 env；非活跃实例有 Gitea 白名单字段回退，不能概括为所有分支始终返回完整 env。
- [安装密钥生成](../apphub/src/services/install_secrets.py)既处理模板中存在的平台字段，也处理 `env.secrets` 声明，不是只生成两个固定字段。

## 3. 统一模板应该怎样写

### 3.1 基本结构

仍放在 `variables.json` 的 `database` 下。新声明统一用数组，一个元素代表一个数据库实例；旧对象形式由平台兼容读取。以下为拟议格式，不是当前 Schema 已支持的格式。

WordPress 示例：

```json
{
  "database": [
    {
      "type": "mysql",
      "service": "mysql",
      "port": 3306,
      "auth": "password",
      "databases": [{ "env": "MYSQL_DATABASE" }],
      "accounts": [
        {
          "role": "app",
          "username": { "env": "MYSQL_USER" },
          "password": { "env": "MYSQL_PASSWORD" }
        },
        {
          "role": "admin",
          "username": { "value": "root" },
          "password": { "env": "MYSQL_ROOT_PASSWORD" }
        }
      ]
    }
  ]
}
```

含义：定位 `mysql` 服务，从它最终使用的环境配置中读取库名、账号和密码。当前模板库名和应用用户名是 `wordpress`；旧安装可能不同，必须读取该安装自己的配置，不能套用示例值。

### 3.2 字段规则

| 字段 | 意思 |
| :--- | :--- |
| `type` | 数据库类型；至少覆盖现有业务应用所需的 mysql、mariadb、postgresql、mongodb、redis、clickhouse、couchdb |
| `service` | 数据库在 Compose 中的服务名，不是拼接的容器名 |
| `port` | 连接使用的容器内端口；优先明确填写，通用值可复用公共默认配置 |
| `auth` | `password` 表示密码认证，`none` 表示已确认无需认证；未知不能当作 `none` |
| `databases` | 已知库名的取值说明；允许缺省，不能为满足校验编造库名 |
| `accounts` | 已知账号及密码的取值说明；`auth: none` 时允许没有账号 |
| `role` | 账号用途标签：`admin`、`app`、`readonly`；不代表已验证权限或库访问范围 |
| `supported_modes/default_mode` | 如保留，沿用已有模式声明；不能仅靠它们声称平台已支持某种外部库安装 |

库名、用户名、密码的来源统一支持三种：

| 写法 | 用途 |
| :--- | :--- |
| `{ "value": "root" }` | 已知固定值；不要在密码声明中重复保存明文密码 |
| `{ "env": "MYSQL_PASSWORD" }` | 从本实例 `service` 的最终环境配置读取 |
| `{ "service": "seafile", "env": "SEAFILE_MYSQL_DB_USER" }` | 从同一应用的另一个服务读取 |
| `{ "service": "backend", "json_file": "/path/site_config.json", "key": "db_name" }` | 从指定服务挂载的 JSON 文件读取字段 |

每个来源只能选择 `value`、`env`、`json_file` 中的一种。`json_file` 必须配合 `key`；可选 `fallback_key` 表示主字段未设置时，读取同一文件的备用字段。缺失、空值与无需认证应分别处理。

多账号和多库分别列出，不自动生成所有账号与库的组合，也不承诺每个账号均可访问所有库。PostgreSQL 初始化账号通常有超级用户权限，不能因为被应用使用就标成低权限账号。

### 3.3 Seafile：从不同服务取值

数据库位于 `db` 服务，但应用账号和三个库名位于 `seafile` 服务的环境配置中：

```json
{
  "database": [
    {
      "type": "mariadb",
      "service": "db",
      "port": 3306,
      "auth": "password",
      "databases": [
        { "service": "seafile", "env": "SEAFILE_MYSQL_DB_CCNET_DB_NAME" },
        { "service": "seafile", "env": "SEAFILE_MYSQL_DB_SEAFILE_DB_NAME" },
        { "service": "seafile", "env": "SEAFILE_MYSQL_DB_SEAHUB_DB_NAME" }
      ],
      "accounts": [
        {
          "role": "app",
          "username": { "service": "seafile", "env": "SEAFILE_MYSQL_DB_USER" },
          "password": { "service": "seafile", "env": "SEAFILE_MYSQL_DB_PASSWORD" }
        },
        {
          "role": "admin",
          "username": { "value": "root" },
          "password": { "env": "MYSQL_ROOT_PASSWORD" }
        }
      ]
    }
  ]
}
```

当前三个库名为 `ccnet_db`、`seafile_db`、`seahub_db`，不擅自标记主库或次要内部库。不需要改变安装流程。Seafile 的 Redis 若纳入展示，应另外声明，不能把 Redis 密码当作 MariaDB 密码。

### 3.4 ERPNext：读取安装后生成的信息

当前模板的 `create-site` 服务执行 `bench new-site ... --set-default frontend`，未显式传入应用库名、应用数据库账号或密码。这些信息不能用不存在的 `ERPNEXT_DB_*` 字段代替。

管理员连接可直接读取 MariaDB 环境配置；应用连接应读取站点文件：

```json
{
  "database": [
    {
      "type": "mariadb",
      "service": "mariadb",
      "port": 3306,
      "auth": "password",
      "databases": [
        { "service": "backend", "json_file": "/home/frappe/frappe-bench/sites/frontend/site_config.json", "key": "db_name" }
      ],
      "accounts": [
        {
          "role": "app",
          "username": { "service": "backend", "json_file": "/home/frappe/frappe-bench/sites/frontend/site_config.json", "key": "db_user", "fallback_key": "db_name" },
          "password": { "service": "backend", "json_file": "/home/frappe/frappe-bench/sites/frontend/site_config.json", "key": "db_password" }
        },
        {
          "role": "admin",
          "username": { "value": "root" },
          "password": { "env": "MYSQL_ROOT_PASSWORD" }
        }
      ]
    }
  ]
}
```

Frappe 官方说明：站点配置保存 `db_name` 和 `db_password`；v16 支持独立 `db_user`，未设置时默认使用库名作为用户名。当前模板的 `backend` 服务挂载 `sites` 卷，因此可定位到该文件。

以上路径和字段依据当前模板及官方契约，尚未逐个检查运行实例。平台还需实现安全的只读 JSON 获取；这不是现有 env 读取自动具备的能力。安装未完成或文件不可读时，保留已知管理员信息，应用字段不猜测。不为方便显示而固定或重新生成应用数据库密码。

## 4. 其他需要单独处理的应用

| 应用 | 已核实的情况 | 声明处理 |
| :--- | :--- | :--- |
| activepieces | 数据库服务将 `AP_POSTGRES_*` 映射为 `POSTGRES_*`，同时载入 `.env` | 新声明优先指向数据库服务最终使用的 `POSTGRES_*` |
| affine、litellm | 部分库名、用户名是 Compose 的字面值，不在 `.env` | 读取服务环境，不只扫描 `.env` |
| lobehub | 旧声明混用 `.env` 中的 `LOBE_DB_NAME` 与服务环境中的 `POSTGRES_*` | 统一指向数据库服务的 `POSTGRES_DB/USER/PASSWORD` |
| mattermost | `postgres.POSTGRES_PASSWORD` 引用 `W9_RCODE` | 指向 `POSTGRES_PASSWORD`，不是统一改取 `W9_POWER_PASSWORD` |
| zammad | 管理员密码来自 `W9_POWER_PASSWORD`；应用账号密码来自 `W9_RCODE`，初始化脚本分别处理 | 管理员指向 `POSTGRES_PASSWORD`；应用账号、库名、密码指向 `ZAMMAD_DB_USER/DB/PASS` |
| dify | 有 PostgreSQL、Redis；插件服务另外使用 `DB_PLUGIN_DATABASE` 对应的库名 | 分别声明实例及已知库名，不把 Redis 算作第二个 SQL 库；插件库需核对安装结果 |
| jitsu | 有 PostgreSQL、MongoDB、ClickHouse，旧 `W9_DB_EXPOSE` 只写 PostgreSQL | 声明多个实例；MongoDB 连接还需表达认证库，ClickHouse 需区分 HTTP 与原生协议端口 |
| budibase | 有 CouchDB、Redis，以及 LiteLLM 使用的 PostgreSQL | 增加 CouchDB 类型；分别声明，不把 PostgreSQL 当作唯一数据库 |
| graylog | MongoDB 服务没有配置认证，应用 URI 为无账号连接 | 明确 `auth: none`，不虚构 root 或密码；库名可从已知配置补声明 |
| supabase | 内部组件使用多个数据库账号 | 分别核对需要展示的账号、密码及用途，不把内部账号当作通用连接账号 |
| thingsboard | PostgreSQL 使用模板中的固定初始密码配置 | 读取服务的 `POSTGRES_PASSWORD`；更改弱口令属于另一个任务，不并入展示优化 |
| zulip | 有 PostgreSQL、Redis，但未声明 `W9_DB_EXPOSE` | 核对纳入展示的服务后补声明及兼容字段 |
| phpmyadmin | MariaDB 服务属于可选 `db` profile | 仅实际启用该服务时展示，不能因为 Compose 中存在就认定已部署 |

上表是已核实的特殊情况，不是全部应用已通过验收的证明。MongoDB 的认证库、ClickHouse 的协议选择等扩展字段需在对应模板落地前明确写入契约和 Schema，不能由平台猜测。

## 5. 平台怎样按声明读取

1. 外部库模式先走现有分支，保留 `W9_DATABASE_MODE=external`、`W9_DB_*_SET` 和已有回退；不让新的内置声明重新引入已移除的数据库服务。
2. 读取该已安装实例的 `variables.json` 和 Compose 配置，不拿当前模板仓库的值覆盖旧实例。
3. 以应用所属 stack、endpoint 和 Compose service 定位服务，避免跨应用或跨 endpoint 取错容器。
4. `env` 指运行容器中该服务的最终环境配置；无容器时可解析该安装自己的 Compose、`env_file` 和 `.env`。配置解析必须遵循 Compose 插值、默认值、转义及覆盖规则，不把已有容器的字面密码再当变量展开。
5. JSON 来源只读取同一应用指定服务挂载的允许文件；限制路径、符号链接、文件大小及允许字段，不开放任意主机文件读取或模板自定义命令。读取完整配置后也只返回声明字段，不返回整份含密钥文件。
6. 用服务实际容器名确定容器网络地址，端口优先取明确声明并与该实例配置核对；宿主端口另从实际端口映射判断。`ExposedPorts` 不是监听或网络可达的证据，不统一声称所有内置库只能在容器网络访问。
7. 无认证、值缺失、读取失败、服务未启用是不同情况。读取失败不能伪装成“无数据库”；服务名不匹配时不自动换成同镜像的其他容器，避免选中备份服务。

这里读取的是安装配置及安装生成的连接信息，不是数据库在线账号清单，也不做实时连接验证。用户自行改密或改权限不在本期范围内。

## 6. 兼容与生效范围

- 保留 `W9_DB_EXPOSE` 作为旧版兼容信号，不能把它当作完整数据库清单；该字段还影响外部库类型判断。
- 新声明统一用数组；现有四个模板的对象、`bundled` 和旧字段需兼容归一化。旧字段的来源若不唯一，应标记不完整而不是任意选值；迁移后使用明确来源。
- 公共类型默认值与应用配置合并方式须在契约中明确。应用声明优先，密码不按类型统一回退，工具推荐可按类型复用，不要求每个模板重复填写。
- 新模板说明随新安装交付。旧安装不会自动获得新说明，普通重新部署也不保证会更新模板元数据。
- 旧安装的声明补齐方式需另行确定：可考虑受控迁移并逐项校验该安装的服务和字段，不能直接覆盖旧 Compose、凭据或 JSON 文件。
- 未声明的旧安装和自定义 Compose 不保证完整信息。保留明确的兼容边界，不增加“扫描所有镜像猜数据库”的承诺。
- 沿用现有 Portainer endpoint 能力，新增读取不能静默改成本机 Docker 读取。旧安装迁移和远端 JSON 文件读取需在实施前验证。

## 7. 显示与接口边界

模板规范确定后，再实现必要的读取接口；可采用 `GET /api/apps/{app_id}/databases` 并沿用现有 `endpointId` 选择。模板的取值说明和接口返回的解析结果不是同一份数据结构。

- 返回数据库类型、地址、端口、已知库名和账号密码，不返回运行状态。
- 缺失字段返回 `null`，前端沿用现有占位样式；没有密码时不显示掩码和复制按钮。
- 工具沿用现有商店跳转，工具对象需有 `label` 与 `app_key`，不是只有文字标签。
- 角色文案由前端中英文资源处理，不把中文角色名写死在模板。
- 明文返回方式保持现状；接入现有网关和 API 校验，不能将共享 API key 校验描述成用户级权限校验。
- 外部库原有字段、布局和工具列行为不变，不改左侧「数据库」聚合页。
- 当前「数据」页签依赖卷是否存在；有数据库信息但没有卷时也必须能进入，保留 `?tab=database` 深链接。
- UI 方案 A 平铺与 B 分组仍待选择，不把推荐当作已确认。无论哪种方案，都不自动列出所有账号与库的组合、不标记 Seafile 主库、不添加运行状态，按钮保持直角。

## 8. 实施顺序与验收

### 8.1 先统一规范

同步更新模板仓库的数据库契约、默认配置、Schema 和校验测试。新格式需校验来源互斥、服务存在、端口合法、变量确实属于指定服务、JSON 路径和字段明确、密码不重复保存明文。不能强制所有类型都有库名和用户名。

### 8.2 先验证典型模板，再逐个补齐

先选 WordPress、Seafile、ERPNext、Mattermost、Zammad、Jitsu、Graylog 验证普通配置、跨服务读取、安装结果、不同密码、多实例及无认证。再逐应用核对其余模板，记录已验证、字段不完整和未覆盖项，不承诺固定的账号数量或覆盖百分比。

### 8.3 必须通过的检查

- WordPress：当前模板库名及应用用户名为 `wordpress`；旧实例按自己的配置显示，不使用固定测试实例 ID。
- Seafile：三个库名及应用账号从 `seafile` 服务取值，root 密码从 `db` 取值，不标主库、不混入 Redis 密码。
- ERPNext：安装完成后可只读站点配置；`db_user` 未设置时回退 `db_name`；文件缺失或安装未完成时不伪造应用连接。
- Mattermost：数据库密码正确经过 `W9_RCODE` 引用取得；Zammad 的管理员和应用账号密码分别读取。
- Dify、Jitsu、Budibase：按声明返回多个实例；同类型多服务也可区分，不使用类型当唯一标识。
- Graylog：明确无需认证；空密码、未知密码与无需认证分别测试。
- 数据库产品本身不纳入本次展示；phpMyAdmin 未启用的可选数据库和 PostgreSQL 备份服务不能误识别为业务数据库。
- Schema 接受新声明和兼容旧声明，拒绝无效服务、模糊来源、未知字段和不安全文件路径。
- 测试 Compose 引用链、嵌套默认值、引号、`$$` 转义，以及含 `$` 的最终密码不被再次展开。
- 测试停止、删除、读取权限不足、文件不存在和指定 endpoint，失败不能伪装成没有数据库。
- 外部库安装和展示回归不变；无卷应用和数据库深链接可访问；密码掩码、复制和商店工具跳转正常。

## 9. 尚待确定

1. UI 选择 A 平铺还是 B 分组。
2. 各应用展示哪些依赖服务及内部账号；Redis 等服务不能一概遗漏或一概纳入。
3. MongoDB 认证库、ClickHouse 协议等补充字段的最终定义。
4. 旧安装如何安全补充声明，以及安装结果文件在各 endpoint 的只读获取实现。

这四项不影响当前问题结论，但需要在批量修改模板和实施平台功能前确定。本次只修订文档，不代表模板、Schema 或平台能力已经实现。

## 10. 参考

- [Frappe 站点配置](https://docs.frappe.io/framework/user/en/basics/site_config)：自动生成的库名、密码及 `db_user`。
- [Compose 变量插值](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)：默认值、引号及来源优先级。
- [Docker EXPOSE](https://docs.docker.com/reference/dockerfile/#expose)：端口声明不等于发布端口或连接可用。