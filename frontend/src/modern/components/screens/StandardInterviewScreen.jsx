import React, { useState } from 'react';
import { Stethoscope, AlertTriangle, Clock, Activity, Check } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import { useAudio } from '../../context/AudioContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayMicDome from '../atoms/ClayMicDome';
import ClayBodyMap from '../atoms/ClayBodyMap';
import ClayBadge from '../atoms/ClayBadge';
import { DrCharakaAvatar } from '../atoms/AyushIcons';

export default function StandardInterviewScreen({
  onProceedAyush,
  onTriggerRedFlag
}) {
  const { interview, updateInterview, language } = useKioskSession();
  const { playTts, isPlaying } = useAudio();

  const [selectedSymptoms, setSelectedSymptoms] = useState(interview.chief_complaints || []);
  const [selectedZones, setSelectedZones] = useState(interview.body_zones || []);
  const [duration, setDuration] = useState(interview.duration_days || 3);
  const [severity, setSeverity] = useState(interview.severity || 5);
  const [isListening, setIsListening] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState('');

  const symptomsList = [
    { id: 'fever', labelHi: 'ज्वर / बुखार', labelEn: 'Fever', isRedFlag: false },
    { id: 'cough', labelHi: 'कास / खांसी', labelEn: 'Cough', isRedFlag: false },
    { id: 'chest_pain', labelHi: 'सीने में तीव्र दर्द (छाती में भारीपन)', labelEn: 'Severe Chest Pain', isRedFlag: true },
    { id: 'breathless', labelHi: 'श्वास कष्ट / सांस फूलना', labelEn: 'Breathlessness', isRedFlag: true },
    { id: 'joint_pain', labelHi: 'संधि शूल / जोड़ों में दर्द', labelEn: 'Joint Pain', isRedFlag: false },
    { id: 'acidity', labelHi: 'अम्लपित्त / एसिडिटी व जलन', labelEn: 'Hyperacidity', isRedFlag: false },
    { id: 'headache', labelHi: 'शिरःशूल / सिरदर्द', labelEn: 'Headache', isRedFlag: false },
    { id: 'indigestion', labelHi: 'अजीर्ण / अपच व कब्ज', labelEn: 'Indigestion', isRedFlag: false }
  ];

  const handleToggleSymptom = (symptom) => {
    if (symptom.isRedFlag) {
      updateInterview({
        is_red_flag: true,
        red_flag_reason: symptom.labelHi
      });
      onTriggerRedFlag(symptom.labelHi);
      return;
    }

    setSelectedSymptoms((prev) => {
      const exists = prev.includes(symptom.labelHi);
      const updated = exists ? prev.filter((s) => s !== symptom.labelHi) : [...prev, symptom.labelHi];
      updateInterview({ chief_complaints: updated });
      return updated;
    });
  };

  const handleToggleZone = (zoneId) => {
    setSelectedZones((prev) => {
      const exists = prev.includes(zoneId);
      const updated = exists ? prev.filter((z) => z !== zoneId) : [...prev, zoneId];
      updateInterview({ body_zones: updated });
      return updated;
    });
  };

  const handleVoiceToggle = () => {
    if (!isListening) {
      setIsListening(true);
      setTimeout(() => {
        setIsListening(false);
        const recognized = "मुझे 3 दिनों से हल्का बुखार और जोड़ों में दर्द है";
        setVoiceTranscript(recognized);
        setSelectedSymptoms((prev) => [...new Set([...prev, 'ज्वर / बुखार', 'संधि शूल / जोड़ों में दर्द'])]);
        updateInterview({
          chief_complaints: [...new Set([...selectedSymptoms, 'ज्वर / बुखार', 'संधि शूल / जोड़ों में दर्द'])],
          duration_days: 3
        });
      }, 3500);
    } else {
      setIsListening(false);
    }
  };

  const handlePlayDrCharaka = () => {
    const speech = language === 'hi'
      ? "नमस्ते, मैं डॉ. चरक हूँ। कृपया अपने मुख्य लक्षण चुनें या माइक बटन दबाकर बोलकर बताएं।"
      : "Hello, I am Dr. Charaka. Please select your chief symptoms or tap the microphone to speak.";
    playTts(speech, language);
  };

  return (
    <div className="flex-1 flex flex-col max-w-5xl mx-auto w-full py-2">
      {/* Dr. Charaka Assistant Banner */}
      <ClayCard className="p-4 mb-6 flex items-center justify-between bg-gradient-to-r from-cream-warm/80 via-shweta-white to-cream-warm/50 border border-haritaki-gold/50 shadow-sm">
        <div className="flex items-center gap-4">
          <DrCharakaAvatar className="w-14 h-14" isSpeaking={isPlaying} />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-display font-bold text-btn-sec text-teak-grey">
                डॉ. चरक एआई क्लिनिकल सहायक • Dr. Charaka AI
              </h3>
              <ClayBadge variant="ayush">सक्रिय / Active</ClayBadge>
            </div>
            <p className="text-caption text-teak-muted">
              कृपया अपने मुख्य लक्षण चुनें अथवा बोलकर बताएं।
            </p>
          </div>
        </div>

        <ClayButton
          variant="neutral"
          size="sm"
          onClick={handlePlayDrCharaka}
          className="hidden sm:inline-flex"
        >
          {isPlaying ? 'सुन रहे हैं... / Listening' : 'निर्देश सुनें / Listen'}
        </ClayButton>
      </ClayCard>

      {/* Main Grid: Symptoms & Body Map */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Symptom Cards & Duration */}
        <div className="lg:col-span-8 flex flex-col gap-5">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="font-display font-bold text-heading text-teak-grey">
                मुख्य लक्षण चुनें • Select Symptoms
              </span>
              <span className="text-xs text-teak-muted">
                {selectedSymptoms.length} चुने गए
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {symptomsList.map((sym) => {
                const isSel = selectedSymptoms.includes(sym.labelHi);
                return (
                  <ClayCard
                    key={sym.id}
                    selected={isSel}
                    interactive
                    onClick={() => handleToggleSymptom(sym)}
                    className={`p-3.5 flex items-center justify-between transition-all ${
                      sym.isRedFlag ? 'hover:border-manjistha-red/60' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center border text-xs ${
                        isSel ? 'bg-haritaki-gold border-haritaki-gold text-white' : 'border-copper-border bg-cream-recess text-transparent'
                      }`}>
                        {isSel && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                      </div>
                      <div>
                        <span className={`text-caption font-bold block ${sym.isRedFlag ? 'text-manjistha-red' : 'text-teak-grey'}`}>
                          {sym.labelHi}
                        </span>
                        <span className="text-xs text-teak-muted block">
                          {sym.labelEn}
                        </span>
                      </div>
                    </div>

                    {sym.isRedFlag && (
                      <span className="text-[10px] font-bold text-manjistha-red bg-manjistha-red/10 px-2 py-0.5 rounded-pill border border-manjistha-red/30">
                        आपातकालीन
                      </span>
                    )}
                  </ClayCard>
                );
              })}
            </div>
          </div>

          {/* Duration Selector */}
          <ClayCard className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-5 h-5 text-haritaki-deep" />
              <span className="font-display font-bold text-caption text-teak-grey">
                लक्षण कितने समय से हैं? • Duration of Symptoms
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { val: 1, label: 'आज से / Today' },
                { val: 3, label: '2-3 दिन / Days' },
                { val: 7, label: '1 सप्ताह / Week' },
                { val: 30, label: '1 माह+ / Month+' }
              ].map((d) => (
                <button
                  key={d.val}
                  type="button"
                  onClick={() => {
                    setDuration(d.val);
                    updateInterview({ duration_days: d.val });
                  }}
                  className={`py-2 px-3 rounded-btn text-caption font-bold border transition-all cursor-pointer ${
                    duration === d.val
                      ? 'bg-cream-warm border-haritaki-gold text-haritaki-deep shadow-btn-gold'
                      : 'bg-cream-neutral border-copper-border text-teak-muted'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </ClayCard>

          {/* Severity Slider */}
          <ClayCard className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-haritaki-deep" />
                <span className="font-display font-bold text-caption text-teak-grey">
                  कष्ट की तीव्रता • Severity (1-10)
                </span>
              </div>
              <span className="font-mono font-bold text-title text-haritaki-deep">
                {severity}/10
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="10"
              value={severity}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                setSeverity(val);
                updateInterview({ severity: val });
              }}
              className="w-full accent-haritaki-gold cursor-pointer h-2 bg-cream-recess rounded-lg"
            />
            <div className="flex justify-between text-[11px] text-teak-muted mt-1 font-semibold">
              <span>हल्का / Mild (1-3)</span>
              <span>मध्यम / Moderate (4-7)</span>
              <span className="text-manjistha-red">तीव्र / Severe (8-10)</span>
            </div>
          </ClayCard>
        </div>

        {/* Right Column: Voice Dome & Body Map */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          {/* Voice Input Dome */}
          <ClayCard className="p-5 flex flex-col items-center text-center">
            <ClayMicDome
              isListening={isListening}
              onToggle={handleVoiceToggle}
              volumeLevel={isListening ? 0.6 : 0}
            />
            {voiceTranscript && (
              <p className="text-xs text-teak-grey bg-cream-warm/70 p-2.5 rounded-btn border border-haritaki-gold/30 mt-3 italic">
                "{voiceTranscript}"
              </p>
            )}
          </ClayCard>

          {/* Interactive Body Map */}
          <ClayBodyMap
            selectedZones={selectedZones}
            onToggleZone={handleToggleZone}
          />
        </div>
      </div>
    </div>
  );
}
