import React, { useState, useEffect } from 'react';
import { KioskSessionProvider, useKioskSession } from './context/KioskSessionContext';
import { AudioProvider } from './context/AudioContext';
import ErrorBoundary from './components/common/ErrorBoundary';
import KioskShell from './components/layout/KioskShell';

// Screens
import WelcomeScreen from './components/screens/WelcomeScreen';
import IdentityScreen from './components/screens/IdentityScreen';
import ManualEntryScreen from './components/screens/ManualEntryScreen';
import ConsentScreen from './components/screens/ConsentScreen';
import InterviewContainerScreen from './components/screens/InterviewContainerScreen';
import DocumentScanScreen from './components/screens/DocumentScanScreen';
import PatientSummaryScreen from './components/screens/PatientSummaryScreen';
import DoctorDashboardScreen from './components/screens/DoctorDashboardScreen';
import AnalyticsDashboardScreen from './components/screens/AnalyticsDashboardScreen';

// Modals
import OtpVerificationModal from './components/modals/OtpVerificationModal';
import QaLauncherModal from './components/modals/QaLauncherModal';

function ModernKioskRouter() {
  const {
    appMode,
    setAppMode,
    currentStep,
    setCurrentStep,
    currentScreen,
    setCurrentScreen,
    patient,
    resetSession
  } = useKioskSession();

  const [showOtpModal, setShowOtpModal] = useState(false);
  const [otpTargetMobile, setOtpTargetMobile] = useState('');
  const [showQaLauncher, setShowQaLauncher] = useState(false);

  // Global hotkey Ctrl+Shift+Q for QA Screen Launcher
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.ctrlKey && e.shiftKey && (e.key === 'Q' || e.key === 'q')) {
        e.preventDefault();
        setShowQaLauncher((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Step transition handlers
  const handleBegin = () => {
    setCurrentStep(1);
    setCurrentScreen('IDENTITY');
  };

  const handleIdentityVerified = () => {
    setCurrentStep(2);
    setCurrentScreen('CONSENT');
  };

  const handleTriggerOtp = (mobile) => {
    setOtpTargetMobile(mobile);
    setShowOtpModal(true);
  };

  const handleOtpSuccess = () => {
    setShowOtpModal(false);
    handleIdentityVerified();
  };

  const handleConsentAgreed = () => {
    setCurrentStep(3);
    setCurrentScreen('INTERVIEW');
  };

  const handleConsentDeclined = () => {
    resetSession();
  };

  const handleInterviewComplete = () => {
    setCurrentStep(4);
    setCurrentScreen('DOCS');
  };

  const handleDocsComplete = () => {
    setCurrentStep(5);
    setCurrentScreen('SUMMARY');
  };

  const handleBack = () => {
    if (currentScreen === 'IDENTITY') {
      setCurrentScreen('WELCOME');
    } else if (currentScreen === 'MANUAL') {
      setCurrentScreen('IDENTITY');
    } else if (currentScreen === 'CONSENT') {
      setCurrentStep(1);
      setCurrentScreen('IDENTITY');
    } else if (currentScreen === 'INTERVIEW') {
      setCurrentStep(2);
      setCurrentScreen('CONSENT');
    } else if (currentScreen === 'DOCS') {
      setCurrentStep(3);
      setCurrentScreen('INTERVIEW');
    } else if (currentScreen === 'SUMMARY') {
      setCurrentStep(4);
      setCurrentScreen('DOCS');
    }
  };

  const handleProceed = () => {
    if (currentScreen === 'IDENTITY') {
      setCurrentStep(2);
      setCurrentScreen('CONSENT');
    } else if (currentScreen === 'MANUAL') {
      setCurrentStep(2);
      setCurrentScreen('CONSENT');
    } else if (currentScreen === 'CONSENT') {
      setCurrentStep(3);
      setCurrentScreen('INTERVIEW');
    } else if (currentScreen === 'INTERVIEW') {
      setCurrentStep(4);
      setCurrentScreen('DOCS');
    } else if (currentScreen === 'DOCS') {
      setCurrentStep(5);
      setCurrentScreen('SUMMARY');
    }
  };

  const handleSkip = () => {
    if (currentScreen === 'DOCS') {
      setCurrentStep(5);
      setCurrentScreen('SUMMARY');
    }
  };

  // Render Doctor Workstation Mode
  if (appMode === 'DOCTOR') {
    return (
      <KioskShell showStepBar={false} showActionBar={false} onOpenQaLauncher={() => setShowQaLauncher(true)}>
        <DoctorDashboardScreen />
        <QaLauncherModal isOpen={showQaLauncher} onClose={() => setShowQaLauncher(false)} />
      </KioskShell>
    );
  }

  // Render Analytics Dashboard Mode
  if (appMode === 'ANALYTICS') {
    return (
      <KioskShell showStepBar={false} showActionBar={false} onOpenQaLauncher={() => setShowQaLauncher(true)}>
        <AnalyticsDashboardScreen />
        <QaLauncherModal isOpen={showQaLauncher} onClose={() => setShowQaLauncher(false)} />
      </KioskShell>
    );
  }

  // Render Kiosk Patient Flow
  return (
    <KioskShell
      onBack={handleBack}
      onProceed={currentScreen !== 'WELCOME' && currentScreen !== 'SUMMARY' ? handleProceed : undefined}
      onSkip={currentScreen === 'DOCS' ? handleSkip : undefined}
      showSkip={currentScreen === 'DOCS'}
      canProceed={true}
      canBack={currentScreen !== 'WELCOME'}
      proceedLabel="आगे बढ़ें / Proceed"
      backLabel="पीछे / Back"
      skipLabel="छोड़ें / Skip"
      onOpenQaLauncher={() => setShowQaLauncher(true)}
    >
      {currentScreen === 'WELCOME' && (
        <WelcomeScreen onBegin={handleBegin} />
      )}

      {currentScreen === 'IDENTITY' && (
        <IdentityScreen
          onSelectManual={() => setCurrentScreen('MANUAL')}
          onVerified={handleIdentityVerified}
          onTriggerOtp={handleTriggerOtp}
        />
      )}

      {currentScreen === 'MANUAL' && (
        <ManualEntryScreen
          onComplete={handleIdentityVerified}
          onBack={() => setCurrentScreen('IDENTITY')}
        />
      )}

      {currentScreen === 'CONSENT' && (
        <ConsentScreen
          onAgree={handleConsentAgreed}
          onDecline={handleConsentDeclined}
        />
      )}

      {currentScreen === 'INTERVIEW' && (
        <InterviewContainerScreen onComplete={handleInterviewComplete} />
      )}

      {currentScreen === 'DOCS' && (
        <DocumentScanScreen onProceed={handleDocsComplete} />
      )}

      {currentScreen === 'SUMMARY' && (
        <PatientSummaryScreen onReset={resetSession} />
      )}

      {/* OTP Verification Modal */}
      <OtpVerificationModal
        isOpen={showOtpModal}
        onClose={() => setShowOtpModal(false)}
        mobile={otpTargetMobile || patient.mobile}
        onSuccess={handleOtpSuccess}
      />

      {/* QA Launcher Modal */}
      <QaLauncherModal
        isOpen={showQaLauncher}
        onClose={() => setShowQaLauncher(false)}
      />
    </KioskShell>
  );
}

export default function ModernApp() {
  return (
    <ErrorBoundary>
      <KioskSessionProvider>
        <AudioProvider>
          <ModernKioskRouter />
        </AudioProvider>
      </KioskSessionProvider>
    </ErrorBoundary>
  );
}
