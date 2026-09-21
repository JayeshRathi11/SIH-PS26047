import React, { useState } from 'react';
import { ShieldCheck, Volume2, CheckCircle2, ArrowRight, ArrowLeft, Info, Lock } from 'lucide-react';

const CONSENT_ITEMS = [
  {
    id: 'voice_transcription',
    titleHi: 'आवाज़ रिकॉर्डिंग और अनुवाद',
    titleEn: 'Voice Recording & AI Transcription',
    descHi: 'आपके लक्षणों को समझने के लिए आपकी आवाज़ को सुरक्षित रूप से प्रोसेस किया जाएगा।',
    descEn: 'Your speech will be securely processed to transcribe symptoms and complaints.',
    required: true,
    default: true
  },
  {
    id: 'ocr_document',
    titleHi: 'दस्तावेज़ स्कैनिंग और ओसीआर',
    titleEn: 'Document Scanning & OCR',
    descHi: 'पिछले पर्चे, डिस्चार्ज सारांश और लैब रिपोर्ट का डिजिटल विश्लेषण।',
    descEn: 'Digital scanning and text extraction from prior prescriptions and reports.',
    required: true,
    default: true
  },
  {
    id: 'ayush_extraction',
    titleHi: 'आयुष एवं आधुनिक निदान विश्लेषण',
    titleEn: 'AYUSH Clinical Entity Extraction',
    descHi: 'आयुर्वेदिक एवं आधुनिक औषधियों और लक्षणों का राष्ट्रीय मानकों (AFI / NAMASTE) से मिलान।',
    descEn: 'Mapping Ayurvedic & allopathic terms against national AFI and NAMASTE standards.',
    required: true,
    default: true
  },
  {
    id: 'doctor_verification',
    titleHi: 'डॉक्टर द्वारा सत्यापन एवं समीक्षा',
    titleEn: 'Doctor Review & Clinical Verification',
    descHi: 'यह सारांश केवल आपके परामर्श चिकित्सक के उपयोग हेतु है। डॉक्टर अंतिम निर्णय लेंगे।',
    descEn: 'The generated case sheet is shared exclusively with your attending physician.',
    required: true,
    default: true
  },
  {
    id: 'emergency_dispatch',
    titleHi: 'आपातकालीन चेतावनी प्रोटोकॉल',
    titleEn: 'Emergency Flagging Protocol',
    descHi: 'यदि कोई गंभीर लक्षण (रेड फ्लैग) मिले तो क्लिनिकल टीम को तुरंत सूचित किया जाएगा।',
    descEn: 'Immediate escalation to the clinical triage team if high-risk red flags are detected.',
    required: true,
    default: true
  },
  {
    id: 'research_opt_in',
    titleHi: 'अनाम अनुसंधान एवं गुणवत्ता सुधार (वैकल्पिक)',
    titleEn: 'Anonymized Research & Quality (Optional)',
    descHi: 'आपकी पहचान छिपाकर केवल डेटा का उपयोग आयुष अनुसंधान के लिए किया जा सकता है।',
    descEn: 'De-identified clinical trends may be used for national health research.',
    required: false,
    default: false
  }
];

export default function ConsentStep({ patient, onComplete, onBack }) {
  const [consents, setConsents] = useState(() => {
    const initial = {};
    CONSENT_ITEMS.forEach(item => {
      initial[item.id] = item.default;
    });
    return initial;
  });

  const [playingAudioId, setPlayingAudioId] = useState(null);

  const toggleConsent = (id) => {
    setConsents(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const handleSelectAll = () => {
    const updated = {};
    CONSENT_ITEMS.forEach(item => {
      updated[item.id] = true;
    });
    setConsents(updated);
  };

  const playAudioGuide = (item) => {
    if (playingAudioId === item.id) {
      setPlayingAudioId(null);
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      return;
    }

    setPlayingAudioId(item.id);
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const text = `${item.titleHi}। ${item.descHi}`;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'hi-IN';
      utterance.rate = 0.9;
      utterance.onend = () => setPlayingAudioId(null);
      utterance.onerror = () => setPlayingAudioId(null);
      window.speechSynthesis.speak(utterance);
    } else {
      setTimeout(() => setPlayingAudioId(null), 2500);
    }
  };

  const canProceed = CONSENT_ITEMS.filter(i => i.required).every(i => consents[i.id]);

  const handleProceed = () => {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    onComplete({
      consents,
      timestamp: new Date().toISOString()
    });
  };

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      <div className="bg-white rounded-2xl shadow-xl border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-ayush-primary to-ayush-primary-dark text-white p-6 sm:p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center border border-white/20">
                <ShieldCheck className="w-7 h-7 text-ayush-accent" />
              </div>
              <div>
                <h2 className="text-2xl sm:text-3xl font-bold font-serif">
                  डेटा सहमति / DPDP Consent
                </h2>
                <p className="text-emerald-100 text-sm mt-1">
                  डिजिटल व्यक्तिगत डेटा संरक्षण अधिनियम 2023 • Digital Personal Data Protection
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleSelectAll}
              className="text-xs bg-white/15 hover:bg-white/25 px-3 py-1.5 rounded-lg border border-white/30 transition text-emerald-50"
            >
              सभी स्वीकारें / Accept All
            </button>
          </div>
        </div>

        {/* Notice */}
        <div className="bg-amber-50 border-b border-amber-100 p-4 px-6 sm:px-8 flex items-center gap-3 text-amber-900 text-xs sm:text-sm">
          <Lock className="w-4 h-4 text-amber-700 shrink-0" />
          <span>
            आपकी निजता हमारी प्राथमिकता है। आपका डेटा एनक्रिप्टेड है और परामर्श समाप्त होने के बाद कियोस्क से मिटा दिया जाता है।
          </span>
        </div>

        {/* Consent Items */}
        <div className="p-6 sm:p-8 space-y-4">
          {CONSENT_ITEMS.map((item) => {
            const isChecked = consents[item.id];
            const isPlaying = playingAudioId === item.id;

            return (
              <div
                key={item.id}
                className={`p-4 rounded-xl border transition-all ${
                  isChecked
                    ? 'border-ayush-primary/40 bg-emerald-50/40 shadow-sm'
                    : 'border-stone-200 bg-stone-50/50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1">
                    <input
                      type="checkbox"
                      id={`consent-${item.id}`}
                      checked={isChecked}
                      onChange={() => toggleConsent(item.id)}
                      className="mt-1 w-5 h-5 rounded text-ayush-primary focus:ring-ayush-primary border-stone-300 cursor-pointer"
                    />
                    <label htmlFor={`consent-${item.id}`} className="cursor-pointer select-none flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm sm:text-base text-stone-900">
                          {item.titleHi}
                        </span>
                        {item.required && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 font-semibold">
                            आवश्यक / Required
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-stone-600 mt-0.5">{item.titleEn}</p>
                      <p className="text-xs text-stone-500 mt-1.5">{item.descHi}</p>
                    </label>
                  </div>

                  {/* Audio Guide Button */}
                  <button
                    type="button"
                    onClick={() => playAudioGuide(item)}
                    title="सुनें / Listen audio guide"
                    className={`min-h-[44px] min-w-[44px] p-2 rounded-xl border flex items-center justify-center transition ${
                      isPlaying
                        ? 'bg-ayush-accent text-stone-900 border-ayush-accent animate-pulse'
                        : 'bg-white text-stone-600 border-stone-200 hover:bg-stone-100'
                    }`}
                  >
                    <Volume2 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            );
          })}

          {/* Navigation Controls */}
          <div className="pt-6 border-t border-stone-200 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={onBack}
              className="min-h-[48px] px-6 py-2.5 rounded-xl border border-stone-300 text-stone-700 font-semibold hover:bg-stone-100 transition flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>पीछे / Back</span>
            </button>

            <button
              type="button"
              disabled={!canProceed}
              onClick={handleProceed}
              className="min-h-[52px] px-8 py-3 bg-ayush-primary hover:bg-ayush-primary-dark text-white rounded-xl font-bold text-base shadow-lg shadow-ayush-primary/20 flex items-center gap-3 transition-all transform active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span>स्वीकार करें और साक्षात्कार शुरू करें / Agree & Start</span>
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
