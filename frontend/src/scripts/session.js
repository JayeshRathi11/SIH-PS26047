/**
 * MediKiosk Session State Management
 * Uses browser sessionStorage for transient, active kiosk-scoped workflow state.
 *
 * STRICT SECURITY & PRIVACY POLICY:
 * - Allowed to store: auth_token, patient_id, session_id, interview_id
 * - FORBIDDEN to store: passwords, API keys, clinical transcripts, OCR text,
 *   medical documents, JWT secrets, provider credentials.
 */
(function (root) {
  'use strict';

  var STORAGE_KEYS = {
    AUTH_TOKEN: 'medikiosk_auth_token',
    PATIENT_ID: 'medikiosk_patient_id',
    SESSION_ID: 'medikiosk_session_id',
    INTERVIEW_ID: 'medikiosk_interview_id'
  };

  // In-memory fallback if sessionStorage is inaccessible (e.g., privacy/sandbox modes)
  var fallbackMemoryStorage = {};

  function getStorage() {
    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        return window.sessionStorage;
      }
    } catch (e) {
      // Storage access blocked or restricted
    }
    return {
      getItem: function (k) { return fallbackMemoryStorage[k] || null; },
      setItem: function (k, v) { fallbackMemoryStorage[k] = String(v); },
      removeItem: function (k) { delete fallbackMemoryStorage[k]; },
      clear: function () { fallbackMemoryStorage = {}; }
    };
  }

  var MediKioskSession = {
    KEYS: STORAGE_KEYS,

    // ==========================================
    // 1. Auth Token
    // ==========================================
    setAuthToken: function (token) {
      var s = getStorage();
      if (token) {
        s.setItem(STORAGE_KEYS.AUTH_TOKEN, String(token).trim());
      } else {
        s.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      }
    },
    getAuthToken: function () {
      return getStorage().getItem(STORAGE_KEYS.AUTH_TOKEN) || null;
    },
    clearAuthToken: function () {
      getStorage().removeItem(STORAGE_KEYS.AUTH_TOKEN);
    },

    // ==========================================
    // 2. Patient Identifier
    // ==========================================
    setPatientId: function (id) {
      var s = getStorage();
      if (id) {
        s.setItem(STORAGE_KEYS.PATIENT_ID, String(id).trim());
      } else {
        s.removeItem(STORAGE_KEYS.PATIENT_ID);
      }
    },
    getPatientId: function () {
      return getStorage().getItem(STORAGE_KEYS.PATIENT_ID) || null;
    },
    clearPatientId: function () {
      getStorage().removeItem(STORAGE_KEYS.PATIENT_ID);
    },

    // ==========================================
    // 3. Kiosk Session Identifier
    // ==========================================
    setSessionId: function (id) {
      var s = getStorage();
      if (id) {
        s.setItem(STORAGE_KEYS.SESSION_ID, String(id).trim());
      } else {
        s.removeItem(STORAGE_KEYS.SESSION_ID);
      }
    },
    getSessionId: function () {
      return getStorage().getItem(STORAGE_KEYS.SESSION_ID) || null;
    },
    clearSessionId: function () {
      getStorage().removeItem(STORAGE_KEYS.SESSION_ID);
    },

    // ==========================================
    // 4. Clinical Interview Identifier
    // ==========================================
    setInterviewId: function (id) {
      var s = getStorage();
      if (id) {
        s.setItem(STORAGE_KEYS.INTERVIEW_ID, String(id).trim());
      } else {
        s.removeItem(STORAGE_KEYS.INTERVIEW_ID);
      }
    },
    getInterviewId: function () {
      return getStorage().getItem(STORAGE_KEYS.INTERVIEW_ID) || null;
    },
    clearInterviewId: function () {
      getStorage().removeItem(STORAGE_KEYS.INTERVIEW_ID);
    },

    // ==========================================
    // 5. Workflow State Cleanup
    // ==========================================
    clearWorkflowState: function () {
      var s = getStorage();
      s.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      s.removeItem(STORAGE_KEYS.PATIENT_ID);
      s.removeItem(STORAGE_KEYS.SESSION_ID);
      s.removeItem(STORAGE_KEYS.INTERVIEW_ID);
    },

    /**
     * Inspect active workflow IDs without exposing or logging tokens
     */
    getWorkflowSummary: function () {
      return {
        hasAuthToken: !!this.getAuthToken(),
        patientId: this.getPatientId(),
        sessionId: this.getSessionId(),
        interviewId: this.getInterviewId()
      };
    }
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = MediKioskSession;
  }
  if (root) {
    root.MediKioskSession = MediKioskSession;
  }
})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));
