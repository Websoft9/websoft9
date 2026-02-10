# Cockpit Base Image

这是 Websoft9 项目的 Cockpit 基础镜像，提供容器化的 Cockpit 服务。

## 特性

- 基于 Debian Bookworm Slim
- 包含 Cockpit 完整组件（ws, bridge）
- 内置默认管理员账户（websoft9/websoft9）
- 自定义配置（AllowUnencrypted, LoginTitle, ProtocolHeader）
- 自定义菜单（隐藏多语言选项，添加文档链接）
- 健康检查内置

## 构建

```bash
cd docker/cockpit
docker build -t websoft9dev/cockpit-base:297 .
```

## 测试

```bash
# 启动容器
docker run -d --name test-cockpit \
  --privileged \
  -v /run/systemd:/run/systemd:ro \
  -p 9091:9090 \
  websoft9dev/cockpit-base:297

# 等待启动
sleep 5

# 浏览器访问
# http://localhost:9091
# 用户名: websoft9
# 密码: websoft9

# 清理
docker stop test-cockpit && docker rm test-cockpit
```

### 用户管理

**默认账户**:
- 用户名: `websoft9`
- 密码: `websoft9`
- 权限: sudo (NOPASSWD)

**添加新用户** (通过 Cockpit Web 界面或命令行):
```bash
docker exec test-cockpit useradd -m -s /bin/bash newuser
docker exec test-cockpit bash -c "echo 'newuser:password' | chpasswd"
docker exec test-cockpit usermod -aG sudo newuser
```

## 版本

- Cockpit: 297 (Debian Bullseye 默认版本)
- 镜像大小: ~250-300MB

## 使用

此镜像作为基础镜像，供其他 Websoft9 服务（如 apphub）继承使用：

```dockerfile
FROM websoft9dev/cockpit-base:297
# 添加你的应用层...
```

## 配置文件

- `cockpit.conf`: Cockpit Web 服务配置
- `menu_override/*.override.json`: Cockpit UI 菜单覆盖配置
