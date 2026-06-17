# Websoft9 安装脚本

本目录包含 Websoft9 生命周期管理脚本，支持全新安装、升级、卸载和备份操作。

---

## 快速开始

### 全新安装（推荐，一行命令）

```bash
wget -O install.sh https://artifact.websoft9.com/websoft9/release/install.sh
bash install.sh install
```

或使用 `curl`：

```bash
curl -fsSL https://artifact.websoft9.com/websoft9/release/install.sh | bash -s -- install
```

### 卸载

```bash
wget -O uninstall.sh https://artifact.websoft9.com/websoft9/release/uninstall.sh
bash uninstall.sh
```

---

## 目录结构

```
install/
├── install.sh          # 生命周期统一入口（发布分发版为自包含单文件）
├── uninstall.sh        # 卸载独立入口（历史契约，可单独下载）
├── install_docker.sh   # Docker 安装脚本（无 Docker 时自动下载并执行）
├── build-bundle.sh     # 发布构建器：将 lib/*.sh 内联生成 dist/ 单文件
├── lib/                # 实现层（仅开发/源码仓库，发布单文件已内联）
│   ├── common.sh       # 常量、日志、退出码、通用工具
│   ├── detect.sh       # 环境识别（empty / modern / legacy / mixed）
│   ├── install-fresh.sh# 全新安装逻辑
│   ├── upgrade-modern.sh # 现代运行时迭代升级
│   ├── upgrade-legacy.sh # 旧版跨代迁移
│   ├── uninstall.sh    # 卸载逻辑
│   ├── backup.sh       # 备份逻辑
│   └── validate.sh     # 健康检查/验收
└── dist/               # 构建产物（git-ignored，由 build-bundle.sh 生成）
    ├── install.sh
    └── uninstall.sh
```

> **发布说明**：制品服务器上分发的 `install.sh` / `uninstall.sh` 均为自包含单文件（无需 `lib/`）。
> 源码仓库中的 `install/install.sh` 在运行时依赖同目录下的 `lib/` 目录。

---

## install.sh — 命令参考

### 语法

```
bash install.sh [选项]
```

自动识别当前环境，**未安装时全新安装，已安装时升级**，无需区分命令。

### 常用选项

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--channel <release\|rc\|dev>` | `release` | 发布通道 |
| `--console-port <port>` | `9000` | 控制台对外端口 |
| `--dry-run` | _(关闭)_ | 演练模式：仅前置检查，不实际操作 |
| `--yes` | _(关闭)_ | 跳过所有交互确认（CI / 自动化使用） |
| `-h, --help` | — | 显示帮助 |

### 高级选项（通常无需修改）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--version <tag>` | `latest` | 镜像标签 |
| `--path <dir>` | `/opt/websoft9` | 安装目录 |
| `--image-repo <repo>` | `websoft9dev/websoft9` | 镜像仓库地址 |
| `--network <name>` | `websoft9` | Docker 网络名 |
| `--force` | _(关闭)_ | 跳过非破坏性前置检查，在环境有残留时强制继续 |

### 行为说明

| 检测到的状态 | 行为 |
|---|---|
| 未安装 | 直接全新安装，无需确认 |
| 已安装 | 提示当前版本，询问是否升级（`--yes` 跳过确认） |
| 有残留组件 | 警告异常状态，默认 N 询问是否强制继续 |

### 示例

```bash
# 标准安装（自动判断安装或升级）
bash install.sh

# 指定发布通道
bash install.sh --channel rc

# CI/自动化，跳过所有确认
bash install.sh --yes

# 演练：只做前置检查，不实际操作
bash install.sh --dry-run

# 指定控制台端口
bash install.sh --console-port 8080
```

---

## uninstall.sh — 命令参考

独立卸载脚本，保留历史契约（可单独下载并执行），功能与 `install.sh` 内置卸载流程等同。

### 语法

```
uninstall.sh [options]
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode <stop\|standard\|purge>` | `standard` | 卸载模式（同上） |
| `--path <dir>` | `/opt/websoft9` | 安装目录 |
| `--keep-data [true\|false]` | `true` | 是否保留数据卷；裸 `--keep-data` 等同于 `true` |
| `--purge` | — | 等同于 `--mode purge` 的快捷别名 |
| `--yes` | _(关闭)_ | 跳过确认 |
| `--dry-run` | _(关闭)_ | 仅计划，不执行 |
| `--remove-legacy-controlplane` | _(关闭)_ | 清理旧 Cockpit/systemd 遗留 |
| `-h, --help` | — | 显示帮助并退出 |

### 示例

```bash
# 标准卸载（交互确认）
bash uninstall.sh

# 完全清除，跳过确认
bash uninstall.sh --purge --keep-data false --yes

# 仅停服，不删容器
bash uninstall.sh --mode stop

# 保留数据，清理旧版遗留组件
bash uninstall.sh --keep-data --remove-legacy-controlplane
```

---

## 环境变量

以下环境变量可在执行前设置，覆盖脚本内默认值：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `W9_ARTIFACT_BASE` | `https://artifact.websoft9.com/websoft9` | 制品分发根（无本地物料时按通道拼接 URL 下载） |
| `W9_DRY_RUN` | _(空)_ | 设为 `1` 等同于 `--dry-run` |
| `W9_CHANNEL` | _(由 `--channel` 设置)_ | 发布通道，通常通过参数指定 |

### 自定义制品源示例

```bash
# 使用内网镜像站（适合离线或受限网络环境）
W9_ARTIFACT_BASE=https://my-mirror.example.com/websoft9 bash install.sh install
```

---

## 发布通道

| 通道 | 用途 | 制品地址 |
|------|------|----------|
| `release` | 正式稳定版（**默认**） | `https://artifact.websoft9.com/websoft9/release/` |
| `rc` | Release Candidate | `https://artifact.websoft9.com/websoft9/rc/` |
| `dev` | 开发/测试版 | `https://artifact.websoft9.com/websoft9/dev/` |

各通道目录下包含以下制品文件：

```
install.sh            # 自包含安装脚本
uninstall.sh          # 自包含卸载脚本
install_docker.sh     # Docker 安装脚本
docker-compose.yml    # 部署 compose 文件（release/rc）
docker-compose.dev.yml# 部署 compose 文件（dev 通道）
version.json          # 版本元数据
mirrors.json          # 镜像加速配置
manifest.json         # 发布清单（含所有文件名引用）
SHA256SUMS            # 所有制品的校验和
```

---

## 构建单文件（开发者）

仅在开发或 CI 中构建自包含发布包时使用：

```bash
# 生成 install/dist/install.sh 和 install/dist/uninstall.sh
bash install/build-bundle.sh

# 指定输出目录
bash install/build-bundle.sh /tmp/w9-dist
```

构建器会：
1. 将 `lib/*.sh` 按依赖顺序内联进入口脚本
2. 去除各 lib 文件的 shebang 行
3. 对输出文件执行 `bash -n` 语法检查
4. 验证无残留的 `source` 语句（确保真正自包含）

`install/dist/` 目录已在 `.gitignore` 中忽略，不应提交到版本库。

---

## 退出码

| 退出码 | 常量 | 含义 |
|--------|------|------|
| `0` | `EXIT_OK` | 成功 |
| `2` | `EXIT_USAGE` | 参数错误 |
| `3` | `EXIT_PRECHECK` | 前置检查失败（端口占用、权限不足等） |
| `4` | `EXIT_ENV_GUARD` | 环境不匹配（mixed、unknown 或命令与环境不符） |
| `5` | `EXIT_RUNTIME` | 运行时启动/切换失败 |
| `6` | `EXIT_VALIDATE` | 健康检查/验收失败 |
| `7` | `EXIT_ROLLBACK` | 回退过程失败 |
