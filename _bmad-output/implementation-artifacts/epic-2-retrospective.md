# Epic 2 Retrospective: Embedded Workspaces and Session Continuity Closeout

## Status

done

## Scope Closed

- Story 2.1: integration workspace entry cards and shell route mounts
- Story 2.2: Gitea embedded workspace and session continuity
- Story 2.3: Portainer embedded workspace and session continuity
- Story 2.4: Nginx Proxy Manager embedded workspace and session continuity
- Story 2.5: shared degraded-state and failure contract across integrations

## What Went Well

- Epic 2 kept the user-facing migration incremental. Repository, containers, and gateway access moved under the new Websoft9 shell without forcing an immediate native replacement of third-party UIs.
- The team converged on one product-owned workspace model for all three integrations, which reduced route drift and kept failure handling consistent.
- The final integration pattern proved that frontend shell continuity and backend session brokerage can stay decoupled: the console owns the workspace surface, while AppHub and the product gateway own session establishment and auth bridging.
- The shared state taxonomy from Story 2.5 held up under real fixes. Loading, available, unavailable, configuration-error, and session-error remained usable across cards and embedded workspace routes.
- The Portainer recovery work improved not just the UI path but the runtime truth. Fixing the upstream route, JWT-to-Bearer bridge, and local endpoint bootstrap removed a real operational gap rather than masking it in the shell.

## Issues Found During Closeout

- The first Portainer issue looked like an embed problem, but the controlling failures were split across multiple layers: the wrong `/w9deployment/` upstream, missing API auth forwarding, and missing `/var/run/docker.sock` for local endpoint creation.
- Gitea continuity initially failed because the login flow crossed an internal proxy hop that rewrote cookie paths incorrectly for the product-owned `/w9git` route.
- Layout polish for third-party workspaces initially drifted toward visual cropping, which hid real page edges instead of solving the embedding fit problem.
- BMAD implementation artifacts drifted behind runtime truth during the live-fix phase, so story status and sprint status had to be synchronized explicitly at closeout.

## Carry-Forward Decisions

- Keep product-owned reserved routes as the only supported entry pattern for third-party full-UI continuity inside Websoft9.
- Keep session continuity backend-controlled. Do not move Gitea, Portainer, or NPM auth brokerage into frontend-only logic.
- Treat iframe embedding as a containment strategy, not as proof that upstream UI, auth, or runtime issues are solved.
- Preserve the shared integration-state taxonomy and recovery vocabulary as the contract for later observability and native replacement work.
- Treat `/var/run/docker.sock` as a required runtime dependency whenever Portainer is expected to auto-create and manage the local Docker environment inside the converged product container.

## Validation Summary

- Epic 2 story closeout validated the console shell changes repeatedly with focused frontend builds and linting.
- Gitea closeout validated that the repository workspace bootstrap returns normalized `/w9git` cookies, preserves auto-login, and synchronizes the embedded locale with the Websoft9 shell.
- NPM closeout validated that the gateway workspace opens through the direct embedded route at `/w9proxy/nginx/proxy-hosts` and stays inside the shared continuity model.
- Portainer closeout validated that `/w9deployment/` serves the Portainer UI, `/w9deployment/api/*` accepts the browser session through the JWT-to-Bearer bridge, and the live API reports a restored `local` endpoint.
- Epic 2 closeout also verified that the shared failure contract still applies after repository, containers, and gateway became first-class shell entries.

## Residual Risks

- Epic 2 still depends on Epic 3 and later work for native replacement of high-frequency repository, container, and proxy-management flows; current continuity still relies on third-party UIs inside product-owned workspaces.
- Embedded third-party pages can still surface layout changes or upstream UI regressions after vendor updates, so executable validation should remain the default after runtime or proxy changes.
- The current pattern now depends on route, cookie, and gateway ownership staying aligned. Future changes to reserved paths or internal upstreams should be treated as integration-contract changes, not as isolated config tweaks.

## Next Epic Preparation

- Epic 3 should treat the Epic 2 shell routes as stable anchors: `appstore`, `myapps`, `gateway`, `repository`, `containers`, `files`, `terminal`, `services`, `logs`, `users`, and `settings` already define the navigation frame that new native pages must fit.
- Native App Store and My Apps work should not break the established embedded-workspace routes. The third-party workspaces remain part of the operator workflow during the migration period.
- Future product settings and application-access work should reuse the same product-origin boundary discipline proven in Epic 2 rather than introducing raw direct-port shortcuts.
- Story planning for Epic 3 should assume that failure surfaces, retry affordances, and diagnostics entry points already exist as a shared pattern and should be extended rather than reinvented.

## Result

Epic 2 is ready to remain marked done. The Websoft9 shell now owns stable third-party workspace entry, session continuity, and explicit degraded-state handling for Gitea, Portainer, and Nginx Proxy Manager, and the closeout fixes resolved the highest-risk runtime gaps instead of leaving them hidden behind the embed layer.