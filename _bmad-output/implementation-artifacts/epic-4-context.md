# Epic 4 Context: Product-Native Operations and Observability Expansion

## Goal

Epic 4 adds the first batch of product-native operational modules that cannot stay as legacy-plugin placeholders once the shell, integrations, App Store, My Apps, and settings flows are stable. The epic establishes a product-owned operator model where required, then layers backup, file and terminal tools, services, and logs on top of that baseline so sensitive operations remain inside the new Websoft9 boundary instead of falling back to Cockpit or host-user assumptions.

## Stories

- Story 4.1: Build the home overview and global task-feedback baseline
- Story 4.2: Build minimal product-side login and administrator initialization
- Story 4.3: Build the basic user-management entry
- Story 4.4: Build the backup list and restore loop
- Story 4.5: Build the controlled file-management workspace
- Story 4.6: Build the controlled terminal bridge and session audit
- Story 4.7: Build the core services view and log drilldown
- Story 4.8: Build the Websoft9 runtime logs page

## Requirements & Constraints

Websoft9 may introduce minimal product-side user management in Phase 1, but only at the level needed for continuity of protected product-native flows. The required action set is intentionally narrow: create user, disable user, reset password, and delete user. Phase 1 explicitly does not require a complete RBAC system or fine-grained permission matrix.

If product-side accounts and sessions exist in Phase 1, they must remain independent from host Linux accounts and Cockpit sessions. High-risk capabilities such as terminal access, controlled file management, backup restore, upgrade actions, and other privileged operations must remain protected by the product-owned authentication context. Primary navigation and first meaningful interaction for core pages should remain fast, so new pages should reuse shell and AppHub baselines rather than introducing heavy new infrastructure.

New durable state should only be added where Cockpit removal or native capability delivery makes it necessary. Sessions, audit records, task history, and similar state may be persisted by AppHub, but the epic should preserve compatibility-first storage evolution rather than forcing a database redesign. Validation continues to live at Pydantic request/response and domain-service boundaries first.

## Technical Decisions

FastAPI AppHub remains the single backend API layer. New epic capabilities should extend AppHub routes and services instead of growing a parallel backend. Existing AppHub response and config patterns remain the practical baseline unless a story needs a narrowly scoped additive contract. For the host-access slice, AppHub owns the only public boundary: terminal sessions are bridged through AppHub-owned SSH PTY WebSocket endpoints, current-host file operations are bridged through AppHub-owned SFTP-backed REST endpoints, and both capabilities reuse one current-host SSH authorization profile. Separately, application-detail surfaces may continue to expose volume-scoped file browsing through AppHub-owned contracts limited to the selected app volume boundary.

Authentication and credential changes stay minimal and capability-driven. Story 4.2 already established the reusable operator record shape, password hashing, session-backed login model, protected-module status contract, forced session invalidation semantics, audit events, and product-owned JSON persistence. Downstream stories in this epic must reuse that identity boundary instead of replacing its storage model or re-coupling to host identities.

Security controls remain explicit: secure cookie behavior, same-origin defaults, minimal upstream header trust, structured audit logging for privileged actions, and stronger protection for authentication, file, terminal, backup/restore, and upgrade endpoints. Product-auth state is separable from integration credentials and must remain compatible with later backup, restore, and upgrade work.

## UX & Interaction Patterns

Epic 4 surfaces must live inside the shared console shell and follow the route-and-module conventions already established by the console workspace. New feature pages should replace shell placeholders in-place, preserve bilingual resource usage, and avoid recreating entry/bootstrap patterns. Protected-module behavior should feel consistent: if a module is enabled and protected, the user enters it through the existing shell route and is either shown the native product surface or redirected by the product-auth guard.

## Cross-Story Dependencies

Epic 4 depends on the stabilized shell, runtime, integrations, My Apps continuity, and settings baseline delivered by Epics 1 through 3. Story 4.2 is the direct prerequisite for Story 4.3 because user-management actions must reuse the operator account model, session invalidation rules, disabled-state semantics, and protected-route gate introduced there. Later file, terminal, services, and logs stories should in turn consume the same product-auth boundary rather than inventing their own identity model. For the host-access slice specifically, Story 4.6 should establish the shared current-host authorization and terminal-first workspace shell, while Story 4.5 should reuse that authorization model for SFTP-backed file operations without requiring an extra host agent.