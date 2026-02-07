# Story 1.5: 版本管理规范化

**Epic**: Epic 1 - 基础架构与构建系统  
**优先级**: P2  
**状态**: Not Started

## User Story
作为项目维护者，我想要清晰的版本管理策略，这样用户可以明确知道每个版本的变更和兼容性。

## 验收标准
- [ ] `version.json` 包含所有组件版本（core, apphub, deployment, git, proxy, media, library）
- [ ] 版本号遵循 SemVer（主.次.补丁）
- [ ] `CHANGELOG.md` 自动生成（Features/Fixes/Breaking Changes）
- [ ] Release notes 包含 Docker tag、安装命令、已知问题
- [ ] 版本兼容性矩阵文档

## 技术细节
**version.json 示例**:
```json
{
  "core_version": "2.0.3",
  "apphub_version": "0.2.6",
  "deployment_version": "2.20.0",
  "git_version": "1.21.0",
  "proxy_version": "2.11.0",
  "media_version": "0.1.1",
  "library_version": "0.7.3"
}
```

**规范**:
- Conventional Commits
- GitHub Actions 自动生成 CHANGELOG

**涉及文件**:
- `version.json`
- `CHANGELOG.md`
- `.github/workflows/release.yml`

## 测试
```bash
# 验证 version.json 格式
cat version.json | jq .
# 检查 CHANGELOG 生成
git log --oneline --pretty=format:"%s"
```
