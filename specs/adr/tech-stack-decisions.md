# Dashboard Technology Stack Decisions

**Date**: 2026-02-10  
**Context**: Epic 7 - Dashboard Unified Frontend Framework  
**Status**: Approved

---

## Decision Summary

After evaluating Convex SaaS reference architecture, we decided to **start fresh** and build Dashboard from scratch following Epic 7 stories, rather than adapting existing codebase.

---

## Core Technology Stack

### Build & Framework
- **Vite 5+**: Fast build tool with HMR
- **React 18**: UI framework with concurrent features
- **TypeScript 5+**: Type safety

### Routing
- **TanStack Router** (file-based routing)
  - **Why**: Type-safe, file-based routing matching our route structure
  - **Alternatives considered**: React Router, Next.js App Router
  - **Decision rationale**: 
    - Better TypeScript integration than React Router
    - File-based routing simplifies route organization
    - No need for full framework (Next.js) since we're building SPA

### UI & Styling
- **shadcn/ui**: Component library (headless + Radix UI)
- **Tailwind CSS**: Utility-first CSS framework
- **CSS Variables**: For theme customization
- **Dark/Light Mode**: System preference detection + manual toggle

### Internationalization (i18n)
- **react-i18next**
  - **Why**: Standard React i18n solution with good ecosystem
  - **Includes**: i18next-browser-languagedetector for automatic language detection
  - **Supported languages**: English (en), Chinese (zh) [extensible]

### State Management

#### Server State: **TanStack Query** (formerly React Query)
- **Use cases**:
  - All BaaS API calls (auth, services, apps, deployments)
  - Data fetching, caching, synchronization
  - Optimistic updates for mutations
  - Real-time subscriptions integration
- **Why**: 
  - Best-in-class server state management
  - Built-in caching, refetching, background updates
  - Excellent DevTools
  - Perfect match for BaaS API pattern

#### Client State: **React Context API**
- **Use cases**:
  - Theme preference (dark/light)
  - Locale selection (en/zh/etc)
  - User session/auth state (user object, permissions)
  - UI state (sidebar collapsed, modals open, etc)
- **Why**:
  - Native React solution, no extra dependency
  - Sufficient for our client state needs
  - Works well with TanStack Query for hybrid state
  - No need for Redux/Zustand complexity

#### BaaS Subscriptions
- **Integration**: TanStack Query + BaaS real-time subscriptions
- **Pattern**: Subscribe to BaaS events → Invalidate TanStack Query cache → Auto-refetch

---

## Backend Integration

### BaaS Client
- Authentication & session management
- Database queries (services, apps, logs)
- Server functions (deploy, control operations)
- Real-time subscriptions (service status, logs)

### cockpit.js
- System operations: docker, systemctl
- File operations: read/write configs
- DBus communication
- **Requirement**: Same-origin via reverse proxy

---

## File Structure

```
dashboard/
├── src/
│   ├── routes/              # TanStack Router file-based routes
│   │   ├── _app/
│   │   │   ├── _auth/       # Authenticated routes
│   │   │   │   ├── dashboard/
│   │   │   │   ├── store/
│   │   │   │   └── services/
│   │   │   └── login/
│   │   └── __root.tsx
│   ├── components/
│   │   └── ui/              # shadcn/ui components
│   ├── lib/
│   │   ├── baas.ts          # BaaS client wrapper
│   │   ├── cockpit.ts       # cockpit.js wrapper
│   │   ├── i18n.ts          # i18next configuration
│   │   └── query-client.ts  # TanStack Query setup
│   ├── contexts/            # React Context providers
│   │   ├── ThemeContext.tsx
│   │   ├── LocaleContext.tsx
│   │   └── AuthContext.tsx
│   ├── hooks/               # Custom hooks
│   │   ├── useBaasMutation.ts
│   │   └── useCockpit.ts
│   └── styles/
│       └── globals.css      # Tailwind + CSS variables
├── public/
│   └── locales/             # Translation files
│       ├── en/
│       └── zh/
└── vite.config.ts
```

---

## Migration from Convex SaaS Reference

**Decision**: ❌ Do NOT adapt Convex SaaS codebase  
**Rationale**:
- Convex-specific patterns don't map cleanly to our BaaS
- Auth system (Resend OTP, GitHub OAuth) incompatible
- Stripe/billing features unnecessary overhead
- Cleaner to build from scratch following our stories
- Epic 7 stories already define clear implementation path

**Reusable learnings**:
- ✅ TanStack Router file-based routing pattern
- ✅ shadcn/ui + Tailwind CSS design system approach
- ✅ Dark/light theme implementation
- ✅ i18next setup patterns

---

## Next Steps

1. **Story 7.1**: Initialize fresh dashboard/ with Vite + React + TypeScript
2. **Story 7.2**: Setup TanStack Router with basic route structure
3. **Story 7.3**: Install shadcn/ui, configure Tailwind, implement theme system
4. **Story 7.4**: Setup react-i18next with language detection
5. **Story 7.5**: Configure TanStack Query + React Context architecture

---

## References

- [TanStack Router Docs](https://tanstack.com/router)
- [TanStack Query Docs](https://tanstack.com/query)
- [shadcn/ui Components](https://ui.shadcn.com)
- [react-i18next Guide](https://react.i18next.com)
