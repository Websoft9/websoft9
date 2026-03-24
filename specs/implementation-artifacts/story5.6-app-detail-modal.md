# Story 5.6: Application Detail Modal

**Epic**: Epic 5 - Store Plugin  
**Priority**: P1  
**Status**: ready-for-dev

## User Story
As a user, when I click on an application card in the catalog, I want to see a detailed modal dialog with comprehensive information about the application, so that I can understand the application's features, requirements, and documentation before deciding to install it.

## Acceptance Criteria
- [x] Clicking on a MediaCard opens a modal dialog with application details
- [x] Modal displays application icon, name, and version information
- [x] Modal shows system requirements (vCPU, memory, storage)
- [x] Modal includes clickable documentation link (opens in new tab)
- [x] Modal displays application categories as clickable tags (navigates to catalog filter)
- [x] Modal shows application description in current locale (zh/en)
- [x] Modal includes GitHub repository and website links
- [x] Modal has a close button (top-right X and backdrop click)
- [x] Modal includes screenshots carousel with side arrow navigation
- [x] Modal has Install and Favorite action buttons (placeholder for future)
- [x] Modal is responsive on mobile devices (320px width minimum)
- [x] Modal content is scrollable when content exceeds viewport height
- [x] All text is internationalized using i18n system from Story 5.5

## Definition of Done
- [ ] Code review passed
- [ ] All acceptance criteria met and verified
- [ ] Local testing passed: Modal opens/closes smoothly
- [ ] No TypeScript/ESLint errors or warnings
- [ ] Mobile responsive verified at 320px, 768px, and 1920px widths
- [ ] Browser tested: Chrome and Firefox latest versions
- [ ] Documentation updated: Component usage examples
- [ ] Integration tested: Works seamlessly with MediaCard click events
- [ ] i18n tested: All modal text switches correctly between zh/en

---

## Developer Context

### ✋ Prerequisites Check

Before starting implementation, verify these prerequisites:

**Environment**:
- [ ] Node.js >= 16.x installed
- [ ] `plugins/store/` directory exists
- [ ] Story 5.1-5.5 completed and working
- [ ] `npm install` completed successfully
- [ ] MediaCard component exists in `src/components/MediaCard.js`

**Dependencies**:
- [ ] Story 5.1: MediaCard and MediaGrid components working
- [ ] Story 5.2: API integration with `/api/products/{key}` endpoint
- [ ] Story 5.5: i18n system with `t()` function available

**Current State Analysis**:
- [ ] MediaCard displays basic app information (icon, name, categories)
- [ ] MediaCard currently has no click handler
- [ ] No AppDetailModal component exists yet in **store plugin** (`plugins/store/`)
- [ ] Reference implementation available in appstore plugin at `plugins/appstore/src/pages/appstore.js` (lines 126-621)

### 🎯 Mission

Create a **display-only** application detail modal component for the **store plugin** (`plugins/store/`) that shows comprehensive information about an application when a user clicks on its card in the catalog. This modal should be similar to the appstore's AppDetailModal but **without installation functionality** (no version selection, no domain configuration, no install button).

### 📋 What Already Exists (Reference Implementation)

**Reference Location**: `/data/dev/websoft9/plugins/appstore/src/pages/appstore.js`

**Note**: This is the **appstore plugin** (for reference only). We are implementing for **store plugin** at `plugins/store/`.

**AppDetailModal Component** (lines 126-621):
- Material-UI Dialog/Modal from react-bootstrap
- Multi-section layout with header and scrollable body
- Image carousel for screenshots
- Version display and selection (⚠️ EXCLUDE from store plugin)
- Domain configuration UI (⚠️ EXCLUDE from store plugin)
- Installation button and settings (⚠️ EXCLUDE from store plugin)

**Dependencies Used in appstore**:
```json
{
  "react-bootstrap": "^2.1.2",
  "@mui/material": "^5.12.2",
  "@mui/icons-material": "^5.11.16",
  "react-markdown": "^9.0.1"
}
```

### 🚨 Critical Requirements

**DO**:
1. ✅ Use Material-UI Dialog component for modal (already in package.json)
2. ✅ Extract modal header layout from appstore (app icon, title, metadata)
3. ✅ Display application description using react-markdown (support for Markdown content)
4. ✅ Show system requirements clearly (vCPU, memory, storage)
5. ✅ Include clickable Documentation link and GitHub icon
6. ✅ Display categories as clickable Chip components
7. ✅ Make modal scrollable with `scroll="body"` or `scroll="paper"`
8. ✅ Implement proper open/close state management in App.js
9. ✅ Use i18n `t()` function for all UI labels
10. ✅ Fetch detailed product data from `/api/products/{key}` endpoint

**DON'T**:
1. ❌ Don't include version selection dropdown
2. ❌ Don't add domain configuration fields
3. ✅ Include placeholder action buttons (Install/Favorite) without functionality
4. ❌ Don't add application settings/configuration UI

---

## Technical Implementation Guide

### Component Structure

**Target Directory**: `plugins/store/src/`

```
src/
├── components/
│   ├── MediaCard.js          # ✏️ MODIFY: Add onClick handler
│   ├── AppDetailModal.js     # ✨ NEW: Create modal component
│   └── ...
├── App.js                    # ✏️ MODIFY: Add modal state management
├── i18n/
│   ├── translations.js       # ✏️ MODIFY: Add modal-specific keys
│   └── index.js              # (no changes)
└── utils/
    └── api.js                # ✏️ MODIFY: Add getProductDetail(key) function
```

### 1. API Integration

**File**: `src/utils/api.js`

**Requirements**:
- Add `getProductDetail(key)` function to fetch single product details
- Use current locale from i18n system
- Handle errors gracefully with try-catch
- Return Promise that resolves to product detail object

**API Contract**:
- **Endpoint**: `GET /api/products/{key}?locale={locale}`
- **Response Structure**:
```json
{
  "key": "espocrm",
  "trademark": "EspoCRM",
  "logo": "espocrm.png",
  "version": ["9.2.2", "latest"],
  "vcpu": 1,
  "memory": 2,
  "storage": 8,
  "overview": "Short description (1-2 sentences)",
  "description": "Full Markdown description",
  "websiteurl": "https://www.espocrm.com",
  "github": "espocrm/espocrm",
  "catalogCollection": {
    "items": [
      {"key": "crm", "title": "CRM"},
      {"key": "distribution", "title": "分销/订单"}
    ]
  }
}
```

### 2. Internationalization Keys

**File**: `src/i18n/translations.js`

### 2. Internationalization Keys

**File**: `src/i18n/translations.js`

**Required Keys**:

| Key | English | Chinese |
|-----|---------|---------|
| `modal.version` | Version | 版本 |
| `modal.requires` | Requires at least | 最低配置要求 |
| `modal.categories` | Categories | 分类 |
| `modal.documentation` | Documentation | 文档 |
| `modal.overview` | Overview | 概览 |
| `modal.description` | Description | 详情 |
| `modal.close` | Close | 关闭 |
| `modal.loading` | Loading... | 加载中... |
| `modal.error` | Failed to load application details | 加载应用详情失败 |

### 3. AppDetailModal Component

**File**: `src/components/AppDetailModal.js` (NEW)

**Component Interface**:
```javascript
<AppDetailModal 
  open={boolean}
  onClose={function}
  product={object|null}
  loading={boolean}
  error={string|null}
/>
```

**Key Requirements**:
- Use Material-UI `Dialog` component with `maxWidth="md"` and `fullWidth`
- Set `scroll="paper"` for scrollable content
- Show loading state with `CircularProgress` component
- Show error state with `Alert` component
- Display app metadata in DialogTitle section
- Use `DialogContent` with `dividers` for body section
- Use `DialogActions` for footer with close button

**Layout Structure**:
1. **Header (DialogTitle)**:
   - Close button (IconButton with CloseIcon) - positioned absolute top-right
   - App icon (64x64px) with fallback to default image on error
   - App name as Typography variant="h5"
   - Documentation link as Chip component
   - GitHub icon link (opens in new tab)
   - Version info (comma-separated list)
   - System requirements (vCPU, memory, storage)
   - Categories as clickable Link components separated by "|"

2. **Body (DialogContent)**:
   - Overview section (if product.overview exists):
     - Typography variant="h6" for section title
     - Typography variant="body2" for content
   - Description section (if product.description exists):
     - Typography variant="h6" for section title
     - ReactMarkdown component for Markdown rendering
     - Apply CSS class "markdown-content" for styling

3. **Footer (DialogActions)**:
   - Close button (variant="outlined")

**Helper Functions**:
- `getDocUrl(key)`: Construct documentation URL based on current locale
  - EN: `https://support.websoft9.com/en/docs/{key}`
  - ZH: `https://support.websoft9.com/docs/{key}`
- `getGithubUrl(key)`: Construct GitHub URL
  - Format: `https://github.com/Websoft9/docker-library/tree/main/apps/{key}`

**Styling Requirements** (`AppDetailModal.css`):
- Style Markdown content with proper spacing and typography
- Code blocks: gray background, monospace font, horizontal scroll
- Headings: proper hierarchy with margins
- Links: primary color, underline on hover
- Lists: indentation and spacing

**Reference**: See `/data/dev/websoft9/plugins/appstore/src/pages/appstore.js` lines 126-621 for similar implementation

### 4. App.js Modifications

**Required State Variables**:
```javascript
const [modalOpen, setModalOpen] = useState(false);
const [selectedProduct, setSelectedProduct] = useState(null);
const [modalLoading, setModalLoading] = useState(false);
const [modalError, setModalError] = useState(null);
```

**Required Functions**:
- `handleCardClick(productKey)`: 
  - Open modal immediately
  - Set loading state
  - Fetch product detail using `getProductDetail(productKey)`
  - Handle success/error states
- `handleModalClose()`:
  - Close modal
  - Clear selected product and error state

**Component Integration**:
- Pass `handleCardClick` to MediaGrid as `onCardClick` prop
- Render `AppDetailModal` with modal state props

### 5. Component Updates

**MediaGrid.js**:
- Accept `onCardClick` prop
- Pass it through to each MediaCard

**MediaCard.js**:
- Accept `onClick` prop
- Add `onClick` handler to Card component
- Add cursor pointer and hover effects (translateY, box-shadow)
- Call `onClick(media.key)` when card is clicked

---

## Testing Checklist

### Functional Testing

- [ ] **Test 1: Modal Opens on Card Click**
  - Click on any MediaCard
  - Modal should open with loading indicator
  - Product details should load and display

- [ ] **Test 2: Modal Close**
  - Click X button in top-right → modal closes
  - Click backdrop (outside modal) → modal closes
  - Press ESC key → modal closes

- [ ] **Test 3: Display Product Information**
  - Verify app icon displays correctly
  - Verify app name matches card
  - Verify version info displays
  - Verify system requirements (vCPU, memory, storage) show correctly
  - Verify categories display as clickable links
  - Verify Documentation link opens in new tab
  - Verify GitHub icon link opens in new tab

- [ ] **Test 4: Description Rendering**
  - Verify overview text displays correctly
  - Verify description Markdown renders (headings, lists, links)
  - Verify Markdown styling matches design

- [ ] **Test 5: Loading State**
  - Open modal → should show loading spinner
  - Wait for data to load → spinner disappears

- [ ] **Test 6: Error Handling**
  - Simulate API failure (disconnect network)
  - Click card → should show error message
  - Error message should be in correct language

- [ ] **Test 7: Internationalization**
  - Change Cockpit language to Chinese → all labels should be in Chinese
  - Change Cockpit language to English → all labels should be in English
  - Documentation link should change based on language

### Responsive Testing

- [ ] **Mobile (320px)**
  - Modal should be full-width
  - Content should not overflow horizontally
  - Buttons should be touch-friendly (min 44px height)

- [ ] **Tablet (768px)**
  - Modal should have reasonable width (not full-screen)
  - Two-column layout where appropriate

- [ ] **Desktop (1920px)**
  - Modal should not exceed max-width
  - Content should be centered

### Browser Testing

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (if available)
- [ ] Edge (if available)

### Performance Testing

- [ ] Modal opens within 200ms of click
- [ ] API request completes within 500ms
- [ ] Smooth scroll inside modal body
- [ ] No lag when closing modal

---

## Known Limitations & Future Enhancements

### Out of Scope for This Story

1. **Image Carousel**: Screenshots/gallery view (reference exists in appstore.js but excluded for MVP)
2. **Installation Functionality**: Version selection, domain configuration, install button
3. **Favorite/Bookmark**: Star/bookmark feature for applications
4. **Category Navigation**: Clicking category tags to filter catalog (can be added later)
5. **Related Apps**: "You might also like" section
6. **Reviews/Ratings**: User reviews and ratings display

### Future Story Ideas

- **Story 5.7**: Image gallery carousel in modal
- **Story 5.8**: "Install" button integration with AppHub API
- **Story 5.9**: Favorite/bookmark functionality
- **Story 5.10**: Related applications recommendation

---

## Dependencies & Package Updates

Verify `react-markdown` is installed (should be from previous stories):

```bash
cd /data/dev/websoft9/plugins/store
npm list react-markdown
# If not installed: npm install react-markdown@^9.0.1
```

---

## Rollback Plan

If issues occur, revert in reverse order:
1. Remove AppDetailModal component files
2. Revert App.js, MediaGrid.js, MediaCard.js changes
3. Remove i18n modal keys
4. Remove getProductDetail API function

---

## Open Questions

1. **Category Click**: Should clicking category tags close modal and filter catalog?
2. **Default Image**: Confirm path for default logo fallback
3. **Documentation Link**: Always visible or only if docs exist?
4. **GitHub Link**: Should it show repo stats (stars, forks)?
5. **Modal Size**: Is maxWidth="md" (900px) appropriate?

---

## Success Metrics

Track after implementation:
- Modal open rate: >30% of catalog views
- Average engagement time: >10 seconds
- Documentation click rate: >15%
- Modal load time: <500ms (P95)
- Error rate: <1%

---

## References

- **Epic 5 Overview**: [epic5-store.md](epic5-store.md)
- **Story 5.1**: [story5.1-core-ui.md](story5.1-core-ui.md)
- **Story 5.2**: [story5.2-media-api.md](story5.2-media-api.md)
- **Story 5.5**: [story5.5-i18n.md](story5.5-i18n.md)
- **Appstore Reference**: `/data/dev/websoft9/plugins/appstore/src/pages/appstore.js`
- **Material-UI Dialog**: https://mui.com/material-ui/react-dialog/
- **React Markdown**: https://github.com/remarkjs/react-markdown

---

## Implementation Summary

**Status**: ✅ Completed

**Key Changes**:
1. **AppDetailModal.js** - Created modal with side-arrow screenshots carousel, action buttons, clickable category navigation
2. **App.js** - Added modal state management and category filter callback
3. **api.js** - Added `getProductDetail(key)` function with proper locale and path handling
4. **translations.js** - Added modal keys including `modal.favorite` and `modal.install`
5. **AppDetailModal.css** - Added Markdown content styling

**UI Enhancements**:
- Fixed icon alignment (24px height, vertically centered with Chip)
- Screenshots carousel with left/right arrows + dot indicators
- Install and Favorite buttons (placeholder for future implementation)
- Category links navigate and filter catalog when clicked

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-02-09 | 1.0 | Initial story creation | Websoft9 |
| 2026-02-09 | 2.0 | Implementation completed with carousel and action buttons | Websoft9 |
