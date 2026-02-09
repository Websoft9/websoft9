# Story 6.1: Service List & Status Display

**Epic**: Epic 6 - Services Plugin  
**Priority**: P0  
**Status**: ✅ Implemented (with enhancements)

## Context
This plugin provides a visual interface for managing supervisord programs running in the **current container** (where the plugin itself runs). It replaces CLI \`supervisorctl\` commands with a clean web UI.

**Technical Approach**: Uses `cockpit.http()` to call supervisord XML-RPC API (port 9001). Avoids browser CORS by running HTTP client server-side.

## User Story
As a user, I want to see all supervisord programs in the current container with their real-time status, so that I can monitor service health without using the command line.

## Acceptance Criteria
- [x] Enable supervisord XML-RPC server in supervisord.conf
- [x] Fetch program list using supervisord.getAllProcessInfo() XML-RPC method
- [x] Display program name, statename (RUNNING/STOPPED/FATAL/etc), PID, and uptime
- [x] Map supervisord statename to visual indicators:
  - RUNNING → Green label
  - STOPPED → Grey label  
  - FATAL/EXITED → Red label
  - STARTING/STOPPING/BACKOFF → Orange label
- [x] Auto-refresh status every 5 seconds
- [x] Manual refresh button in page header
- [x] Use PatternFly Table component (compact variant)
- [x] Loading state: Show EmptyState with Spinner on initial load
- [x] Empty state: Show friendly message if no programs configured
- [x] Error state: Show Alert if XML-RPC call fails
- [x] Follows cockpit-files design patterns
- [x] Responsive layout works on mobile (320px+)

## Enhanced Features (Implemented)
- [x] **Layout fix**: Full-width display using `pf-m-no-sidebar`
- [x] **Summary stats**: Total/Running/Stopped/Error counts, aggregate CPU%, Memory
- [x] **Resource monitoring**: CPU% and Memory (RSS) per process via `ps`
- [x] **Log viewer**: Modal with stdout/stderr logs (last 200 lines via `tail`)
- [~] **Port display**: Listening ports (partial - `ss` + cmdline parsing, complex cases pending)

## Definition of Done
- [x] Supervisord XML-RPC server enabled and accessible
- [x] Code follows PatternFly patterns
- [x] All acceptance criteria met
- [x] No console errors
- [x] Browser tested: Chrome/Firefox
- [x] Mobile responsive

---

## Visual Structure

```
┌─ Page (pf-m-no-sidebar) ───────────────────────────────────┐
│  ┌─ PageSection (Header) ──────────────────────────────┐   │
│  │  Supervisord Services                 🔄 Refresh    │   │
│  │  ┌─ Stats Cards ──────────────────────────────────┐ │   │
│  │  │ 🧊 10 Total │ ✓ 8 Running │ ⚠️ 2 Error         │ │   │
│  │  │ CPU: 15.2% │ Memory: 245.3 MB                  │ │   │
│  │  └────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─ PageSection (Body) ─────────────────────────────────┐  │
│  │  ┌─ Card ───────────────────────────────────────────┐│  │
│  │  │  ┌────────────────────────────────────────────┐ ││  │
│  │  │  │Program│Status│PID│Ports│CPU│Mem│Uptime│Logs│ ││  │
│  │  │  ├────────────────────────────────────────────┤ ││  │
│  │  │  │apphub │●RUN  │40 │8080│2%│76MB│2h│stdout│  ││  │
│  │  │  │nginx  │●RUN  │35 │80  │0%│7MB │1d│stdout│  ││  │
│  │  │  │gitea  │●RUN  │33 │3000│1%│164M│1d│stdout│  ││  │
│  │  │  └────────────────────────────────────────────┘ ││  │
│  │  └──────────────────────────────────────────────────┘│  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
plugins/services/
├── manifest.json               # Cockpit plugin manifest
├── package.json
├── webpack.config.js
└── src/
    ├── index.js                # Entry point
    ├── App.js                  # Main component
    ├── App.css
    ├── components/
    │   ├── ServiceTable.js     # PatternFly Table
    │   └── ProgramStatusLabel.js
    └── utils/
        └── api.js              # XML-RPC API calls
```

---

## Implementation Summary

### Core Architecture
- **API**: `cockpit.http()` → supervisord XML-RPC (127.0.0.1:9001) → `supervisor.getAllProcessInfo()`
- **Resource data**: `cockpit.spawn(['ps', ...])` → parse CPU% + RSS memory
- **Port detection**: `cockpit.spawn(['ss', '-tlnpH'])` + `/proc/<pid>/cmdline` parsing
- **Logs**: `cockpit.spawn(['tail', '-n', '200', logfile])` → display in Modal

### Key Challenges
- ⚠️ **Port detection complexity**: `ss -tlnp` only shows PIDs for direct socket owners, not parent processes. Child processes (e.g., uvicorn under supervisord) don't appear with parent PID. Current solution uses cmdline parsing as fallback but incomplete for some services.

### Data Flow
1. Fetch programs via XML-RPC → get name, state, PID, uptime, log paths
2. Parallel fetch: resources (ps) + ports (ss + cmdline)
3. Merge data → enrich programs with cpu, memory, ports
4. Render table + summary stats (aggregate CPU/Memory)

---

## Testing Checklist

### Functional
- [x] XML-RPC server accessible at `http://127.0.0.1:9001/RPC2`
- [x] `supervisor.getAllProcessInfo()` returns valid response
- [x] Table displays program name, statename, PID, ports, CPU, memory, uptime, logs
- [x] Status labels show correct colors per statename
- [x] Auto-refresh updates every 5 seconds
- [x] Manual refresh button works
- [x] Summary stats update with data
- [x] Log viewer modal opens on stdout/stderr click
- [x] Port display for direct socket owners (nginx, sshd, portainer, cockpit)
- [~] Port display for child processes (partially working)

### States
- [x] Loading: Spinner on initial load
- [x] Empty: Message when no programs
- [x] Error: Alert when connection fails

### Visual
- [x] PatternFly Table (compact variant)
- [x] Responsive at 320px width (no sidebar layout)
- [x] Matches cockpit-files design patterns

---

## Dev Agent Record

**Implementation Date**: 2026-02-09  
**Agent**: Amelia (Dev Agent)

### What Was Implemented
1. **Core Service List**: XML-RPC integration with supervisord, table display with auto-refresh
2. **Layout Fix**: Added `pf-m-no-sidebar` to Page component for full-width display
3. **Summary Statistics**: Header cards showing Total/Running/Stopped/Error counts, aggregate CPU/Memory
4. **Resource Monitoring**: Per-process CPU% and Memory (RSS) via `ps` command
5. **Log Viewer**: Modal dialog with stdout/stderr logs (last 200 lines via `tail`)
6. **Port Display**: Listening ports via `ss -tlnp` + cmdline parsing (partial implementation)

### Technical Decisions
- **API approach**: Changed from browser `fetch()` to `cockpit.http()` to avoid CORS issues when accessing container-internal endpoints
- **Data fetching**: Parallel execution of XML-RPC + ps + ss using `Promise.all()` for performance
- **Port detection**: Hybrid strategy (ss + cmdline + defaults) due to child process limitations
- **Webpack config**: Added `cockpit` as external dependency in `config-overrides.js`

### Known Issues
- **Port detection incomplete**: `ss -tlnp` only shows PIDs for direct socket owners. Child processes (uvicorn, gitea workers) don't appear with parent supervisord PID. Current workaround uses cmdline parsing but doesn't cover all cases. Deferred for future improvement.

### Files Changed
- `plugins/services/src/App.js` - Main component with stats and data orchestration
- `plugins/services/src/components/ServiceTable.js` - Table with log viewer modal
- `plugins/services/src/utils/api.js` - XML-RPC, resource, port, log fetching
- `plugins/services/config-overrides.js` - Webpack externals for cockpit
- `docker/cockpit/supervisord.conf` - Enabled inet_http_server on 9001

---

## Technical Reference

For complete implementation code, see:
- [story6.1-technical-reference.md](story6.1-technical-reference.md)

