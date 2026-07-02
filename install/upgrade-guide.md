# Websoft9 升级与旧控制面卸载指南

本文档面向两类升级场景：

1. 从 main 分支时代的旧 Cockpit 多容器架构升级到当前单容器架构
2. 从比 main 更老的历史变种升级到当前单容器架构

目标是把两件事分开处理：

1. 先完成数据迁移与新架构接管
2. 再在回退窗口关闭后卸载旧 Cockpit/systemd 控制面

不要把这两步合并为一次“边迁移边删除”。旧控制面删早了，会直接丢失回退能力。

---

## 1. 适用范围

### 1.1 main 分支时代旧架构

这一代通常具备下面的信号：

- systemd 单元：`websoft9.service`、`cockpit.socket`、`cockpit.service`
- 旧容器：`websoft9-apphub`、`websoft9-deployment`、`websoft9-git`、`websoft9-proxy`
- 旧卷：`apphub_logs`、`apphub_config`、`portainer`、`gitea`、`nginx_data`、`nginx_letsencrypt`、`nginx_modsec`、`nginx_var`
- 宿主机路径：`/data/compose`、`/data/websoft9/source`

### 1.2 比 main 更老的历史变种

仓库里还能看到更老谱系的实现痕迹，这类主机升级时也要纳入考虑。常见信号包括：

- 旧服务根目录：`/data/apps/w9services`
- 独立组件目录：`w9appmanage`、`w9portainer`、`w9nginxproxymanager`、`w9redis`
- 更老容器名：`websoft9-portainer`、`websoft9-gitea`
- 带前缀的卷名：例如 `w9nginxproxymanager_nginx_data`、`*_portainer_data`、`*_gitea_data`

如果目标机器命中了这一类历史信号，不要只按 main 时代的固定容器名和卷名理解旧环境。

### 1.3 不适用场景

下面这些场景不应直接按自动升级处理：

- 现代单容器与旧 Cockpit 运行时同时存在的 mixed 主机
- 旧卷、旧容器、旧 systemd 信号相互矛盾
- 宿主机上已经人工修改过旧 Portainer、Gitea、NPM 的挂载或数据路径

这类环境应先做人工盘点，再执行迁移。

---

## 2. 升级原则

升级到新架构时，必须坚持下面的顺序：

1. 识别旧环境谱系
2. 备份旧卷、旧 compose 源、旧 config.ini、旧 system.ini、旧证书
3. 停掉旧 Cockpit 和旧多容器运行时，释放端口并冻结旧卷写入
4. 启动新架构完成数据接管与验证
5. 保留旧控制面一段回退窗口
6. 回退窗口关闭后，再卸载旧 Cockpit/systemd

旧 Cockpit/systemd 的卸载是“迁移后收口”，不是“迁移前准备”。

---

## 3. 升级前盘点

在执行升级前，至少记录下面这些信息：

### 3.1 旧 systemd 与 Cockpit

```bash
systemctl status websoft9.service --no-pager || true
systemctl status cockpit.socket --no-pager || true
systemctl status cockpit.service --no-pager || true
```

### 3.2 旧容器与旧卷

```bash
docker ps -a --format '{{.Names}}'
docker volume ls
```

### 3.3 旧宿主机路径

```bash
ls -ld /data/compose /data/websoft9/source /data/apps/w9services 2>/dev/null || true
```

### 3.4 建议额外核对的旧业务资产

- Portainer 中现有 endpoint 和 stacks 数量
- Gitea 仓库数量
- NPM 中 proxy hosts、custom_ssl、letsencrypt 资产
- 旧设置中的全局域名、镜像加速、API key

如果这些值在升级前没有基线，升级后很难判断是“迁移没做”还是“本来就为空”。

---

## 4. 推荐升级流程

### 4.1 先做备份

至少备份下面这些资产：

- 旧 Docker 卷
- `/data/compose`
- `/data/websoft9/source` 或 `/data/apps/w9services`
- 旧 `config.ini` 和 `system.ini`
- 旧 Cockpit 配置目录 `/etc/cockpit`

### 4.2 执行新 install 入口

当前 install 目录的统一入口负责识别 modern 和 legacy，并在 legacy 场景走跨代迁移。

示例：

```bash
sudo bash install.sh
```

历史自动化入口如果仍传递 `--execute_mode upgrade`，当前版本也会兼容接受：

```bash
sudo bash install.sh --execute_mode upgrade
```

如果只是预演，不实际切换：

```bash
sudo bash install.sh --dry-run
```

### 4.3 升级完成后的最小验收

至少验证下面这些结果：

1. `9000` 入口可达
2. `/api` 可达
3. Gitea 仓库仍存在且可访问
4. Portainer 能登录，并且原有 stacks 仍可解释
5. NPM 中原有 proxy hosts、证书或自定义配置仍存在
6. 设置里的全局域名、镜像加速、关键 API key 已接续

如果上面第 3 到第 6 项有任何一项失败，不要立即删除旧 Cockpit/systemd。

---

## 5. 旧 Cockpit/systemd 何时卸载

只有在下面三个条件同时满足时，才进入卸载阶段：

1. 新架构已经稳定运行
2. 旧业务数据已经确认迁移成功
3. 旧运行时已不再作为回退来源

建议至少保留一个明确的回退窗口，再做清理。

---

## 6. 当前版本的一个重要限制

当前 `install/uninstall.sh` 里的 `--remove-legacy-controlplane` 还不能作为“仅清理旧 Cockpit/systemd”的安全命令直接用于已迁移成功的现代主机。

原因是：当宿主机已识别为 modern 时，卸载流程会先处理当前现代运行时，再附带处理 legacy 控制面。

这意味着下面这类命令当前不适合作为“迁移后只清旧壳”的标准做法：

```bash
sudo bash uninstall.sh --remove-legacy-controlplane --yes
```

在没有新增“legacy-cleanup-only”能力前，迁移成功后的旧 Cockpit/systemd 清理应按独立人工步骤执行。

---

## 7. 迁移成功后的旧控制面卸载步骤

下面步骤的前提是：新架构已经验证通过，且你明确不再需要回退。

### 7.1 停止并禁用旧 systemd 单元

```bash
sudo systemctl stop websoft9.service cockpit.socket cockpit.service 2>/dev/null || true
sudo systemctl disable websoft9.service cockpit.socket cockpit.service 2>/dev/null || true
sudo systemctl daemon-reload
```

### 7.2 备份后清理旧 Cockpit 配置

```bash
sudo tar -czf /root/websoft9-legacy-cockpit-backup-$(date +%Y%m%d-%H%M%S).tar.gz /etc/cockpit /usr/share/cockpit 2>/dev/null || true
```

确认备份完成后，再按需删除旧目录：

```bash
sudo rm -rf /etc/cockpit
sudo rm -rf /usr/share/cockpit
```

### 7.3 卸载 Cockpit 软件包

Debian 或 Ubuntu：

```bash
sudo apt remove --purge -y cockpit cockpit-ws cockpit-bridge cockpit-system cockpit-networkmanager cockpit-session-recording cockpit-sosreport pcp-zeroconf
sudo apt autoremove -y
```

RHEL、Rocky、AlmaLinux、CentOS、openEuler：

```bash
sudo dnf remove -y cockpit cockpit-ws cockpit-bridge cockpit-system cockpit-networkmanager cockpit-session-recording cockpit-sosreport pcp-zeroconf || \
sudo yum remove -y cockpit cockpit-ws cockpit-bridge cockpit-system cockpit-networkmanager cockpit-session-recording cockpit-sosreport pcp-zeroconf
```

### 7.4 清理旧安装物料

main 分支时代常见旧目录：

```bash
sudo rm -rf /data/websoft9/source
```

更老版本常见旧目录：

```bash
sudo rm -rf /data/apps/w9services
```

这一步只应在你确认新架构已完全接管，且旧目录不再承载任何唯一业务数据时执行。

### 7.5 清理旧容器与旧卷

如果旧容器和旧卷仍然保留，只应在确认不再需要回退时再清理。

典型旧容器：

```bash
docker rm -f websoft9-apphub websoft9-deployment websoft9-git websoft9-proxy 2>/dev/null || true
docker rm -f websoft9-portainer websoft9-gitea 2>/dev/null || true
```

典型旧卷需要按实际主机盘点后清理，不要只删除固定名字的一小组卷。

---

## 8. 面向更老版本的兼容建议

如果来源不是 main 分支那一代，而是更老的历史版本，升级文档与脚本都应额外考虑下面几点：

1. 旧卷名可能带 compose 前缀，不能只匹配 `gitea`、`portainer`、`nginx_data`
2. 旧容器名可能是 `websoft9-portainer`、`websoft9-gitea`，而不是 `websoft9-git`、`websoft9-proxy`
3. 旧安装根可能是 `/data/apps/w9services`，而不是 `/data/websoft9/source`
4. 旧 NPM 数据可能位于前缀卷，例如 `w9nginxproxymanager_nginx_data`
5. 更老版本可能不是一个统一 compose 项目，而是多个独立组件目录分别 `docker compose up -d`

因此，升级实现不应只做“固定名字存在即迁移”，而应支持：

1. 从旧 compose 文件反查真实卷名
2. 从 `docker inspect` 或 `docker volume ls` 识别带前缀的卷
3. 对旧宿主机目录谱系做多版本兼容
4. 在升级验收中加入“业务数据是否仍存在”的显式检查

---

## 9. 推荐的文档与实现结论

在 install 目录内，应把“迁移”和“旧控制面卸载”明确拆开：

1. `install.sh` 负责安装、现代升级、legacy 迁移
2. 升级文档负责告诉用户旧 Cockpit/systemd 何时可以删
3. 回退窗口关闭前，不要默认删除旧控制面
4. 后续如果要做自动化清理，应该新增一个只清理 legacy 控制面的独立能力，而不是复用现代 uninstall 主流程

这份文档当前就是 install 目录内的操作基线。