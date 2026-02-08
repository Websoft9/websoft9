import React from 'react';
import {
  Box,
  Tabs,
  Tab,
  Typography
} from '@mui/material';

const CategoryTabs = ({ categories, selectedCategory, onCategoryChange }) => {
  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 4 }}>
      <Tabs 
        value={selectedCategory} 
        onChange={onCategoryChange}
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
        {categories.map((category, index) => (
          <Tab 
            key={index} 
            label={
              <Typography variant="body1">
                {category.charAt(0).toUpperCase() + category.slice(1)}
              </Typography>
            }
            value={category}
          />
        ))}
      </Tabs>
    </Box>
  );
};

export default CategoryTabs;
