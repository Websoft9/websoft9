# Story 5.1: Core UI Components & Data Loading

**Epic**: Epic 5 - Store Plugin  
**Priority**: P0  
**Status**: ready-for-dev

## User Story
As a user, I want to browse media resources in a categorized interface, so that I can easily find application logos and screenshots.

## Acceptance Criteria
- [ ] MediaCard component extracted with skeleton loading from appstore
- [ ] MediaGrid displays items in responsive layout (4 cols desktop, 2 tablet, 1 mobile)
- [ ] CategoryTabs switches between filtered category views
- [ ] Lazy loading implemented for performance (react-lazyload)
- [ ] Error handling shows default image fallback on load failure
- [ ] Mock data displays 10-15 sample items with multiple categories
- [ ] No console errors or warnings in browser DevTools
- [ ] Mobile responsive verified at 320px width
- [ ] All apphub dependencies removed from extracted code

## Definition of Done
- [ ] Code review passed (self-review against appstore source)
- [ ] All acceptance criteria met and verified
- [ ] Local testing passed: `npm start` works without errors
- [ ] No TypeScript/ESLint errors or warnings
- [ ] Performance: First paint < 1s with 50 mock items
- [ ] Browser tested: Chrome and Firefox latest versions
- [ ] Documentation updated: inline comments for complex logic
- [ ] Ready for Story 5.2 integration (API connection points identified)

---

## Developer Context

### ✋ Prerequisites Check

Before starting implementation, verify these prerequisites:

**Environment**:
- [ ] Node.js >= 16.x installed and accessible
- [ ] `plugins/store/` directory exists
- [ ] `npm install` completed successfully in plugins/store/
- [ ] `plugins/appstore/` source code accessible for extraction

**Current State Analysis**:
- [ ] `plugins/store/src/App.js` exists but uses SIMPLIFIED data structure
- [ ] `plugins/store/src/components/MediaCard.js` exists but LACKS AppImage logic
- [ ] `plugins/store/src/components/CategoryTabs.js` exists but NEEDS Material-UI Tabs
- [ ] Current code is PLACEHOLDER - needs full refactoring with appstore patterns

**⚠️ Important**: The existing store code is a basic scaffold. This story requires significant refactoring to match appstore's production-quality implementation.

### 🎯 Mission
Refactor the existing appstore plugin's media display functionality into a standalone "store" plugin. This is NOT about creating from scratch - it's about **extracting and decoupling** existing working UI code from apphub dependencies.

### 📋 What Already Exists (Source to Refactor)

**Location**: `/data/dev/websoft9/plugins/appstore/`

**Key Files to Extract From**:
- `src/pages/appstore.js` (lines 1-1255) - Main appstore component with:
  - Media grid layout with LazyLoad
  - AppImage component with skeleton screens (lines 44-103)
  - AppDetailModal for detailed views (lines 106-700+)
  - Image optimization with lazy loading
  - Error handling for missing images
  - Responsive grid using React-Bootstrap

- `src/helpers/api/appHub.js` - API calls:
  - `AppCatalog(locale, params)` - Fetches media catalog from `/apps/catalog/${locale}`
  - Uses APICore class for HTTP requests

- `src/App.js` - Simple routing structure with Routes component

**Current Dependencies in appstore**:
```json
{
  "@mui/material": "^5.12.2",
  "@mui/icons-material": "^5.11.16",
  "react": "^18.2.0",
  "react-bootstrap": "^2.1.2",
  "bootstrap": "5.1.3",
  "react-lazyload": "^3.2.0",
  "react-markdown": "^9.0.1",
  "axios": "^1.3.4"
}
```

### 🚨 Critical Requirements

**DO**:
1. ✅ Extract AppImage component with skeleton loading from appstore.js
2. ✅ Reuse lazy loading pattern for performance (LazyLoad + loading="lazy")
3. ✅ Keep Material-UI Card/Grid layout structure
4. ✅ Maintain responsive design (React-Bootstrap Grid system or MUI Grid)
5. ✅ Extract error handling for missing images (default image fallback)
6. ✅ Simplify: Remove installation logic, domain configuration, version selection
7. ✅ Remove all apphub API dependencies (AppInstall, Settings management)

**DON'T**:
1. ❌ Don't add routing complexity (single page view is fine for now)
2. ❌ Don't include Modal installation flows (just display media)
3. ❌ Don't connect to apphub APIs yet (mock data for now)
4. ❌ Don't add new external dependencies unless necessary

### 🏗️ Architecture Compliance

**Plugin Structure** (Following Story 4.1 Portainer Pattern):
```
plugins/store/
├── package.json              # Dependencies
├── build.sh                  # Build + deploy to Cockpit
├── config-overrides.js       # Webpack externals for Cockpit
├── public/
│   ├── index.html
│   └── manifest.json         # Cockpit plugin config
├── src/
│   ├── index.js             # React entry
│   ├── App.js               # Main component
│   ├── App.css
│   ├── components/
│   │   ├── MediaCard.js     # From appstore AppImage
│   │   ├── MediaGrid.js     # Grid layout wrapper
│   │   └── CategoryTabs.js  # Category navigation
│   └── utils/
│       └── api.js           # Placeholder API functions
└── build/                    # Output (gitignored)
```

**Cockpit Integration** (MUST FOLLOW):
- Externalize `cockpit` module in config-overrides.js
- Use React 18.2.0 (same as appstore)
- Build output goes to `/usr/share/cockpit/store/` in container

### 📦 Data Structure (From Existing Appstore)

```javascript
// Media item structure (extracted from appstore.js usage)
{
  key: string,              // App identifier (e.g., "wordpress")
  trademark: string,        // Display name (e.g., "WordPress")
  logo: {
    imageurl: string        // Path like "/media/logos/wordpress.png"
  },
  overview: string,         // Short description
  description: string,      // Markdown description
  catalogCollection: {
    items: [{              // Categories
      key: string,
      title: string
    }]
  },
  screenshots: [{          // Array of screenshots
    id: number,
    key: string,
    value: string          // Path to screenshot
  }],
  websiteurl: string       // Official website
}
```

### ⚠️ Known Issues in Source Code

From `plugins/appstore/src/pages/appstore.js` analysis:

**Issues to Fix During Extraction**:
1. **Inline Styles Overuse**: AppImage uses inline styles heavily (lines 60-85)
   - Action: Extract to CSS classes in App.css

2. **Hardcoded Animation Values**: Skeleton animation uses magic numbers
   - Action: Define CSS variables for timing/dimensions

3. **Console Logging**: Error handling logs to console (line 98)
   - Action: Silent fallback in production, log only in dev mode

4. **Missing PropTypes**: No type validation for component props
   - Action: Add PropTypes or use TypeScript interfaces (optional)

5. **Cockpit Dependency**: appstore.js imports `cockpit` for i18n
   - Action: Remove cockpit.gettext calls, use plain English for now

**DO NOT Copy These Patterns**:
- Complex state management for installation (lines 106-300)
- Domain configuration logic (lines 400-500)
- AppInstall API calls (lines 600+)
- Form validation for app settings

### 🎨 UI Components to Extract

**1. AppImage Component** (appstore.js lines 44-103):
```javascript
// Key features:
- Skeleton loading animation
- Lazy loading with react-lazyload
- Error fallback to default image
- isFirstScreen prop for eager loading
- Smooth opacity transitions
```

**2. Grid Layout** (appstore.js lines 800+):
```javascript
// Pattern to follow:
- React-Bootstrap Row/Col OR Material-UI Grid
- LazyLoad wrapper for off-screen items
- Responsive: 4 columns desktop, 2 tablet, 1 mobile
- Gap spacing between cards
```

**3. Card Display**:
```javascript
// Material-UI Card with:
- CardMedia for logo (80px height, contain fit)
- CardContent with app name + description
- Chip/Tag for category
- Hover effect (translateY(-4px))
```

### 🔧 Implementation Steps

**Phase 1: Project Setup** (ALREADY DONE ✅)
- [x] Created plugins/store directory
- [x] package.json with dependencies
- [x] Basic App.js structure
- [x] MediaCard.js component skeleton
- [x] CategoryTabs.js component

**Phase 2: Extract Core Components** (THIS STORY)
1. Copy AppImage logic from appstore.js → MediaCard.js
   - Keep skeleton loading
   - Keep lazy load wrapper
   - Simplify to just display (remove click handlers)

2. Create MediaGrid.js wrapper
   - Extract grid layout pattern from appstore
   - Use Material-UI Grid (already in package.json)
   - Handle responsive breakpoints

3. Update App.js with proper state management
   - Loading state
   - Error state
   - Mock data array for testing

4. Add CategoryTabs.js functionality
   - Material-UI Tabs component
   - Category filtering logic

**Phase 3: Mock Data Integration**
1. Create sample media data array in App.js
   - Follow existing data structure
   - 10-15 sample items
   - Multiple categories

2. Test with mock images
   - Use placeholder images or existing /media/logos/
   - Verify lazy loading works
   - Test error handling

### 📝 Files to Create/Modify

**New Files**:
- `src/components/MediaGrid.js` - Grid layout wrapper component

**Files to Modify**:
- `src/App.js` - Add state management, mock data, category filtering
- `src/components/MediaCard.js` - Extract AppImage logic from appstore
- `src/components/CategoryTabs.js` - Add Material-UI Tabs implementation
- `src/App.css` - Extract relevant styles from appstore

**Reference Files** (DO NOT MODIFY):
- `plugins/appstore/src/pages/appstore.js` - Source for extraction
- `plugins/appstore/src/App.css` - Style reference

### ⚠️ Common Pitfalls to Avoid

1. **Don't copy installation logic** - This is display-only, no AppInstall calls
2. **Don't add modal complexity** - Keep it simple, cards with basic info
3. **Don't forget lazy loading** - Performance is critical with 300+ apps
4. **Don't hardcode image paths** - Use baseURL variable for flexibility
5. **Don't skip error handling** - Missing images should fallback gracefully

### 🔄 Contingency Plan

**If extraction proves too complex or time-consuming:**

**Decision Point**: If implementation exceeds 4 hours, evaluate options below.

**Option A: Simplified Skeleton** (Recommended)
- Use basic Material-UI Card without custom skeleton
- Rely on MUI's built-in loading states
- Keep lazy loading but skip custom animations
- Time saved: ~2 hours
- Trade-off: Less polished loading experience

**Option B: Third-Party Component**
- Use `react-loading-skeleton` library
- Pre-built, well-tested skeleton screens
- Add dependency: +100KB bundle size
- Trade-off: External dependency, but production-ready

**Option C: Defer Optimization**
- Implement basic display without skeleton loading
- Defer lazy loading to Story 5.2 (API integration)
- Focus on core grid layout and filtering
- Trade-off: Performance impact with 300+ items

**Decision Criteria**:
- Code complexity exceeds story scope → Option A
- Bundle size not critical → Option B  
- Tight deadline, working code priority → Option C

**Escalation**: Consult Scrum Master if extraction blocked > 2 hours

### 🧪 Testing Requirements

**Local Testing**:
```bash
cd plugins/store
npm install
npm start
# Should open localhost:3000 with media grid
```

**Verify**:
- [ ] Cards display in responsive grid
- [ ] Images load with skeleton animation
- [ ] Lazy loading works (scroll to load more)
- [ ] Category tabs switch filtered view
- [ ] Missing images show default fallback
- [ ] No console errors
- [ ] Mobile responsive (test 320px width)

**Container Testing** (After Story 5.4):
```bash
npm run build
# Deploy to container via build.sh
# Access at http://localhost:9000/store
```

### 📚 Key References

**Existing Code**:
- [plugins/appstore/src/pages/appstore.js](../../../plugins/appstore/src/pages/appstore.js) - Main source to extract from
- [plugins/appstore/src/helpers/api/appHub.js](../../../plugins/appstore/src/helpers/api/appHub.js) - API pattern reference

**Similar Implementation**:
- [Story 4.1: Plugin Foundation](story4.1-plugin-foundation.md) - Build setup pattern

**Architecture**:
- [Architecture Document](../planning-artifacts/architecture.md) - Cockpit plugin integration

---

## Completion Checklist

Before marking this story as done:

- [ ] MediaCard component displays app logo + name + description
- [ ] MediaGrid arranges cards in responsive layout
- [ ] CategoryTabs filters by category
- [ ] Skeleton loading works during image load
- [ ] Lazy loading implemented for performance
- [ ] Error handling shows default image on failure
- [ ] Mock data tests full functionality
- [ ] No console errors or warnings
- [ ] Code follows existing appstore patterns
- [ ] All apphub dependencies removed

---

**Status**: ready-for-dev  
**Context Engine Analysis**: Comprehensive developer guide created with source extraction points, architecture compliance, and testing requirements.
