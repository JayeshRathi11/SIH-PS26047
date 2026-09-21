/**
 * MediKiosk Shared API Client
 * Reusable vanilla JavaScript HTTP client built on window.fetch.
 *
 * Capabilities:
 * - Base URL resolution from MediKioskConfig
 * - Automatic Authorization: Bearer <token> injection from MediKioskSession
 * - Safe JSON handling for empty/non-JSON responses
 * - Structured ApiError with classification (network, auth, consent, validation, rate limit, server)
 * - Support for GET, POST, PUT, PATCH, DELETE, and multipart/form-data
 * - ZERO sensitive logging: no tokens, authorization headers, or clinical data printed
 */
(function (root) {
  'use strict';

  /**
   * Structured API Error Class
   * @param {string} message - User-safe summary message
   * @param {number} status - HTTP status code (0 for network errors)
   * @param {any} data - Parsed response data/detail if available
   * @param {boolean} isNetworkError - True if request failed before server response
   */
  function ApiError(message, status, data, isNetworkError) {
    this.name = 'ApiError';
    this.message = message || 'An unexpected error occurred.';
    this.status = typeof status === 'number' ? status : 0;
    this.data = data || null;
    this.isNetworkError = !!isNetworkError;
    this.isClientError = this.status >= 400 && this.status < 500;
    this.isServerError = this.status >= 500;
    this.isAuthError = this.status === 401;
    this.isForbidden = this.status === 403;
    this.isNotFound = this.status === 404;
    this.isConflict = this.status === 409;
    this.isValidationError = this.status === 422;
    this.isRateLimit = this.status === 429;

    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiError);
    }
  }

  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  /**
   * Extract user-safe error message from response payload
   */
  function extractErrorMessage(status, responseData) {
    if (responseData) {
      if (typeof responseData.detail === 'string') {
        return responseData.detail;
      }
      if (Array.isArray(responseData.detail) && responseData.detail.length > 0) {
        var first = responseData.detail[0];
        if (first && typeof first.msg === 'string') {
          return first.msg;
        }
      }
      if (typeof responseData.message === 'string') {
        return responseData.message;
      }
    }

    switch (status) {
      case 400: return 'Invalid request. Please verify entered information.';
      case 401: return 'Authentication required. Please re-authenticate.';
      case 403: return 'Access denied. Required consent or authorization missing.';
      case 404: return 'Requested record or resource was not found.';
      case 409: return 'Conflict occurred with the current record state.';
      case 422: return 'Data validation failed. Please check form fields.';
      case 429: return 'Too many requests. Please wait a moment and try again.';
      case 500:
      case 502:
      case 503:
      case 504: return 'Kiosk server error. Please contact clinic staff if this persists.';
      default: return 'Request failed with HTTP status ' + status;
    }
  }

  /**
   * Resolve complete URL from endpoint and configuration
   */
  function resolveUrl(endpoint) {
    if (typeof endpoint !== 'string' || endpoint.trim().length === 0) {
      throw new Error('API endpoint must be a valid string');
    }

    var cleanEndpoint = endpoint.trim();
    if (/^https?:\/\//i.test(cleanEndpoint)) {
      return cleanEndpoint;
    }

    var baseUrl = 'http://127.0.0.1:8000';
    if (root && root.MediKioskConfig && typeof root.MediKioskConfig.getApiBaseUrl === 'function') {
      baseUrl = root.MediKioskConfig.getApiBaseUrl();
    }

    baseUrl = baseUrl.replace(/\/+$/, '');
    cleanEndpoint = cleanEndpoint.replace(/^\/+/, '');

    return baseUrl + '/' + cleanEndpoint;
  }

  /**
   * Get active token from session state if available
   */
  function getActiveAuthToken() {
    if (root && root.MediKioskSession && typeof root.MediKioskSession.getAuthToken === 'function') {
      return root.MediKioskSession.getAuthToken();
    }
    return null;
  }

  /**
   * Core request function
   */
  async function request(endpoint, options) {
    options = options || {};
    var method = (options.method || 'GET').toUpperCase();
    var headers = Object.assign({}, options.headers || {});
    var body = options.body;
    var isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

    // Attach Authorization header if token exists and not already set
    var token = getActiveAuthToken();
    var hasAuthHeader = Object.keys(headers).some(function (key) {
      return key.toLowerCase() === 'authorization';
    });

    if (token && !hasAuthHeader) {
      headers['Authorization'] = 'Bearer ' + token;
    }

    // Default Accept header
    if (!headers['Accept'] && !headers['accept']) {
      headers['Accept'] = 'application/json';
    }

    // Set JSON Content-Type when sending object / non-FormData body
    if (body !== undefined && body !== null && !isFormData) {
      var hasContentType = Object.keys(headers).some(function (key) {
        return key.toLowerCase() === 'content-type';
      });

      if (!hasContentType) {
        headers['Content-Type'] = 'application/json';
      }

      if (typeof body === 'object' && !(body instanceof Blob) && !(body instanceof ArrayBuffer)) {
        body = JSON.stringify(body);
      }
    }

    var fullUrl = resolveUrl(endpoint);
    var fetchImpl = (root && root.fetch) || (typeof fetch !== 'undefined' ? fetch : null);

    if (!fetchImpl) {
      throw new ApiError('Fetch API is not available in current environment.', 0, null, true);
    }

    var response;
    try {
      response = await fetchImpl(fullUrl, {
        method: method,
        headers: headers,
        body: body,
        credentials: options.credentials || 'same-origin'
      });
    } catch (networkErr) {
      throw new ApiError(
        'Network error: Unable to communicate with MediKiosk backend. Please check connectivity.',
        0,
        null,
        true
      );
    }

    // Parse response body safely
    var parsedData = null;
    var status = response.status;
    var contentType = response.headers ? (response.headers.get('content-type') || '') : '';

    if (status !== 204 && status !== 205) {
  try {
    if (options.responseType === 'blob') {
      parsedData = await response.blob();
    } else if (contentType.indexOf('application/json') !== -1) {
      parsedData = await response.json();
    } else {
      var rawText = await response.text();
      try {
        parsedData = JSON.parse(rawText);
      } catch (jsonErr) {
        parsedData = rawText.length > 0 ? rawText : null;
      }
    }
  } catch (parseErr) {
    parsedData = null;
  }
}

    if (!response.ok) {
      var safeMessage = extractErrorMessage(status, parsedData);
      throw new ApiError(safeMessage, status, parsedData, false);
    }

    return {
      status: status,
      ok: response.ok,
      data: parsedData,
      headers: response.headers
    };
  }

  // MediKiosk API Client Object
  var MediKioskApi = {
    ApiError: ApiError,
    request: request,

    get: function (endpoint, options) {
      return request(endpoint, Object.assign({}, options, { method: 'GET' }));
    },

    post: function (endpoint, body, options) {
      return request(endpoint, Object.assign({}, options, { method: 'POST', body: body }));
    },

    put: function (endpoint, body, options) {
      return request(endpoint, Object.assign({}, options, { method: 'PUT', body: body }));
    },

    patch: function (endpoint, body, options) {
      return request(endpoint, Object.assign({}, options, { method: 'PATCH', body: body }));
    },

    delete: function (endpoint, options) {
      return request(endpoint, Object.assign({}, options, { method: 'DELETE' }));
    },

    postForm: function (endpoint, formData, options) {
      return request(endpoint, Object.assign({}, options, { method: 'POST', body: formData }));
    },
    tts: function (text, languageCode) {
  return request('/api/tts', {
    method: 'POST',
    body: JSON.stringify({
      text: text,
      language_code: languageCode || 'en'
    }),
    headers: {
      'Content-Type': 'application/json'
    },
    responseType: 'blob'
  });
}
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = MediKioskApi;
  }
  if (root) {
    root.MediKioskApi = MediKioskApi;
    // Convenience alias for concise screen scripts
    if (!root.api) {
      root.api = MediKioskApi;
    }
  }
})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));
