import React from 'react';
import { Pagination } from '@patternfly/react-core';
import { t } from '../i18n';

const PaginationControls = ({ 
  page, 
  totalPages, 
  pageSize,
  totalItems, 
  onPageChange, 
  onPageSizeChange 
}) => {
  return (
    <Pagination
      itemCount={totalItems}
      perPage={pageSize}
      page={page}
      onSetPage={(_event, pageNumber) => onPageChange(pageNumber)}
      onPerPageSelect={(_event, perPage) => onPageSizeChange(perPage)}
      perPageOptions={[
        { title: '12', value: 12 },
        { title: '24', value: 24 },
        { title: '48', value: 48 },
        { title: '96', value: 96 }
      ]}
      variant="bottom"
      titles={{
        paginationAriaLabel: t('store.pagination.pageInfo', { page, totalPages, totalItems })
      }}
    />
  );
};

export default PaginationControls;
