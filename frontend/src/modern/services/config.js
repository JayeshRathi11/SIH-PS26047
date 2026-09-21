/**
 * MediKiosk Frontend Configuration
 * Single source of truth for frontend application settings & API base URL.
 */

const defaultApiUrl = 'http://127.0.0.1:8000';

function getInitialUrl() {
  if (typeof window !== 'undefined') {
    if (window.__MEDIKIOSK_CONFIG__ && window.__MEDIKIOSK_CONFIG__.API_BASE_URL) {
      return window.__MEDIKIOSK_CONFIG__.API_BASE_URL;
    }
    if (window.MEDIKIOSK_API_BASE_URL) {
      return window.MEDIKIOSK_API_BASE_URL;
    }
  }
  return defaultApiUrl;
}

export const MediKioskConfig = {
  DEFAULT_API_BASE_URL: defaultApiUrl,
  API_BASE_URL: getInitialUrl(),

  getApiBaseUrl() {
    const url = this.API_BASE_URL || this.DEFAULT_API_BASE_URL;
    return String(url).trim().replace(/\/+$/, '');
  },

  setApiBaseUrl(url) {
    if (typeof url === 'string' && url.trim().length > 0) {
      this.API_BASE_URL = url.trim().replace(/\/+$/, '');
    }
  }
};

if (typeof window !== 'undefined') {
  window.MediKioskConfig = MediKioskConfig;
}

export default MediKioskConfig;
