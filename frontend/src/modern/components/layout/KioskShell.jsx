import React from 'react';
import TopBar from './TopBar';
import StepBar from './StepBar';
import ActionBar from './ActionBar';
import { useKioskSession } from '../../context/KioskSessionContext';

export default function KioskShell({
  children,
  showStepBar = true,
  showActionBar = true,
  onBack,
  onProceed,
  onSkip,
  canProceed = true,
  canBack = true,
  showSkip = false,
  proceedLabel,
  backLabel,
  skipLabel,
  loading = false,
  onOpenQaLauncher
}) {
  const { currentScreen } = useKioskSession();
  const isWelcome = currentScreen === 'WELCOME';

  return (
    <div className="min-h-screen bg-[#EDE8DE] text-teak-grey flex flex-col items-center justify-start antialiased">
      <div className="app-container w-full max-w-[1440px] min-h-screen bg-bg flex flex-col relative shadow-2xl">
        {/* Top Navigation Bar */}
        <TopBar onOpenQaLauncher={onOpenQaLauncher} />

        {/* 5-Step Progress Bar (hidden on welcome screen) */}
        {showStepBar && !isWelcome && <StepBar />}

        {/* Dynamic Content Zone */}
        <main className="flex-1 flex flex-col relative overflow-y-auto px-6 sm:px-12 py-6">
          {children}
        </main>

        {/* Fixed Action Tray */}
        {showActionBar && !isWelcome && (
          <ActionBar
            onBack={onBack}
            onProceed={onProceed}
            onSkip={onSkip}
            canProceed={canProceed}
            canBack={canBack}
            showSkip={showSkip}
            proceedLabel={proceedLabel}
            backLabel={backLabel}
            skipLabel={skipLabel}
            loading={loading}
            onOpenQaLauncher={onOpenQaLauncher}
          />
        )}
      </div>
    </div>
  );
}
