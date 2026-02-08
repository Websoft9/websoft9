import React from 'react';
import { Box, Chip, Stack } from '@mui/material';
import { locale } from '../i18n';

/**
 * Secondary category navigation as chips
 */
const SecondaryCategoryNav = ({ 
  catalogData, 
  primaryCategory, 
  secondaryCategory, 
  onSecondaryChange,
  primaryCategoryCount 
}) => {
  const isZh = locale === 'zh';
  
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
    <Box sx={{ mb: 2 }}>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        <Chip
          label={`${isZh ? '全部' : 'All'} (${primaryCategoryCount})`}
          onClick={() => onSecondaryChange('all')}
          color={secondaryCategory === 'all' ? 'primary' : 'default'}
          clickable
          sx={{ mb: 1 }}
        />
        {sortedSecondary.map((subCat) => (
          <Chip
            key={subCat.key}
            label={subCat.title}
            onClick={() => onSecondaryChange(subCat.key)}
            color={secondaryCategory === subCat.key ? 'primary' : 'default'}
            clickable
            sx={{ mb: 1 }}
          />
        ))}
      </Stack>
    </Box>
  );
};

export default SecondaryCategoryNav;
