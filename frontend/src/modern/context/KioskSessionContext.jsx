import React, { createContext, useContext, useState, useEffect } from 'react';
import { MediKioskSession } from '../services/session';

const KioskSessionContext = createContext(null);

export function KioskSessionProvider({ children }) {
  const [appMode, setAppMode] = useState('KIOSK'); // 'KIOSK' | 'DOCTOR' | 'ANALYTICS'
  const [currentStep, setCurrentStep] = useState(1); // 1: Identity, 2: Consent, 3: Interview, 4: Docs, 5: Token
  const [currentScreen, setCurrentScreen] = useState('WELCOME'); // 'WELCOME' | 'IDENTITY' | 'MANUAL' | 'CONSENT' | 'INTERVIEW_STANDARD' | 'INTERVIEW_AYUSH' | 'RED_FLAG' | 'DOCS' | 'SUMMARY'

  const [language, setLanguage] = useState(() => {
    try {
      return localStorage.getItem('medikiosk_lang') || 'hi';
    } catch {
      return 'hi';
    }
  });

  const [patient, setPatient] = useState({
    id: null,
    abha_id: '',
    name: '',
    age: '',
    gender: 'Other',
    mobile: '',
    district: '',
    state: 'Delhi',
    verification_mode: 'NONE' // 'ABHA_QR' | 'OTP' | 'MANUAL'
  });

  const [consent, setConsent] = useState({
    granted: false,
    triage_consent: true,
    ocr_consent: true,
    ai_consent: true,
    timestamp: null
  });

  const [interview, setInterview] = useState({
    interview_id: null,
    chief_complaints: [],
    primary_symptom: '',
    duration_days: 3,
    severity: 5,
    body_zones: [],
    pariksha: {
      prakriti: 'Vata-Pitta',
      agni: 'Samagni',
      koshtha: 'Madhyama',
      nadi: 'Normal',
      mutra: 'Normal',
      mala: 'Normal',
      jihva: 'Niram',
      shabda: 'Spashta',
      sparsha: 'Sheeta',
      drik: 'Prakrita',
      akriti: 'Madhyama'
    },
    chat_history: [],
    is_red_flag: false,
    red_flag_reason: null
  });

  const [documents, setDocuments] = useState([]);
  const [tokenSlip, setTokenSlip] = useState(null);

  const changeLanguage = (lang) => {
    setLanguage(lang);
    try {
      localStorage.setItem('medikiosk_lang', lang);
    } catch {
      // ignore
    }
  };

  const updatePatient = (newData) => {
    setPatient((prev) => {
      const updated = { ...prev, ...newData };
      if (updated.id) {
        MediKioskSession.setPatientId(updated.id);
      }
      return updated;
    });
  };

  const updateConsent = (newData) => {
    setConsent((prev) => ({ ...prev, ...newData }));
  };

  const updateInterview = (newData) => {
    setInterview((prev) => {
      const updated = { ...prev, ...newData };
      if (updated.interview_id) {
        MediKioskSession.setInterviewId(updated.interview_id);
      }
      return updated;
    });
  };

  const addDocument = (doc) => {
    setDocuments((prev) => [...prev, doc]);
  };

  const removeDocument = (docId) => {
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
  };

  const resetSession = () => {
    MediKioskSession.clearWorkflowState();
    setPatient({
      id: null,
      abha_id: '',
      name: '',
      age: '',
      gender: 'Other',
      mobile: '',
      district: '',
      state: 'Delhi',
      verification_mode: 'NONE'
    });
    setConsent({
      granted: false,
      triage_consent: true,
      ocr_consent: true,
      ai_consent: true,
      timestamp: null
    });
    setInterview({
      interview_id: null,
      chief_complaints: [],
      primary_symptom: '',
      duration_days: 3,
      severity: 5,
      body_zones: [],
      pariksha: {
        prakriti: 'Vata-Pitta',
        agni: 'Samagni',
        koshtha: 'Madhyama',
        nadi: 'Normal',
        mutra: 'Normal',
        mala: 'Normal',
        jihva: 'Niram',
        shabda: 'Spashta',
        sparsha: 'Sheeta',
        drik: 'Prakrita',
        akriti: 'Madhyama'
      },
      chat_history: [],
      is_red_flag: false,
      red_flag_reason: null
    });
    setDocuments([]);
    setTokenSlip(null);
    setCurrentStep(1);
    setCurrentScreen('WELCOME');
  };

  const value = {
    appMode,
    setAppMode,
    currentStep,
    setCurrentStep,
    currentScreen,
    setCurrentScreen,
    language,
    changeLanguage,
    patient,
    updatePatient,
    consent,
    updateConsent,
    interview,
    updateInterview,
    documents,
    addDocument,
    removeDocument,
    tokenSlip,
    setTokenSlip,
    resetSession
  };

  return (
    <KioskSessionContext.Provider value={value}>
      {children}
    </KioskSessionContext.Provider>
  );
}

export function useKioskSession() {
  const context = useContext(KioskSessionContext);
  if (!context) {
    throw new Error('useKioskSession must be used within a KioskSessionProvider');
  }
  return context;
}

export default KioskSessionContext;
