import React, { useEffect, useState } from 'react';
import { AlertOctagon, Siren, PhoneCall, ArrowLeft, CheckCircle2, ShieldAlert } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import { useAudio } from '../../context/AudioContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function RedFlagAlertScreen({ onDismiss }) {
  const { interview, updateInterview, patient } = useKioskSession();
  const { playTts } = useAudio();
  const [dispatched, setDispatched] = useState(false);

  useEffect(() => {
    // Play emergency auditory guidance
    playTts(
      "सावधान! आपके द्वारा बताए गए लक्षण तत्काल चिकित्सकीय ध्यान चाहते हैं। कृपया काउंटर नंबर 001 आपातकालीन कक्ष में तुरंत संपर्क करें। अस्पताल सहायक को सूचित किया जा रहा है।",
      'hi'
    );

    // Call backend emergency trigger
    MediKioskApi.post('/api/emergency/trigger', {
      patient_id: patient.id || 1,
      reason: interview.red_flag_reason || 'Severe Chest Pain / Critical Alert',
      location: 'Kiosk-01 Central OPD'
    }).catch(() => {});
  }, []);

  const handleDispatchStaff = () => {
    setDispatched(true);
    MediKioskApi.post('/api/emergency/trigger', {
      patient_id: patient.id || 1,
      reason: interview.red_flag_reason || 'Critical Alert',
      staff_call: true
    }).catch(() => {});
  };

  return (
    <div className="flex-1 flex flex-col justify-center max-w-3xl mx-auto w-full py-4 select-none">
      {/* Red Alert Banner Card */}
      <ClayCard className="p-8 border-3 border-manjistha-red bg-gradient-to-b from-manjistha-red/10 via-shweta-white to-cream-warm shadow-2xl flex flex-col items-center text-center gap-6">
        {/* Pulsing Siren Icon */}
        <div className="relative flex items-center justify-center">
          <div className="absolute w-24 h-24 rounded-full bg-manjistha-red/20 animate-ping" />
          <div className="w-20 h-20 rounded-full bg-manjistha-red text-white flex items-center justify-center shadow-lg">
            <Siren className="w-10 h-10 animate-bounce" />
          </div>
        </div>

        {/* Title */}
        <div>
          <span className="inline-block text-xs font-bold text-white bg-manjistha-red px-3 py-1 rounded-pill uppercase tracking-wider mb-2">
            अति-आवश्यक क्लिनिकल डायवर्जन • Red Flag Triage Diversion
          </span>
          <h2 className="font-display font-extrabold text-title sm:text-hero text-manjistha-red leading-tight">
            तत्काल आपातकालीन परामर्श आवश्यक
          </h2>
          <p className="text-body text-teak-grey font-medium mt-1">
            Immediate Emergency Care Required
          </p>
        </div>

        {/* Reason Box */}
        <div className="bg-manjistha-red/10 border border-manjistha-red/30 rounded-card p-4 w-full max-w-lg">
          <span className="text-caption text-teak-muted block mb-1">
            पहचाना गया गंभीर लक्षण / Identified Critical Symptom:
          </span>
          <strong className="text-heading font-display font-bold text-manjistha-red">
            {interview.red_flag_reason || 'सीने में तीव्र दर्द / Severe Chest Pain'}
          </strong>
        </div>

        {/* Destination Card */}
        <div className="bg-shweta-white border-2 border-haritaki-gold rounded-card p-6 w-full max-w-lg shadow-card">
          <span className="text-caption text-teak-muted">
            कृपया सीधे यहां जाएं / Please proceed immediately to:
          </span>
          <h3 className="font-display font-extrabold text-title text-teak-grey my-1">
            कक्ष संख्या 001 — आकस्मिक चिकित्सा विभाग
          </h3>
          <p className="text-caption text-haritaki-deep font-bold">
            Room 001 — Emergency &amp; Casualty Ward (Ground Floor)
          </p>
        </div>

        {/* Dispatch Status & Buttons */}
        <div className="w-full max-w-lg flex flex-col gap-3">
          {dispatched ? (
            <div className="flex items-center justify-center gap-2 p-3 bg-herbal-green/10 border border-herbal-green/30 rounded-btn text-herbal-green font-bold text-caption">
              <CheckCircle2 className="w-5 h-5" />
              <span>अस्पताल सहायक को सूचना भेज दी गई है। कृपया वहीं प्रतीक्षा करें।</span>
            </div>
          ) : (
            <ClayButton
              variant="danger"
              size="touch"
              onClick={handleDispatchStaff}
              className="w-full text-btn-pri shadow-btn-gold bg-manjistha-red hover:bg-manjistha-red/90 text-white"
            >
              <span className="flex items-center justify-center gap-2">
                <PhoneCall className="w-5 h-5 animate-pulse" />
                <span>अस्पताल सहायक को बुलाएं / Dispatch Hospital Staff Now</span>
              </span>
            </ClayButton>
          )}

          <ClayButton
            variant="neutral"
            size="md"
            onClick={() => {
              updateInterview({ is_red_flag: false, red_flag_reason: null });
              onDismiss();
            }}
            className="w-full"
          >
            <span className="flex items-center justify-center gap-2 text-teak-muted hover:text-teak-grey">
              <ArrowLeft className="w-4 h-4" />
              <span>गलत चयन था? लक्षण पुनः चुनें / Mistake? Re-select Symptoms</span>
            </span>
          </ClayButton>
        </div>
      </ClayCard>
    </div>
  );
}
