import React, { useState } from 'react';
import { RotateCw, CheckCircle2 } from 'lucide-react';

/**
 * 2D Interactive Anatomical Body Map Selector
 * Allows patients (especially high-friction/elderly/illiterate) to tap where they feel pain or discomfort.
 */

const ANTERIOR_ZONES = [
  { id: 'HEAD', label: 'Head / Face', hindi: 'सिर / चेहरा', x: 100, y: 35, r: 24 },
  { id: 'NECK', label: 'Throat / Neck', hindi: 'गला / गर्दन', x: 100, y: 72, w: 24, h: 14 },
  { id: 'CHEST', label: 'Chest / Heart', hindi: 'छाती / हृदय', x: 100, y: 105, w: 56, h: 42 },
  { id: 'EPIGASTRIC', label: 'Upper Stomach / Acidity', hindi: 'वरचे पोट / जळजळ', x: 100, y: 145, w: 46, h: 26 },
  { id: 'ABDOMEN', label: 'Lower Abdomen / Bowel', hindi: 'खालचे पोट / पचन', x: 100, y: 180, w: 50, h: 36 },
  { id: 'PELVIS', label: 'Pelvis / Groin', hindi: 'कमर / मूत्राशय', x: 100, y: 220, w: 46, h: 26 },
  { id: 'RIGHT_ARM', label: 'Right Arm', hindi: 'उजवा हात', x: 50, y: 140, w: 28, h: 90 },
  { id: 'LEFT_ARM', label: 'Left Arm', hindi: 'डावा हात', x: 150, y: 140, w: 28, h: 90 },
  { id: 'RIGHT_LEG', label: 'Right Leg / Knee', hindi: 'उजवा पाय / गुडघा', x: 78, y: 290, w: 32, h: 110 },
  { id: 'LEFT_LEG', label: 'Left Leg / Knee', hindi: 'डावा पाय / गुडघा', x: 122, y: 290, w: 32, h: 110 },
];

const POSTERIOR_ZONES = [
  { id: 'HEAD_BACK', label: 'Back of Head', hindi: 'डोक्याची मागची बाजू', x: 100, y: 35, r: 24 },
  { id: 'NECK_BACK', label: 'Cervical / Neck', hindi: 'मानेचा मागचा भाग', x: 100, y: 72, w: 24, h: 14 },
  { id: 'UPPER_BACK', label: 'Upper Back / Shoulders', hindi: 'पाठीचा वरचा भाग', x: 100, y: 115, w: 60, h: 48 },
  { id: 'LOWER_BACK', label: 'Lower Back / Lumbar', hindi: 'कंबर / पाठीचा खालचा भाग', x: 100, y: 175, w: 54, h: 44 },
  { id: 'GLUTES', label: 'Hips / Glutes', hindi: 'खुबा / नितंब', x: 100, y: 225, w: 52, h: 32 },
  { id: 'RIGHT_ARM', label: 'Right Arm (Back)', hindi: 'उजवा हात (मागे)', x: 50, y: 140, w: 28, h: 90 },
  { id: 'LEFT_ARM', label: 'Left Arm (Back)', hindi: 'डावा हात (मागे)', x: 150, y: 140, w: 28, h: 90 },
  { id: 'RIGHT_LEG_BACK', label: 'Right Leg / Calf', hindi: 'उजवा पाय (मागे)', x: 78, y: 290, w: 32, h: 110 },
  { id: 'LEFT_LEG_BACK', label: 'Left Leg / Calf', hindi: 'डावा पाय (मागे)', x: 122, y: 290, w: 32, h: 110 },
];

export default function BodyMapPicker({
  selectedZone = null,
  onSelectZone = () => {},
  language = 'hi',
}) {
  const [view, setView] = useState('ANTERIOR'); // 'ANTERIOR' | 'POSTERIOR'
  const zones = view === 'ANTERIOR' ? ANTERIOR_ZONES : POSTERIOR_ZONES;

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-stone-200 flex flex-col items-center w-full max-w-md mx-auto">
      <div className="flex items-center justify-between w-full mb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-800">
            {language === 'mr' ? 'त्रास कुठे होत आहे? (शरीराचा भाग निवडा)' : (language === 'hi' ? 'दर्द / तकलीफ कहाँ है? (शरीर पर छुएँ)' : 'Where does it hurt? (Tap body zone)')}
          </h3>
          <p className="text-xs text-slate-500">
            {view === 'ANTERIOR' ? 'Front View (समोरासमोर)' : 'Back View (पाठीमागे)'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setView(v => v === 'ANTERIOR' ? 'POSTERIOR' : 'ANTERIOR')}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-ayush-primary bg-emerald-50 hover:bg-emerald-100 rounded-xl border border-emerald-200 transition-colors"
        >
          <RotateCw className="w-3.5 h-3.5" />
          {view === 'ANTERIOR' ? 'Turn to Back' : 'Turn to Front'}
        </button>
      </div>

      {/* SVG Interactive Anatomical Figure */}
      <div className="relative w-64 h-[380px] bg-stone-50 rounded-2xl border border-stone-200 flex items-center justify-center p-2">
        <svg viewBox="0 0 200 420" className="w-full h-full select-none">
          {/* Base Anatomical Silhouette */}
          <g className="fill-stone-200 stroke-stone-300 stroke-2">
            {/* Head */}
            <circle cx="100" cy="35" r="24" />
            {/* Neck */}
            <rect x="88" y="59" width="24" height="15" rx="4" />
            {/* Torso */}
            <path d="M 65 74 L 135 74 L 126 230 L 74 230 Z" rx="10" />
            {/* Left Arm */}
            <rect x="138" y="76" width="24" height="130" rx="12" />
            {/* Right Arm */}
            <rect x="38" y="76" width="24" height="130" rx="12" />
            {/* Left Leg */}
            <rect x="105" y="230" width="30" height="175" rx="14" />
            {/* Right Leg */}
            <rect x="65" y="230" width="30" height="175" rx="14" />
          </g>

          {/* Interactive Clickable Hotspots */}
          {zones.map((z) => {
            const isSelected = selectedZone === z.id;
            return (
              <g
                key={z.id}
                onClick={() => onSelectZone(z.id, z.label)}
                className="cursor-pointer transition-all duration-200"
              >
                {z.r ? (
                  <circle
                    cx={z.x}
                    cy={z.y}
                    r={z.r}
                    className={`transition-colors ${
                      isSelected
                        ? 'fill-amber-400/80 stroke-amber-600 stroke-2'
                        : 'fill-emerald-600/20 hover:fill-emerald-500/40 stroke-emerald-600/60'
                    }`}
                  />
                ) : (
                  <rect
                    x={z.x - z.w / 2}
                    y={z.y - z.h / 2}
                    width={z.w}
                    height={z.h}
                    rx="8"
                    className={`transition-colors ${
                      isSelected
                        ? 'fill-amber-400/80 stroke-amber-600 stroke-2'
                        : 'fill-emerald-600/20 hover:fill-emerald-500/40 stroke-emerald-600/60'
                    }`}
                  />
                )}
                {isSelected && (
                  <circle
                    cx={z.x}
                    cy={z.y}
                    r="5"
                    className="fill-amber-700 animate-pulse"
                  />
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Selected Zone Confirmation Display */}
      <div className="w-full mt-4 p-3 bg-stone-50 rounded-xl border border-stone-200 text-center">
        {selectedZone ? (
          <div className="flex items-center justify-center gap-2 text-ayush-primary font-bold text-sm">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>
              {zones.find(z => z.id === selectedZone)?.label || selectedZone}
              {' — '}
              <span className="text-xs text-slate-600">
                {zones.find(z => z.id === selectedZone)?.hindi || ''}
              </span>
            </span>
          </div>
        ) : (
          <span className="text-xs text-slate-400 font-medium">
            शरीरावरील दुखणाऱ्या भागावर स्पर्श करा (Tap painful area on figure)
          </span>
        )}
      </div>
    </div>
  );
}
