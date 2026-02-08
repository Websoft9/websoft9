import React from 'react';
import {
  Box,
  Tabs,
  Tab,
  Chip,
  Typography
} from '@mui/material';

/**
 * Two-level category navigation component
 * Level 1: Primary categories (horizontal tabs)
 * Level 2: Secondary categories (chips under selected primary)
 */
const TwoLevelCategoryNav = ({ 
  catalogData, 
  primaryCategory, 
  secondaryCategory, 
  onPrimaryChange, 
  onSecondaryChange,
  totalCount,
  primaryCategoryCount
}) => {
  // Sort primary categories by position
  const sortedCatalog = [...catalogData].sort((a, b) => {
    const posA = a.position ?? 999;
    const posB = b.position ?? 999;
    return posA - posB;
  });

  // Extract primary categories with counts
  const isZh = catalogData.length > 0 && catalogData[0].title.match(/[\u4e00-\u9fa5]/);
  const primaryCategories = [
    { 
      key: 'all', 
      title: isZh ? `全部 (${totalCount})` : `All (${totalCount})` 
    },
    ...sortedCatalog
  ];

  // Get secondary categories for selected primary
  const getSecondaryCategories = () => {
    if (primaryCategory === 'all') return [];
    
    const selected = catalogData.find(cat => cat.key === primaryCategory);
    if (!selected || !selected.linkedFrom?.catalogCollection?.items) return [];
    
    return selected.linkedFrom.catalogCollection.items;
  };

  const secondaryCategories = getSecondaryCategories();

  return (
    <Box>
      {/* Primary Categories */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs
          value={primaryCategory}
          onChange={(e, val) => onPrimaryChange(val)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            '& .MuiTab-root': {
              textTransform: 'none',
              fontSize: '1rem',
              fontWeight: 500,
              minWidth: 100
            }
          }}
        >
          {primaryCategories.map((cat) => (
            <Tab
              key={cat.key}
              label={
                <Typography variant="body1">
                  {cat.title}
                </Typography>
              }
              value={cat.key}
            />
          ))}
        </Tabs>
      </Box>

      {/* Secondary Categories (Chips) */}
      {secondaryCategories.length > 0 && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 3 }}>
          <Chip
            label={isZh ? `全部 (${primaryCategoryCount})` : `All (${primaryCategoryCount})`}
            clickable
            color={secondaryCategory === 'all' ? 'primary' : 'default'}
            onClick={() => onSecondaryChange('all')}
            sx={{ fontSize: '0.9rem' }}
          />
          {secondaryCategories.map((cat) => (
            <Chip
              key={cat.key}
              label={cat.title}
              clickable
              color={secondaryCategory === cat.key ? 'primary' : 'default'}
              onClick={() => onSecondaryChange(cat.key)}
              sx={{ fontSize: '0.9rem' }}
            />
          ))}
        </Box>
      )}
    </Box>
  );
};

export default TwoLevelCategoryNav;
