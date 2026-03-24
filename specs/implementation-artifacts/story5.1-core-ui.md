# Story 5.1: Core UI Layout (PatternFly Design)

**Epic**: Epic 5 - Store Plugin  
**Priority**: P0  
**Status**: ✅ **Completed**

> **✅ 重构完成**: 已全面迁移到 PatternFly React v6，100% 符合设计要求。  
> **详见**: [story-5.1-refactor-report.md](story-5.1-refactor-report.md)

## User Story
As a user, I want to browse applications in a clean, Cockpit-native interface that follows the same design language as cockpit-files, so that the experience feels integrated and familiar.

## Acceptance Criteria
- [x] ✅ Use PatternFly React components (consistent with cockpit-files)
- [x] ✅ Page/PageSection layout structure with Card container
- [x] ✅ Application cards display in responsive PatternFly Gallery layout
- [x] ✅ Category navigation using PatternFly Select (MenuToggle-based)
- [x] ✅ Search/filter functionality using PatternFly SearchInput
- [x] ✅ Loading state with EmptyState + Spinner
- [x] ✅ Error handling with PatternFly Alert components
- [x] ✅ Mobile responsive verified at 320px width minimum
- [x] ✅ Follows cockpit-files design patterns and conventions
- [x] ✅ Supports Cockpit light/dark mode switching

**符合度**: 10/10 = **100%**

## Implementation Summary

### Final: February 2026 - PatternFly v6 + UI Polish

**Version**: PatternFly React v6.4.1 (matching cockpit-files)

**Key Optimizations**:
- ✅ **Dark mode**: Added cockpit-dark-theme logic to [index.js](../../../plugins/store/src/index.js) - responds to Cockpit shell theme toggle
- ✅ **Data fields**: Cards show `summary` field (not `overview` or `description`)
- ✅ **Modal layout**: Buttons right-aligned (Install → Favorite → Close)
- ✅ **Visual polish**: Links aligned, pointer cursor on cards

**Components**:
1. **App.js**: Page → PageSection → Card layout
2. **FilterBar.js**: Toolbar + SearchInput + Select (v6 API)
3. **MediaCard.js**: Shows `summary`, `trademark`, logo, category
4. **MediaGrid.js**: Gallery with responsive minWidths
5. **SecondaryCategoryNav.js**: LabelGroup for filters
6. **PaginationControls.js**: PatternFly Pagination
7. **AppDetailModal.js**: ModalHeader + ModalBody + ModalFooter

**Bundle Size**: 
- JS: 160.6 kB (gzip)
- CSS: 168.9 kB (gzip)

**Detailed Report**: [story-5.1-refactor-report.md](story-5.1-refactor-report.md)

---

## Definition of Done
- [x] ✅ Code follows cockpit-files design patterns
- [x] ✅ All acceptance criteria met
- [x] ✅ No console errors or warnings
- [x] ✅ Browser tested: Chrome and Firefox ready
- [x] ✅ Mobile responsive at 320px, 768px, 1920px
- [x] ✅ Performance: Smooth scrolling with 300+ apps
- [x] ✅ Light/dark mode switching via CSS variables

---

## Design Reference: cockpit-files

**Location**: `/data/dev/websoft9/plugins/cockpit-files/`

### Key Design Patterns to Follow

1. **PatternFly Components** - Use `@patternfly/react-core`
2. **Clean Page Structure** - `Page` → `PageSection` → `Card` 
3. **Simple, Functional** - No unnecessary decoration
4. **Context-based State** - React Context for shared data
5. **Native Cockpit Feel** - Integrated, not standalone

### Visual Structure

```
┌─ Page (no sidebar) ──────────────────────────────┐
│  ┌─ PageSection (Card Header) ──────────────────┐│
│  │  🔍 Search    📁 All Apps ▼    🔳/☰ View    ││
│  └──────────────────────────────────────────────┘│
│  ┌─ PageSection (hasBodyWrapper=false) ─────────┐│
│  │  ┌─ Card.body ──────────────────────────────┐││
│  │  │  [App] [App] [App] [App] [App] [App]    │││
│  │  │  [App] [App] [App] [App] [App] [App]    │││
│  │  │  [App] [App] [App] [App] [App] [App]    │││
│  │  └──────────────────────────────────────────┘││
│  └──────────────────────────────────────────────┘│
└───────────────────────────────────────────────────┘
```

**Reference Files**:
- `plugins/cockpit-files/src/app.tsx` - Page structure, EmptyStatePanel
- `plugins/cockpit-files/src/files-folder-view.tsx` - Search/filter/view controls
- `plugins/cockpit-files/src/files-card-body.tsx` - Grid/list view implementation
- `plugins/cockpit-files/src/header.tsx` - Header controls

---

## Architecture

### File Structure

```
plugins/store/src/
├── App.js                      # Main Page + PageSection layout
├── App.css                     # Minimal custom styles
├── components/
│   ├── StoreHeader.js          # Search + Category + View controls
│   ├── MediaCard.js            # Single app card (like file item)
│   └── MediaGrid.js            # Grid/list layout wrapper
├── i18n/
│   ├── index.js                # i18n utilities
│   └── translations.js         # UI text dictionary  
└── utils/
    └── api.js                  # Data fetching functions
```

### Component Hierarchy

```
App (Page)
├── EmptyStatePanel (loading)
└── StoreContext.Provider
    ├── PageSection (header)
    │   └── Card
    │       └── StoreHeader
    │           ├── SearchInput
    │           ├── Select (category)
    │           └── ToggleGroup (grid/list)
    └── PageSection (body)
        ├── Card (error state)
        │   └── EmptyStatePanel
        └── Stack (success state)
            ├── MediaGrid
            │   └── MediaCard (×N)
            └── Pagination (footer)
```

---

## Technical Implementation

### 1. App.js - Main Container

**Based on**: `cockpit-files/src/app.tsx`

```javascript
import React, { useState, useEffect } from 'react';
import { 
  Page, PageSection, Card, AlertGroup, Alert 
} from '@patternfly/react-core';
import { EmptyStatePanel } from 'cockpit-components-empty-state';
import { StoreContext } from './context';
import { StoreHeader } from './components/StoreHeader';
import { MediaGrid } from './components/MediaGrid';

export const Application = () => {
  const [loading, setLoading] = useState(true);
  const [mediaData, setMediaData] = useState([]);
  const [error, setError] = useState(null);
  const [currentCategory, setCurrentCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid | list
  
  useEffect(() => {
    // Load data from API
    // For now using mock data
  }, []);
  
  if (loading) {
    return <EmptyStatePanel loading />;
  }
  
  return (
    <Page className="pf-m-no-sidebar" isContentFilled>
      <StoreContext.Provider value={{ /* shared state */ }}>
        {/* Header Section */}
        <PageSection>
          <Card>
            <StoreHeader 
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              currentCategory={currentCategory}
              setCurrentCategory={setCurrentCategory}
              viewMode={viewMode}
              setViewMode={setViewMode}
            />
          </Card>
        </PageSection>
        
        {/* Body Section */}
        <PageSection hasBodyWrapper={false}>
          {error && (
            <Card className="store-empty-state">
              <EmptyStatePanel 
                paragraph={error}
                icon={ExclamationCircleIcon}
              />
            </Card>
          )}
          
          {!error && (
            <Card>
              <MediaGrid 
                data={filteredData}
                viewMode={viewMode}
              />
            </Card>
          )}
        </PageSection>
      </StoreContext.Provider>
    </Page>
  );
};
```

**Key Points**:
- ✅ Uses PatternFly `Page`, `PageSection`, `Card`
- ✅ `EmptyStatePanel` for loading state (Cockpit standard)
- ✅ Context for shared state
- ✅ No sidebar (`pf-m-no-sidebar`)
- ✅ `hasBodyWrapper={false}` for custom layout control

---

### 2. StoreHeader.js - Controls

**Based on**: `cockpit-files/src/header.tsx`

```javascript
import React from 'react';
import {
  Toolbar, ToolbarContent, ToolbarItem,
  SearchInput, Select, SelectOption,
  ToggleGroup, ToggleGroupItem
} from '@patternfly/react-core';
import { 
  ThIcon, ListIcon 
} from '@patternfly/react-icons';

export const StoreHeader = ({
  searchQuery, setSearchQuery,
  currentCategory, setCurrentCategory,
  viewMode, setViewMode
}) => {
  return (
    <Toolbar>
      <ToolbarContent>
        {/* Search Input */}
        <ToolbarItem variant="search-filter">
          <SearchInput
            placeholder="Search applications..."
            value={searchQuery}
            onChange={(_, value) => setSearchQuery(value)}
            onClear={() => setSearchQuery('')}
          />
        </ToolbarItem>
        
        {/* Category Filter */}
        <ToolbarItem>
          <Select
            selections={currentCategory}
            onSelect={(_, selection) => setCurrentCategory(selection)}
          >
            <SelectOption value="all">All Categories</SelectOption>
            <SelectOption value="cms">CMS</SelectOption>
            <SelectOption value="database">Database</SelectOption>
            {/* ... */}
          </Select>
        </ToolbarItem>
        
        {/* View Mode Toggle */}
        <ToolbarItem alignment={{ default: 'alignRight' }}>
          <ToggleGroup>
            <ToggleGroupItem
              icon={<ThIcon />}
              isSelected={viewMode === 'grid'}
              onChange={() => setViewMode('grid')}
            />
            <ToggleGroupItem
              icon={<ListIcon />}
              isSelected={viewMode === 'list'}
              onChange={() => setViewMode('list')}
            />
          </ToggleGroup>
        </ToolbarItem>
      </ToolbarContent>
    </Toolbar>
  );
};
```

**Key Points**:
- ✅ PatternFly Toolbar for controls layout
- ✅ SearchInput for app filtering
- ✅ Select for category dropdown
- ✅ ToggleGroup for grid/list view switch
- ❌ NO custom Material-UI components

---

### 3. MediaGrid.js - Layout

**Based on**: `cockpit-files/src/files-card-body.tsx`

```javascript
import React from 'react';
import { Gallery, DataList } from '@patternfly/react-core';
import { MediaCard } from './MediaCard';

export const MediaGrid = ({ data, viewMode }) => {
  if (viewMode === 'grid') {
    return (
      <Gallery hasGutter minWidths={{ default: '200px' }}>
        {data.map(app => (
          <MediaCard key={app.key} app={app} />
        ))}
      </Gallery>
    );
  }
  
  // List view
  return (
    <DataList>
      {data.map(app => (
        <DataListItem key={app.key}>
          {/* List item content */}
        </DataListItem>
      ))}
    </DataList>
  );
};
```

**Key Points**:
- ✅ PatternFly `Gallery` component for grid
- ✅ Responsive with `minWidths` prop
- ✅ Alternative `DataList` for list view
- ✅ Clean, minimal layout

---

### 4. MediaCard.js - Application Card

**Based on**: cockpit-files file item display

```javascript
import React from 'react';
import { Card, CardTitle, CardBody } from '@patternfly/react-core';
import './MediaCard.css';

export const MediaCard = ({ app, onClick }) => {
  return (
    <Card 
      isClickable
      isSelectable
      onClick={() => onClick(app)}
      className="media-card"
    >
      <CardBody>
        <div className="media-card-logo">
          <img 
            src={app.logo?.imageurl || '/placeholder.png'}
            alt={app.trademark}
            onError={(e) => e.target.src = '/placeholder.png'}
          />
        </div>
        <CardTitle>{app.trademark}</CardTitle>
        <div className="media-card-overview">
          {app.overview}
        </div>
        {app.catalogCollection?.items && (
          <div className="media-card-categories">
            {app.catalogCollection.items.map(cat => (
              <span key={cat.key} className="category-tag">
                {cat.title}
              </span>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
};
```

**Key Points**:
- ✅ PatternFly `Card` with `isClickable`
- ✅ Clean, minimal design
- ✅ Error handling for missing images
- ✅ Simple category tags (not chips)
- ❌ NO skeleton animations (keep it simple)

---

## Key Differences from Old appstore Design

| Aspect | Old (appstore/MUI) | New (cockpit-files/PF) |
|--------|--------------------|------------------------|
| **Design System** | Material-UI | PatternFly React |
| **Layout** | AppBar + Container | Page + PageSection |
| **Components** | Card, Grid, Chip | Card, Gallery, ToggleGroup |
| **Search** | TextField | SearchInput |
| **Categories** | Tabs | Select dropdown |
| **Complexity** | Many abstractions | Simple, flat |
| **Feel** | Standalone app | Native Cockpit module |
| **Loading** | Custom skeleton | EmptyStatePanel |
| **Error** | Snackbar | Alert + EmptyStatePanel |

---

## PatternFly Components Used

### Required Dependencies

```json
{
  "@patternfly/react-core": "^5.x",
  "@patternfly/react-icons": "^5.x",
  "@patternfly/patternfly": "^5.x"
}
```

### Core Components

| Component | Usage | Example |
|-----------|-------|---------|
| `Page` | Main container | `<Page className="pf-m-no-sidebar">` |
| `PageSection` | Section wrapper | `<PageSection hasBodyWrapper={false}>` |
| `Card` | Content container | `<Card>...</Card>` |
| `Toolbar` | Controls bar | `<Toolbar><ToolbarContent>` |
| `SearchInput` | Search field | `<SearchInput placeholder="..." />` |
| `Select` | Dropdown | `<Select><SelectOption>` |
| `Gallery` | Grid layout | `<Gallery hasGutter>` |
| `EmptyStatePanel` | Loading/error | `<EmptyStatePanel loading />` |
| `Alert` | Toast notifications | `<Alert variant="success">` |

**Documentation**: https://www.patternfly.org/components/all-components

---

## CSS Styling Guidelines

### Use PatternFly Utilities First

```css
/* ❌ Don't: Custom CSS for spacing */
.my-component {
  padding: 16px;
  margin-bottom: 24px;
}

/* ✅ Do: PatternFly utility classes */
<Card className="pf-v5-u-p-md pf-v5-u-mb-lg">
```

### Minimal Custom CSS

```css
/* MediaCard.css */
.media-card {
  transition: transform 0.2s;
}

.media-card:hover {
  transform: translateY(-2px);
}

.media-card-logo {
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.media-card-logo img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.category-tag {
  font-size: 0.875rem;
  color: var(--pf-v5-global--Color--200);
}
```

**Key Points**:
- Use PatternFly CSS variables (`--pf-v5-global--*`)
- Keep custom styles minimal
- Follow PatternFly design tokens

---

## Implementation Checklist

### Phase 1: Layout Structure
- [ ] Replace Material-UI with PatternFly imports
- [ ] Implement Page/PageSection layout in App.js
- [ ] Add EmptyStatePanel for loading state
- [ ] Remove old AppBar/Container structure

### Phase 2: Header Controls
- [ ] Create StoreHeader component
- [ ] Add SearchInput for filtering
- [ ] Add Select for category dropdown
- [ ] Add ToggleGroup for view mode
- [ ] Wire up state management

### Phase 3: Application Display
- [ ] Implement MediaGrid with Gallery component
- [ ] Create MediaCard with PatternFly Card
- [ ] Add click handlers for modal opening
- [ ] Test responsive layout (320px-1920px)

### Phase 4: Polish
- [ ] Add Alert/Toast for notifications
- [ ] Implement error states with EmptyStatePanel
- [ ] Test keyboard navigation
- [ ] Verify Cockpit integration

---

## Testing Requirements

### Visual Regression
- [ ] Matches cockpit-files design language
- [ ] PatternFly components render correctly
- [ ] Responsive at 320px, 768px, 1920px
- [ ] Grid layout adapts to screen size

### Functional
- [ ] Search filters applications correctly
- [ ] Category dropdown switches views
- [ ] Grid/list toggle works
- [ ] Card click opens detail modal
- [ ] Loading state displays properly
- [ ] Error state shows correctly

### Browser Compatibility
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (if available)

---

## Migration Notes

### From Material-UI to PatternFly

```javascript
// ❌ Old (Material-UI)
import { AppBar, Toolbar, Container, Grid, Card, Chip } from '@mui/material';

<AppBar position="static">
  <Toolbar>
    <Typography>Store</Typography>
  </Toolbar>
</AppBar>
<Container>
  <Grid container spacing={2}>
    <Grid item xs={12} sm={6} md={3}>
      <Card>...</Card>
    </Grid>
  </Grid>
</Container>

// ✅ New (PatternFly)
import { Page, PageSection, Card, Gallery } from '@patternfly/react-core';

<Page className="pf-m-no-sidebar">
  <PageSection>
    <Card>Header Controls</Card>
  </PageSection>
  <PageSection hasBodyWrapper={false}>
    <Card>
      <Gallery hasGutter minWidths={{ default: '200px' }}>
        <Card>...</Card>
      </Gallery>
    </Card>
  </PageSection>
</Page>
```

---

## Performance Considerations

### Keep It Simple
- ❌ NO react-lazyload (overcomplicated)
- ❌ NO skeleton animations (not needed)
- ✅ Use browser native lazy loading: `<img loading="lazy" />`
- ✅ Pagination for large datasets
- ✅ Simple CSS transitions

### Optimization Strategy
1. **Pagination** - Show 24-48 apps per page
2. **Native Lazy Loading** - `<img loading="lazy" />`
3. **Virtualization** (future) - Only if 1000+ apps

---

## Success Criteria

### Visual
- [ ] Looks like a native Cockpit module
- [ ] Follows cockpit-files design patterns
- [ ] Clean, minimal, functional interface
- [ ] No Material-UI artifacts

### Technical
- [ ] Zero Material-UI dependencies in new code
- [ ] PatternFly components used correctly
- [ ] Follows React best practices
- [ ] Context API for state management

### User Experience
- [ ] Fast, responsive interface
- [ ] Intuitive search and filtering
- [ ] Smooth grid/list view switching
- [ ] Accessible keyboard navigation

---

## 当前实现状态 (2026-02-09)

### ❌ 不符合设计要求

**问题总结**:
1. ❌ 使用 Material-UI 而不是 PatternFly
2. ❌ 布局结构不符合 cockpit-files 模式
3. ❌ 不支持 Cockpit light/dark mode (硬编码颜色)
4. ❌ 视觉风格与其他 Cockpit 模块不一致

**详细审核报告**: [story5.1-audit-report.md](story5.1-audit-report.md)

### 需要的改动

**高优先级** (P0):
- [ ] 安装 `@patternfly/react-core` 和 `@patternfly/react-icons`
- [ ] 重构 App.js: AppBar/Container → Page/PageSection
- [ ] 重构 FilterBar.js: TextField → SearchInput
- [ ] 移除硬编码颜色，使用 PatternFly CSS 变量
- [ ] 测试 light/dark mode 切换

**中优先级** (P1):
- [ ] 移除 Material-UI 依赖
- [ ] 所有组件迁移到 PatternFly
- [ ] 响应式布局验证

**预估工作量**: 10-12 小时

---

## References

- **Design Reference**: `/data/dev/websoft9/plugins/cockpit-files/`
- **PatternFly Docs**: https://www.patternfly.org
- **Cockpit Docs**: https://cockpit-project.org/guide/latest/
- **Epic 5 Overview**: [epic5-store.md](epic5-store.md)
- **Story 5.2**: API Integration (next step)
- **Audit Report**: [story5.1-audit-report.md](story5.1-audit-report.md)

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-02-09 | 1.0 | Initial story (Material-UI design) | Websoft9 |
| 2026-02-09 | 2.0 | Redesign with PatternFly (cockpit-files style) | Websoft9 |
| 2026-02-09 | 2.1 | Audit: Current implementation does not meet requirements | AI Assistant |

