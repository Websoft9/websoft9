/**
 * Centralized Translation Dictionary for Store Plugin
 * Story 5.5: UI-level i18n (frontend static text)
 * 
 * Two layers of i18n:
 * 1. Data-level i18n: w9media provides catalog_zh.json/product_zh.json (Story 5.2)
 * 2. UI-level i18n: This dictionary for frontend labels/buttons/messages (Story 5.5)
 */

export const translations = {
  en: {
    // Page title
    'store.title': 'Application Store',
    
    // Search
    'store.search.placeholder': 'Search applications...',
    
    // Categories
    'store.category.all': 'All',
    'store.category.allWithCount': 'All ({count})',
    'store.category.allCategories': 'All Categories',
    'store.category.allCategoriesWithCount': 'All Categories ({count})',
    
    // Pagination
    'store.pagination.itemsPerPage': 'Items per page',
    'store.pagination.pageInfo': 'Page {page} of {totalPages} ({totalItems} items)',
    
    // Empty state
    'store.noResults': 'No applications found',
    
    // MediaCard fallbacks
    'store.card.unknownApp': 'Unknown App',
    'store.card.noDescription': 'No description available',
    'store.card.defaultCategory': 'General',
    
    // Error messages
    'store.error.loadFailed': 'Failed to load applications',
    'store.error.apiError': 'API Error: {message}. Using mock data as fallback.',
    'store.error.fetchCatalog': 'Failed to fetch catalog: {message}',
    'store.error.fetchProducts': 'Failed to fetch products: {message}',
    
    // Modal (Story 5.6)
    'modal.version': 'Version',
    'modal.requires': 'Requires at least',
    'modal.categories': 'Categories',
    'modal.documentation': 'Documentation',
    'modal.website': 'Official Website',
    'modal.overview': 'Overview',
    'modal.description': 'Description',
    'modal.close': 'Close',
    'modal.loading': 'Loading...',
    'modal.error': 'Failed to load application details',
    'modal.next': 'Next',
    'modal.prev': 'Back',
    'modal.favorite': 'Favorite',
    'modal.install': 'Install',
  },
  zh: {
    // 页面标题
    'store.title': '应用商店',
    
    // 搜索
    'store.search.placeholder': '搜索应用...',
    
    // 分类
    'store.category.all': '全部',
    'store.category.allWithCount': '全部 ({count})',
    'store.category.allCategories': '全部分类',
    'store.category.allCategoriesWithCount': '全部分类 ({count})',
    
    // 分页
    'store.pagination.itemsPerPage': '每页显示',
    'store.pagination.pageInfo': '第 {page} 页 / 共 {totalPages} 页 (共 {totalItems} 个应用)',
    
    // 空状态
    'store.noResults': '未找到相关应用',
    
    // 卡片默认值
    'store.card.unknownApp': '未知应用',
    'store.card.noDescription': '暂无描述',
    'store.card.defaultCategory': '通用',
    
    // 错误消息
    'store.error.loadFailed': '加载应用失败',
    'store.error.apiError': 'API 错误: {message}。使用模拟数据作为备选。',
    'store.error.fetchCatalog': '获取目录失败: {message}',
    'store.error.fetchProducts': '获取产品失败: {message}',
    
    // 模态窗口 (Story 5.6)
    'modal.version': '版本',
    'modal.requires': '最低配置要求',
    'modal.categories': '分类',
    'modal.documentation': '文档',
    'modal.website': '官方网站',
    'modal.overview': '概览',
    'modal.description': '详情',
    'modal.close': '关闭',
    'modal.loading': '加载中...',
    'modal.error': '加载应用详情失败',
    'modal.next': '下一张',
    'modal.prev': '上一张',
    'modal.favorite': '收藏',
    'modal.install': '安装',
  }
};
