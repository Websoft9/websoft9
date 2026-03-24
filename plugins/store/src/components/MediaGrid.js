import React from 'react';
import { Gallery } from '@patternfly/react-core';
import MediaCard from './MediaCard';

/**
 * MediaGrid Component - PatternFly Gallery layout for application cards
 * Responsive grid that adapts to screen size:
 * - Desktop: 4-6 columns
 * - Tablet: 2-3 columns
 * - Mobile: 1 column
 */
const MediaGrid = ({ items, onItemSelect }) => {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <Gallery 
      hasGutter
      minWidths={{
        default: '100%',       // Mobile: 1 column
        sm: '280px',           // Small: 2-3 columns per row
        md: '250px',           // Medium: 3-4 columns per row
        lg: '220px',           // Large: 4-5 columns per row
        xl: '200px'            // Extra large: 5-6 columns per row
      }}
    >
      {items.map((item) => (
        <MediaCard 
          key={item.key || item.id}
          item={item} 
          onSelect={onItemSelect}
        />
      ))}
    </Gallery>
  );
};

export default MediaGrid;
