# Story 5.3: Category Management

**Epic**: Epic 5 - Store Plugin  
**Priority**: P1  
**Status**: Complete  
**Dependencies**: Story 5.1 (Core UI), Story 5.2 (Media API)

## User Story
As a user, I want to filter media by two-level categories, search apps, and paginate results.

## Acceptance Criteria
- [x] Two-level category navigation (primary → secondary)
- [x] Primary category dropdown + secondary category chips
- [x] Real-time search by name/description/tags
- [x] Pagination with configurable page sizes (12/24/48/96)
- [x] App counts displayed per category
- [x] Compact card layout with overview field
- [x] Responsive design

## Technical Details

**Files**:
- `plugins/store/src/App.js` - State management, filtering logic
- `plugins/store/src/components/FilterBar.js` - Primary dropdown + search
- `plugins/store/src/components/SecondaryCategoryNav.js` - Secondary chips
- `plugins/store/src/components/PaginationControls.js` - Pagination UI
- `plugins/store/src/components/MediaCard.js` - Compact card (120px image)
- `plugins/store/src/components/MediaGrid.js` - Grid layout (spacing=2)

**W9Media API Data Structure**:
```javascript
// catalog_zh.json - Primary categories at root level
[{
  "key": "cms",
  "title": "网站与内容聚合",
  "position": 5,
  "linkedFrom": {
    "catalogCollection": {
      "items": [/* secondary categories */]
    }
  }
}]

// product_zh.json - Products with multiple secondary categories
{
  "catalogCollection": {
    "items": [  // Array of secondary categories
      {
        "key": "website",
        "title": "企业建站",
        "catalogCollection": {
          "items": [{  // Parent primary category
            "key": "cms",
            "title": "网站与内容聚合"
          }]
        }
      }
    ]
  }
}
```

**Implementation Pattern**:
```javascript
// Build primary category structure
const primaryCategories = catalogResult.map(pc => ({
  ...pc,
  catalogCollection: {
    items: pc.linkedFrom?.catalogCollection?.items || []
  }
}));

// Filter by primary (products may belong to multiple secondary categories)
filtered = mediaData.filter(item => {
  const secondaryCategories = item.catalogCollection?.items || [];
  return secondaryCategories.some(sc => 
    sc.catalogCollection?.items?.[0]?.key === primaryCategory
  );
});

// Filter by secondary
filtered = filtered.filter(item => {
  return item.catalogCollection?.items?.some(
    cat => cat.key === secondaryCategory
  );
});
```

## UI Pattern
- **FilterBar**: Dropdown (primary) + Search input in one row
- **SecondaryCategoryNav**: Chips navigation (hidden when "all")
- **Compact Cards**: 120px image, single-line overview, spacing=2
- **i18n**: Inline zh/en check (no translation dict)

## Definition of Done
- [x] Two-level category filtering works
- [x] Search real-time filtering
- [x] Pagination functional
- [x] Mobile responsive
- [x] Deployed to websoft9-cockpit container
- [x] Using real w9media API
- [x] Bundle: 119.52 KB gzipped
