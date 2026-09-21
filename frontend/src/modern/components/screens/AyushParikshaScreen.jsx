import React, { useState } from 'react';
import { Sparkles, Check, Info } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import { AshtavidhaIcons } from '../atoms/AyushIcons';

export default function AyushParikshaScreen({ onProceedDocs }) {
  const { interview, updateInterview } = useKioskSession();

  const [prakriti, setPrakriti] = useState(interview.pariksha?.prakriti || 'Vata-Pitta');
  const [agni, setAgni] = useState(interview.pariksha?.agni || 'Samagni');
  const [koshtha, setKoshtha] = useState(interview.pariksha?.koshtha || 'Madhyama');
  const [selectedPariksha, setSelectedPariksha] = useState(interview.pariksha || {});

  const handleUpdatePariksha = (field, value) => {
    const next = { ...selectedPariksha, [field]: value };
    setSelectedPariksha(next);
    updateInterview({ pariksha: next });
  };

  const parikshaItems = [
    { key: 'nadi', label: 'नाड़ी (Nadi / Pulse)', icon: AshtavidhaIcons.nadi, options: ['Vata (Chala)', 'Pitta (Vegavat)', 'Kapha (Manda)', 'Normal'] },
    { key: 'jihva', label: 'जिह्वा (Jihva / Tongue)', icon: AshtavidhaIcons.jihva, options: ['Niram (Clean)', 'Saam (Coated)', 'Ruksha (Dry)', 'Rakta (Red)'] },
    { key: 'mala', label: 'मल (Mala / Bowel)', icon: AshtavidhaIcons.mala, options: ['Normal', 'Baddha (Constipated)', 'Drava (Loose)', 'Saam'] },
    { key: 'mutra', label: 'मूत्र (Mutra / Urine)', icon: AshtavidhaIcons.mutra, options: ['Prakrita (Clear)', 'Peeta (Yellow)', 'Daha (Burning)', 'Alpa'] },
    { key: 'shabda', label: 'शब्द (Shabda / Voice)', icon: AshtavidhaIcons.shabda, options: ['Spashta (Clear)', 'Guru (Heavy)', 'Ksheena (Weak)', 'Khasa'] },
    { key: 'sparsha', label: 'स्पर्श (Sparsha / Skin)', icon: AshtavidhaIcons.sparsha, options: ['Sheeta (Cold)', 'Ushna (Warm)', 'Ruksha (Rough)', 'Snigdha'] },
    { key: 'drik', label: 'दृक् (Drik / Eyes)', icon: AshtavidhaIcons.drik, options: ['Prakrita (Normal)', 'Peeta (Yellow)', 'Rakta (Red)', 'Shushka'] },
    { key: 'akriti', label: 'आकृति (Akriti / Physique)', icon: AshtavidhaIcons.akriti, options: ['Madhyama (Medium)', 'Krisha (Lean)', 'Sthoola (Heavy)'] }
  ];

  return (
    <div className="flex-1 flex flex-col max-w-5xl mx-auto w-full py-2">
      {/* Title */}
      <div className="text-center mb-6">
        <ClayBadge variant="ayush" className="mb-2">
          चरण 3 • Step 3: आयुष परीक्षण
        </ClayBadge>
        <h2 className="font-display font-extrabold text-heading sm:text-title text-teak-grey">
          अष्टविध परीक्षा एवं प्रकृति विवरण • AYUSH Assessment
        </h2>
        <p className="text-caption text-teak-muted max-w-lg mx-auto">
          आयुर्वेदिक निदान हेतु अपनी शारीरिक प्रकृति एवं सामान्य स्वास्थ्य संकेतकों का चयन करें।
        </p>
      </div>

      {/* Prakriti & Agni Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Prakriti Card */}
        <ClayCard className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey">
              दोष प्रकृति • Body Constitution (Prakriti)
            </h3>
            <ClayBadge variant="ayush">त्रिदोष</ClayBadge>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: 'Vata', labelHi: 'वात', labelEn: 'Vata (Air)' },
              { id: 'Pitta', labelHi: 'पित्त', labelEn: 'Pitta (Fire)' },
              { id: 'Kapha', labelHi: 'कफ', labelEn: 'Kapha (Earth)' },
              { id: 'Vata-Pitta', labelHi: 'वात-पित्त', labelEn: 'Vata-Pitta' },
              { id: 'Pitta-Kapha', labelHi: 'पित्त-कफ', labelEn: 'Pitta-Kapha' },
              { id: 'Tridoshaja', labelHi: 'सन्निपातज', labelEn: 'Tridoshaja' }
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setPrakriti(p.id);
                  handleUpdatePariksha('prakriti', p.id);
                }}
                className={`py-2 px-2 rounded-btn font-display font-bold text-caption flex flex-col items-center justify-center transition-all border cursor-pointer ${
                  prakriti === p.id
                    ? 'bg-cream-warm border-haritaki-gold text-haritaki-deep shadow-btn-gold'
                    : 'bg-cream-neutral border-copper-border text-teak-muted'
                }`}
              >
                <span>{p.labelHi}</span>
                <span className="text-[10px] font-normal">{p.labelEn}</span>
              </button>
            ))}
          </div>
        </ClayCard>

        {/* Agni & Koshtha Card */}
        <ClayCard className="p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey">
              अग्नि एवं कोष्ठ • Digestion &amp; Bowel Pattern
            </h3>
            <ClayBadge variant="ayush">अग्नि</ClayBadge>
          </div>

          <div className="flex flex-col gap-3">
            <div>
              <span className="text-xs font-semibold text-teak-muted block mb-1.5">
                जठराग्नि (Digestive Fire):
              </span>
              <div className="grid grid-cols-4 gap-1.5">
                {[
                  { id: 'Samagni', label: 'समाग्नि (Balanced)' },
                  { id: 'Vishamagni', label: 'विषमाग्नि (Irregular)' },
                  { id: 'Tikshnagni', label: 'तीक्ष्णाग्नि (Intense)' },
                  { id: 'Mandagni', label: 'मन्दाग्नि (Slow)' }
                ].map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => {
                      setAgni(a.id);
                      handleUpdatePariksha('agni', a.id);
                    }}
                    className={`py-1.5 px-1 rounded-btn text-[11px] font-bold border transition-all cursor-pointer text-center ${
                      agni === a.id
                        ? 'bg-cream-warm border-haritaki-gold text-haritaki-deep shadow-sm'
                        : 'bg-cream-neutral border-copper-border text-teak-muted'
                    }`}
                  >
                    {a.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <span className="text-xs font-semibold text-teak-muted block mb-1.5">
                कोष्ठ (Bowel Pattern):
              </span>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'Mridu', label: 'मृदु (Soft/Loose)' },
                  { id: 'Madhyama', label: 'मध्यम (Regular)' },
                  { id: 'Krura', label: 'क्रूर (Hard/Dry)' }
                ].map((k) => (
                  <button
                    key={k.id}
                    type="button"
                    onClick={() => {
                      setKoshtha(k.id);
                      handleUpdatePariksha('koshtha', k.id);
                    }}
                    className={`py-1.5 px-2 rounded-btn text-xs font-bold border transition-all cursor-pointer text-center ${
                      koshtha === k.id
                        ? 'bg-cream-warm border-haritaki-gold text-haritaki-deep shadow-sm'
                        : 'bg-cream-neutral border-copper-border text-teak-muted'
                    }`}
                  >
                    {k.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </ClayCard>
      </div>

      {/* Ashtavidha Pariksha 8 Grid Cards */}
      <div className="mb-6">
        <h3 className="font-display font-bold text-heading text-teak-grey mb-3">
          अष्टविध परीक्षा घटक • Ashtavidha Pariksha Matrix
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {parikshaItems.map((item) => {
            const IconComponent = item.icon;
            const currentVal = selectedPariksha[item.key] || item.options[0];

            return (
              <ClayCard key={item.key} className="p-3.5 flex flex-col justify-between">
                <div className="flex items-center gap-2.5 mb-2.5">
                  <div className="w-8 h-8 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep flex items-center justify-center flex-shrink-0">
                    <IconComponent className="w-4 h-4" />
                  </div>
                  <span className="text-caption font-bold text-teak-grey leading-tight">
                    {item.label}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-1.5">
                  {item.options.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => handleUpdatePariksha(item.key, opt)}
                      className={`py-1 px-1 rounded-sm text-[10px] font-bold border truncate transition-all cursor-pointer ${
                        currentVal === opt
                          ? 'bg-cream-warm border-haritaki-gold text-haritaki-deep shadow-sm'
                          : 'bg-shweta-white border-copper-border text-teak-muted hover:text-teak-grey'
                      }`}
                      title={opt}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </ClayCard>
            );
          })}
        </div>
      </div>
    </div>
  );
}
