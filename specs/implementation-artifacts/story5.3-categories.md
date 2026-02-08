# Story 5.3: Category Management

**Epic**: Epic 5 - Store Plugin  
**Priority**: P1  
**Status**: Not Started

## User Story
As a user, I want to filter media by category, so that I can quickly find specific types of applications.

## Acceptance Criteria
- [ ] Dynamic category extraction from media data
- [ ] Tab navigation switches between categories
- [ ] "All" category shows everything
- [ ] Category counts displayed (optional)
- [ ] Persist selected category in URL/state

## Technical Details

**Files**:
- `plugins/store/src/App.js` - Category state management
- `plugins/store/src/components/CategoryTabs.js` - Tab UI

**Category Logic**:
```javascript
// Extract from media items
categories = ['All', 'CMS', 'DevOps', 'Database', ...]

// Filter logic
filteredData = category === 'All' 
  ? allData 
  : allData.filter(item => item.category === category)
```

**URL State** (optional):
```
/store?category=CMS
```

## Testing
- Verify all categories appear
- Click each tab, verify filtering
- Check "All" shows complete list
- Test with empty categories
