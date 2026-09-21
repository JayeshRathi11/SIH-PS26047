import React from 'react';
import { Delete, X } from 'lucide-react';

/**
 * Tactile On-Screen Numeric Keypad for Kiosk Touch Entry
 */
export default function ClayKeypad({
  onKeyPress,
  onDelete,
  onClear,
  className = ''
}) {
  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'clear', '0', 'backspace'];

  return (
    <div className={`grid grid-cols-3 gap-3 p-3 bg-cream-warm/40 rounded-card border border-copper-border/60 ${className}`}>
      {keys.map((k) => {
        if (k === 'clear') {
          return (
            <button
              key={k}
              type="button"
              onClick={onClear}
              className="key-btn touch-target min-h-[56px] bg-cream-neutral text-teak-muted font-display font-bold text-caption rounded-btn border border-copper-border flex items-center justify-center transition-all active:scale-[0.96] active:translate-y-[2px]"
            >
              <span className="flex items-center gap-1">
                <X className="w-4 h-4" /> साफ़
              </span>
            </button>
          );
        }

        if (k === 'backspace') {
          return (
            <button
              key={k}
              type="button"
              onClick={onDelete}
              className="key-btn touch-target min-h-[56px] bg-cream-neutral text-teak-muted font-display font-bold rounded-btn border border-copper-border flex items-center justify-center transition-all active:scale-[0.96] active:translate-y-[2px]"
            >
              <Delete className="w-5 h-5 text-manjistha-red" />
            </button>
          );
        }

        return (
          <button
            key={k}
            type="button"
            onClick={() => onKeyPress(k)}
            className="key-btn touch-target min-h-[56px] bg-shweta-white text-teak-grey font-display font-bold text-heading rounded-btn border border-copper-border shadow-btn-neutral flex items-center justify-center transition-all active:scale-[0.96] active:translate-y-[2px]"
          >
            {k}
          </button>
        );
      })}
    </div>
  );
}
