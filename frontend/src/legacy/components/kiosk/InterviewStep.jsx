import React, { useState, useEffect } from 'react';
import { Sparkles, MessageSquare, ArrowLeft, ArrowRight, Activity, HelpCircle } from 'lucide-react';
import useAdaptiveFriction from '../../hooks/useAdaptiveFriction';
import AdaptiveQuestions from './AdaptiveQuestions';

const INTERVIEW_QUESTIONS = [
  {
    id: 'chief_complaint',
    stepNumber: 1,
    textHi: 'आज आपको क्या मुख्य समस्या या तकलीफ है?',
    textEn: 'What is your primary medical concern today?',
    suggestedPills: [
      'तेज़ बुखार / High Fever',
      'छाती में दर्द व भारीपन / Chest Pain',
      'सांस फूलना / Shortness of Breath',
      'पेट में दर्द व मरोड़ / Abdominal Cramps',
      'गंभीर सिरदर्द / Severe Headache',
      'जोड़ों में दर्द व सूजन / Joint Pain'
    ]
  },
  {
    id: 'duration_onset',
    stepNumber: 2,
    textHi: 'यह तकलीफ कब से है और कैसे शुरू हुई?',
    textEn: 'Since when do you have this, and how did it begin?',
    suggestedPills: [
      'आज सुबह से / Since today morning',
      'पिछले 2-3 दिनों से / Past 2-3 days',
      'एक सप्ताह से / Since 1 week',
      'अचानक शुरू हुआ / Sudden onset',
      'धीरे-धीरे बढ़ रहा है / Gradually worsening'
    ]
  },
  {
    id: 'severity_associated',
    stepNumber: 3,
    textHi: 'दर्द या तकलीफ कितनी तेज़ है और क्या कोई अन्य लक्षण भी हैं?',
    textEn: 'How severe is it, and are there associated symptoms?',
    suggestedPills: [
      'हल्का दर्द (1-3) / Mild',
      'मध्यम दर्द (4-6) / Moderate',
      'अत्यधिक तेज़ दर्द (7-10) / Severe',
      'उल्टी व चक्कर / Vomiting & Dizziness',
      'पसीना आना व घबराहट / Sweating & Anxiety'
    ]
  },
  {
    id: 'past_medical_ayush',
    stepNumber: 4,
    textHi: 'क्या आप पहले से कोई बीमारी या आयुर्वेदिक/एलोपैथिक दवा ले रहे हैं?',
    textEn: 'Any pre-existing conditions or prior Ayurvedic/Allopathic medicines?',
    suggestedPills: [
      'मधुमेह / Diabetes',
      'उच्च रक्तचाप / Hypertension',
      'अस्थमा / दमा / Asthma',
      'गिलोय / अश्वगंधा / Giloy / Ashwagandha',
      'कोई दवा नहीं / No medications'
    ]
  },
  {
    id: 'allergies_lifestyle',
    stepNumber: 5,
    textHi: 'क्या आपको किसी दवा से एलर्जी है? आपकी भूख और नींद कैसी है?',
    textEn: 'Any known drug allergies? How is your digestion and sleep?',
    suggestedPills: [
      'पेनिसिलिन / सल्फा एलर्जी / Drug Allergy',
      'कोई एलर्जी नहीं / No known allergy',
      'भूख कम लगना (मंदाग्नि) / Poor appetite',
      'अनिद्रा / नींद में कमी / Insomnia',
      'सामान्य नींद व भूख / Normal'
    ]
  }
];

export default function InterviewStep({ patient, onComplete, onBack }) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [interviewAnswers, setInterviewAnswers] = useState({});
  const [isRecording, setIsRecording] = useState(false);

  const {
    frictionLevel,
    stepDownModality,
    resetFriction,
    recordInteraction,
    frictionScore
  } = useAdaptiveFriction({
    hesitationThresholdMs: 7000,
    maxFrictionLevel: 2
  });

  const currentQuestion = INTERVIEW_QUESTIONS[currentQuestionIndex];
  const totalQuestions = INTERVIEW_QUESTIONS.length;
  const progressPercent = Math.round(((currentQuestionIndex) / totalQuestions) * 100);

  const handleToggleRecording = () => {
    setIsRecording(prev => !prev);
    recordInteraction('VOICE_MIC_TOGGLE');
  };

  const handleAnswerSubmitted = (answerText) => {
    recordInteraction('ANSWER_SUBMITTED');

    const updatedAnswers = {
      ...interviewAnswers,
      [currentQuestion.id]: {
        questionHi: currentQuestion.textHi,
        questionEn: currentQuestion.textEn,
        answer: answerText
      }
    };
    setInterviewAnswers(updatedAnswers);

    if (currentQuestionIndex < totalQuestions - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
      resetFriction();
      setIsRecording(false);
    } else {
      // Completed all questions
      onComplete({
        patient,
        interviewAnswers: updatedAnswers,
        frictionScore,
        completedAt: new Date().toISOString()
      });
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      <div className="bg-white rounded-2xl shadow-xl border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-ayush-primary to-ayush-primary-dark text-white p-6 sm:p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center border border-white/20">
                <MessageSquare className="w-7 h-7 text-ayush-accent" />
              </div>
              <div>
                <h2 className="text-2xl sm:text-3xl font-bold font-serif">
                  क्लिनिकल साक्षात्कार / Clinical Interview
                </h2>
                <p className="text-emerald-100 text-sm mt-1">
                  रोगी: {patient?.name || 'अतिथि / Guest'} ({patient?.age || '--'} वर्ष, {patient?.gender || '--'})
                </p>
              </div>
            </div>

            <div className="text-right">
              <span className="text-xs text-emerald-200">प्रगति / Progress</span>
              <div className="text-xl font-bold font-mono text-white">
                {currentQuestionIndex + 1} / {totalQuestions}
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-black/20 h-2 rounded-full mt-4 overflow-hidden">
            <div
              className="bg-ayush-accent h-full transition-all duration-300 rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Adaptive Friction Indicator Banner */}
        <div className="bg-stone-50 border-b border-stone-200 px-6 py-2.5 flex items-center justify-between text-xs text-stone-600">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-ayush-primary" />
            <span>
              अनुकूली इंटरैक्शन मोड: {frictionLevel === 0 ? 'आवाज़ (Voice L0)' : frictionLevel === 1 ? 'मार्गदर्शित विकल्प (Pills L1)' : 'विजुअल मैप (Body Map L2)'}
            </span>
          </div>

          <button
            type="button"
            onClick={stepDownModality}
            className="text-ayush-primary font-medium hover:underline flex items-center gap-1"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            सरल मोड में बदलें / Simplify Input
          </button>
        </div>

        {/* Questions Body */}
        <div className="p-6 sm:p-8">
          <AdaptiveQuestions
            question={currentQuestion}
            frictionLevel={frictionLevel}
            onAnswerSubmitted={handleAnswerSubmitted}
            onFrictionEvent={(ev) => recordInteraction(ev.type)}
            isRecording={isRecording}
            onToggleRecording={handleToggleRecording}
          />

          {/* Navigation Back */}
          <div className="pt-4 mt-6 border-t border-stone-100 flex items-center justify-between">
            <button
              type="button"
              onClick={onBack}
              className="min-h-[44px] px-4 py-2 rounded-xl text-stone-500 hover:text-stone-800 hover:bg-stone-100 transition text-sm flex items-center gap-1.5"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>सहमति पर वापस / Back to Consent</span>
            </button>
            <span className="text-xs text-stone-400">
              चरण {currentQuestionIndex + 1} का उत्तर दें / Answer step {currentQuestionIndex + 1}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
