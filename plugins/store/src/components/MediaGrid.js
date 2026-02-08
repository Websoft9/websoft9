import React from 'react';
import { Grid } from '@mui/material';
import MediaCard from './MediaCard';

/**
 * MediaGrid Component - Responsive grid layout for media cards
 * Extracted pattern from appstore.js grid layout
 * - Desktop: 4 columns (3 cards per row = 33.33% width = 4 in MUI Grid)
 * - Tablet: 2 columns (6 in MUI Grid = 50%)
 * - Mobile: 1 column (12 in MUI Grid = 100%)
 */
const MediaGrid = ({ items, onItemSelect }) => {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <Grid container spacing={2}>
      {items.map((item, index) => (
        <Grid 
          item 
          xs={12}  // Mobile: 1 column
          sm={6}   // Tablet: 2 columns
          md={4}   // Desktop: 3 columns
          lg={3}   // Large desktop: 4 columns
          key={item.key || item.id || index}
        >
          <MediaCard 
            item={item} 
            onSelect={onItemSelect}
            isFirstScreen={index < 8} // First 8 items load eagerly
          />
        </Grid>
      ))}
    </Grid>
  );
};

export default MediaGrid;
