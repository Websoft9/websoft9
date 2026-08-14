# WordPress 外部 MySQL 试点方案

## 目标

在应用商店为**新安装**的 WordPress 提供数据库来源选择：

- **内置 MySQL**：保持当前 WordPress 与 MySQL 容器一起部署的行为不变。
- **外部 MySQL**：部署不包含 MySQL 服务的 WordPress；使用用户提供的 MySQL-compatible 数据库、数据库名和可访问账号。

本试点用于验证完整安装模型。验证完成前，不扩展到 PostgreSQL、Odoo、已安装应用迁移、`/setup` 或云数据库自动创建。

## 明确不做的事项

- 不修改 `/setup`。
- 不迁移已安装的 WordPress，也不自动识别或转换其数据库模式。
- 不自动创建 RDS、VPC、安全组或其他云资源；用户自行准备可访问的数据库服务。
- 不支持 PostgreSQL、Odoo、任意数据库 URL、复用已有数据库或导入已有应用数据。
- 不修改现有内置 WordPress 安装行为，也不修改其他应用模板。
- 卸载应用时不删除外部数据库、外部数据库账号或外部数据库服务。

## 支持范围与固定边界

首期只支持 WordPress + MySQL 协议：MySQL、MariaDB、Aurora MySQL 均可接入。数据库类型由 WordPress 外部模板固定，用户不需要在表单中选择其他引擎。

首期按以下边界实现：

1. **密码存储**：首期沿用现有应用模板模型。用户提供的数据库用户名和密码保存到该应用私有 Gitea 仓库的 `.env`，Portainer 从该仓库拉取并部署，后续重部署直接复用连接配置。数据库密码不得写入安装日志、安装状态或错误响应；拥有“我的应用”详情访问权限的用户可在详情页掩码查看和复制密码。
2. **TLS 范围**：首期使用用户名密码认证，不额外配置客户端证书或 WordPress MySQL SSL 参数。数据库地址不区分公网、私网或 Docker 服务名：安装前实际 MySQL 连通性测试成功即可继续；连接失败由安装流程直接返回错误。

## 安装界面

现有 WordPress 安装表单保留应用名称、访问方式、端口或域名设置。新增如下数据库区块：

```text
应用数据库
[ 系统内置 | 自定义 ]

选择“使用外部 MySQL”后：

数据库连接信息
主机地址             [ db.example.internal ]
端口                 [ 3306 ]
数据库名称           [ wordpress_myblog ]
数据库用户           [ wordpress_user ]
数据库密码           [ ******** ]  [显示/隐藏] [测试连接]
```

规则：

- 用户负责预先创建数据库并提供仅需访问目标数据库的可用账号。
- 平台不生成 WordPress 数据库账号或密码，也不检查或修改数据库对象。
- 主机地址可填写 Docker 服务名、宿主机地址、私网 IP、私有 DNS、RDS/Aurora endpoint 或公网域名；平台只以实际 MySQL 连通性测试结果判断能否继续。
- 不在安装日志、安装状态或错误响应中显示数据库密码；应用详情页仅向拥有现有详情访问权限的用户提供掩码查看和复制。

## 外部数据库生命周期

1. 校验当前 profile 模板声明的 `W9_*_SET`。
2. AppHub 使用用户提供的主机、端口、数据库名、用户名和密码进行 MySQL 协议认证，并执行只读 `SELECT 1`。
3. 成功后复制并规范化 WordPress 外部模板，创建 Gitea 仓库并由 Portainer 部署。WordPress 首次启动时自行创建表。
4. 将用户提供的连接参数写入最终应用私有 `.env`；不得写入日志、状态或错误响应。

平台不执行 `CREATE DATABASE`、`CREATE USER`、`GRANT`、删除数据库、删除账号或其他数据库生命周期操作。失败处理沿用现有应用安装流程：Gitea、Portainer Stack 和本地卷按既有回滚逻辑删除；平台不对外部数据库、外部账号或其数据执行额外删除操作。

## 模板与部署契约

仅为 WordPress 模板增加：

```text
apps/wordpress/docker-compose.external-mysql.yml
apps/wordpress/.env.external-mysql
```

默认模式固定使用 `docker-compose.yml` 与 `.env`。额外安装模式使用配对命名约定：

```text
docker-compose.<模式>.yml
.env.<模式>
```

因此本试点的模式键为 `external-mysql`。发布工具仅将同时存在的一对文件识别为额外安装模式；未来可以按相同规则增加 `external-postgresql`、`with-redis` 或 `high-availability` 等模式，而不增加每个应用专用的描述文件。

`docker-compose.external-mysql.yml` 保留 WordPress 服务、既有支持服务、Websoft9 网络和应用卷，但不包含：

- `mysql` 服务；
- `mysql_data` 卷；
- `depends_on: mysql`；
- 本地 MySQL 初始化变量。

`.env.external-mysql` 保留必需的 `W9_*` 应用元数据。用户在安装页填写的安装阶段字段由该文件中的 `W9_*_SET` 声明：

```text
W9_DB_HOST_SET=
W9_DB_PORT_SET=3306
W9_DB_NAME_SET=
W9_DB_USER_SET=
W9_DB_PASSWORD_SET=
```

其中 `W9_DB_PASSWORD_SET` 是秘密字段，安装页必须使用密码输入框且不回显。用户负责预先创建数据库并提供可访问该数据库的账号；Websoft9 仅在安装前使用只读 `SELECT 1` 验证 MySQL-compatible 连接，不建库、不建用户或授权。

最终 `.env` 使用已有的数据库类型字段与新增的模式标识：

```text
W9_DATABASE_MODE=external
W9_DB_EXPOSE=mysql
WORDPRESS_DB_HOST
WORDPRESS_DB_NAME
WORDPRESS_DB_USER
WORDPRESS_DB_PASSWORD
```

安装时，通用安装模式解析逻辑在“复制模板并生成安装目录”的边界选择 `external-mysql` 源文件，并在镜像拉取、Gitea 推送和 Portainer Stack 创建之前，将结果规范化为应用私有 Gitea 仓库中的：

```text
docker-compose.yml
.env
```

不修改 Portainer、重部署、启停、卸载、镜像拉取和仓库文件发现逻辑以识别第二个 compose 文件名；这些既有链路始终只消费上述规范化文件名。

外接模式不使用内置 MySQL 的 `W9_POWER_PASSWORD`。最终 `.env` 保存用户提供的 WordPress 运行凭据；`W9_DATABASE_MODE=external` 标记外接模式，缺少该变量即为现有内置模式；数据库类型复用现有 `W9_DB_EXPOSE=mysql`。此文件属于明文敏感配置，必须保持仓库私有；密码不得出现在日志、安装状态或错误响应，且只在“我的应用”详情中向已授权用户掩码显示。

## API 与后端契约

扩展安装元数据与安装请求，使其携带受约束的安装模式；当前选中模板中的 `W9_*_SET` 仍通过既有 `settings` 字典提交。

```json
{
  "profile": "external-mysql",
  "settings": {
    "W9_HTTP_PORT_SET": "9001",
    "W9_DB_HOST_SET": "db.example.internal",
    "W9_DB_PORT_SET": "3306",
    "W9_DB_NAME_SET": "wordpress_myblog",
    "W9_DB_USER_SET": "wordpress_user",
    "W9_DB_PASSWORD_SET": "数据库密码"
  }
}
```

规则：

- 默认模式不传 `profile`，继续使用 `docker-compose.yml` 与 `.env`；额外模式必须来自已发布的配对文件，未知模式返回 `400`。
- WordPress 的 `external-mysql` 模式只支持 MySQL、MariaDB 和 Aurora MySQL；用户必须预先创建目标数据库并提供可访问它的账号。
- `W9_DB_PASSWORD_SET` 不得进入 Pydantic 校验错误、安装状态、日志、遥测或 API 响应；模板物化后作为 WordPress 运行密码写入私有 Gitea `.env`。
- 后端仅接受当前选中模板声明的 `W9_*_SET`，并使用既有通用设置写入流程写入最终 `.env`。
- 后端在创建安装资源前验证外部 MySQL 的账号、密码、数据库可访问性和 MySQL 协议兼容性；不创建数据库、账号或授权。
- 最终 `.env` 必须写入 `W9_DATABASE_MODE=external` 与 `W9_DB_EXPOSE=mysql`；不得通过主机名推断外部模式。

### 安装元数据与通用表单

`install metadata JSON` 是安装页面的参数来源。发布和运行时本地回退生成逻辑都必须扫描每个应用目录中的模式文件对，并把模式与其 `W9_*_SET` 字段写入元数据。例如：

```json
{
  "apps": {
    "wordpress": {
      "settings": { "W9_HTTP_PORT_SET": "9001" },
      "is_web_app": true,
      "profiles": {
        "external-mysql": {
          "settings": {
            "W9_DB_HOST_SET": "",
            "W9_DB_PORT_SET": "3306",
            "W9_DB_NAME_SET": "",
            "W9_DB_USER_SET": "",
            "W9_DB_PASSWORD_SET": ""
          }
        }
      }
    }
  }
}
```

前端通用地读取 `profiles`：没有额外模式的应用维持现有表单；存在额外模式时显示模式选择器，并以所选模式的 `settings` 完整替换默认模式字段。`external-mysql` 作为平台 MySQL-compatible 协议 profile，将其标准五项连接字段显示为数据库连接卡片并用于连接测试；其他 `W9_*_SET` 仍按通用表单显示。所有匹配 `W9_*_PASSWORD_SET` 的字段按全局命名约定使用密码输入框，并在日志、状态和响应中脱敏；其他秘密类型若未来需要支持，必须先定义同样通用的命名约定。

`apps index JSON` 和 `manifest` 不承载模式或字段定义：它们继续发布整个应用 bundle 并校验 checksum。模式文件随 bundle 下载后，由安装服务按用户选择的 `profile` 物化。

## 密码存储、详情与重部署

外接模式不使用 `W9_POWER_PASSWORD`，应用私有 Gitea 仓库 `.env` 保存用户提供的 `W9_DB_*_SET` 与对应的 `WORDPRESS_DB_*` 运行连接信息，能够支持 Portainer Git Stack 的创建与重部署。

明确边界：

1. 用户负责预先创建数据库并提供账号；Websoft9 仅做只读连接验证，不创建数据库、账号或授权。WordPress 运行时使用 `WORDPRESS_DB_USER` 与 `WORDPRESS_DB_PASSWORD`。
2. 私有 `.env` 是明文配置：拥有 Gitea 仓库读取权限、Portainer Stack 配置权限或宿主机 Docker 管理权限的人员可能读取它；这些管理权限必须严格控制。
3. 数据库密码不得出现在日志、安装进度或错误响应；数据库详情按现有权限模型向已授权用户提供掩码显示和复制。
4. 用户需要修改外部数据库地址、账号或密码时，更新该应用私有仓库中的 `.env` 后执行既有“重部署”即可；密码变更应先在数据库侧完成。
5. 彻底卸载会删除应用 Gitea 仓库，因此也会删除 `.env`；外部数据库、外部账号及其数据由用户自行保留和管理。

后续可增加加密秘密存储与 `WORDPRESS_DB_PASSWORD_FILE` 注入，作为安全增强；该增强不应改变首期 API 字段、模板选择或重部署流程。

停机与重部署语义：

- 运行中时，应用详情可从主容器环境读取模式标识和 WordPress 运行连接信息。
- 停机后容器环境不可用，详情服务必须从私有 Gitea `.env` 回读 `W9_DATABASE_MODE`、`W9_DB_EXPOSE` 与 `WORDPRESS_DB_*`。不能因停机而退回为假设存在 `<app_id>-mysql` 的内置数据库。
- 重部署不连接或修改外部数据库；Portainer 继续从私有仓库中的规范化 `.env` 读取 WordPress 运行配置。

卸载语义：

- 现有 `purge_data=true` 会删除应用 Gitea 仓库和本地卷；外部数据库、外部账号和数据不由平台额外处理。
- `.env` 随 Gitea 仓库删除，平台不保证能再次取得原外部数据库凭据；用户必须自行保留外部数据库连接信息。
- `purge_data=false` 仅停止 Stack 并保留私有仓库和连接配置，可使用既有重部署恢复。
- `purge_data=true` 以及对非活动应用执行“移除”都会删除私有仓库和 `.env`；UI 必须准确表述“外部数据库资源由用户管理；彻底删除会删除平台保存的连接配置”。

## 网络要求

安装服务直接以用户输入的主机、端口、数据库名和账号执行 MySQL 连接测试。地址可以是 Docker 服务名、宿主机地址、私网地址或公网地址；测试成功则继续，失败则返回错误。网络路由、防火墙、安全组、数据库监听和部署 Endpoint 的网络可达性均由用户环境负责，Websoft9 不管理或限制这些网络拓扑。

## 备份、卸载与升级

- 当前 AppHub 备份仅备份 Docker 卷，不包含外部数据库数据。外部模式的创建和恢复备份入口都必须明确提示“数据库备份与恢复由外部数据库服务负责”。
- 卸载仅按现有行为处理应用 Stack、本地卷、代理和 Gitea 仓库；不得对外部数据库发出删除命令。
- 平台升级保留应用私有 Gitea 仓库，不应修改外部数据库数据。已安装应用维持内置模式，不自动转换。
- 外部 WordPress 必须在平台升级后，使用规范化 Gitea `docker-compose.yml` 与 `.env` 成功重部署。

## 具体实施设计

### 改动范围

| 位置 | 改动 | 不改动的行为 |
|---|---|---|
| docker-library `apps/wordpress/` | 增加 `docker-compose.external-mysql.yml`、`.env.external-mysql` | 现有 `docker-compose.yml` 与 `.env` 原样保留 |
| 安装元数据生成与同步 | 自动发现配对的 `docker-compose.<模式>.yml` 与 `.env.<模式>`，写入 `profiles` | 无额外模式的应用维持当前元数据 |
| `apphub/src/schemas/appInstall.py`、校验与安装服务 | 增加受约束的 `profile`，通过既有 `settings` 写入当前模板字段 | 默认模式的请求、端口保留与模板行为不变 |
| `console/src/features/app-store/` | 渲染元数据 `profiles` 的选择器与字段；`external-mysql` 使用标准数据库连接卡片 | 其他 profile 字段仍按通用表单渲染 |
| 我的应用详情、备份和卸载提示 | 识别外接模式；增加准确提示 | 列表、启停与既有重部署接口保持不变 |

### 请求与数据模型

```json
{
  "app_name": "wordpress",
  "edition": { "dist": "community", "version": "6.9" },
  "app_id": "myblog",
  "proxy_enabled": true,
  "domain_names": ["blog.example.com"],
  "settings": {
    "W9_HTTP_PORT_SET": "9001",
    "W9_DB_HOST_SET": "db.internal",
    "W9_DB_PORT_SET": "3306",
    "W9_DB_NAME_SET": "wordpress_myblog",
    "W9_DB_USER_SET": "wordpress_user",
    "W9_DB_PASSWORD_SET": "数据库密码"
  },
  "profile": "external-mysql",
}
```

- `profile` 必须由当前应用已发布的模式文件对导出，并拒绝未知模式、额外字段或缺少字段。
- `W9_DB_PASSWORD_SET` 不得写入 `appInstalling`、安装日志或持久化状态；模板物化后作为 `WORDPRESS_DB_PASSWORD` 的来源写入私有 Gitea `.env`。
- 外接模式写入 `W9_DATABASE_MODE=external` 和 `W9_DB_EXPOSE=mysql`，用于我的应用、备份和卸载提示；没有 `W9_DATABASE_MODE` 的应用沿用内置模式。

### 安装时序与补偿

```text
1. 前端依据 install metadata 的 `profiles` 选择模板，并提交完整的当前模板 `settings` 与 `profile=external-mysql`
2. 安装路由校验模式及字段；使用 MySQL 协议认证并对指定数据库执行只读 `SELECT 1`
3. 用户负责确保目标数据库和账号已经存在且可访问；验证成功后安装服务创建安装任务
4. 复制 WordPress 模板；选择 `external-mysql` 配对文件，并覆盖为标准 `docker-compose.yml` 与 `.env`
5. 使用既有通用设置写入流程写入 `W9_*_SET`；模板派生 `WORDPRESS_DB_*`、`W9_DATABASE_MODE=external`、`W9_DB_EXPOSE=mysql`
6. 安装服务复用既有 `GiteaManager`、`PortainerManager`、`ProxyManager` 和安装状态服务：推送 Gitea、预拉镜像、创建 Portainer Git Stack、创建代理
7. 安装完成
```

失败时沿用既有安装回滚：删除本次创建的 Gitea 仓库、Portainer Stack 和本地卷。外部数据库、账号和数据从未由 Websoft9 创建或清理。

### 我的应用最小适配

- **列表与启停**：不改变服务逻辑。外部模板同样规范化为 `docker-compose.yml` 和 `.env`，现有 Portainer Stack 操作继续可用。
- **详情**：运行时从容器环境读取，停机时从 Gitea `.env` 回读模式标识和 WordPress 运行连接信息；数据库密码按现有详情权限模型以掩码形式显示并支持复制。
- **重部署**：不增加新接口。Portainer 从 Gitea 重新读取 `.env`，因此可取得应用低权限密码；不得要求用户再次输入安装账号密码。
- **卸载**：不改变删除 Stack/卷/Gitea 仓库的后端基础语义。仅增加外部模式提示，说明不会删除外部数据库，且彻底卸载会删除本地保存的连接配置。
- **备份**：不改变 Restic 卷备份实现。仅在外部模式提示其不包含数据库数据。

### 我的应用数据页

当前数据库连接信息由 `W9_DB_EXPOSE` 推断，内置模式默认假定主机为 `<app_id>-<db type>`、账号为内置初始账号、密码为 `W9_POWER_PASSWORD`。外接模式必须先将数据库标签纳入详情页标签集合，再按 `W9_DATABASE_MODE` 分支：

```text
无 W9_DATABASE_MODE（内置）
  type     = W9_DB_EXPOSE
  host     = <app_id>-<db type>
  account  = 内置数据库初始账号
  password = W9_POWER_PASSWORD

W9_DATABASE_MODE=external
  type     = W9_DB_EXPOSE
  host     = WORDPRESS_DB_HOST
  account  = WORDPRESS_DB_USER
  password = WORDPRESS_DB_PASSWORD
```

外接数据页只展示 WordPress 实际运行连接信息。即使外接模式没有 MySQL 数据卷，也必须保留数据库信息表；详情标签与数据库信息区块的显示条件必须使用“存在数据库信息”，不能仅依赖卷列表。

## 实施顺序

1. 在 docker-library 源仓库添加 WordPress 外部模板，分别验证内置与外部变体的 `docker compose config`。
2. 扩展安装元数据生成与同步，使其自动发现模式文件对；前端通用渲染模式选择与字段，并完成密码字段脱敏。
3. 增加受类型约束的 `profile` 模型；当前选中模板的 `W9_*_SET` 继续通过 `settings` 提交，并在安装前验证外部 MySQL 连接。
4. 在通用安装服务中按 `profile` 复制/物化模板，并在既有 Gitea、镜像拉取、Portainer 步骤之前规范化为固定文件名和 `.env`；默认模式必须保持兼容。
5. 在我的应用详情中加入数据库标签和外接连接信息；在备份与卸载界面增加外接数据库生命周期提示。
7. 将构建物部署到运行中的产品容器，从实际应用商店入口完成验证。
8. 后续独立评估加密秘密存储、TLS 和公网数据库支持，不与本试点混合实施。

## 必需测试

后端测试：

- 内置 WordPress 安装请求与现有行为完全一致。
- 外部请求拒绝未知 profile、错误模板字段、空连接参数、无效端口和非 MySQL-compatible 端点。
- 数据库密码不出现在校验错误、日志、状态或遥测中；仅向已授权的“我的应用”详情用户提供掩码显示和复制。
- 使用具备目标数据库访问权限的非 root 账号可通过只读认证和 `SELECT 1`。
- 权限不足、网络不可达、凭据错误和数据库不存在均返回可操作错误。
- 安装失败沿用既有 Gitea、Stack 和本地卷回滚，不额外删除外部数据库资源。
- 内置和外部模式都仅向 Gitea 写入 `docker-compose.yml` 与 `.env`；外部 `.env` 保存用户提供的 WordPress 运行连接参数。

集成与运行时测试：

- WordPress 内置安装、启停、重部署、卸载和卷备份回归通过。
- 外部 WordPress 可对用户管理的 MySQL-compatible 数据库成功完成只读验证并安装。
- 外部 WordPress 使用私有 `.env` 中的运行凭据即可重部署。
- 外部 WordPress 卸载后，外部数据库及其数据不由平台额外处理；用户界面提示符合实际凭据清理语义。
- 我的应用数据库页在运行和停机状态都正确显示 `WORDPRESS_DB_HOST`、`WORDPRESS_DB_USER` 与外接模式，不回显 `WORDPRESS_DB_PASSWORD`，也不显示不存在的 `<app_id>-mysql` 主机。
- 外接 WordPress 部署失败时，安装错误不会对外部数据库发出删除命令。
- 平台升级后外部 WordPress 可以重部署。
- 真实产品入口验证表单渲染、安装账号密码脱敏、成功安装、网络失败和权限失败。
- 已提交的 Gitea/Portainer 镜像升级需补充运行时验证：Gitea 登录桥接、Portainer 登录、Git Stack 创建、Git Stack 重部署，以及升级后平台数据兼容性。

## 发布条件

仅在以下条件全部满足后发布试点：

- 内置 WordPress 行为无回归；
- 外部 WordPress 使用仅授权目标数据库的运行账号；
- 数据库密码仅存在私有 Gitea `.env` 且未被 API、日志或状态回显；
- 连接验证、部署、重部署、卸载、备份提示和平台升级回归测试全部通过；
- 若启用 TLS，已通过对应端到端测试。