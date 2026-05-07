---
title: 'Story 3.8: Consolidate integration credential source of truth'
type: 'feature'
created: '2026-05-07'
status: 'done'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/3-7-build-product-settings-and-the-sensitive-configuration-baseline.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Gitea, Portainer, and Nginx Proxy Manager initialization credentials already exist in runtime credential files under `/data`, but AppHub and runtime sync scripts were still mirroring the same usernames and passwords back into `config.ini`. That created duplicate storage, widened the sensitive-data surface, and made it unclear which location is the real source of truth.

**Approach:** Keep the runtime credential files as the only authoritative source for integration usernames and passwords. Introduce one shared AppHub provider that reads those files first and only falls back to `config.ini` for legacy tolerance. Then migrate current AppHub callers to the shared provider, move integration API base URLs to runtime defaults with safe fallback behavior, and remove the legacy `gitea`, `portainer`, and `nginx_proxy_manager` sections from `config.ini` entirely.

## Boundaries & Constraints

**Always:** Treat `/data/gitea/credential`, `/data/portainer/credential`, and `/data/nginx-proxy-manager/credential.json` as the source of truth; keep current integration flows working without requiring a database migration; preserve `GET /api/settings` compatibility after the legacy integration sections are removed; keep the credential-provider logic centralized.

**Ask First:** Moving integration credentials into a database; redesigning the settings contract to remove the legacy credential fields entirely; rotating runtime credentials as part of this slice; changing third-party account bootstrap semantics.

**Never:** Keep writing live integration passwords back into `config.ini`; scatter new direct reads of runtime credential files across more services; break bulk integration bootstrap, direct-login continuity, or current runtime startup.

</frozen-after-approval>

## Code Map

- `apphub/src/services/integration_credentials.py` -- new shared provider for Gitea, Portainer, and NPM runtime credentials.
- `apphub/src/services/integration_session_bridge.py` -- browser session bootstrap should reuse the shared provider instead of reading files or `config.ini` directly.
- `apphub/src/external/gitea_api.py` and `apphub/src/external/portainer_api.py` -- external API helpers should pull usernames/passwords from the provider.
- `apphub/src/services/gitea_manager.py`, `apphub/src/services/proxy_manager.py`, `apphub/src/services/git_manager.py`, `apphub/src/services/app_manager.py`, and `apphub/src/cli/apphub_cli.py` -- current AppHub callers that previously depended on mirrored config credentials.
- `docker/product/scripts/platform-sync-config.sh` and `scripts/platform-sync-config.sh` -- runtime sync layer that previously wrote real integration credentials back into `config.ini`.
- `apphub/src/services/settings_manager.py` and `apphub/src/schemas/appSettings.py` -- settings compatibility boundary that must stop requiring the legacy integration sections before `config.ini` can drop them.

## Tasks & Acceptance

**Execution:**
- [x] Add a shared integration credential provider in AppHub with file-first and config-fallback behavior.
- [x] Migrate current AppHub Gitea, Portainer, and NPM credential readers to the provider.
- [x] Stop runtime sync scripts from mirroring real integration usernames and passwords into `config.ini`.
- [x] Remove the legacy `gitea`, `portainer`, and `nginx_proxy_manager` sections from `config.ini` and prevent runtime sync from recreating them.
- [x] Add focused regression tests for provider behavior and validate touched backend/runtime files.
- [x] Hot-sync the slice into the running product container and validate live runtime behavior.

**Acceptance Criteria:**
- Given runtime credential files exist, when AppHub needs Gitea, Portainer, or NPM credentials, then it reads them through one shared provider instead of scattered direct `config.ini` lookups.
- Given runtime config sync runs, when `config.ini` is updated, then the legacy `gitea`, `portainer`, and `nginx_proxy_manager` sections are not recreated.
- Given the product is running live, when `/api/settings` and `/api/integrations/session` are called, then both still succeed after the source-of-truth consolidation.

## Spec Change Log

- 2026-05-07: Story created to make runtime credential files the single source of truth for Gitea, Portainer, and NPM integration credentials while keeping settings compatibility.
- 2026-05-07: Completed provider migration, removed the legacy integration sections from `config.ini`, updated sync behavior so they stay deleted, and revalidated live runtime behavior.

## Verification

**Commands:**
- `cd /workspace/websoft9/apphub && pytest -q -o addopts='' tests/test_integration_credentials.py`
- `cd /workspace/websoft9/apphub && python3 -m py_compile src/services/integration_credentials.py src/services/integration_session_bridge.py src/external/gitea_api.py src/external/portainer_api.py src/services/gitea_manager.py src/services/proxy_manager.py src/services/git_manager.py src/services/app_manager.py src/cli/apphub_cli.py`
- `bash -n /workspace/websoft9/docker/product/scripts/platform-sync-config.sh && bash -n /workspace/websoft9/scripts/platform-sync-config.sh`
- `cd /workspace/websoft9 && ./scripts/sync_websoft9_product_current.sh`
- `docker exec websoft9-product-current python3 -c "import configparser; c=configparser.ConfigParser(); c.read('/websoft9/apphub/src/config/config.ini', encoding='utf-8'); print(c.has_section('gitea')); print(c.has_section('portainer')); print(c.has_section('nginx_proxy_manager'))"`
- `docker exec websoft9-product-current python3 -c "import json, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:9000/api/settings'); p=json.load(r); print(r.status); print(sorted(p.keys()))"`
- `docker exec websoft9-product-current python3 -c "import json, urllib.request; req=urllib.request.Request('http://127.0.0.1:9000/api/integrations/session', data=json.dumps({'locale':'en'}).encode(), headers={'Content-Type':'application/json'}, method='POST'); print(urllib.request.urlopen(req).status)"`

## Dev Agent Record

### Agent Model Used

GPT-5.4

### Completion Notes List

- Added `IntegrationCredentialProvider` so AppHub now resolves Gitea, Portainer, and NPM credentials from the runtime credential files first and only falls back to `config.ini` for legacy tolerance.
- Migrated all known AppHub call sites in this slice away from direct mirrored credential reads.
- Changed both runtime sync scripts so they no longer recreate the legacy `gitea`, `portainer`, and `nginx_proxy_manager` sections in `config.ini`.
- Moved integration API base URL resolution to runtime defaults with missing-section-safe fallback behavior so AppHub no longer depends on those three config sections.
- Added focused provider tests for file-first and config-fallback behavior.
- Live runtime validation confirmed the three legacy integration sections were absent from `config.ini`, while `GET /api/settings` and `POST /api/integrations/session` both continued to return 200 inside the running product container.

### File List

- _bmad-output/implementation-artifacts/3-8-consolidate-integration-credential-source-of-truth.md
- _bmad-output/implementation-artifacts/3-8-consolidate-integration-credential-source-of-truth_cn.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- apphub/src/services/integration_credentials.py
- apphub/src/services/integration_session_bridge.py
- apphub/src/external/gitea_api.py
- apphub/src/external/nginx_proxy_manager_api.py
- apphub/src/external/portainer_api.py
- apphub/src/services/gitea_manager.py
- apphub/src/services/proxy_manager.py
- apphub/src/services/git_manager.py
- apphub/src/services/app_manager.py
- apphub/src/cli/apphub_cli.py
- apphub/tests/test_integration_credentials.py
- apphub/src/config/config.ini
- docker/product/scripts/platform-sync-config.sh
- scripts/platform-sync-config.sh

### Change Log

- 2026-05-07: Story created and implemented.
- 2026-05-07: Validated with targeted tests, backend compile checks, shell script syntax checks, live hot-sync, and live internal API probes.
- 2026-05-07: Follow-up convergence removed the legacy `gitea`, `portainer`, and `nginx_proxy_manager` sections from `config.ini`, updated runtime sync to keep them deleted, and confirmed live continuity.