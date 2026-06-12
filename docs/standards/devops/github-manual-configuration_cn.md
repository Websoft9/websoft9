# GitHub 仓库手工配置清单

创建时间：2026-06-05
状态：可实施
适用对象：仓库管理员、DevOps、发布负责人
所属阶段：Phase 5 平台侧手工配置执行包

## 1. 文档定位

这份清单只解决一个问题：

当前仓库里已经落地了一批 workflow、门禁和发布规则，但其中仍有一部分必须在 GitHub 仓库设置页面手工完成。

这份文档把这些必须手工配置的项整理成可直接执行的操作清单。

它已经达到可实施状态：仓库管理员可以直接按本文在 GitHub 后台完成 Rulesets、Secrets、Pages 与手工核对。

## 2. 配置优先级

建议按下面顺序完成：

1. 先配 Branch Protection
2. 再配 Repository Secrets
3. 再配 GitHub Pages
4. 最后做一次手工核对

## 3. Branch Protection

进入：`Settings -> Rules -> Rulesets`

说明：

当前 GitHub 新界面默认推荐使用 `Rulesets`，而不是旧的 `Settings -> Branches -> Branch protection rules`。

建议：

1. 为 `main` 新建一个 `branch ruleset`
2. 为 `dev` 新建一个 `branch ruleset`
3. 不建议一开始把多个核心分支混在同一个 ruleset 中，避免排查困难

### 3.1 `main`

至少配置：

- [ ] New branch ruleset，目标分支选择 `main`
- [ ] Require a pull request before merging
- [ ] Require approvals
- [ ] Dismiss stale approvals when new commits are pushed
- [ ] Require status checks to pass
- [ ] Required status check: `PR Check Summary`
- [ ] Require branches to be up to date before merging
- [ ] Block force pushes
- [ ] Restrict deletions 或 Block deletions

### 3.2 `dev`

至少配置：

- [ ] New branch ruleset，目标分支选择 `dev`
- [ ] Require a pull request before merging
- [ ] Require approvals
- [ ] Require status checks to pass
- [ ] Required status check: `PR Check Summary`
- [ ] Require branches to be up to date before merging
- [ ] Block force pushes

### 3.3 `PR Check Summary` 为什么有时搜不到

在 Rulesets 界面里，`Required status checks` 往往只会显示“最近真实跑出来过的检查名”。

如果你暂时搜不到 `PR Check Summary`，通常不是配置项不存在，而是：

1. 当前仓库还没有一条最近的 PR 真实跑出这个检查
2. 当前目标分支上还没有出现过这条检查记录

建议处理顺序：

1. 先创建一个普通 PR 到 `dev`
2. 等 `.github/workflows/ci-pr.yml` 跑完
3. 在 PR 页面确认已经出现 `PR Check Summary`
4. 再回到 Ruleset 里添加这条 required status check

### 3.4 `Block force pushes` 在哪里

在 Rulesets 界面里，这一项通常就直接叫：

1. `Block force pushes`

如果你没有看到它，优先检查：

1. 你创建的是不是 `branch ruleset`
2. 规则列表是否已全部展开
3. 当前页面是不是仓库级 `Rulesets`，而不是旧的 `Branches` 页面

## 4. Repository Secrets

进入：`Settings -> Secrets and variables -> Actions`

### 4.1 必需 Secrets

这些不配置，对应 workflow 就无法正常工作：

| Secret | 用途 | 关联 workflow |
|---|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare R2 上传 | `release.yml` |
| `CLOUDFLARE_R2_SECRET_ID` | Cloudflare R2 Access Key | `release.yml` |
| `CLOUDFLARE_R2_SECRET_KEY` | Cloudflare R2 Secret Key | `release.yml` |
| `CLOUDFLARE_ZONE_ID` | Cloudflare Cache Purge | `release.yml` |
| `CLOUDFLARE_API_TOKEN` | Cloudflare Cache Purge | `release.yml` |
| `DOCKER_USERNAME` | 推送 Docker 镜像 | `ci-main.yml` |
| `DOCKER_PASSWORD` | 推送 Docker 镜像 | `ci-main.yml` |

### 4.2 推荐 Secrets

这些不配置不会阻断全部流程，但对应能力会降级：

| Secret | 用途 | 关联 workflow |
|---|---|---|
| `GITLEAKS_LICENSE` | Secret Scan 授权 | `ci-pr.yml` |
| `CODECOV_TOKEN` | 覆盖率上报 | `ci-pr.yml` |
| `WIXIN_ROBOT_KEY` | 企业微信通知 | `release.yml` |

## 5. Actions 设置

进入：`Settings -> Actions -> General`

建议确认：

- [ ] Allow all actions and reusable workflows，或至少允许当前仓库已用到的官方/第三方 actions
- [ ] Workflow permissions 允许 `Read repository contents permission`

说明：

- `release.yml` 中自动创建 hotfix 分支的 job 已经显式声明 `contents: write`，不再依赖仓库默认写权限
- 但如果仓库整体禁用第三方 actions，当前 CI/CD 仍会失败，因为使用了 `dorny/paths-filter`、`ryand56/r2-upload-action`、`softprops/action-gh-release` 等 action

## 6. GitHub Pages

进入：`Settings -> Pages`

建议确认：

- [ ] Source 使用 GitHub Actions

说明：

- `release.yml` 在正式发布通道会执行 `configure-pages`、`upload-pages-artifact`、`deploy-pages`
- 如果 Pages 未启用为 GitHub Actions，正式版页面发布链会失败

## 7. Environment 与权限核对

进入：`Settings -> Environments`

当前阶段建议：

- [ ] 若存在 `github-pages` environment，确认未配置会阻断自动发布的额外审批规则
- [ ] 若仓库对部署环境启用了保护，需确保发布负责人在批准范围内

## 8. 手工验收步骤

全部配置完成后，建议按顺序核对：

1. 新建一个普通 PR 到 `dev`，确认 `PR Check Summary` 出现
2. 回到 `Rulesets`，将 `PR Check Summary` 加入 `main` 和 `dev` 的 required status checks
3. 确认 `main` / `dev` 的 ruleset 都已生效
3. 手动打开 Actions 页面，确认 workflow 没有因为缺 secret 报错
4. 如需验证应用商店数据发布，请在 `docker-library` 仓库执行对应的 appstore 发布 workflow
5. 手动执行一次 `release.yml` 的正式发布链路做冒烟验证

## 9. 当前结论

当前仓库内的大部分治理逻辑已经在代码中落地，但下面这些仍然必须人工完成：

1. `main` / `dev` 分支保护
2. required check 配置
3. Cloudflare / Docker / 通知类 secrets
4. GitHub Pages 发布来源配置

如果这些项没有配置完整，即使仓库中的 workflow 文件已经存在，也不能视为整套治理真正上线。