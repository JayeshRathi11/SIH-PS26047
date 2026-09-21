/**
 * MediKiosk Shared API Client (ES Module & Global export)
 * Reusable HTTP client built on window.fetch with zero-leakage error handling.
 */
import { MediKioskConfig } from './config';
import { MediKioskSession } from './session';

export class ApiError extends Error {
  constructor(message, status = 0, data = null, isNetworkError = false) {
    super(message || 'An unexpected error occurred.');
    this.name = 'ApiError';
    this.status = typeof status === 'number' ? status : 0;
    this.data = data;
    this.isNetworkError = !!isNetworkError;
    this.isClientError = this.status >= 400 && this.status < 500;
    this.isServerError = this.status >= 500;
    this.isAuthError = this.status === 401;
    this.isForbidden = this.status === 403;
    this.isNotFound = this.status === 404;
    this.isConflict = this.status === 409;
    this.isValidationError = this.status === 422;
    this.isRateLimit = this.status === 429;
  }
}

function extractErrorMessage(status, responseData) {
  if (responseData) {
    if (typeof responseData.detail === 'string') {
      return responseData.detail;
    }
    if (Array.isArray(responseData.detail) && responseData.detail.length > 0) {
      const first = responseData.detail[0];
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
    default: return `Request failed with HTTP status ${status}`;
  }
}

function resolveUrl(endpoint) {
  if (typeof endpoint !== 'string' || endpoint.trim().length === 0) {
    throw new Error('API endpoint must be a valid string');
  }

  const cleanEndpoint = endpoint.trim();
  if (/^https?:\/\//i.test(cleanEndpoint)) {
    return cleanEndpoint;
  }

  const baseUrl = MediKioskConfig.getApiBaseUrl().replace(/\/+$/, '');
  const cleanPath = cleanEndpoint.replace(/^\/+/, '');
  return `${baseUrl}/${cleanPath}`;
}

export async function request(endpoint, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = { ...(options.headers || {}) };
  let body = options.body;
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  const token = MediKioskSession.getAuthToken();
  const hasAuthHeader = Object.keys(headers).some(k => k.toLowerCase() === 'authorization');
  if (token && !hasAuthHeader) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!headers['Accept'] && !headers['accept']) {
    headers['Accept'] = 'application/json';
  }

  if (body !== undefined && body !== null && !isFormData) {
    const hasContentType = Object.keys(headers).some(k => k.toLowerCase() === 'content-type');
    if (!hasContentType) {
      headers['Content-Type'] = 'application/json';
    }
    if (typeof body === 'object' && !(body instanceof Blob) && !(body instanceof ArrayBuffer)) {
      body = JSON.stringify(body);
    }
  }

  const fullUrl = resolveUrl(endpoint);
  let response;
  try {
    response = await fetch(fullUrl, {
      method,
      headers,
      body,
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

  let parsedData = null;
  const status = response.status;
  const contentType = response.headers ? (response.headers.get('content-type') || '') : '';

  if (status !== 204 && status !== 205) {
    try {
      if (options.responseType === 'blob') {
        parsedData = await response.blob();
      } else if (contentType.includes('application/json')) {
        parsedData = await response.json();
      } else {
        const rawText = await response.text();
        try {
          parsedData = JSON.parse(rawText);
        } catch {
          parsedData = rawText.length > 0 ? rawText : null;
        }
      }
    } catch {
      parsedData = null;
    }
  }

  if (!response.ok) {
    const safeMessage = extractErrorMessage(status, parsedData);
    throw new ApiError(safeMessage, status, parsedData, false);
  }

  return {
    status,
    ok: response.ok,
    data: parsedData,
    headers: response.headers
  };
}

export const MediKioskApi = {
  ApiError,
  request,
  get: (endpoint, options) => request(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options) => request(endpoint, { ...options, method: 'POST', body }),
  put: (endpoint, body, options) => request(endpoint, { ...options, method: 'PUT', body }),
  patch: (endpoint, body, options) => request(endpoint, { ...options, method: 'PATCH', body }),
  delete: (endpoint, options) => request(endpoint, { ...options, method: 'DELETE' }),
  postForm: (endpoint, formData, options) => request(endpoint, { ...options, method: 'POST', body: formData }),
  tts: (text, languageCode = 'en') => request('/api/tts', {
    method: 'POST',
    body: JSON.stringify({
      text,
      language_code: languageCode
    }),
    headers: {
      'Content-Type': 'application/json'
    },
    responseType: 'blob'
  })
};

if (typeof window !== 'undefined') {
  window.MediKioskApi = MediKioskApi;
  window.api = MediKioskApi;
}

export default MediKioskApi;
