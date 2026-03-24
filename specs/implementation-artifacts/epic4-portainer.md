# Epic 4: Portainer SSO Integration

## Goal

Implement Portainer plugin as a Cockpit module with Single Sign-On (SSO) capability, enabling seamless navigation from Cockpit to Portainer without manual authentication.

## Scope

- Portainer plugin foundation and integration
- SSO authentication flow implementation
- Authentication token management and transmission
- Session management and security
- Configuration persistence

## Success Criteria

- Portainer plugin successfully integrated into Cockpit interface
- Users automatically authenticated when accessing Portainer (no manual credentials required)
- Authentication tokens securely generated and managed
- Smooth transition flow with good user experience
- Proper handling of session expiration
- Configuration persists across container restarts
- Complies with security best practices

## Dependencies

- Epic 1: Infrastructure & Build System
- Epic 3: Cockpit Customization
- Portainer service running

## Stories

- 4.1: Plugin Foundation & Build System
- 4.2: SSO Authentication & Navigation (merged from 4.2 + 4.3)
- 4.3: Session Management & Security (renumbered from 4.4)
- 4.4: Configuration Management (renumbered from 4.5)
- 4.5: User Experience Optimization (renumbered from 4.6)
- 4.6: Testing & Documentation (renumbered from 4.7)

## Technical Notes

### Tech Stack
- React 18+
- Portainer API (authentication & session management)
- Cockpit SDK
- Webpack/Create React App
- JavaScript/TypeScript
- JWT or API Key authentication

### SSO Implementation Approaches
1. **Backend Proxy**: Proxy Portainer requests through Cockpit backend to hide auth details
2. **JWT Token Passing**: Obtain Portainer JWT token and pass securely to client
3. **API Key**: Use Portainer API key for authentication

### Key Files
- `plugins/portainer/src/` - React source code (SSO logic)
- `plugins/portainer/src/auth/` - Authentication module
- `plugins/portainer/public/` - Static assets
- `plugins/portainer/build.sh` - Build script
- `plugins/portainer/portainer.json` - Cockpit plugin configuration
- `plugins/portainer/package.json` - NPM dependencies

### Integration Points
- Cockpit plugin system (menu, iframe embedding)
- Portainer REST API (`/api/auth`, `/api/users/admin/init`)
- Websoft9 configuration system (store Portainer connection config)
- Optional: Reverse proxy layer for secure token transmission

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Authentication token leakage | Use HTTP-only cookies, backend proxy, or encrypted transmission; avoid exposing sensitive info in client JavaScript |
| Portainer service unavailable | Implement health checks, friendly error messages, auto-retry mechanism |
| Session expiration handling | Implement auto token refresh, graceful expiration prompts, re-login flow |
| Cross-origin and CORS issues | Configure proper CORS policies, use reverse proxy to avoid CORS, proper iframe sandbox config |
| Portainer version compatibility | Define supported Portainer version range, API compatibility checks, upgrade guidelines |

## Definition of Done

- [ ] All story acceptance criteria met
- [ ] Code reviewed and approved
- [ ] Unit and integration tests pass (including auth flow tests)
- [ ] Plugin loads and runs properly in Cockpit
- [ ] SSO verified in multiple scenarios (first login, token expiry, network failure, etc.)
- [ ] Security review passed (no token leakage, CSRF protection, secure transmission)
- [ ] User documentation and configuration guide completed
- [ ] Performance requirements met (SSO navigation < 2s)
- [ ] Integration with Epic 1 and Epic 3 verified
- [ ] Supported Portainer versions tested

