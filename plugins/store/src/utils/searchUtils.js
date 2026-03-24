/**
 * Search utilities for autocomplete functionality
 * - Build search index from media data
 * - Match with priority scoring
 * - Search history management in localStorage
 */

// Configuration constants
const HISTORY_KEY = 'store_search_history';
const MAX_HISTORY = 10;
const MAX_SUGGESTIONS = 10;
const DEBOUNCE_MS = 300;
const MAX_QUERY_LENGTH = 100;

// Match priority scores
const SCORES = {
  HISTORY: 100,
  PREFIX: 50,
  CONTAINS: 10
};

/**
 * Build search index from media data
 * @param {Array} mediaData - Array of media items
 * @returns {Array} Search index with key, name, category, logo
 */
export const buildSearchIndex = (mediaData) => {
  if (!Array.isArray(mediaData)) return [];
  
  return mediaData.map(item => {
    const name = item.trademark || item.title || item.name || '';
    return {
      key: item.key,
      name,
      nameLower: name.toLowerCase(),
      category: item.catalogCollection?.items?.[0]?.title || '',
      logo: item.logo?.imageurl || item.logo || ''
    };
  });
};

/**
 * Get autocomplete suggestions based on query
 * @param {string} query - Search query
 * @param {Array} searchIndex - Pre-built search index
 * @param {Array} history - Search history array
 * @param {number} limit - Max number of suggestions
 * @returns {Array} Sorted suggestions with priority scoring
 */
export const getSuggestions = (query, searchIndex, history = [], limit = MAX_SUGGESTIONS) => {
  // If empty query, return recent history
  if (!query || query.trim() === '') {
    return history.slice(0, limit).map(text => ({ 
      text, 
      type: 'history', 
      score: SCORES.HISTORY 
    }));
  }
  
  // Validate query length to prevent abuse
  const trimmedQuery = query.trim();
  if (trimmedQuery.length > MAX_QUERY_LENGTH) {
    return [];
  }
  
  const q = trimmedQuery.toLowerCase();
  const results = [];
  const seen = new Set();
  
  // Process history matches first (highest priority)
  history.forEach(h => {
    const hLower = h.toLowerCase();
    if (hLower.startsWith(q) && !seen.has(hLower)) {
      results.push({ text: h, type: 'history', score: SCORES.HISTORY });
      seen.add(hLower);
    }
  });
  
  // Single loop through search index - check both prefix and contains
  searchIndex.forEach(item => {
    if (seen.has(item.nameLower)) return;
    
    if (item.nameLower.startsWith(q)) {
      results.push({ ...item, type: 'prefix', score: SCORES.PREFIX });
      seen.add(item.nameLower);
    } else if (item.nameLower.includes(q)) {
      results.push({ ...item, type: 'contains', score: SCORES.CONTAINS });
      seen.add(item.nameLower);
    }
  });
  
  // Sort by score descending, then alphabetically
  return results
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      const aText = a.text || a.name || '';
      const bText = b.text || b.name || '';
      return aText.localeCompare(bText);
    })
    .slice(0, limit);
};

/**
 * Debounce utility function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

/**
 * Get search history from localStorage
 * @returns {Array} Array of search terms
 */
export const getSearchHistory = () => {
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch (error) {
    console.error('Failed to load search history:', error);
    return [];
  }
};

/**
 * Add a search term to history
 * @param {string} term - Search term to add
 */
export const addSearchHistory = (term) => {
  if (!term || term.trim() === '') return;
  
  try {
    const history = getSearchHistory();
    // Remove if already exists, add to front
    const filtered = history.filter(h => h !== term);
    const updated = [term, ...filtered].slice(0, MAX_HISTORY);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
  } catch (error) {
    console.error('Failed to save search history:', error);
  }
};

/**
 * Clear all search history
 */
export const clearSearchHistory = () => {
  try {
    localStorage.removeItem(HISTORY_KEY);
  } catch (error) {
    console.error('Failed to clear search history:', error);
  }
};

// Export configuration constants for external use
export { MAX_SUGGESTIONS, DEBOUNCE_MS, MAX_QUERY_LENGTH };
