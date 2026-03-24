/**
 * i18n Configuration for Store Plugin
 * Story 5.5: UI-level i18n with centralized translation dictionary
 * 
 * Two layers of i18n:
 * 1. Data-level: w9media provides catalog_zh.json/product_zh.json (Story 5.2)
 * 2. UI-level: This module for frontend labels/buttons/messages (Story 5.5)
 */

/* global cockpit */
import { translations } from './translations';

/**
 * Get user's preferred locale
 * Priority: Cockpit language → browser language → default 'en'
 * @returns {string} locale code ('zh' | 'en')
 */
export const getLocale = () => {
  try {
    if (typeof cockpit !== 'undefined' && cockpit.language) {
      // cockpit.language can be: 'en', 'en_US', 'zh', 'zh_CN', etc.
      return cockpit.language.startsWith('zh') ? 'zh' : 'en';
    }
  } catch (e) {
    // Cockpit not available (dev environment)
  }
  const browserLang = navigator.language || navigator.userLanguage || 'en';
  return browserLang.startsWith('zh') ? 'zh' : 'en';
};

/**
 * Get current locale dynamically
 * This function should be called each time to get the latest Cockpit language
 * Cockpit automatically reloads the plugin iframe when user changes language
 */
export const getCurrentLocale = () => getLocale();

// For backward compatibility - get locale at module load time
// NOTE: Components should use getCurrentLocale() for real-time language detection
export const locale = getLocale();

/**
 * Translation function with interpolation support
 * @param {string} key - Translation key (e.g., 'store.title')
 * @param {Object} params - Interpolation parameters (e.g., {count: 5})
 * @returns {string} Translated text with interpolated values
 * 
 * @example
 * t('store.title') // → 'Application Store' or '应用商店'
 * t('store.category.allWithCount', {count: 42}) // → 'All (42)' or '全部 (42)'
 */
export const t = (key, params = {}) => {
  const currentLocale = getCurrentLocale();
  // Get translation string (fallback to English if key not found in current locale)
  const str = translations[currentLocale]?.[key] || translations['en']?.[key] || key;
  
  // Interpolate parameters: replace {param} with values
  return Object.entries(params).reduce(
    (result, [param, value]) => result.replace(`{${param}}`, value),
    str
  );
};
