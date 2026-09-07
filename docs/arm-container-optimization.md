# ARM 与容器构建优化方案

## 当前状态

Websoft9 尚未形成完整的 ARM64 支持链路。业务代码和新版 Docker 安装器通常不依赖特定 CPU 架构，但官方产品镜像仅发布 AMD64 版本，集成运行时镜像中也存在 AMD64 专用库路径。

本文定义在维持当前单容器用户体验的前提下，交付 `linux/amd64` 与 `linux/arm64` 官方镜像，并降低单容器运行时维护成本的分阶段方案。

## 当前架构

产品镜像将多个上游镜像的产物组装到最终的 `python:3.11-slim` 镜像中：

- Console：由 `node:22-bookworm-slim` 构建。
- AppHub：由 Python 3.11 构建和运行。
- Gitea：从 `gitea/gitea:1.25.5` 复制。
- Portainer：从 `portainer/portainer-ce:2.40.0` 复制。
- Nginx Proxy Manager：从 `jc21/nginx-proxy-manager:2.12.6` 复制。

所有核心服务均由产品容器内的 Supervisor 管理。容器挂载宿主机 Docker socket，用于管理已部署应用。

## 兼容性评估

### 上游镜像

以下当前固定的上游镜像均已发布 `linux/arm64` 变体：

| 组件 | 当前镜像 | ARM64 Manifest |
|---|---|---|
| Console 构建器 | `node:22-bookworm-slim` | 是 |
| Portainer 引导器构建器 | `golang:1.24` | 是 |
| AppHub 构建器与运行时 | `python:3.11-slim` | 是 |
| Gitea | `gitea/gitea:1.25.5` | 是 |
| Portainer | `portainer/portainer-ce:2.40.0` | 是 |
| Nginx Proxy Manager | `jc21/nginx-proxy-manager:2.12.6` | 是 |

因此 ARM64 支持在技术上可行，但上游镜像具备 ARM64 变体并不意味着当前组装后的产品镜像可移植。

### 产品镜像与发布链路

- 官方 `websoft9dev/websoft9:latest` 与 `:dev` 当前仅发布 `linux/amd64`。
- 可复用 Docker 工作流已支持 `platforms` 输入，并初始化 QEMU 与 Buildx。
- Dev 与 release 工作流显式传入 `linux/amd64`，阻止了 ARM64 镜像发布。

### 架构专用的运行时复制

最终镜像基于 Debian，而 Gitea 来自 Alpine/musl 源镜像。Dockerfile 当前复制了以下 AMD64 专用路径：

```dockerfile
/lib/x86_64-linux-gnu/libpcre.so.3
/lib/x86_64-linux-gnu/libpcre.so.3.13.3
/lib/ld-musl-x86_64.so.1
/lib/libc.musl-x86_64.so.1
```

ARM64 上游镜像中的对应路径使用 `aarch64` 名称。直接复制这些固定路径会在构建最终镜像前失败。

### Portainer 集成

Websoft9 通过 Portainer 管理 endpoint、Stack、容器和卷。当前集成调用认证、endpoint 创建、Git Stack 创建、更新、重部署，以及 Docker 代理 API。

评估期间，Portainer CE `2.45.0` 是当前 LTS，且支持 ARM64。受控的 `2.40.0` 至 `2.45.0` 数据迁移验证表明：管理员凭据、`local` endpoint 和 Docker 代理调用在升级后仍可用。迁移会创建数据库备份，并将 Git Stack 记录转换为 Source 与 Workflow 记录；Git Stack 工作流必须在生产发布前完成专项回归。

## 目标状态

1. 官方镜像通过同一 manifest list 发布 `linux/amd64` 和 `linux/arm64`。
2. Dockerfile 不再包含 CPU 架构专用文件路径。
3. Portainer 引导过程不再依赖 Go 工具链或宿主机编译的二进制文件。
4. 每次发布均通过 AMD64 和 ARM64 的 smoke test。
5. 用户部署不含 ARM64 变体的应用镜像前，可见应用商店兼容性信息。

## 实施方案

### 阶段 0：建立回归基线

保持现有产品镜像不变，自动化以下检查：

- 持久化数据条件下的新装、重启和升级。
- AppHub、Gitea、Portainer、Nginx Proxy Manager 与网关的就绪状态。
- 应用安装、更新、卸载、容器生命周期和卷清理。
- Git Stack 的创建、更新、重部署、删除、私有仓库认证及 Webhook 或自动更新。
- 完整数据根目录的备份与恢复，包括 Portainer 数据。

该套件是后续每个阶段的发布准入条件。

### 阶段 1：独立升级 Portainer

将 Portainer 源镜像更新为固定 tag：

```dockerfile
FROM portainer/portainer-ce:2.45.0 AS portainer-runtime
```

不要在 Dockerfile 使用 `:lts`，因为它是会随上游版本推进的移动 tag。可行时，应在发布证据中记录准确的镜像 digest。

升级前：

- 备份完整 `${WEBSOFT9_DATA_ROOT}/portainer` 目录。
- 在独立测试实例中验证备份可恢复。

验收条件：

- 原有 Portainer 管理员凭据仍可认证。
- 原有 endpoint 和 Stack 可见。
- 阶段 0 中全部 Git Stack 回归用例通过。
- 经 Websoft9 对公开和认证 Git 仓库的重新部署成功。

升级后数据库已迁移，回滚必须恢复升级前的 Portainer 数据目录；仅回退镜像 tag 不是安全的数据库回滚方法。

### 阶段 2：替换 Go Portainer 引导器

使用 `docker/scripts/` 下的 Python 脚本替换 `docker/deployment/init_portainer.go`。最终镜像已有 Python，因此可以移除 `golang:1.24` 构建阶段和编译出的 `init_portainer` 二进制。

替代脚本必须保留以下职责：

- 使用现有数据目录、资源目录、监听地址、HTTP 和标签参数启动 `/portainer`。
- 在有总截止时间和单请求超时的情况下等待 Portainer 健康接口。
- 仅在需要时初始化管理员。
- 生成并以 `0600` 权限持久化凭据文件，保持 AppHub 集成可用。
- 验证并创建名称为 `local` 的 endpoint；不能因存在无关 endpoint 而跳过此步骤。
- 将 Portainer 子进程退出状态传递给 Supervisor。

Portainer 在 `2.40.0` 起已支持 `--admin-password` 和 `--admin-password-file`。确认密码格式后，这些选项可替代自定义的首次管理员 API 调用；但不能替代就绪等待、`local` endpoint 创建和子进程监管。

使用本地 HTTP 测试服务为初始化状态、重试、超时、凭据处理和 endpoint 幂等性添加单元测试。

### 阶段 3：移除架构专用库复制

#### Nginx Proxy Manager

删除复制 PCRE 文件的语句，改在最终 Debian 镜像中通过包管理器安装运行库。包管理器会自动选择正确的架构和库路径。

完成最终包列表前，必须在两个目标架构上检查 `ldd /usr/sbin/nginx` 并补齐全部运行时依赖，不能假设 PCRE 是唯一依赖。

#### Gitea

当前最终镜像使用 Debian/glibc，而 Gitea 源镜像使用 Alpine/musl。这一边界是现有方案最脆弱的部分。

短期方案：

- 在 Gitea 源阶段收集实际存在的 musl loader 与 libc，而不在最终 Dockerfile 写入 `x86_64` 或 `aarch64`。
- 在两个架构上为复制的 Gitea 二进制增加可执行启动检查。

长期优选方案：

- 避免在 Debian 最终镜像中运行来自 Alpine 的可执行文件。使用兼容的源镜像与最终发行版，或将 Gitea 改为独立容器。

### 阶段 4：发布多架构镜像

将 Dev 与 release 工作流调用方改为：

```yaml
platforms: linux/amd64,linux/arm64
```

保留 CI 中的 Buildx 与 QEMU 设置。增加检查步骤，确保每个已推送 tag 都同时包含两个 Linux 平台。

构建策略：

- QEMU 可用于交叉构建。
- release 推广前，ARM64 smoke test 必须在原生 ARM64 基础设施上执行。
- smoke test 必须启动产品容器、等待就绪，并执行与 AMD64 相同的核心服务和应用生命周期检查。

### 阶段 5：应用商店架构感知

当前应用商店将镜像架构解析完全交给 Docker。为应用元数据增加可选 `platforms` 字段，并在生成应用目录时进行校验。

初始行为：

- 检测 Docker 宿主机架构。
- 当所选应用没有声明兼容架构时显示警告。
- 过渡期不拒绝元数据未知的应用。

应用目录覆盖充分后，将已声明的不兼容作为阻止安装的预检错误。

## 推荐发布顺序

1. 建立回归基线。
2. 固定升级至 Portainer `2.45.0` 并验证 Git Stack 回归。
3. 使用 Python 替换 Go 引导器。
4. 处理 NPM 与 Gitea 运行时依赖。
5. 内部 AMD64 与 ARM64 镜像构建。
6. 发布多架构 Dev 镜像。
7. 完成原生 ARM64 smoke test。
8. 发布多架构 release 镜像。
9. 增加应用商店架构元数据。

不要在同一次发布中同时进行 Portainer 数据迁移、引导器替换、运行时库变更和多架构发布。

## 验证矩阵

| 范围 | AMD64 | ARM64 | 所需证据 |
|---|---:|---:|---|
| 镜像构建 | 是 | 是 | 构建成功且没有架构专用路径 |
| 产品启动 | 是 | 是 | 就绪接口健康 |
| 核心服务 | 是 | 是 | Gitea、Portainer、NPM、AppHub、网关健康 |
| Portainer endpoint | 是 | 是 | `local` Docker endpoint 存在且可用 |
| Git Stack 生命周期 | 是 | 是 | 创建、更新、重部署、删除通过 |
| 应用生命周期 | 是 | 是 | 安装、启动、停止、卸载通过 |
| 发布 manifest | 是 | 是 | `imagetools inspect` 显示两个平台 |

## 长期架构选项

当前单容器设计简化了安装，但要求在不同镜像边界之间复制可执行文件与运行时库。长期优选架构是将 Gitea、Portainer 和 Nginx Proxy Manager 拆分为独立服务，同时保留 Console 与 AppHub 作为产品控制面。

这样可消除跨发行版二进制复制，让每个组件直接使用上游多架构镜像，并支持组件级升级。但它也会带来迁移、服务发现、网络和卷管理工作，应在上述增量方案稳定后作为独立项目实施。