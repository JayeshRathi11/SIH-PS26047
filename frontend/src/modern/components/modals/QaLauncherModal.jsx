import React from 'react';
import { X, Sparkles, UserCheck, Stethoscope, FileText, Ticket, AlertTriangle, BarChart3, RotateCcw } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import { useKioskSession } from '../../context/KioskSessionContext';

export default function QaLauncherModal({ isOpen, onClose }) {
  const {
    setCurrentScreen,
    setCurrentStep,
    setAppMode,
    updatePatient,
    updateInterview,
    addDocument,
    resetSession
  } = useKioskSession();

  if (!isOpen) return null;

  const handleJump = (screen, step, mode = 'KIOSK') => {
    setAppMode(mode);
    setCurrentStep(step);
    setCurrentScreen(screen);
    onClose();
  };

  const handleInjectPreset = (type) => {
    if (type === 'STANDARD') {
      updatePatient({
        id: 101,
        name: 'रमेश कुमार / Ramesh Kumar',
        age: 48,
        gender: 'Male',
        mobile: '9876543210',
        district: 'South Delhi',
        state: 'Delhi',
        verification_mode: 'ABHA_QR'
      });
      updateInterview({
        chief_complaints: ['ज्वर / बुखार', 'संधि शूल / जोड़ों में दर्द'],
        duration_days: 3,
        severity: 5,
        is_red_flag: false
      });
      handleJump('INTERVIEW_STANDARD', 3);
    } else if (type === 'RED_FLAG') {
      updatePatient({
        id: 102,
        name: 'सुमन लता / Suman Lata',
        age: 68,
        gender: 'Female',
        mobile: '9811223344',
        district: 'New Delhi',
        state: 'Delhi',
        verification_mode: 'OTP'
      });
      updateInterview({
        chief_complaints: ['सीने में तीव्र दर्द (छाती में भारीपन)'],
        is_red_flag: true,
        red_flag_reason: 'सीने में तीव्र दर्द (Severe Chest Pain)'
      });
      handleJump('RED_FLAG', 3);
    } else if (type === 'DOCS') {
      addDocument({
        id: Date.now(),
        fileName: 'Prescription_AIIA_2026.jpg',
        docType: 'Prescription',
        confidence: '96%',
        extractedMeds: [
          { name: 'Sudarshan Vati', dosage: '2 tablets', freq: 'Twice daily', duration: '5 days' },
          { name: 'Mahasudarshan Churna', dosage: '3 grams', freq: 'Warm water', duration: '7 days' }
        ],
        doctorNotes: 'विगत 4 दिनों से हल्का ज्वर एवं अंगमर्द।'
      });
      handleJump('DOCS', 4);
    }
  };

  const screens = [
    { id: 'WELCOME', name: '0. Welcome Portal', step: 1, mode: 'KIOSK', icon: Sparkles },
    { id: 'IDENTITY', name: '1a. Identity / ABHA', step: 1, mode: 'KIOSK', icon: UserCheck },
    { id: 'MANUAL', name: '1a. Manual Demographics', step: 1, mode: 'KIOSK', icon: UserCheck },
    { id: 'CONSENT', name: '1b. DPDP Consent', step: 2, mode: 'KIOSK', icon: FileText },
    { id: 'INTERVIEW_STANDARD', name: '2a. Chief Symptoms', step: 3, mode: 'KIOSK', icon: Stethoscope },
    { id: 'INTERVIEW_AYUSH', name: '2b. AYUSH Pariksha', step: 3, mode: 'KIOSK', icon: Stethoscope },
    { id: 'RED_FLAG', name: '2c. Red Flag Alert', step: 3, mode: 'KIOSK', icon: AlertTriangle },
    { id: 'DOCS', name: '3. Document Upload & OCR', step: 4, mode: 'KIOSK', icon: FileText },
    { id: 'SUMMARY', name: '4. Token Summary Slip', step: 5, mode: 'KIOSK', icon: Ticket },
    { id: 'DOCTOR', name: '5. Doctor Workstation', step: 5, mode: 'DOCTOR', icon: Stethoscope },
    { id: 'ANALYTICS', name: '6. Analytics Dashboard', step: 5, mode: 'ANALYTICS', icon: BarChart3 }
  ];

  return (
    <div className="fixed inset-0 z-50 bg-teak-grey/70 backdrop-blur-sm flex items-center justify-center p-4 select-none">
      <ClayCard elevated className="max-w-3xl w-full p-6 border-2 border-haritaki-gold shadow-2xl flex flex-col gap-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-copper-border/50 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-haritaki-gold text-white flex items-center justify-center font-bold">
              QA
            </div>
            <div>
              <h3 className="font-display font-bold text-btn-sec text-teak-grey">
                Developer / QA Screen Launcher Matrix
              </h3>
              <p className="text-xs text-teak-muted">
                1-Click Jump to any screen state or inject test scenarios (Hotkey: Ctrl+Shift+Q)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-teak-muted hover:text-teak-grey p-1.5 rounded-full cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Screen Jump Buttons Grid */}
        <div>
          <span className="text-xs font-bold text-haritaki-deep uppercase tracking-wider block mb-2">
            कियोस्क स्क्रीन चुनें / Jump to Screen:
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {screens.map((s) => {
              const IconComp = s.icon;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => handleJump(s.id, s.step, s.mode)}
                  className="p-3 rounded-btn bg-cream-neutral border border-copper-border text-left hover:border-haritaki-gold hover:bg-cream-warm transition-all cursor-pointer flex items-center gap-2.5 shadow-sm"
                >
                  <IconComp className="w-4 h-4 text-haritaki-deep flex-shrink-0" />
                  <span className="text-caption font-display font-bold text-teak-grey truncate">
                    {s.name}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Scenario Injectors */}
        <div className="border-t border-copper-border/40 pt-3">
          <span className="text-xs font-bold text-haritaki-deep uppercase tracking-wider block mb-2">
            परीक्षण डेटा इंजेक्ट करें / Inject Test Scenarios:
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <button
              type="button"
              onClick={() => handleInjectPreset('STANDARD')}
              className="p-2.5 rounded-btn bg-shweta-white border border-haritaki-gold/50 text-left hover:bg-cream-warm transition-all cursor-pointer text-xs"
            >
              <strong className="block font-display text-teak-grey font-bold">1. Standard Adult</strong>
              <span className="text-teak-muted">Ramesh, 48y, Fever &amp; Joint Pain</span>
            </button>

            <button
              type="button"
              onClick={() => handleInjectPreset('RED_FLAG')}
              className="p-2.5 rounded-btn bg-manjistha-red/10 border border-manjistha-red/40 text-left hover:bg-manjistha-red/20 transition-all cursor-pointer text-xs"
            >
              <strong className="block font-display text-manjistha-red font-bold">2. Red Flag Emergency</strong>
              <span className="text-teak-muted">Suman, 68y, Severe Chest Pain</span>
            </button>

            <button
              type="button"
              onClick={() => handleInjectPreset('DOCS')}
              className="p-2.5 rounded-btn bg-shweta-white border border-herbal-green/50 text-left hover:bg-herbal-green/10 transition-all cursor-pointer text-xs"
            >
              <strong className="block font-display text-herbal-green font-bold">3. Loaded Prescription OCR</strong>
              <span className="text-teak-muted">Extracted Sudarshan Vati</span>
            </button>
          </div>
        </div>

        {/* Reset */}
        <div className="flex justify-between items-center border-t border-copper-border/40 pt-3">
          <button
            type="button"
            onClick={() => {
              resetSession();
              handleJump('WELCOME', 1, 'KIOSK');
            }}
            className="text-xs text-copper-patina hover:text-manjistha-red font-bold flex items-center gap-1.5 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" /> सत्र रीसेट करें / Reset All State
          </button>
          <ClayButton variant="neutral" size="sm" onClick={onClose}>
            बंद करें / Close
          </ClayButton>
        </div>
      </ClayCard>
    </div>
  );
}
