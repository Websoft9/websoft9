# 分支保护与必过检查清单

创建时间：2026-06-05
状态：可实施
适用对象：仓库管理员、DevOps、发布负责人
所属阶段：Phase 5 仓库门禁执行包

## 1. 文档定位

这份文档将“分支保护”和“required checks”落成可执行清单。

它已经达到可实施状态：仓库管理员可以直接按本文配置 `main` / `dev` 的 ruleset 与 required checks。

默认按 GitHub 新版 `Settings -> Rules -> Rulesets` 界面编写。

它的目标不是解释理念，而是告诉仓库管理员：

1. 哪些分支要保护
2. 应该启用哪些保护项
3. 应该要求哪些检查通过

## 2. 保护目标

当前阶段必须重点保护两个分支：

1. `main`
2. `dev`

原因：

1. `main` 是正式发布基线
2. `dev` 是日常集成基线

## 3. 分支保护建议

建议优先使用 `branch ruleset`，分别保护：

1. `main`
2. `dev`

### 3.1 `main` 分支

推荐启用：

1. 禁止直接推送
2. 必须通过 Pull Request 合并
3. 至少 1 名评审通过
4. 必须通过 required checks
5. 禁止在有冲突时合并
6. 建议启用线性历史
7. 建议限制强制推送和删除分支

### 3.2 `dev` 分支

推荐启用：

1. 禁止普通开发者直接推送
2. 必须通过 Pull Request 合并
3. 至少 1 名评审通过
4. 必须通过 required checks
5. 禁止在有冲突时合并

## 4. required checks 设计原则

1. 尽量少而关键，不追求把每个 job 都列为 required
2. 优先要求“汇总门禁”而不是零散子检查
3. required check 必须稳定、名称固定、可长期维护
4. 对路径分流的可选 job，不建议直接全部列为 required

## 5. 当前阶段推荐 required checks

基于当前仓库流水线结构，推荐：

### `main` 和 `dev` PR 必过项

1. `PR Check Summary`

说明：

- 这是当前 PR 工作流中的汇总门禁
- 它已经聚合 secret scan、version consistency、python、console、cli、dockerfile、shellcheck，以及应用商店数据制品 smoke 校验的结果
- 使用汇总门禁可以避免把所有可选 job 都单独配置为 required checks
- 在 Rulesets 界面中，这条检查通常需要先在真实 PR 中跑出来一次，之后才能被选为 required status check

## 6. 可观察但暂不强制的检查

这些检查应该运行，但当前阶段不一定都配置为 required：

1. `Secret Scan`
2. `Version Consistency`
3. `Python CI`
4. `Console CI`
5. `CLI CI`
6. `Dockerfile Lint`
7. `ShellCheck`
8. `App Store Artifact CI`

原因：

1. 当前工作流存在路径分流
2. 某些 job 在无相关改动时会被跳过
3. 直接把全部 job 都配置为 required，容易在仓库设置层引入误阻断

## 7. 下一阶段 required checks 演进建议

当流水线进一步稳定后，可以考虑升级为：

1. 继续保留 `PR Check Summary`
2. 增加单独的安全门禁汇总项
3. 增加应用程序制品发布前校验门禁
4. 增加应用商店数据制品校验门禁

## 8. 仓库管理员执行清单

### 8.1 `main` 分支

- [ ] `Settings -> Rules -> Rulesets -> New branch ruleset`
- [ ] Target branches: `main`
- [ ] Require a pull request before merging
- [ ] Require approvals
- [ ] Dismiss stale approvals when new commits are pushed
- [ ] Require status checks to pass
- [ ] Required status check: `PR Check Summary`
- [ ] Require branches to be up to date before merging
- [ ] Block force pushes
- [ ] Restrict deletions 或 Block deletions

### 8.2 `dev` 分支

- [ ] `Settings -> Rules -> Rulesets -> New branch ruleset`
- [ ] Target branches: `dev`
- [ ] Require a pull request before merging
- [ ] Require approvals
- [ ] Require status checks to pass
- [ ] Required status check: `PR Check Summary`
- [ ] Require branches to be up to date before merging
- [ ] Block force pushes

## 9. 注意事项

1. required checks 名称必须与 GitHub Actions 中显示名称完全一致
2. 修改 workflow job 名称时，必须同步检查仓库保护设置
3. 如将来新增数据制品专用门禁，需要单独评估是否加入 required checks
4. 不要在尚未稳定的 job 上直接启用 required
5. 如果在 Rulesets 中搜不到 `PR Check Summary`，先创建一个普通 PR 到 `dev`，等检查真实出现后再回来选择

## 10. 当前结论

当前阶段最稳妥的做法是：

1. 先保护 `main` 和 `dev`
2. 先使用 `PR Check Summary` 作为唯一必过门禁
3. 待制品与数据治理工作流稳定后，再增加更细的 required checks
