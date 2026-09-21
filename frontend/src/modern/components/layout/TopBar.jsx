import React from 'react';
import { Volume2, VolumeX, Stethoscope, HeartPulse, BarChart3, AlertCircle } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import { useAudio } from '../../context/AudioContext';
import { AIIALogo } from '../atoms/AyushIcons';

export default function TopBar({ onOpenQaLauncher }) {
  const { language, changeLanguage, appMode, setAppMode } = useKioskSession();
  const { isPlaying, audioEnabled, setAudioEnabled, stopAudio } = useAudio();

  const handleToggleAudio = () => {
    if (isPlaying) {
      stopAudio();
    }
    setAudioEnabled(!audioEnabled);
  };

  return (
    <header className="flex-none h-[88px] bg-topbar-bg border-b border-topbar-border flex items-center justify-between px-6 sm:px-10 select-none shadow-sm">
      {/* Brand & Emblem */}
      <div className="flex items-center gap-3.5">
        <div className="w-12 h-12 rounded-card bg-shweta-white border border-haritaki-gold/40 shadow-pill flex items-center justify-center flex-shrink-0">
          <AIIALogo className="w-8 h-8" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display font-bold text-title text-teak-grey tracking-tight leading-tight">
              MEDIKIOSK • आयुष स्वास्थ्य कियोस्क
            </h1>
            <span className="hidden md:inline-block text-xs bg-haritaki-gold/20 text-haritaki-deep font-mono px-2 py-0.5 rounded-pill font-bold">
              SIH-PS26047
            </span>
          </div>
          <p className="text-caption text-teak-muted font-body">
            All India Institute of Ayurveda — New Delhi
          </p>
        </div>
      </div>

      {/* Action Controls & Mode Switcher */}
      <div className="flex items-center gap-3">
        {/* Multilingual Selector Chips */}
        <div className="flex items-center bg-cream-recess p-1 rounded-pill border border-copper-border/60 shadow-inset-recess">
          {[
            { id: 'en', label: 'English' },
            { id: 'hi', label: 'हिन्दी' },
            { id: 'mr', label: 'मराठी' }
          ].map((lang) => (
            <button
              key={lang.id}
              type="button"
              onClick={() => changeLanguage(lang.id)}
              className={`px-3 py-1 text-caption font-semibold rounded-pill transition-all cursor-pointer ${
                language === lang.id
                  ? 'bg-haritaki-gold text-white shadow-pill font-bold'
                  : 'text-teak-muted hover:text-teak-grey'
              }`}
            >
              {lang.label}
            </button>
          ))}
        </div>

        {/* Audio Narration Toggle */}
        <button
          type="button"
          onClick={handleToggleAudio}
          title={audioEnabled ? 'ध्वनि चालू / Audio Enabled' : 'ध्वनि बंद / Audio Muted'}
          className={`touch-target w-11 h-11 rounded-full flex items-center justify-center border transition-all cursor-pointer ${
            audioEnabled
              ? isPlaying
                ? 'bg-haritaki-gold text-white border-haritaki-gold animate-pulse shadow-btn-gold'
                : 'bg-cream-neutral text-haritaki-deep border-copper-border shadow-btn-neutral'
              : 'bg-cream-recess text-copper-patina border-copper-border/50'
          }`}
        >
          {audioEnabled ? (
            <Volume2 className="w-5 h-5" />
          ) : (
            <VolumeX className="w-5 h-5" />
          )}
        </button>

        {/* Workstation Mode Switcher */}
        <div className="hidden lg:flex items-center gap-1 bg-cream-recess p-1 rounded-pill border border-copper-border/60 shadow-inset-recess">
          <button
            type="button"
            onClick={() => setAppMode('KIOSK')}
            className={`px-3 py-1.5 text-caption font-semibold rounded-pill flex items-center gap-1.5 transition-all cursor-pointer ${
              appMode === 'KIOSK'
                ? 'bg-haritaki-gold text-white shadow-pill font-bold'
                : 'text-teak-muted hover:text-teak-grey'
            }`}
          >
            <HeartPulse className="w-3.5 h-3.5" />
            <span>कियोस्क / Kiosk</span>
          </button>
          <button
            type="button"
            onClick={() => setAppMode('DOCTOR')}
            className={`px-3 py-1.5 text-caption font-semibold rounded-pill flex items-center gap-1.5 transition-all cursor-pointer ${
              appMode === 'DOCTOR'
                ? 'bg-haritaki-gold text-white shadow-pill font-bold'
                : 'text-teak-muted hover:text-teak-grey'
            }`}
          >
            <Stethoscope className="w-3.5 h-3.5" />
            <span>डॉक्टर / Doctor</span>
          </button>
          <button
            type="button"
            onClick={() => setAppMode('ANALYTICS')}
            className={`px-3 py-1.5 text-caption font-semibold rounded-pill flex items-center gap-1.5 transition-all cursor-pointer ${
              appMode === 'ANALYTICS'
                ? 'bg-haritaki-gold text-white shadow-pill font-bold'
                : 'text-teak-muted hover:text-teak-grey'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>एनालिटिक्स / Analytics</span>
          </button>
        </div>
      </div>
    </header>
  );
}
