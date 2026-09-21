import React, { useState, useEffect } from 'react';
import AppLegacy from './legacy/AppLegacy';
import ModernApp from './modern/ModernApp';

export default function App() {
  const [uiVersion, setUiVersion] = useState(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const queryUi = params.get('ui');
      if (queryUi === 'legacy') return 'LEGACY';
      if (queryUi === 'modern') return 'MODERN';

      const saved = localStorage.getItem('MEDIKIOSK_UI_VERSION');
      if (saved === 'LEGACY') return 'LEGACY';
    }
    return 'MODERN';
  });

  const toggleVersion = (version) => {
    setUiVersion(version);
    try {
      localStorage.setItem('MEDIKIOSK_UI_VERSION', version);
      const url = new URL(window.location.href);
      url.searchParams.set('ui', version.toLowerCase());
      window.history.replaceState({}, '', url.toString());
    } catch (e) {
      // ignore
    }
  };

  return (
    <div className="relative min-h-screen">
      {uiVersion === 'LEGACY' ? <AppLegacy /> : <ModernApp />}

      {/* Floating UI Version Switcher / Emergency Rollback Badge */}
      <aside aria-label="Developer switcher" className="fixed bottom-3 right-3 z-50 flex items-center gap-1.5 bg-stone-900/90 text-white text-[11px] px-3 py-1.5 rounded-full shadow-lg border border-stone-700 backdrop-blur">
        <span className="font-mono text-stone-400">UI:</span>
        <button
          type="button"
          onClick={() => toggleVersion('MODERN')}
          className={`px-2 py-0.5 rounded font-semibold transition-all ${
            uiVersion === 'MODERN'
              ? 'bg-amber-600 text-white shadow-sm'
              : 'text-stone-400 hover:text-white'
          }`}
        >
          Modern (Clay)
        </button>
        <span className="text-stone-600">|</span>
        <button
          type="button"
          onClick={() => toggleVersion('LEGACY')}
          className={`px-2 py-0.5 rounded font-semibold transition-all ${
            uiVersion === 'LEGACY'
              ? 'bg-emerald-700 text-white shadow-sm'
              : 'text-stone-400 hover:text-white'
          }`}
        >
          Legacy
        </button>
      </aside>
    </div>
  );
}
