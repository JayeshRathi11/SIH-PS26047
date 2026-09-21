import React, { useState } from 'react';
import RegistrationStep from './components/kiosk/RegistrationStep';
import ConsentStep from './components/kiosk/ConsentStep';
import InterviewStep from './components/kiosk/InterviewStep';
import DocumentUploadStep from './components/kiosk/DocumentUploadStep';
import PatientConfirmationStep from './components/kiosk/PatientConfirmationStep';
import DoctorDashboard from './components/doctor/DoctorDashboard';
import { HeartPulse, Stethoscope, Sparkles } from 'lucide-react';

export default function App() {
  const [appMode, setAppMode] = useState('KIOSK'); // 'KIOSK' | 'DOCTOR'
  const [kioskStep, setKioskStep] = useState(1); // 1: Reg, 2: Consent, 3: Interview, 4: Docs, 5: Confirm

  const [sessionData, setSessionData] = useState({
    patient: null,
    consentData: null,
    interviewData: null,
    documentData: null
  });

  const handleRegistrationComplete = (patient) => {
    setSessionData(prev => ({ ...prev, patient }));
    setKioskStep(2);
  };

  const handleConsentComplete = (consentData) => {
    setSessionData(prev => ({ ...prev, consentData }));
    setKioskStep(3);
  };

  const handleInterviewComplete = (interviewData) => {
    setSessionData(prev => ({ ...prev, interviewData }));
    setKioskStep(4);
  };

  const handleDocumentComplete = (documentData) => {
    setSessionData(prev => ({ ...prev, documentData }));
    setKioskStep(5);
  };

  const handleResetKiosk = () => {
    setSessionData({
      patient: null,
      consentData: null,
      interviewData: null,
      documentData: null
    });
    setKioskStep(1);
  };

  return (
    <div className="min-h-screen bg-stone-100 flex flex-col font-sans">
      {/* Top Global Mode Navigation Bar */}
      <nav className="bg-stone-900 text-white px-4 sm:px-6 py-2.5 flex items-center justify-between border-b border-stone-800 shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-ayush-primary flex items-center justify-center font-bold text-white shadow">
            <HeartPulse className="w-5 h-5 text-ayush-accent" />
          </div>
          <div>
            <span className="font-serif font-bold text-sm sm:text-base tracking-wide text-stone-100">
              MEDIKIOSK • आयुष स्वास्थ्य कियोस्क
            </span>
            <span className="hidden sm:inline-block ml-2 text-[10px] bg-ayush-primary/40 text-emerald-300 px-2 py-0.5 rounded font-mono">
              SIH-PS26047
            </span>
          </div>
        </div>

        {/* Mode Selector */}
        <div className="flex items-center gap-2 bg-stone-800 p-1 rounded-xl border border-stone-700">
          <button
            type="button"
            onClick={() => setAppMode('KIOSK')}
            className={`min-h-[38px] px-3 sm:px-4 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              appMode === 'KIOSK'
                ? 'bg-ayush-primary text-white shadow-sm'
                : 'text-stone-300 hover:text-white'
            }`}
          >
            <HeartPulse className="w-4 h-4" />
            <span>रोगी कियोस्क / Kiosk</span>
          </button>

          <button
            type="button"
            onClick={() => setAppMode('DOCTOR')}
            className={`min-h-[38px] px-3 sm:px-4 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              appMode === 'DOCTOR'
                ? 'bg-ayush-primary text-white shadow-sm'
                : 'text-stone-300 hover:text-white'
            }`}
          >
            <Stethoscope className="w-4 h-4" />
            <span>डॉक्टर वर्कस्टेशन / Doctor</span>
          </button>
        </div>
      </nav>

      {/* Main Mode Views */}
      {appMode === 'DOCTOR' ? (
        <DoctorDashboard />
      ) : (
        <main className="flex-1 py-4 sm:py-6">
          {kioskStep === 1 && (
            <RegistrationStep
              initialData={sessionData.patient || {}}
              onComplete={handleRegistrationComplete}
            />
          )}

          {kioskStep === 2 && (
            <ConsentStep
              patient={sessionData.patient}
              onComplete={handleConsentComplete}
              onBack={() => setKioskStep(1)}
            />
          )}

          {kioskStep === 3 && (
            <InterviewStep
              patient={sessionData.patient}
              onComplete={handleInterviewComplete}
              onBack={() => setKioskStep(2)}
            />
          )}

          {kioskStep === 4 && (
            <DocumentUploadStep
              patient={sessionData.patient}
              onComplete={handleDocumentComplete}
              onBack={() => setKioskStep(3)}
            />
          )}

          {kioskStep === 5 && (
            <PatientConfirmationStep
              patient={sessionData.patient}
              interviewData={sessionData.interviewData}
              documentData={sessionData.documentData}
              onEdit={() => setKioskStep(1)}
              onResetKiosk={handleResetKiosk}
            />
          )}
        </main>
      )}
    </div>
  );
}
