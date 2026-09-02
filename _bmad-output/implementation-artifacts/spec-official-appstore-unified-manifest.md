---
title: '官方应用商店统一 Manifest'
type: 'refactor'
created: '2026-09-02'
status: 'done'
baseline_commit: '2fdc259b23d3efa0a3132a1377ce80d315720661'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/3-1-build-the-app-store-list-and-filters-page_cn.md'
  - '{project-root}/_bmad-output/implementation-artifacts/3-2-build-the-app-detail-and-install-parameters-page_cn.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 官方应用商店的展示信息位于 `product_{locale}.json`，而安装参数、profile 和帮助信息位于独立的 `app-store-install-metadata.json`；同时 API 在缓存失效后会再次读取并装配 Library 文件。两条数据路径容易字段不一致，且浏览请求有不必要的文件扫描。

**Approach:** 在官方 Media 与 Docker Library 已同步并激活后，预生成每种语言一份完整应用 manifest。AppHub API 和 Console 静态回退均读取完整 manifest；安装提交、最终 Library 校验和部署链保持原样。

## Boundaries & Constraints

**Always:** 保持 `POST /api/apps/install` 请求契约及 `install_validate`、安装跟踪、`AppManger.install_app` 的部署逻辑不变；`GET /api/apps/available/{locale}` 继续返回应用数组，不暴露 manifest 外层对象；manifest 只能包含展示和安装表单元数据，不能包含密码、已安装应用状态或用户数据；版本、settings、profile 仍以激活的官方 Docker Library 为权威来源；完整保留 `product_{locale}.json` 中的 `catalogBindings`、图标、截图与文案字段，只附加安装元数据；`initial_apps` 只在 API 返回层动态过滤，不裁剪 manifest；同步、历史数据集激活和新镜像启动必须通过唯一共享构建函数生成并校验完整 manifest 后原子发布；删除 `app-store-install-metadata.json` 及其所有生产、读取、下载、校验和回退逻辑；旧文件如残留于既有镜像或数据目录可保留，但运行时不得读取、更新或迁移它。

**Ask First:** 若需要修改公开 API 路径、安装请求 schema 或应用商店同步快照格式，必须先确认。

**Never:** 不实现本地/自定义应用来源，不改 Docker Compose 自定义部署，不改云市场向导流程，不改变已安装应用的 Gitea、Portainer、NPM、卷或升级/重部署行为，不将 manifest 作为安装执行的唯一事实来源。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| 官方资源同步成功 | 同一数据集的 Media 与 Library 可读 | 生成 `app-store-manifest_zh.json` 和 `app-store-manifest_en.json`；每项保留全部媒体展示字段，并含 `distribution`、`settings`、`is_web_app`、`profiles`、`help` | 生成失败时不替换现有有效 manifest |
| 资源数据不完整 | 媒体条目缺 Library 模板，或模板缺媒体条目 | 该应用不进入 manifest，构建日志记录应用 key 与缺失来源 | 不发布半完整应用；已有有效 manifest 保持可用 |
| 应用无有效版本 | `variables.json.edition` 缺失、类型错误或无可选版本 | 该应用不进入 manifest，构建日志记录应用 key 与版本错误 | 不让详情页展示无法提交的应用 |
| API 浏览 | manifest 存在且有效 | `/api/apps/available/{locale}` 仅读取 manifest 并应用 `initial_apps` 过滤 | manifest 缺失或无效时返回 `503` 与明确错误，不扫描 Library 作为隐式回退 |
| 静态回退 | API 临时不可用、静态 `/media/` 路径仍可用 | Console 读取同 locale 的完整 manifest，不再合并两个旧文件；单个文件足以渲染卡片、详情、版本和安装表单 | manifest 请求失败时保留既有页面错误状态 |
| 历史数据集激活 | `/api/appstore/activate` 切换 Media 与 Library | 在 staging 中准备候选 Media、Library 和 manifest，全部校验成功后才切换为当前版本 | 任一步失败时原激活版本保持不变，不能暴露跨数据集组合 |
| Websoft9 镜像升级或同步无变化 | 新镜像启动，或远端数据集未变化 | 从当前激活的官方 Media 与 Library 重建/校验 manifest；不依赖或读取旧安装元数据文件 | manifest 缺失、损坏或 schema 不兼容时自动重建；重建失败时 API 明确返回不可用状态且记录原因 |

</frozen-after-approval>

## Code Map

- `docker/scripts/platform-sync-runtime-assets.py` -- 官方 Media/Library 同步、staging/快照发布以及唯一 manifest 共享构建函数的归属点。
- `scripts/generate_appstore_install_metadata.py` -- 当前构建/CI 安装元数据生成器；本次应删除或替换为调用运行时脚本中的共享 manifest 构建函数，不能复制构建逻辑。
- `apphub/src/services/app_manager.py` -- `get_available_apps(locale)` 的应用浏览数据读取、`initial_apps` 过滤和缓存；也是安装时 Library 模板读取的归属点。
- `console/src/features/app-store/use-app-store-apps.ts` -- Console 的 API 首选与静态资源回退数据访问层。
- `apphub/src/services/appstore_sync_manager.py` -- 同步和历史数据集激活入口，需要在资源切换后触发 manifest 重建。
- `.github/workflows/ci-pr.yml`、上游/本地制品 manifest、构建脚本与面向用户/开发者文档 -- 旧安装元数据制品、协议、校验或说明的清理范围；不改写 `_bmad-output` 历史记录。
- `apphub/tests/`、`console/` 测试配置 -- 覆盖生成、API 和回退契约。

## Tasks & Acceptance

**Execution:**
- [x] `docker/scripts/platform-sync-runtime-assets.py` -- 定义唯一的共享 manifest 构建/发布函数；从 `product_{locale}.json` 与官方 Library 生成两份完整 manifest，完整保留媒体条目并跳过/记录缺模板、缺媒体或无有效版本的应用；校验 `key`、媒体字段、`distribution`、`settings`、`profiles` 类型；临时文件校验后原子替换；删除旧安装元数据的下载、生成和写入；即使同步判定资源无变化，也校验/重建当前 manifest。
- [x] `scripts/generate_appstore_install_metadata.py`、`.github/workflows/ci-pr.yml`、上游/本地制品 manifest 与面向用户/开发者文档引用 -- 删除旧安装元数据生成器、制品定义、上游协议字段、校验和引用，或将构建调用替换为唯一共享 manifest 构建入口，确保不再产出或请求 `app-store-install-metadata.json`；不修改 `_bmad-output` 历史文档。
- [x] `apphub/src/services/app_manager.py` -- 将浏览读取改为单个官方 manifest，保留 `initial_apps` 动态过滤；缓存依据 manifest 的 `mtime_ns` 和大小失效，而非固定 60 秒后重新扫描 Library；manifest 不可用时返回 `503`；安装校验和模板复制仍从官方 Library 读取。
- [x] `apphub/src/services/appstore_sync_manager.py` 与同步脚本调用边界 -- 同步、历史数据集激活和启动资源准备都使用同一共享构建函数；激活必须在 staging 中完成候选 Media、Library 和 manifest 的准备与校验后再提交，失败保留原激活数据集。
- [x] `console/src/features/app-store/use-app-store-apps.ts` -- 保持 API 优先；静态回退改为读取完整 manifest；删除对 `product_{locale}.json` 与 `app-store-install-metadata.json` 的合并读取，并保留现有错误状态。
- [x] `apphub/tests/` 与 `console/` 相邻测试 -- 覆盖 WordPress 的完整字段、`initial_apps` 过滤、manifest 更新后缓存失效、静态回退，以及 API/静态版本一致性。

**Acceptance Criteria:**
- Given 同步后的官方 WordPress Library 含 `variables.json.edition`、`.env` 与 `.env.external-db`, when 生成官方 manifest, then zh/en manifest 中同一应用同时包含本地化展示内容、版本、HTTP 端口、Web 标识、profile 和帮助信息。
- Given API 和静态回退使用相同的当前官方数据集, when 浏览同一 locale 的应用商店, then 两条路径返回的版本、安装参数和 profile 一致。
- Given `initial_apps` 被修改, when 调用应用列表 API, then 返回结果立即按配置过滤且不需要重建官方资源。
- Given `websoft9 upgrade apps`、`/api/appstore/sync`、`/api/appstore/activate` 或 Websoft9 新镜像启动成功, when 后续浏览请求到达, then 只会读取与激活 Media/Library 数据集一致的 manifest，且运行时不再依赖 `app-store-install-metadata.json`。
- Given manifest 文件被原子替换, when 随后的应用列表 API 请求到达, then API 基于新的文件版本重新加载而不等待固定 TTL。
- Given manifest 缺失、损坏或新 schema 无法从当前 Media/Library 重建, when 应用商店 API 被请求, then 返回明确的 `503` 错误而非空应用列表。
- Given 历史数据集的候选 manifest 无法构建或校验, when 请求激活该数据集, then 当前 Media、Library 和 manifest 均保持为原激活版本。
- Given API 不可用但静态媒体仍可访问, when Console 使用静态回退, then 单份同 locale manifest 足以呈现应用卡片、详情、版本和安装表单。
- Given 用户提交官方应用安装, when 后端执行安装, then 仍通过当前官方 Docker Library 校验、复制和部署模板，行为与本次改动前一致。

## Spec Change Log

## Design Notes

统一 manifest 是可再生运行时资产，而不是用户数据、持久化快照格式的一部分或安装模板。建议路径为：

```text
/websoft9/media/json/app-store-manifest_zh.json
/websoft9/media/json/app-store-manifest_en.json
```

正式同步的发布顺序：

```text
准备 staging 中的候选 Media + Library
-> 由唯一共享函数构建 zh/en 临时 manifest
-> schema、展示条目、版本与关联模板目录校验
-> 原子提交当前数据集与正式 manifest
-> 使 AppHub 浏览缓存失效
```

安装阶段保留双重边界：manifest 决定展示和表单；`install_validate()` 与 `AppManger.install_app()` 决定最终事实，并继续访问 Library。`app-store-install-metadata.json` 是本次明确删除的过渡结构；平台升级不迁移它，既有残留文件也不处理，新镜像即使未同步到新数据集也会使用当前激活的 Media/Library 校验或重建 manifest。静态回退要求 `/media/` 路径由网关直接服务，不依赖 AppHub API。

## Verification

**Commands:**
- `cd apphub && pytest -q <新增或相邻的应用商店测试>` -- expected: manifest 生成、过滤、失效和安装 Library 校验通过。
- `cd console && npm run typecheck` -- expected: 静态回退与应用模型类型通过。
- `cd console && npm run build` -- expected: Console 可正常构建。
- `python -m py_compile docker/scripts/platform-sync-runtime-assets.py` -- expected: 唯一 manifest 生成脚本无语法错误。
- `grep -R "app-store-install-metadata.json" docker scripts .github console apphub docs` -- expected: 仅允许测试中的负向断言；无生产读取、生成、下载、制品或文档引用。
- `<激活失败的聚焦测试>` -- expected: staging manifest 构建失败时，当前 Media、Library 和 manifest 的内容均不变。

**Manual checks (if no CLI):**
- 同步、同步无变化、历史数据集激活和容器重启后读取两份 manifest，确认 WordPress 同时具备 `catalogBindings`、`distribution`、`W9_HTTP_PORT_SET`、`external-db` profile 与展示字段；在 API 不可用但 `/media/` 可用时，确认 Console 静态回退呈现相同安装选项。

## Suggested Review Order

**构建与发布一致性**

- 统一生成双语言 manifest，并在失败时恢复活跃资源。
  [platform-sync-runtime-assets.py:1027](../../docker/scripts/platform-sync-runtime-assets.py#L1027)

- 同步入口拒绝单包更新，避免 Media 与 Library 跨数据集组合。
  [platform-sync-runtime-assets.py:1164](../../docker/scripts/platform-sync-runtime-assets.py#L1164)

**浏览与激活边界**

- 浏览 API 只读取并校验完整 manifest，安装仍保留 Library 权威。
  [app_manager.py:617](../../apphub/src/services/app_manager.py#L617)

- 历史数据集先构建候选 manifest，再切换并在失败时恢复目录。
  [appstore_sync_manager.py:178](../../apphub/src/services/appstore_sync_manager.py#L178)

- Console API 优先，静态回退只读取同语言完整 manifest。
  [use-app-store-apps.ts:34](../../console/src/features/app-store/use-app-store-apps.ts#L34)

**验证与清理**

- 覆盖 WordPress 完整安装表单元数据及发布失败保留旧 manifest。
  [test_appstore_manifest_builder.py:33](../../apphub/tests/test_appstore_manifest_builder.py#L33)

- 覆盖历史数据集切换期间的目录恢复。
  [test_appstore_sync_manager_versions.py:129](../../apphub/tests/test_appstore_sync_manager_versions.py#L129)

- 删除旧生成器及 CI/校验中的旧 metadata 制品契约。
  [ci-pr.yml:1](../../.github/workflows/ci-pr.yml#L1)