# Story 1.1: Container Build & Deployment

**Epic**: Epic 1 - Infrastructure & Build System  
**Priority**: P0  
**Status**: Ready for Dev

---

## User Story

As a developer, I need to verify and standardize the existing container build configuration (`build/` directory) to ensure the All-in-One container solution can be quickly built, started, and run all services correctly.

## Config Verification (Existing Implementation)

**Core Config (`build/`)**:
- `docker-compose.yml`: Single service `websoft9`, environment variable driven, minimal configuration.
- `Dockerfile`: Multi-stage build (Base -> Builder -> Convex/Portainer -> Final).
- `supervisord.conf`: 7 services orchestration (dbus, sshd, cockpit-ws, portainer, gitea, nginx, convex).

## Acceptance Criteria

- [ ] `make build` successfully builds `websoft9:latest` image
- [ ] `make start` successfully starts the container with health check status as healthy
- [ ] All 7 services have RUNNING status in Supervisor
- [ ] Nginx correctly routes the following paths:
  - `/` (Dashboard)
  - `/baas/` (Convex)
  - `/cockpit/` (Cockpit)
  - `/w9git/` (Gitea)
  - `/w9deployment/` (Portainer)
  - `/w9media/` (Static resources)
  - `/health` → returns 200
- [ ] Data persistence verification: `/websoft9/data` data retained after container destroy and recreate

## Tasks

- [ ] **Task 1: Configuration Audit**
  - Verify `build/docker-compose.yml` is single-service minimal mode
  - Verify `build/Dockerfile` uses multi-stage build optimization
  - Check `.env` contains all variables: `CONTAINER_NAME`, `HTTP_PORT`, `IMAGE_TAG`, `WEBSOFT9_DATA_PATH`, `RESTART_POLICY`, `ADMIN_USER`, `ADMIN_PASSWORD`

- [ ] **Task 2: Build & Run Verification**
  - Execute `make build-base && make build` to verify build process
  - Execute `make start` to verify container startup and port mapping (default 9091)
  - Execute `docker exec websoft9 supervisorctl -c /etc/supervisor/supervisord.conf status` to confirm all services RUNNING

- [ ] **Task 3: Functional & Persistence Test**
  - Browser access Dashboard and all sub-service paths to verify connectivity
  - Verify Gitea/Portainer data is not lost after container restart

- [ ] **Task 4: Documentation**
  - Update `build/README.md`: include build, startup, environment variables instructions

## Dev Notes

- **Architecture**: Single Container (All-in-One), Supervisor managed, Nginx ingress.
- **Constraints**: Same-origin policy requires Cockpit and Dashboard on same domain; all data mounted at `/websoft9/data`.
- **Key Files**: `docker-compose.yml`, `Dockerfile`, `supervisord.conf` in `build/` directory.

---

## Dev Agent Record
_To be filled by developer_

## File List
_To be updated by developer_

## Change Log
_To be recorded by developer_

## Status
**Current**: Ready for Dev
**Last Updated**: 2026-02-11
