import React, { useState } from 'react';
import { ShieldCheck, Volume2, CheckCircle2, Lock, AlertTriangle, ArrowRight, X } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import { useAudio } from '../../context/AudioContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function ConsentScreen({ onAgree, onDecline }) {
  const { consent, updateConsent, language, patient } = useKioskSession();
  const { playTts, isPlaying } = useAudio();

  const [triageConsent, setTriageConsent] = useState(consent.triage_consent ?? true);
  const [voiceConsent, setVoiceConsent] = useState(consent.ai_consent ?? true);
  const [ocrConsent, setOcrConsent] = useState(consent.ocr_consent ?? true);
  const [showDeclineModal, setShowDeclineModal] = useState(false);
  const [loading, setLoading] = useState(false);

  const allSelected = triageConsent && voiceConsent && ocrConsent;

  const handleToggleAll = () => {
    const nextVal = !allSelected;
    setTriageConsent(nextVal);
    setVoiceConsent(nextVal);
    setOcrConsent(nextVal);
  };

  const handleReadout = () => {
    const speechText = language === 'hi'
      ? "डिजिटल व्यक्तिगत डेटा संरक्षण अधिनियम 2023 के तहत आपकी सहमति आवश्यक है। पहला, आयुष ट्राइएज के लिए लक्षण साझा करना। दूसरा, डॉ. चरक एआई द्वारा आवाज समझना। तीसरा, पुराने पर्चों का ओसीआर स्कैन। क्या आप सहमत हैं?"
      : "Under the Digital Personal Data Protection Act 2023, your consent is requested for AYUSH clinical triage, AI voice transcription with zero data retention, and prescription document scanning.";
    playTts(speechText, language);
  };

  const handleAgreeAndProceed = async () => {
    setLoading(true);
    const consentPayload = {
      patient_id: patient.id || 1,
      triage_consent: triageConsent,
      ai_consent: voiceConsent,
      ocr_consent: ocrConsent,
      granted: triageConsent,
      timestamp: new Date().toISOString()
    };

    try {
      await MediKioskApi.post('/api/consents', consentPayload);
    } catch {
      // Offline fallback
    }

    updateConsent(consentPayload);
    setLoading(false);
    onAgree();
  };

  return (
    <div className="flex-1 flex flex-col justify-center max-w-4xl mx-auto w-full py-2">
      {/* Title */}
      <div className="text-center mb-6">
        <ClayBadge variant="ayush" className="mb-2">
          चरण 2 • Step 2
        </ClayBadge>
        <div className="flex items-center justify-center gap-2 mb-1">
          <ShieldCheck className="w-8 h-8 text-haritaki-deep" />
          <h2 className="font-display font-extrabold text-heading sm:text-title text-teak-grey">
            डिजिटल सहमति प्रपत्र • DPDP Digital Consent
          </h2>
        </div>
        <p className="text-caption sm:text-body text-teak-muted max-w-xl mx-auto">
          डिजिटल व्यक्तिगत डेटा संरक्षण अधिनियम (DPDP Act 2023) के तहत आपका स्वास्थ्य डेटा पूर्णतः सुरक्षित एवं गोपनीय रखा जाता है।
        </p>
      </div>

      {/* Controls Bar: Select All + Listen Audio */}
      <div className="flex items-center justify-between bg-cream-recess px-6 py-2.5 rounded-btn border border-copper-border/60 mb-6 shadow-inset-recess">
        <button
          type="button"
          onClick={handleToggleAll}
          className="font-display font-bold text-caption text-haritaki-deep hover:text-haritaki-gold flex items-center gap-2 cursor-pointer"
        >
          <div className={`w-5 h-5 rounded flex items-center justify-center border ${
            allSelected ? 'bg-haritaki-gold border-haritaki-gold text-white' : 'border-copper-border bg-shweta-white'
          }`}>
            {allSelected && <CheckCircle2 className="w-4 h-4" />}
          </div>
          <span>सभी चुनें / Select All</span>
        </button>

        <button
          type="button"
          onClick={handleReadout}
          className={`px-3 py-1 rounded-pill text-caption font-semibold flex items-center gap-1.5 transition-all cursor-pointer border ${
            isPlaying
              ? 'bg-haritaki-gold text-white border-haritaki-gold animate-pulse'
              : 'bg-cream-neutral text-haritaki-deep border-copper-border'
          }`}
        >
          <Volume2 className="w-4 h-4" />
          <span>{isPlaying ? 'सुन रहे हैं... / Playing' : 'सहमति सुनें / Read Out'}</span>
        </button>
      </div>

      {/* 3 Granular Consent Cards */}
      <div className="flex flex-col gap-4 mb-6">
        {/* Clause 1: Clinical Triage */}
        <ClayCard
          selected={triageConsent}
          interactive
          onClick={() => setTriageConsent(!triageConsent)}
          className="p-5 flex items-start gap-4"
        >
          <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 border ${
            triageConsent
              ? 'bg-haritaki-gold border-haritaki-gold text-white shadow-check-disk'
              : 'border-copper-border bg-cream-recess text-transparent'
          }`}>
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey">
              1. आयुष क्लिनिकल ट्राइएज परामर्श सहमति (Clinical Triage Consent)
            </h3>
            <p className="text-caption text-teak-muted mt-1 leading-relaxed">
              मैं डॉक्टर से मिलने से पहले अपने मुख्य लक्षण, स्वास्थ्य इतिहास और अष्टविध परीक्षा संबंधी जानकारी साझा करने की सहमति देता/देती हूँ।
            </p>
          </div>
        </ClayCard>

        {/* Clause 2: Voice & AI Assistant */}
        <ClayCard
          selected={voiceConsent}
          interactive
          onClick={() => setVoiceConsent(!voiceConsent)}
          className="p-5 flex items-start gap-4"
        >
          <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 border ${
            voiceConsent
              ? 'bg-haritaki-gold border-haritaki-gold text-white shadow-check-disk'
              : 'border-copper-border bg-cream-recess text-transparent'
          }`}>
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey">
              2. एआई वॉयस ट्रांसक्रिप्शन सहमति (AI Voice & Sarvam ASR Consent)
            </h3>
            <p className="text-caption text-teak-muted mt-1 leading-relaxed">
              मैं डॉ. चरक एआई सहायक के साथ आवाज में बातचीत और त्वरित पाठ अनुवाद की सहमति देता/देती हूँ। परामर्श पूर्ण होने पर वॉयस रिकॉर्डिंग स्वतः नष्ट हो जाएगी (Zero Retention)।
            </p>
          </div>
        </ClayCard>

        {/* Clause 3: OCR Prescription Scanning */}
        <ClayCard
          selected={ocrConsent}
          interactive
          onClick={() => setOcrConsent(!ocrConsent)}
          className="p-5 flex items-start gap-4"
        >
          <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 border ${
            ocrConsent
              ? 'bg-haritaki-gold border-haritaki-gold text-white shadow-check-disk'
              : 'border-copper-border bg-cream-recess text-transparent'
          }`}>
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey">
              3. पुराने पर्चे व रिपोर्ट ओसीआर स्कैनिंग (OCR Document Scan Consent)
            </h3>
            <p className="text-caption text-teak-muted mt-1 leading-relaxed">
              मैं अपने पूर्व चिकित्सकीय पर्चों एवं जांच रिपोर्टों के ओसीआर (OCR) डिजिटलीकरण और दवा इतिहास मिलान की सहमति देता/देती हूँ।
            </p>
          </div>
        </ClayCard>
      </div>

      {/* Buttons: Agree / Decline */}
      <div className="flex flex-col sm:flex-row items-center justify-end gap-4 pt-2">
        <ClayButton
          variant="decline"
          size="md"
          onClick={() => setShowDeclineModal(true)}
        >
          अस्वीकार करें / Decline
        </ClayButton>

        <ClayButton
          variant="agree"
          size="touch"
          disabled={!triageConsent}
          loading={loading}
          onClick={handleAgreeAndProceed}
          className="shadow-btn-gold px-8"
        >
          <span className="flex items-center gap-2">
            <span>सहमति दें एवं आगे बढ़ें / Agree &amp; Proceed</span>
            <ArrowRight className="w-5 h-5" />
          </span>
        </ClayButton>
      </div>

      {/* Decline Safety Modal */}
      {showDeclineModal && (
        <div className="fixed inset-0 z-50 bg-teak-grey/60 backdrop-blur-sm flex items-center justify-center p-4">
          <ClayCard className="max-w-md w-full p-6 flex flex-col gap-4 border-2 border-manjistha-red shadow-2xl">
            <div className="flex items-center gap-3 text-manjistha-red">
              <AlertTriangle className="w-8 h-8 flex-shrink-0" />
              <h3 className="font-display font-bold text-heading">
                सहमति अस्वीकार? / Decline Consent?
              </h3>
            </div>
            <p className="text-caption text-teak-muted leading-relaxed">
              यदि आप डिजिटल सहमति अस्वीकार करते हैं, तो कियोस्क द्वारा स्वचालित स्वास्थ्य जांच नहीं की जा सकेगी। आपको सामान्य ओपीडी काउंटर पर जाकर मैन्युअल पंजीकरण कराना होगा।
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <ClayButton
                variant="neutral"
                size="sm"
                onClick={() => setShowDeclineModal(false)}
              >
                वापस जाएं / Go Back
              </ClayButton>
              <ClayButton
                variant="danger"
                size="sm"
                onClick={() => {
                  setShowDeclineModal(false);
                  onDecline();
                }}
              >
                पुष्टि करें / Confirm Exit
              </ClayButton>
            </div>
          </ClayCard>
        </div>
      )}
    </div>
  );
}
