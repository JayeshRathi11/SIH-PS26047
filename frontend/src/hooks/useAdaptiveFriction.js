import { useState, useCallback } from 'react';

/**
 * Adaptive Accessibility Step-Down Hook
 *
 * Computes Interaction Friction:
 * friction = w1 * (1 - ASR_Confidence) + w2 * (Latency_Sec / 10) + w3 * Confusion_Count
 *
 * Levels:
 * - Level 0 (Normal): Conversational open-ended voice prompts
 * - Level 1 (Moderate): Spoken multiple-choice options (2-4 pills)
 * - Level 2 (High): Disable speech; High-contrast touch icon cards + 2D Body Map
 */

const CONFUSION_PHRASES = [
  'what', 'kya', 'samajh nahi aaya', 'pata nahi', 'repeat', 'phir se bolo',
  'help', 'madad', 'kay mhanto', 'nahi samjhe', 'boliye', 'again'
];

export function useAdaptiveFriction({
  w1 = 1.5,
  w2 = 0.5,
  w3 = 1.0,
  level1Threshold = 1.0,
  level2Threshold = 2.2,
} = {}) {
  const [currentLevel, setCurrentLevel] = useState(0);
  const [frictionHistory, setFrictionHistory] = useState([]);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);

  const assessTurn = useCallback(({
    asrConfidence = 0.95,
    latencySec = 2.0,
    transcript = '',
    wasTimeout = false,
  }) => {
    // Check for confusion phrases
    const lower = transcript.toLowerCase();
    const confusionCount = CONFUSION_PHRASES.reduce((count, phrase) => {
      return lower.includes(phrase) ? count + 1 : count;
    }, 0) + (wasTimeout ? 2 : 0);

    // Compute friction score
    const score = (
      w1 * Math.max(0, 1.0 - asrConfidence) +
      w2 * Math.min(3.0, latencySec / 5.0) +
      w3 * confusionCount
    );

    setFrictionHistory((prev) => [...prev.slice(-9), score]);

    // Determine target level
    let targetLevel = 0;
    if (score >= level2Threshold || wasTimeout || consecutiveFailures >= 2) {
      targetLevel = 2;
      setConsecutiveFailures((prev) => prev + 1);
    } else if (score >= level1Threshold || consecutiveFailures === 1) {
      targetLevel = 1;
      setConsecutiveFailures((prev) => prev + 1);
    } else {
      targetLevel = 0;
      setConsecutiveFailures(0);
    }

    // Never step down too drastically in the same session, but allow manual reset
    setCurrentLevel((prev) => Math.max(prev, targetLevel));

    return { score, targetLevel };
  }, [w1, w2, w3, level1Threshold, level2Threshold, consecutiveFailures]);

  const setLevelManually = useCallback((level) => {
    setCurrentLevel(level);
  }, []);

  const resetFriction = useCallback(() => {
    setCurrentLevel(0);
    setFrictionHistory([]);
    setConsecutiveFailures(0);
  }, []);

  return {
    currentLevel,
    frictionHistory,
    assessTurn,
    setLevelManually,
    resetFriction,
    frictionLevel: currentLevel,
    stepDownModality: () => setCurrentLevel(prev => Math.min(prev + 1, 2)),
    recordInteraction: (type) => assessTurn({ transcript: type, latencySec: 2, asrConfidence: 0.9 }),
    frictionScore: frictionHistory.length > 0 ? frictionHistory[frictionHistory.length - 1].friction : 0,
    isVoiceMode: currentLevel === 0,
    isGuidedMode: currentLevel === 1,
    isTouchCardMode: currentLevel === 2,
  };
}

export default useAdaptiveFriction;
