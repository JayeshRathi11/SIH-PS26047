/**
 * MediKiosk Frontend Configuration
 * Single source of truth for frontend application settings & API base URL.
 * 
 * Local Development Default: http://127.0.0.1:8000 (FastAPI backend)
 */
(function (root) {
  'use strict';

  var defaultApiUrl = 'http://127.0.0.1:8000';

  // Allow runtime override via global window variables if injected during deployment
  var getInitialUrl = function () {
    if (root && root.__MEDIKIOSK_CONFIG__ && root.__MEDIKIOSK_CONFIG__.API_BASE_URL) {
      return root.__MEDIKIOSK_CONFIG__.API_BASE_URL;
    }
    if (root && root.MEDIKIOSK_API_BASE_URL) {
      return root.MEDIKIOSK_API_BASE_URL;
    }
    return defaultApiUrl;
  };

  var MediKioskConfig = {
    DEFAULT_API_BASE_URL: defaultApiUrl,
    API_BASE_URL: getInitialUrl(),

    /**
     * Get the active backend API base URL without trailing slash.
     */
    getApiBaseUrl: function () {
      var url = this.API_BASE_URL || this.DEFAULT_API_BASE_URL;
      return String(url).trim().replace(/\/+$/, '');
    },

    /**
     * Dynamically update the backend API base URL.
     * @param {string} url - Base URL (e.g. 'http://127.0.0.1:8000')
     */
    setApiBaseUrl: function (url) {
      if (typeof url === 'string' && url.trim().length > 0) {
        this.API_BASE_URL = url.trim().replace(/\/+$/, '');
      }
    }
  };

  // Clean trailing slashes on initialization
  MediKioskConfig.setApiBaseUrl(MediKioskConfig.API_BASE_URL);

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = MediKioskConfig;
  }
  if (root) {
    root.MediKioskConfig = MediKioskConfig;
  }
})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));
