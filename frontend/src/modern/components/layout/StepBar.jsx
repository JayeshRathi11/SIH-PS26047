import React from 'react';
import { Check } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';

export default function StepBar() {
  const { currentStep, language } = useKioskSession();

  const steps = [
    {
      id: 1,
      labelEn: 'Identity',
      labelHi: 'पहचान',
      labelMr: 'ओळख'
    },
    {
      id: 2,
      labelEn: 'Consent',
      labelHi: 'सहमति',
      labelMr: 'संमती'
    },
    {
      id: 3,
      labelEn: 'Interview',
      labelHi: 'संवाद',
      labelMr: 'संवाद'
    },
    {
      id: 4,
      labelEn: 'Documents',
      labelHi: 'दस्तावेज',
      labelMr: 'कागदपत्रे'
    },
    {
      id: 5,
      labelEn: 'Queue Token',
      labelHi: 'टोकन',
      labelMr: 'टोकन'
    }
  ];

  const getStepLabel = (s) => {
    if (language === 'hi') return s.labelHi;
    if (language === 'mr') return s.labelMr;
    return s.labelEn;
  };

  return (
    <nav aria-label="Progress" className="flex-none h-[56px] bg-[#EFE8D6] border-b border-[#E8DEC7] flex items-center justify-between px-8 select-none">
      <div className="w-full max-w-4xl mx-auto flex items-center justify-between">
        {steps.map((step, idx) => {
          const isComplete = currentStep > step.id;
          const isActive = currentStep === step.id;
          const isUpcoming = currentStep < step.id;

          return (
            <React.Fragment key={step.id}>
              {/* Step Node */}
              <div className="flex items-center gap-2">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${
                    isComplete
                      ? 'step-dot--complete bg-gradient-to-br from-[#D7A23A] to-[#B47F20] text-white shadow-check-disk'
                      : isActive
                      ? 'step-dot--active w-7 h-7 bg-shweta-white border-[2.5px] border-haritaki-gold shadow-md relative flex items-center justify-center'
                      : 'step-dot--upcoming bg-cream-recess text-copper-patina border border-[#D5C9B3] shadow-inner'
                  }`}
                >
                  {isComplete ? (
                    <Check className="w-4 h-4 text-white stroke-[3]" />
                  ) : isActive ? (
                    <span className="w-2.5 h-2.5 rounded-full bg-haritaki-gold" />
                  ) : (
                    <span className="text-xs font-mono font-bold">{step.id}</span>
                  )}
                </div>

                <span
                  className={`text-caption font-semibold whitespace-nowrap hidden sm:inline-block ${
                    isComplete
                      ? 'text-haritaki-deep font-bold'
                      : isActive
                      ? 'text-teak-grey font-bold'
                      : 'text-teak-muted/70'
                  }`}
                >
                  {step.id}. {getStepLabel(step)}
                </span>
              </div>

              {/* Connector Track between nodes */}
              {idx < steps.length - 1 && (
                <div
                  className={`flex-1 h-1.5 mx-3 rounded-full transition-all ${
                    currentStep > step.id
                      ? 'bg-gradient-to-r from-[#D49E34] to-[#BE8722] shadow-sm'
                      : 'bg-[#EDE5D3] border border-dashed border-[#D5CBBA]'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </nav>
  );
}
