import React from 'react';
import { Mic, MicOff } from 'lucide-react';

/**
 * 3D Dome Microphone Button with tactile acoustic wave feedback
 */
export default function ClayMicDome({
  isListening = false,
  onToggle,
  volumeLevel = 0,
  disabled = false,
  label = 'बोलकर बताएं / Tap to Speak',
  className = ''
}) {
  return (
    <div className={`flex flex-col items-center gap-3 ${className}`}>
      <div className="relative flex items-center justify-center">
        {/* Pulsing acoustic ring when active */}
        {isListening && (
          <div className="absolute w-28 h-28 rounded-full border-2 border-haritaki-gold/60 clay-pulse-wave pointer-events-none" />
        )}
        {isListening && (
          <div
            className="absolute w-24 h-24 rounded-full bg-haritaki-gold/15 transition-transform duration-75 pointer-events-none"
            style={{ transform: `scale(${1 + (volumeLevel || 0.15) * 0.4})` }}
          />
        )}

        <button
          type="button"
          onClick={onToggle}
          disabled={disabled}
          className={`clay-mic-dome touch-target relative w-20 h-20 rounded-full flex items-center justify-center cursor-pointer transition-all active:scale-[0.94] active:translate-y-[2px] disabled:opacity-50 disabled:cursor-not-allowed ${
            isListening ? 'ring-4 ring-haritaki-gold/40' : ''
          }`}
          aria-label={label}
        >
          {isListening ? (
            <MicOff className="w-9 h-9 text-white animate-pulse" />
          ) : (
            <Mic className="w-9 h-9 text-white" />
          )}
        </button>
      </div>

      {label && (
        <span className="font-display text-caption font-bold text-haritaki-deep text-center select-none">
          {isListening ? 'सुन रहा हूँ... बोलिए / Listening...' : label}
        </span>
      )}
    </div>
  );
}
