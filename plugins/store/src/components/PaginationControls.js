import React from 'react';
import {
  Box,
  Pagination,
  Select,
  MenuItem,
  Typography,
  FormControl
} from '@mui/material';
import { locale } from '../i18n';

const PaginationControls = ({ 
  page, 
  totalPages, 
  pageSize,
  totalItems, 
  onPageChange, 
  onPageSizeChange 
}) => {
  const isZh = locale === 'zh';
  
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mt: 4,
        flexWrap: 'wrap',
        gap: 2
      }}
    >
      {/* Page Size Selector */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="body2" color="text.secondary">
          {isZh ? '每页显示' : 'Items per page'}:
        </Typography>
        <FormControl size="small">
          <Select
            value={pageSize}
            onChange={(e) => onPageSizeChange(e.target.value)}
            sx={{ minWidth: 80 }}
          >
            <MenuItem value={12}>12</MenuItem>
            <MenuItem value={24}>24</MenuItem>
            <MenuItem value={48}>48</MenuItem>
            <MenuItem value={96}>96</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Pagination */}
      <Pagination
        count={totalPages}
        page={page}
        onChange={(e, value) => onPageChange(value)}
        color="primary"
        showFirstButton
        showLastButton
        size="large"
      />

      {/* Page Info */}
      <Typography variant="body2" color="text.secondary">
        {isZh 
          ? `第 ${page} 页 / 共 ${totalPages} 页 (共 ${totalItems} 个应用)`
          : `Page ${page} of ${totalPages} (${totalItems} items)`
        }
      </Typography>
    </Box>
  );
};

export default PaginationControls;
