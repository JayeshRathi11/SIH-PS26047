/**
 * MediKiosk Session State Management
 * Uses browser sessionStorage for transient, active kiosk-scoped workflow state.
 *
 * STRICT SECURITY & PRIVACY POLICY:
 * - Allowed to store: auth_token, patient_id, session_id, interview_id
 * - FORBIDDEN to store: passwords, API keys, clinical transcripts, OCR text,
 *   medical documents, JWT secrets, provider credentials.
 */

const STORAGE_KEYS = {
  AUTH_TOKEN: 'medikiosk_auth_token',
  PATIENT_ID: 'medikiosk_patient_id',
  SESSION_ID: 'medikiosk_session_id',
  INTERVIEW_ID: 'medikiosk_interview_id'
};

let fallbackMemoryStorage = {};

function getStorage() {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      return window.sessionStorage;
    }
  } catch (e) {
    // Storage access restricted
  }
  return {
    getItem(k) { return fallbackMemoryStorage[k] || null; },
    setItem(k, v) { fallbackMemoryStorage[k] = String(v); },
    removeItem(k) { delete fallbackMemoryStorage[k]; },
    clear() { fallbackMemoryStorage = {}; }
  };
}

export const MediKioskSession = {
  KEYS: STORAGE_KEYS,

  setAuthToken(token) {
    const s = getStorage();
    if (token) {
      s.setItem(STORAGE_KEYS.AUTH_TOKEN, String(token).trim());
    } else {
      s.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    }
  },
  getAuthToken() {
    return getStorage().getItem(STORAGE_KEYS.AUTH_TOKEN) || null;
  },
  clearAuthToken() {
    getStorage().removeItem(STORAGE_KEYS.AUTH_TOKEN);
  },

  setPatientId(id) {
    const s = getStorage();
    if (id) {
      s.setItem(STORAGE_KEYS.PATIENT_ID, String(id).trim());
    } else {
      s.removeItem(STORAGE_KEYS.PATIENT_ID);
    }
  },
  getPatientId() {
    return getStorage().getItem(STORAGE_KEYS.PATIENT_ID) || null;
  },
  clearPatientId() {
    getStorage().removeItem(STORAGE_KEYS.PATIENT_ID);
  },

  setSessionId(id) {
    const s = getStorage();
    if (id) {
      s.setItem(STORAGE_KEYS.SESSION_ID, String(id).trim());
    } else {
      s.removeItem(STORAGE_KEYS.SESSION_ID);
    }
  },
  getSessionId() {
    return getStorage().getItem(STORAGE_KEYS.SESSION_ID) || null;
  },
  clearSessionId() {
    getStorage().removeItem(STORAGE_KEYS.SESSION_ID);
  },

  setInterviewId(id) {
    const s = getStorage();
    if (id) {
      s.setItem(STORAGE_KEYS.INTERVIEW_ID, String(id).trim());
    } else {
      s.removeItem(STORAGE_KEYS.INTERVIEW_ID);
    }
  },
  getInterviewId() {
    return getStorage().getItem(STORAGE_KEYS.INTERVIEW_ID) || null;
  },
  clearInterviewId() {
    getStorage().removeItem(STORAGE_KEYS.INTERVIEW_ID);
  },

  clearWorkflowState() {
    const s = getStorage();
    s.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    s.removeItem(STORAGE_KEYS.PATIENT_ID);
    s.removeItem(STORAGE_KEYS.SESSION_ID);
    s.removeItem(STORAGE_KEYS.INTERVIEW_ID);
  },

  getWorkflowSummary() {
    return {
      hasAuthToken: !!this.getAuthToken(),
      patientId: this.getPatientId(),
      sessionId: this.getSessionId(),
      interviewId: this.getInterviewId()
    };
  }
};

if (typeof window !== 'undefined') {
  window.MediKioskSession = MediKioskSession;
}

export default MediKioskSession;
