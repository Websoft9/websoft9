# Story 1.4: Makefile 命令集成

**Epic**: Epic 1 - 基础架构与构建系统  
**优先级**: P2  
**状态**: Not Started

## User Story
作为开发者，我想要简化的命令行工具，这样不需要记住复杂的 docker-compose 命令。

## 验收标准
- [ ] 创建根目录 `Makefile` 包含核心命令
- [ ] 每个命令有简短帮助文本
- [ ] `make help` 显示所有命令
- [ ] 支持参数传递（如 `make dev SERVICE=apphub`）
- [ ] 兼容 Linux/macOS

## 技术细节
**核心命令**:
```makefile
make dev          # 启动开发环境
make dev-build    # 重新构建开发镜像
make dev-logs     # 查看所有服务日志
make dev-down     # 停止并清理
make test         # 运行测试
make lint         # 代码检查
make format       # 代码格式化
make clean        # 清理缓存
make release      # 本地构建生产镜像
```

**涉及文件**:
- `Makefile` (新建)

## 测试
```bash
make help
make dev
make dev-logs SERVICE=apphub
make clean
```
