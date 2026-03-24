# Story 1.6: 镜像安全扫描

**Epic**: Epic 1 - 基础架构与构建系统  
**优先级**: P2  
**状态**: Not Started

## User Story
作为安全工程师，我想要自动化的镜像安全扫描，这样可以及时发现并修复安全漏洞。

## 验收标准
- [ ] 集成 Trivy 镜像扫描
- [ ] CI Pipeline 自动扫描构建的镜像
- [ ] 高危漏洞（HIGH/CRITICAL）阻止发布
- [ ] 生成安全报告（HTML/JSON）
- [ ] 定期扫描已发布镜像（每周）
- [ ] `release-cve-check.yml` workflow 正常工作
- [ ] 漏洞修复流程文档

## 技术细节
**工具**: Trivy

**集成点**:
- `.github/workflows/docker.yml`
- `.github/workflows/release-cve-check.yml`

**配置**:
- 扫描时间 < 5分钟
- 支持离线扫描（中国网络）
- 漏洞数据库定期更新

## 测试
```bash
# 本地扫描测试
docker pull websoft9dev/apphub:latest
trivy image --severity HIGH,CRITICAL websoft9dev/apphub:latest
# 检查报告生成
trivy image -f json -o report.json websoft9dev/apphub:latest
```
