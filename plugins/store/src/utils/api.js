/**
 * API Utilities for Store Plugin - Story 5.2 & 5.5
 * Loads media data from nginx-served static JSON files
 * Uses same pattern as appstore: cockpit.spawn to get nginx port
 */

import { getCurrentLocale, t } from '../i18n';

/**
 * Build base URL for media API
 * Uses same-origin path (no CORS issues)
 * Running in Cockpit = same nginx server
 */
const getMediaBase = () => {
  // Same origin, relative path
  return '/w9media';
};

/**
 * Fetch with retry logic and exponential backoff
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {number} retries - Number of retry attempts
 * @returns {Promise} Parsed JSON data
 */
const fetchWithRetry = async (url, options = {}, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url, options);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    } catch (error) {
      // Last attempt failed
      if (i === retries - 1) {
        throw error;
      }
      
      // Wait before retry (exponential backoff: 1s, 2s, 4s)
      const waitTime = 1000 * Math.pow(2, i);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
  }
};

/**
 * Fetch catalog data (categories and grouping)
 * Static JSON file served by nginx: /media/catalog_{locale}.json
 * @returns {Promise<Array>} Catalog data array
 */
export const fetchCatalog = async () => {
  const mediaBase = getMediaBase();
  const currentLocale = getCurrentLocale();
  const url = `${mediaBase}/json/catalog_${currentLocale}.json`;
  
  try {
    return await fetchWithRetry(url);
  } catch (error) {
    console.error('Failed to fetch catalog:', error);
    throw new Error(t('store.error.fetchCatalog', { message: error.message }));
  }
};

/**
 * Fetch product data (full app details with media URLs)
 * Static JSON file served by nginx: /media/product_{locale}.json
 * @returns {Promise<Array>} Product data array
 */
export const fetchProducts = async () => {
  const mediaBase = getMediaBase();
  const currentLocale = getCurrentLocale();
  const url = `${mediaBase}/json/product_${currentLocale}.json`;
  
  try {
    return await fetchWithRetry(url);
  } catch (error) {
    console.error('Failed to fetch products:', error);
    throw new Error(t('store.error.fetchProducts', { message: error.message }));
  }
};

/**
 * Helper: Get full media URL for images
 * Handles both absolute paths (/media/logos/...) and relative paths (logos/...)
 * @param {string} relativePath - Relative or absolute path
 * @returns {string} Full URL path
 */
export const getMediaUrl = (relativePath) => {
  const base = '/w9media';

  if (!relativePath) return `${base}/placeholder.png`;
  if (relativePath.startsWith('http')) return relativePath;
  if (relativePath.startsWith('/w9media/')) return relativePath;
  if (relativePath.startsWith('/media/')) {
    return relativePath.replace('/media/', '/w9media/');
  }
  if (relativePath.startsWith('/')) return `${base}${relativePath}`;
  return `${base}/${relativePath}`;
};

/**
 * Extract unique categories from product data
 * @param {Array} products - Product data array
 * @returns {Array} Array of unique category strings
 */
export const extractCategories = (products) => {
  const uniqueCategories = new Set(['all']);
  
  products.forEach(product => {
    // Primary category
    if (product.catalogCollection?.items?.[0]?.title) {
      uniqueCategories.add(product.catalogCollection.items[0].title);
    }
    
    // Sub-categories (if any)
    if (product.catalogCollection?.items?.[0]?.catalogCollection?.items) {
      product.catalogCollection.items[0].catalogCollection.items.forEach(subCat => {
        if (subCat.title) {
          uniqueCategories.add(subCat.title);
        }
      });
    }
  });
  
  return Array.from(uniqueCategories);
};

/**
 * Categorize media items
 * @param {Array} items - Media items
 * @returns {Object} Categorized media items
 */
export const categorizeMedia = (items) => {
  const categories = {};
  
  items.forEach(item => {
    const category = item.category || 'Uncategorized';
    if (!categories[category]) {
      categories[category] = [];
    }
    categories[category].push(item);
  });

  return categories;
};

/**
 * Get unique categories from media items (legacy, use extractCategories instead)
 * @param {Array} items - Media items
 * @returns {Array} Array of unique categories
 */
export const getUniqueCategories = (items) => {
  const categories = new Set(items.map(item => item.category || 'Uncategorized'));
  return ['All', ...Array.from(categories)];
};

/**
 * Fetch detailed information for a single product by key
 * Story 5.6: Application Detail Modal
 * @param {string} key - Application key (e.g., 'wordpress', 'espocrm')
 * @returns {Promise<Object>} Product detail object
 */
export const getProductDetail = async (key) => {
  const currentLocale = getCurrentLocale();
  const url = `${getMediaBase()}/json/product_${currentLocale}.json`;
  
  try {
    const response = await fetchWithRetry(url);
    
    // Find the specific product in the products array
    const products = response.products || response;
    const product = Array.isArray(products) 
      ? products.find(p => p.key === key)
      : null;
    
    if (!product) {
      throw new Error(`Product not found: ${key}`);
    }
    
    return product;
  } catch (error) {
    console.error(`Error fetching product detail for ${key}:`, error);
    throw error;
  }
};
