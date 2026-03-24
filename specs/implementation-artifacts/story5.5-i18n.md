# Story 5.5: Internationalization (i18n) Support

**Epic**: Epic 5 - Store Plugin  
**Status**: ✅ Complete

## Summary

UI-level i18n for frontend static text (buttons, labels, pagination). Data-level i18n already complete in Story 5.2.

## Final Solution

### Cockpit Integration (Critical)

**`public/index.html`** must include both scripts:
```html
<script type="text/javascript" src="../base1/cockpit.js"></script>
<script type="text/javascript" src="../base1/po.js"></script>
```
- `cockpit.js` — Cockpit SDK, provides `cockpit.language`
- `po.js` — **Cockpit language initializer** (without this, `cockpit.language` returns wrong value!)

### Architecture

```
src/i18n/
├── translations.js    # Dictionary: 17 keys × 2 locales (en/zh)
└── index.js           # getLocale(), t(key, params) with interpolation
```

**Locale detection priority**: `cockpit.language` → `navigator.language` → `'en'`

### Usage Pattern
```javascript
import { t } from './i18n';

// Simple
t('store.title')  // → '应用商店' or 'Application Store'

// With interpolation
t('store.pagination.pageInfo', { page: 1, totalPages: 5, totalItems: 100 })
```

## Key Learnings (For Future Reference)

1. **Cockpit plugins MUST load both `cockpit.js` AND `po.js`** — `po.js` initializes the language context
2. **`cockpit.language` values**: `'en'`, `'zh_CN'`, `'zh_TW'`, etc. — use `.startsWith('zh')` for Chinese detection
3. **Cockpit auto-reloads iframe on language switch** — no manual reload logic needed for most cases
4. **Dictionary approach vs PO files**: For <20 strings with 2 languages, dictionary is simpler and more maintainable

## Files Modified

| File | Change |
|------|--------|
| `public/index.html` | Added cockpit.js + po.js scripts |
| `src/i18n/translations.js` | Created dictionary (17 keys × 2 locales) |
| `src/i18n/index.js` | Enhanced with `getLocale()`, `t()` with interpolation |
| `src/utils/api.js` | Removed duplicate getLocale(), use shared locale |
| `src/App.js` | Replaced isZh ternaries with t() |
| `src/components/FilterBar.js` | Replaced isZh ternaries with t() |
| `src/components/PaginationControls.js` | Replaced isZh ternaries with t() |
| `src/components/SecondaryCategoryNav.js` | Replaced isZh ternaries with t() |
| `src/components/MediaCard.js` | Added fallback string translations |

## Out of Scope

- Dead code cleanup (`TwoLevelCategoryNav.js`, `CategoryTabs.js`, `SearchBar.js` — not imported)
- Languages beyond zh/en
- Cockpit PO file generation
