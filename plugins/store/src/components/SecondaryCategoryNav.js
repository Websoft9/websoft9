import React from 'react';
import { LabelGroup, Label } from '@patternfly/react-core';
import { t } from '../i18n';

/**
 * Secondary category navigation as labels
 */
const SecondaryCategoryNav = ({ 
  catalogData, 
  primaryCategory, 
  secondaryCategory, 
  onSecondaryChange,
  primaryCategoryCount 
}) => {
  // Find selected primary category
  const selectedPrimary = catalogData.find(cat => cat.key === primaryCategory);
  
  // Get secondary categories (sorted by position)
  const secondaryCategories = selectedPrimary?.catalogCollection?.items || [];
  const sortedSecondary = [...secondaryCategories].sort((a, b) => {
    const posA = a.position ?? 999;
    const posB = b.position ?? 999;
    return posA - posB;
  });

  // Don't show if "all" or no secondary categories
  if (primaryCategory === 'all' || sortedSecondary.length === 0) {
    return null;
  }

  return (
    <div style={{ marginTop: 'var(--pf-t--global--spacer--md)' }}>
      <LabelGroup>
        <Label
          color={secondaryCategory === 'all' ? 'blue' : 'grey'}
          isCompact
          onClick={() => onSecondaryChange('all')}
          style={{ cursor: 'pointer' }}
        >
          {t('store.category.allWithCount', { count: primaryCategoryCount })}
        </Label>
        {sortedSecondary.map((subCat) => (
          <Label
            key={subCat.key}
            color={secondaryCategory === subCat.key ? 'blue' : 'grey'}
            isCompact
            onClick={() => onSecondaryChange(subCat.key)}
            style={{ cursor: 'pointer' }}
          >
            {subCat.title}
          </Label>
        ))}
      </LabelGroup>
    </div>
  );
};

export default SecondaryCategoryNav;
