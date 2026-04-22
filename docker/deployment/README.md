# Readme

From official Portainer image, and:

- Initialize username and password
- Initialize the local environment endpoint

## Single-Container Runtime Contract

Story 1.3 does not yet replace the current Portainer image flow, but it defines the future converged runtime contract in `single-container-runtime-skeleton.yaml`.

- Portainer remains a native process inside the future product container.
- Startup order, readiness role, and degraded-state expectations are declared in the runtime skeleton instead of staying implicit in compose wiring.
- The runtime bootstrap stub for Story 1.4 now lives in `../../scripts/platform-entrypoint.sh`.
- Story 1.4 should implement container startup behavior against that contract.
