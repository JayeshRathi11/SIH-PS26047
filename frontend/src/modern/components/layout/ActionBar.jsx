import React from 'react';
import { ArrowLeft, ArrowRight, SkipForward, ShieldCheck } from 'lucide-react';
import ClayButton from '../atoms/ClayButton';
import { ComplianceShield } from '../atoms/AyushIcons';

export default function ActionBar({
  onBack,
  onProceed,
  onSkip,
  canProceed = true,
  canBack = true,
  showSkip = false,
  proceedLabel = 'आगे बढ़ें / Proceed',
  backLabel = 'पीछे / Back',
  skipLabel = 'छोड़ें / Skip',
  loading = false,
  onOpenQaLauncher
}) {
  return (
    <footer className="flex-none h-[88px] bg-actionbar-bg border-t border-actionbar-border flex items-center justify-between px-6 sm:px-10 select-none shadow-actionbar z-40">
      {/* Left Action / Compliance Tag */}
      <div className="flex items-center gap-4">
        {onBack && canBack && (
          <ClayButton
            variant="back"
            size="md"
            onClick={onBack}
            icon={<ArrowLeft className="w-5 h-5" />}
          >
            {backLabel}
          </ClayButton>
        )}

        <div className="hidden md:flex items-center gap-2 text-caption text-teak-muted bg-cream-warm/60 px-3 py-1.5 rounded-pill border border-copper-border/40">
          <ComplianceShield className="w-4 h-4 text-haritaki-deep" />
          <span>DPDP Act 2023 Compliant &bull; ABHA ABDM Verified</span>
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-3">
        {showSkip && onSkip && (
          <ClayButton
            variant="skip"
            size="md"
            onClick={onSkip}
            icon={<SkipForward className="w-4 h-4" />}
          >
            {skipLabel}
          </ClayButton>
        )}

        {onProceed && (
          <ClayButton
            variant="proceed"
            size="touch"
            disabled={!canProceed || loading}
            loading={loading}
            onClick={onProceed}
          >
            <span className="flex items-center gap-2">
              <span>{proceedLabel}</span>
              <ArrowRight className="w-5 h-5" />
            </span>
          </ClayButton>
        )}
      </div>
    </footer>
  );
}
