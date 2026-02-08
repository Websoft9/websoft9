import React from 'react';
import {
  Box,
  TextField,
  InputAdornment,
  FormControl,
  Select,
  MenuItem,
  Grid
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { locale } from '../i18n';

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
  // Sort primary categories by position
  const sortedCatalog = [...catalogData].sort((a, b) => {
    const posA = a.position ?? 999;
    const posB = b.position ?? 999;
    return posA - posB;
  });

  const isZh = locale === 'zh';
  
  return (
    <Box sx={{ mb: 3 }}>
      <Grid container spacing={2}>
        {/* Primary Category Selector */}
        <Grid item xs={12} sm={4} md={3}>
          <FormControl fullWidth>
            <Select
              value={primaryCategory}
              onChange={(e) => onPrimaryChange(e.target.value)}
              displayEmpty
              sx={{
                backgroundColor: 'background.paper',
                '& .MuiSelect-select': {
                  py: '14.5px'
                }
              }}
            >
              <MenuItem value="all">
                {isZh ? '全部分类' : 'All Categories'} ({totalCount})
              </MenuItem>
              {sortedCatalog.map((cat) => (
                <MenuItem key={cat.key} value={cat.key}>
                  {cat.title}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Search Box */}
        <Grid item xs={12} sm={8} md={9}>
          <TextField
            fullWidth
            placeholder={isZh ? '搜索应用...' : 'Search applications...'}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: 'background.paper',
              }
            }}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default FilterBar;
