/**
 * Services Plugin Configuration
 */

// Supervisord connection settings
export const SUPERVISORD_CONFIG = {
  address: '127.0.0.1',
  port: 9001,
  // In production, these should be loaded from environment variables
  // For now using placeholder - actual auth handled by cockpit
  username: process.env.SUPERVISOR_USER || 'admin',
  password: process.env.SUPERVISOR_PASSWORD || 'admin'
};

// UI timing constants
export const UI_TIMINGS = {
  REFRESH_DELAY: 500,        // Delay before refreshing table after operation (ms)
  TOAST_DURATION: 5000,      // Auto-dismiss time for toast notifications (ms)
  AUTO_REFRESH_INTERVAL: 5000 // Auto-refresh interval for status polling (ms)
};

// System-critical services that should not be controlled
export const PROTECTED_SERVICES = ['cockpit-ws', 'nginx'];

// Feature flags (for future use)
export const FEATURES = {
  ENABLE_DEBUG_LOGS: process.env.NODE_ENV === 'development'
};
