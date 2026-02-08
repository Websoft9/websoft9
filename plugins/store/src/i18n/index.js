/**
 * i18n Configuration for Store Plugin
 * Following Cockpit standard: using cockpit.gettext
 */

/* global cockpit */

// Cockpit standard way: use cockpit.gettext
let _ = (text) => text; // Fallback for non-Cockpit environment

try {
  if (typeof cockpit !== 'undefined' && cockpit.gettext) {
    _ = cockpit.gettext;
  }
} catch (e) {
  console.warn('Cockpit not available, using fallback i18n');
}

// Get user's preferred locale
export const getLocale = () => {
  try {
    if (typeof cockpit !== 'undefined' && cockpit.language) {
      return cockpit.language.startsWith('zh') ? 'zh' : 'en';
    }
  } catch (e) {
    // ignore
  }
  const browserLang = navigator.language || navigator.userLanguage || 'en';
  return browserLang.startsWith('zh') ? 'zh' : 'en';
};

// Export gettext function for translation
export const t = _;

export const locale = getLocale();
