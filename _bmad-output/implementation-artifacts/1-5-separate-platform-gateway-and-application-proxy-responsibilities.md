# Story 1.5: Separate Platform Gateway and Application Proxy Responsibilities

## Status

done

## Story

As a platform administrator,
I want the platform gateway and application proxy responsibilities to stay separate even in one-container delivery,
so that platform entry, internal services, and user application access do not collapse into one proxy model.

## Acceptance Criteria

1. Websoft9 product entry and internal-service routing are clearly separated from user application domain routing.
2. The model remains compatible with future physical split deployment.
3. NPM continues to own application-domain access logic in MVP.
4. Platform traffic and application traffic remain logically distinct.

## Dependencies

- Story 1.4 should provide a running converged container baseline.

## Previous Story Intelligence

- Stories 1.3 and 1.4 establish the runtime and startup layer; this story must add responsibility boundaries, not create a new topology.
- Future integration workspaces depend on a clean platform routing boundary.

## Developer Context

- Architecture explicitly requires platform gateway concerns and app-access concerns to remain separate.
- MVP can enforce this boundary inside the retained gateway plus NPM topology; physical separation is deferred.
- Third-party embedded workspaces and platform shell routing both depend on preserving a product-owned origin boundary.

## Implementation Guardrails

- Do not collapse platform entry routing and app-domain routing into one undifferentiated proxy rule set.
- Do not break the current assumption that NPM still handles user app domains in MVP.
- Keep the design future-splittable: responsibilities must stay separable even if processes are packaged together.
- Make the ownership of internal service routes explicit.

## Suggested File Targets

- `docker/proxy/`
- `docker/docker-compose*.yml`
- platform proxy config and any route-mapping artifacts
- integration-facing notes if additional product-origin paths are introduced

## Implementation Tasks

1. Define the platform routing boundary for Websoft9 entry and internal services.
2. Define the app-access boundary that remains under NPM ownership.
3. Encode or document route ownership so future embedded integrations do not bypass the boundary.
4. Validate that the design can later be physically split without semantic rework.

## Testing Requirements

- Verify platform routes and app routes resolve through different logical responsibilities.
- Verify NPM continues to own app-domain behavior in MVP.
- Verify the boundary is understandable enough to support later embedded integrations and proxy-sensitive features.

## Definition of Done

- Platform and app-access routing responsibilities are explicitly separated.
- The MVP retained topology still works.
- The design is future-compatible with a physical split.
- Epic 2 can build embedded third-party continuity on a stable routing boundary.

## Source Notes

- Primary sources: Epic 1, architecture proxy responsibility model, gateway split implementation sequence.

## Dev Agent Record

### Debug Log

- Split the product-origin proxy definition so `initproxy.conf` now acts as a thin default-host shell that includes an explicit platform gateway boundary file plus a dedicated platform route file.
- Added `platform-gateway-boundary.conf` to declare Websoft9 product-origin ownership and reserve the platform prefixes `/`, `/api/`, `/media/`, `/w9deployment/`, `/w9proxy/`, and `/w9git/` away from application-domain proxying.
- Moved the actual product-entry and internal-service route blocks into `platform-gateway-routes.conf`, keeping the existing routing behavior while making the platform/app-access split readable and future-splittable.
- Updated container build assets and NPM init logic so the new split route file receives the same `DOCKER0_IP` replacement and single-container loopback upstream rewrites as the legacy monolithic template.
- Fixed one local regression during validation: the extracted route file initially kept unresolved template placeholders, then platform boundary headers were restored inside locations that define their own `add_header` directives.
- Rebuilt the converged product image and revalidated readiness plus platform-origin ownership headers from the running Story 1.5 smoke container.
- Added the missing `docker/product/gateway/` runtime config set plus `platform-start-gateway.sh`, so the single-container product now runs a dedicated gateway nginx process under supervisord instead of relying on the NPM default-host runtime to impersonate physical separation.

### Completion Notes

- Story 1.5 acceptance criteria are satisfied: Websoft9 product entry and internal-service routes now live in a clearly separated platform gateway configuration layer, while user application-domain proxying remains under Nginx Proxy Manager proxy-host ownership.
- The retained MVP topology still keeps one container, but product-origin ingress now runs in its own gateway nginx process under supervisord instead of staying inside the NPM default-host runtime.
- Platform-origin responses now expose route-ownership headers, making the boundary visible to later embedded integrations and proxy-sensitive features.
- Final validation succeeded with `platform-healthcheck.sh --readiness` returning `status=ready`, and a platform-origin request to `/w9proxy/` returning the expected `X-Websoft9-Route-Owner`, `X-Websoft9-App-Access-Owner`, and reserved-prefix headers.

### File List

- docker/product/Dockerfile
- docker/product/README.md
- docker/product/gateway/default.conf
- docker/product/gateway/nginx.conf
- docker/product/gateway/platform-gateway-boundary.conf
- docker/product/gateway/platform-gateway-routes.conf
- docker/proxy/Dockerfile
- docker/proxy/README.md
- docker/proxy/config/initproxy.conf
- docker/proxy/config/platform-gateway-boundary.conf
- docker/proxy/config/platform-gateway-routes.conf
- docker/proxy/init_nginx.sh
- docker/product/scripts/platform-start-gateway.sh

### Change Log

- 2026-04-22: separated the platform gateway boundary from application-domain proxy ownership for Story 1.5.
- 2026-04-22: updated proxy build assets and startup rewrites so the split route files work in the converged single-container runtime.
- 2026-04-22: completed smoke validation with readiness green and explicit platform-boundary headers; story moved to done.
