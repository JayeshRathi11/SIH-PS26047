import React, { useState } from 'react';
import { Mic, MicOff, Volume2, Sparkles, Check, ChevronRight, CornerDownRight } from 'lucide-react';
import BodyMapPicker from './BodyMapPicker';

export default function AdaptiveQuestions({
  question,
  frictionLevel = 0,
  onAnswerSubmitted,
  onFrictionEvent,
  isRecording = false,
  onToggleRecording
}) {
  const [selectedPills, setSelectedPills] = useState([]);
  const [customText, setCustomText] = useState('');
  const [bodyPartSelected, setBodyPartSelected] = useState(null);

  const togglePill = (pill) => {
    setSelectedPills((prev) => {
      const exists = prev.includes(pill);
      const next = exists ? prev.filter(p => p !== pill) : [...prev, pill];
      if (onFrictionEvent) onFrictionEvent({ type: 'PILL_TOGGLED', pill, selected: !exists });
      return next;
    });
  };

  const handleBodyPartSelect = (part) => {
    setBodyPartSelected(part);
    if (onFrictionEvent) onFrictionEvent({ type: 'BODY_PART_SELECTED', part });
    if (!selectedPills.includes(part.labelHi)) {
      setSelectedPills(prev => [...prev, `${part.labelHi} (${part.labelEn})`]);
    }
  };

  const handleSubmit = () => {
    const finalAnswerParts = [];
    if (selectedPills.length > 0) {
      finalAnswerParts.push(selectedPills.join(', '));
    }
    if (bodyPartSelected) {
      finalAnswerParts.push(`स्थान / Location: ${bodyPartSelected.labelHi} (${bodyPartSelected.labelEn})`);
    }
    if (customText.trim()) {
      finalAnswerParts.push(customText.trim());
    }

    const answer = finalAnswerParts.join('. ') || 'कोई प्रतिक्रिया नहीं / No response';
    onAnswerSubmitted(answer);

    // Reset local state for next question
    setSelectedPills([]);
    setCustomText('');
    setBodyPartSelected(null);
  };

  const playQuestionAudio = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(question.textHi || question.text);
      utterance.lang = 'hi-IN';
      utterance.rate = 0.9;
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <div className="space-y-6">
      {/* Current Question Card */}
      <div className="bg-gradient-to-br from-emerald-50 via-white to-stone-50 border border-emerald-200/80 rounded-2xl p-6 shadow-sm">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <span className="bg-ayush-primary text-white text-xs px-2.5 py-1 rounded-full font-bold">
              प्रश्न / Question {question.stepNumber || 1}
            </span>
            {frictionLevel > 0 && (
              <span className="bg-amber-100 text-amber-800 text-[11px] px-2.5 py-0.5 rounded-full font-medium flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                सरल मोड / Guided Mode (L{frictionLevel})
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={playQuestionAudio}
            className="p-2 rounded-xl bg-white border border-stone-200 text-stone-600 hover:bg-stone-50 transition"
            title="प्रश्न सुनें / Listen question"
          >
            <Volume2 className="w-5 h-5" />
          </button>
        </div>

        <h3 className="text-xl sm:text-2xl font-bold text-stone-900 mt-2 font-serif">
          {question.textHi || question.text}
        </h3>
        {question.textEn && (
          <p className="text-sm text-stone-600 mt-1">{question.textEn}</p>
        )}
      </div>

      {/* Dynamic Interaction based on Friction Level */}
      {/* Level 0: Primary Voice with Waveform */}
      {frictionLevel === 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 text-center space-y-4">
          <p className="text-sm text-stone-600">
            माइक का बटन दबाएं और बोलकर बताएं / Press the mic button and speak clearly:
          </p>

          <div className="flex justify-center">
            <button
              type="button"
              onClick={onToggleRecording}
              className={`w-24 h-24 rounded-full flex items-center justify-center transition-all transform active:scale-95 shadow-xl ${
                isRecording
                  ? 'bg-rose-500 text-white animate-pulse ring-8 ring-rose-200 shadow-rose-300'
                  : 'bg-ayush-primary text-white hover:bg-ayush-primary-dark ring-8 ring-emerald-100 shadow-emerald-200'
              }`}
            >
              {isRecording ? <MicOff className="w-10 h-10" /> : <Mic className="w-10 h-10" />}
            </button>
          </div>

          {isRecording ? (
            <div className="space-y-1">
              <p className="text-sm font-semibold text-rose-600 animate-pulse">
                हम सुन रहे हैं... / Listening...
              </p>
              <div className="flex justify-center items-center gap-1.5 h-6">
                <span className="w-1 h-3 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                <span className="w-1 h-5 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1 h-7 bg-rose-500 rounded-full animate-bounce"></span>
                <span className="w-1 h-4 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1 h-2 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-stone-400">
              बोलना शुरू करने के लिए माइक दबाएं • Tap mic to begin speaking
            </p>
          )}
        </div>
      )}

      {/* Level 1 & Level 2: Symptom Pills / Guided Choices */}
      {(frictionLevel >= 1 || question.suggestedPills?.length > 0) && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-stone-800 flex items-center gap-2">
              <CornerDownRight className="w-4 h-4 text-ayush-primary" />
              उपयुक्त विकल्प चुनें / Tap Matching Symptoms:
            </h4>
            {selectedPills.length > 0 && (
              <span className="text-xs text-ayush-primary font-semibold">
                {selectedPills.length} चुने गए / selected
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-2.5">
            {(question.suggestedPills || [
              'सिरदर्द / Headache',
              'तेज़ बुखार / High Fever',
              'खांसी व बलगम / Cough',
              'छाती में दर्द / Chest Pain',
              'सांस लेने में तकलीफ / Breathlessness',
              'पेट दर्द / Abdominal Pain',
              'उल्टी / जी मिचलाना / Nausea',
              'जोड़ों में दर्द / Joint Pain',
              'थकान व कमजोरी / Fatigue',
              'भूख न लगना / Loss of Appetite'
            ]).map((pill, idx) => {
              const isSelected = selectedPills.includes(pill);
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => togglePill(pill)}
                  className={`min-h-[48px] px-4 py-2 rounded-xl text-sm font-medium border transition-all flex items-center gap-2 ${
                    isSelected
                      ? 'bg-ayush-primary text-white border-ayush-primary shadow-sm scale-102'
                      : 'bg-stone-50 text-stone-700 border-stone-200 hover:bg-stone-100'
                  }`}
                >
                  {isSelected && <Check className="w-4 h-4" />}
                  <span>{pill}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Level 2: Visual Body Map Picker */}
      {frictionLevel >= 2 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-6">
          <h4 className="text-sm font-bold text-stone-800 mb-4">
            शरीर के हिस्से पर स्पर्श करें / Touch Affected Body Area:
          </h4>
          <BodyMapPicker onSelectZone={handleBodyPartSelect} />
        </div>
      )}

      {/* Optional Manual Note / Text Input */}
      <div className="bg-white border border-stone-200 rounded-2xl p-4">
        <label className="block text-xs font-semibold text-stone-600 mb-1.5">
          अतिरिक्त विवरण लिखें (वैकल्पिक) / Additional Notes (Optional):
        </label>
        <textarea
          rows={2}
          value={customText}
          onChange={(e) => setCustomText(e.target.value)}
          placeholder="उदा. लक्षण पिछले 3 दिनों से बढ़ रहे हैं... / e.g. Symptoms worsening since 3 days..."
          className="w-full text-sm p-3 rounded-xl border border-stone-200 focus:outline-none focus:ring-2 focus:ring-ayush-primary/30"
        />
      </div>

      {/* Submit Next Button */}
      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={handleSubmit}
          className="min-h-[52px] px-8 py-3 bg-ayush-primary hover:bg-ayush-primary-dark text-white rounded-xl font-bold text-base shadow-lg shadow-ayush-primary/20 flex items-center gap-2 transition transform active:scale-95"
        >
          <span>आगे बढ़ें / Save & Continue</span>
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
