import React from 'react';

/**
 * Interactive SVG Anatomical Body Map with Claymorphic Tactile Zones
 */
export default function ClayBodyMap({
  selectedZones = [],
  onToggleZone,
  className = ''
}) {
  const zones = [
    { id: 'head', label: 'सिर / Head', x: 100, y: 35, r: 24 },
    { id: 'throat', label: 'गला / Throat', x: 100, y: 72, r: 14 },
    { id: 'chest', label: 'छाती / Chest', x: 100, y: 110, w: 60, h: 40, rx: 12 },
    { id: 'abdomen', label: 'पेट / Abdomen', x: 100, y: 165, w: 56, h: 42, rx: 12 },
    { id: 'back', label: 'पीठ / Spine', x: 220, y: 135, w: 32, h: 70, rx: 10 },
    { id: 'left_arm', label: 'बायां हाथ / Left Arm', x: 50, y: 140, w: 22, h: 70, rx: 10 },
    { id: 'right_arm', label: 'दायां हाथ / Right Arm', x: 150, y: 140, w: 22, h: 70, rx: 10 },
    { id: 'knees', label: 'घुटने व पैर / Legs', x: 100, y: 245, w: 65, h: 80, rx: 14 }
  ];

  const isSelected = (id) => selectedZones.includes(id);

  return (
    <div className={`flex flex-col items-center p-3 bg-cream-warm/30 rounded-card border border-copper-border/60 ${className}`}>
      <span className="text-caption font-bold text-teak-grey mb-2 select-none">
        शरीर का प्रभावित भाग स्पर्श करें • Tap Affected Region
      </span>

      <svg viewBox="0 0 270 340" className="w-full max-w-[240px] h-auto select-none">
        {/* Soft Body Silhouette Outline */}
        <path
          d="M 100,10 C 115,10 125,25 125,40 C 125,55 118,65 112,70 C 135,78 155,90 160,115 L 180,180 C 185,195 175,205 165,195 L 145,150 L 140,210 L 145,310 C 145,325 130,325 125,310 L 115,225 L 100,225 L 85,325 C 80,325 65,325 65,310 L 70,210 L 65,150 L 45,195 C 35,205 25,195 30,180 L 50,115 C 55,90 75,78 98,70 C 92,65 85,55 85,40 C 85,25 95,10 100,10 Z"
          fill="#EDE5D3"
          stroke="#C8922A"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />

        {/* Head */}
        <circle
          cx="100"
          cy="38"
          r="24"
          onClick={() => onToggleZone('head')}
          className={`cursor-pointer transition-all ${
            isSelected('head')
              ? 'fill-haritaki-gold stroke-white stroke-2 filter drop-shadow'
              : 'fill-shweta-white/80 hover:fill-cream-warm stroke-copper-patina'
          }`}
        />
        <text x="100" y="42" textAnchor="middle" fontSize="10" fontWeight="bold" fill={isSelected('head') ? '#fff' : '#2C2520'} pointerEvents="none">
          सिर
        </text>

        {/* Throat */}
        <ellipse
          cx="100"
          cy="74"
          rx="18"
          ry="10"
          onClick={() => onToggleZone('throat')}
          className={`cursor-pointer transition-all ${
            isSelected('throat')
              ? 'fill-haritaki-gold stroke-white stroke-2'
              : 'fill-shweta-white/80 hover:fill-cream-warm stroke-copper-patina'
          }`}
        />
        <text x="100" y="77" textAnchor="middle" fontSize="9" fontWeight="bold" fill={isSelected('throat') ? '#fff' : '#2C2520'} pointerEvents="none">
          गला
        </text>

        {/* Chest */}
        <rect
          x="72"
          y="92"
          width="56"
          height="42"
          rx="10"
          onClick={() => onToggleZone('chest')}
          className={`cursor-pointer transition-all ${
            isSelected('chest')
              ? 'fill-haritaki-gold stroke-white stroke-2'
              : 'fill-shweta-white/80 hover:fill-cream-warm stroke-copper-patina'
          }`}
        />
        <text x="100" y="117" textAnchor="middle" fontSize="11" fontWeight="bold" fill={isSelected('chest') ? '#fff' : '#2C2520'} pointerEvents="none">
          छाती
        </text>

        {/* Abdomen */}
        <rect
          x="75"
          y="142"
          width="50"
          height="45"
          rx="10"
          onClick={() => onToggleZone('abdomen')}
          className={`cursor-pointer transition-all ${
            isSelected('abdomen')
              ? 'fill-haritaki-gold stroke-white stroke-2'
              : 'fill-shweta-white/80 hover:fill-cream-warm stroke-copper-patina'
          }`}
        />
        <text x="100" y="169" textAnchor="middle" fontSize="11" fontWeight="bold" fill={isSelected('abdomen') ? '#fff' : '#2C2520'} pointerEvents="none">
          पेट
        </text>

        {/* Knees & Legs */}
        <rect
          x="68"
          y="205"
          width="64"
          height="100"
          rx="14"
          onClick={() => onToggleZone('knees')}
          className={`cursor-pointer transition-all ${
            isSelected('knees')
              ? 'fill-haritaki-gold stroke-white stroke-2'
              : 'fill-shweta-white/80 hover:fill-cream-warm stroke-copper-patina'
          }`}
        />
        <text x="100" y="255" textAnchor="middle" fontSize="11" fontWeight="bold" fill={isSelected('knees') ? '#fff' : '#2C2520'} pointerEvents="none">
          पैर / जोड़
        </text>

        {/* Spine / Back indicator on side */}
        <g onClick={() => onToggleZone('back')} className="cursor-pointer">
          <rect
            x="200"
            y="95"
            width="44"
            height="100"
            rx="12"
            className={`transition-all ${
              isSelected('back')
                ? 'fill-haritaki-gold stroke-white stroke-2'
                : 'fill-cream-neutral stroke-copper-patina'
            }`}
          />
          <text x="222" y="150" textAnchor="middle" fontSize="11" fontWeight="bold" fill={isSelected('back') ? '#fff' : '#2C2520'} pointerEvents="none">
            पीठ
          </text>
        </g>
      </svg>
    </div>
  );
}
