import React, { useState } from 'react';
import {
  Toolbar,
  ToolbarContent,
  ToolbarItem,
  SearchInput,
  MenuToggle,
  Select,
  SelectList,
  SelectOption
} from '@patternfly/react-core';
import { t } from '../i18n';

/**
 * Filter bar with primary category selector and search box
 */
const FilterBar = ({ 
  catalogData, 
  primaryCategory, 
  onPrimaryChange, 
  searchQuery, 
  onSearchChange,
  totalCount,
  primaryCategoryCount
}) => {
  const [isCategoryOpen, setIsCategoryOpen] = useState(false);

  // Sort primary categories by position
  const sortedCatalog = [...catalogData].sort((a, b) => {
    const posA = a.position ?? 999;
    const posB = b.position ?? 999;
    return posA - posB;
  });

  // Get display text for selected category
  const getSelectedCategoryLabel = () => {
    if (primaryCategory === 'all') {
      return t('store.category.allCategoriesWithCount', { count: totalCount });
    }
    const category = sortedCatalog.find(cat => cat.key === primaryCategory);
    return category ? category.title : t('store.category.allCategories');
  };

  const handleCategorySelect = (_event, value) => {
    onPrimaryChange(value);
    setIsCategoryOpen(false);
  };

  const handleCategoryToggle = () => {
    setIsCategoryOpen(!isCategoryOpen);
  };

  return (
    <Toolbar>
      <ToolbarContent>
        {/* Category Selector */}
        <ToolbarItem>
          <Select
            isOpen={isCategoryOpen}
            selected={primaryCategory}
            onSelect={handleCategorySelect}
            onOpenChange={setIsCategoryOpen}
            toggle={(toggleRef) => (
              <MenuToggle
                ref={toggleRef}
                onClick={handleCategoryToggle}
                isExpanded={isCategoryOpen}
                style={{ minWidth: '250px' }}
              >
                {getSelectedCategoryLabel()}
              </MenuToggle>
            )}
          >
            <SelectList>
              <SelectOption value="all">
                {t('store.category.allCategoriesWithCount', { count: totalCount })}
              </SelectOption>
              {sortedCatalog.map((cat) => (
                <SelectOption key={cat.key} value={cat.key}>
                  {cat.title}
                </SelectOption>
              ))}
            </SelectList>
          </Select>
        </ToolbarItem>

        {/* Search Box */}
        <ToolbarItem variant="search-filter" style={{ flex: 1 }}>
          <SearchInput
            placeholder={t('store.search.placeholder')}
            value={searchQuery}
            onChange={(_event, value) => onSearchChange(value)}
            onClear={() => onSearchChange('')}
          />
        </ToolbarItem>
      </ToolbarContent>
    </Toolbar>
  );
};

export default FilterBar;
