# 我的应用「数据 → 数据库」问题清单

> 2026-10-27 更新。以 `/root/workspace/docker-library` 本地 `main` 分支提交 `a00baaf7` 及当前 Websoft9 代码为依据，未联网更新模板仓库。
> 本文记录问题；统一声明及示例见 [设计方案](my-apps-database-design.md)。两份文档均未实施，不再保留互相冲突的旧建议。

## 1. 范围和结论

重点是补齐业务应用模板的数据库说明，让 Websoft9 按说明显示，不再猜测。

- PostgreSQL、MongoDB、Redis、TimescaleDB 等数据库产品本身，不要求在该区块重复显示。
- 外部库当前安装和显示不变；密码继续直接返回，不新增审计或脱敏任务。
- 不展示运行状态，不处理用户自行改密码或权限，不改变应用建库方式。
- 已知信息准确展示；安装时生成的信息应读取安装结果。不能提前写死，也不能承诺所有应用已经完整覆盖。

## 2. 为什么页面现在显示不准

| 当前做法 | 问题 |
| :--- | :--- |
| 通过 `W9_DB_EXPOSE` 判断数据库 | 只是粗略类型，可能漏掉同一应用的其他数据库 |
| 地址拼接成 `${app_id}-${dbType}` | 服务名和容器名不一定按类型命名 |
| 账号按数据库类型固定 | 看不到应用专用账号，也不能表达多个账号 |
| 密码统一取 `W9_POWER_PASSWORD` | 忽略 `W9_RCODE`、其他变量、无认证及安装生成密码 |
| 内置库库名固定为 `-` | 已有的库名配置没有被读取 |
| 缺失密码也渲染掩码、允许复制 | 会把占位符误当成有效密码 |

控制代码见 [详情页](../console/src/features/my-apps/my-app-detail-page.tsx)的 `dbConfig`、`getDatabaseRows` 与 `getDetailTabs`。

外部库已有 `W9_DB_*_SET` 标准字段及 `WORDPRESS_DB_*` 回退。不能因为回退只写 WordPress，就断定其他使用标准字段的应用一定取不到值。本次保持该分支不变。

后端已有聚合接口为 `GET /api/databases`，不是 `GET /apps/databases`。详情 env 随实例状态走不同读取分支；安装密钥也支持 `env.secrets`，不能概括为只生成两个固定字段。对应代码见 [应用服务](../apphub/src/services/app_manager.py)和 [安装密钥](../apphub/src/services/install_secrets.py)。

## 3. 哪些模板没有写详细说明

当前 143 个模板中，50 个有非空 `W9_DB_EXPOSE`。只有 activepieces、affine、litellm、lobehub 四个有详细 `database` 声明，其余 46 个为：

- airflow、akeneo、budibase、canvas、chatwoot、ckan、dify、directus。
- dolibarr、drupal、erpnext、espocrm、ghost、graylog、inngest、jitsu。
- kong、langfuse、librechat、matomo、mattermost、mautic、metabase、moodle。
- nextcloud、nopcommerce、odoo、prestashop、redmine、seafile、semaphoreui、sonarqube。
- supabase、superset、teamcity、thingsboard、timescaledb、typo3、umami、vaultwarden。
- woocommerce、wordpress、wordpresspro、xwiki、zammad、zentao。

这是声明缺失名单，不是全部都要修改的任务清单。例如 timescaledb 本身是数据库产品，按本次范围排除。未在这 50 个中也不代表没有依赖库：zulip 有依赖库但未声明；phpmyadmin 的数据库是可选 profile，不能默认认定已启用。

此前文档中的“9/50 主机名错误”“32 个专用账号”“45/52 库名可得”等数字，没有按本次范围和逐实例映射重新验证，撤回作为验收或分期承诺。

## 4. 已经写了，为什么还需统一

| 模板 | 当前情况 | 应怎样统一 |
| :--- | :--- | :--- |
| activepieces | 声明指向 `AP_POSTGRES_*`；数据库服务映射为 `POSTGRES_*`，并加载 `.env` | 统一指向数据库服务最终配置的字段，减少双重来源 |
| affine、litellm | 用户和库名有 Compose 字面值，不一定在 `.env` | 从指定服务环境读取，不只扫描 `.env` |
| lobehub | 库名指向 `.env` 的 `LOBE_DB_NAME`，账号密码指向服务环境 | 库名也指向数据库服务的 `POSTGRES_DB` |

现有来源不明确不代表四个模板当前全部取值错误，而是平台无法仅靠统一的“查 `.env`”或“查数据库容器”规则解释所有字段。

模板仓库还已有数据库契约、公共默认映射、JSON Schema 和一致性测试。原设计遗漏了这些约束。实测当前 Schema 拒绝多实例数组、`database.external` 字段及 ClickHouse 类型；公共外部库默认变量名也不同于 Websoft9 当前的 `_SET` 字段。实施时必须同步整理，不能只在应用文件里加字段。

## 5. 特殊应用的问题与解决办法

| 应用 | 具体问题 | 解决办法 |
| :--- | :--- | :--- |
| wordpress、drupal 等 | 配置已有库名、账号密码，但页面未读取 | 补声明，指向数据库服务的具体字段；库名以该安装为准 |
| seafile | MariaDB 服务配置 root；应用账号及三个库名在 Seafile 服务 | 字段允许指定来源服务；不标记主库，不混入 Redis 密码 |
| erpnext | `bench new-site` 生成应用数据库信息，没有所称 `ERPNEXT_DB_*` | 读取 `sites/frontend/site_config.json` 的 `db_name/db_user/db_password`；`db_user` 未设置时回退 `db_name` |
| mattermost | PostgreSQL 密码引用 `W9_RCODE` | 读取数据库服务的 `POSTGRES_PASSWORD` |
| zammad | 管理员与应用账号使用不同密码，后者引用 `W9_RCODE` | 分别读取 `POSTGRES_PASSWORD` 与 `ZAMMAD_DB_PASS`，不能共用一个密码 |
| dify | PostgreSQL、Redis 分属两个实例；插件服务另有库名 | 分别声明；插件库需核对安装结果，不把 Redis 当作第二个 SQL 库 |
| jitsu | 实际含 PostgreSQL、MongoDB、ClickHouse，旧字段只列 PostgreSQL | 补多个实例，明确 MongoDB 认证库与 ClickHouse 协议端口 |
| budibase | 有 CouchDB、Redis，以及 LiteLLM 的 PostgreSQL | 扩展类型并按实际服务声明，不能只显示 PostgreSQL |
| graylog | MongoDB 没有配置认证，连接 URI 也无账号密码 | 明确无需认证，不生成虚假的 root 和平台密码 |
| supabase | 不同内部组件使用不同账号 | 核对哪些账号需展示，各自声明，不声称都是通用账号 |
| thingsboard | 使用模板自己的 PostgreSQL 初始密码 | 如实读取配置；弱口令整改单独处理，不属于本次展示优化 |
| phpmyadmin | MariaDB 仅在可选 `db` profile 中 | 仅启用时展示，不把未部署服务当作可用数据库 |

### Seafile 不需要改变安装流程

已有配置包括三个库名 `ccnet_db`、`seafile_db`、`seahub_db`。从 `seafile` 服务读取 `SEAFILE_MYSQL_DB_*`，从 `db` 服务读取 root 密码即可。问题是来源分散，不是数据不存在。

### ERPNext 需要增加安装结果读取

管理员 root 密码已在 MariaDB 服务配置中。应用库名和密码则由 Frappe 写入站点 JSON，`backend` 服务挂载了该站点卷。模板可以说明去哪里读，但 Websoft9 还需实现安全的只读 JSON 获取；当前平台不能仅补 env 声明就自动得到它们。

不改变建库命令，不把应用密码强制设成平台密码；文件不存在时保留已知字段，不能把缺失当作无需密码。路径和字段依据模板及 [Frappe 官方契约](https://docs.frappe.io/framework/user/en/basics/site_config)，尚未逐运行实例验证。

### W9_RCODE 不是例外回退规则

Mattermost 的 `POSTGRES_PASSWORD` 已引用 `W9_RCODE`；Zammad 的应用密码字段也引用它。统一声明应指向真正使用的字段，让实例配置展开引用，不按照数据库类型固定选取 `W9_POWER_PASSWORD` 或 `W9_RCODE`。

## 6. 统一方案与剩余边界

统一模板需支持固定值、指定服务的环境变量、指定 JSON 文件字段三种来源，并支持多实例、多库、多账号以及明确的无需认证。完整示例见 [设计方案](my-apps-database-design.md#3-统一模板应该怎样写)。

- 库名和账号分别列出，不默认所有账号都能访问所有库；用途标签不等于已验证权限。
- 不把当前模板配置直接套到旧安装上；旧安装补声明方式需单独确定，重新部署不保证更新元数据。
- 不从所有容器或同类镜像中随意猜服务，避免选到可选服务、备份服务或其他应用。
- 容器地址、容器端口和宿主端口需要区分，`ExposedPorts` 不能证明可连接。
- 无声明、缺失字段、读取失败和未启用服务要区分，不将所有情况返回“没有数据库”。
- UI A/B、内部服务和账号的展示范围、补充连接字段及旧安装适配方式仍待确定。

结论：统一格式可以覆盖目前发现的主要取值方式，但各应用映射仍需逐个补齐和验证。本次更新文档不代表全部模板已经适配，也不修改代码、模板或 UI 预览。