# Story 1.3: GitHub Actions CI/CD Pipeline

**Epic**: Epic 1 - 基础架构与构建系统  
**优先级**: P1  
**状态**: Not Started

## User Story
作为发布管理员，我想要自动化的镜像构建和发布流程，这样每次提交都能自动构建发布到 DockerHub。

## 验收标准
- [ ] **docker.yml**: 检测 Dockerfile 修改 → 自动构建推送
- [ ] **release.yml**: 检测 version.json → 构建所有组件 → 打 tag → 生成 Release
- [ ] **release_hotfix.yml**: 快速修复发布流程
- [ ] 构建失败通知（GitHub Notifications）
- [ ] 构建日志保存为 artifact
- [ ] 支持多架构构建（amd64/arm64）

## 技术细节
**Workflows**:
- `.github/workflows/docker.yml`
- `.github/workflows/release.yml`
- `.github/workflows/release_hotfix.yml`

**要求**:
- Docker Buildx 多平台构建
- DockerHub credentials 在 GitHub Secrets
- 构建时间 < 15分钟/镜像

## 测试
```bash
# 本地测试 workflow
act push -W .github/workflows/docker.yml
# 验证多架构构建
docker buildx build --platform linux/amd64,linux/arm64 -t test .
```
