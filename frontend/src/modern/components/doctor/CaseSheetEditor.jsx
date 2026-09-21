import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2, ShieldCheck, Stethoscope, Leaf, Pill } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayInput from '../atoms/ClayInput';
import ClayBadge from '../atoms/ClayBadge';
import HerbNormalizerSearch from './HerbNormalizerSearch';

export default function CaseSheetEditor({ patient, onSave }) {
  const [openSections, setOpenSections] = useState({
    complaints: true,
    hpi: true,
    pariksha: false,
    pastHistory: false,
    medications: true,
    allergies: false,
    diagnosis: true,
    treatment: true
  });

  const [chiefComplaints, setChiefComplaints] = useState(
    patient?.chief_complaint || 'ज्वर (Fever), संधि शूल (Joint Pain), अग्निमांद्य (Loss of Appetite)'
  );
  const [hpi, setHpi] = useState(
    'रोगी विगत 4 दिनों से अनियमित ज्वर एवं घुटनों में शूल की शिकायत कर रहे हैं। शीत लगना एवं भारीपन उपस्थित।'
  );
  const [pastHistory, setPastHistory] = useState('कोई पूर्व शल्यक्रिया नहीं। उच्च रक्तचाप (3 वर्ष से नियंत्रित)।');
  const [allergies, setAllergies] = useState('कोई ज्ञात औषधि एलर्जी नहीं (NKDA)।');
  const [diagnosis, setDiagnosis] = useState('वात-कफज ज्वर (Vata-Kaphaja Jvara) एवं आमवात (Amavata)');

  const [prescriptions, setPrescriptions] = useState([
    {
      name: 'सुदर्शन वटी (Sudarshan Vati)',
      dosage: '2 tablets',
      freq: 'दिन में 2 बार (Twice daily)',
      anupana: 'कोष्ण जल (Warm water)',
      kala: 'भोजनोत्तर (After food)',
      duration: '5 दिन'
    },
    {
      name: 'अश्वगंधा चूर्ण (Ashwagandha Churna)',
      dosage: '3 ग्राम',
      freq: 'रात्रि में (At bedtime)',
      anupana: 'कोष्ण दुग्ध (Warm milk)',
      kala: 'शयन पूर्व',
      duration: '15 दिन'
    }
  ]);

  const toggleSection = (key) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleAddHerb = (herb) => {
    setPrescriptions((prev) => [
      ...prev,
      {
        name: herb.sanskrit,
        dosage: herb.dosage || '1 dose',
        freq: 'दिन में 2 बार',
        anupana: herb.anupana || 'जल',
        kala: herb.kala || 'भोजनोत्तर',
        duration: '7 दिन'
      }
    ]);
  };

  const handleRemovePrescription = (idx) => {
    setPrescriptions((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Section 1: Chief Complaints */}
      <ClayCard className="p-4">
        <div
          onClick={() => toggleSection('complaints')}
          className="flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep font-bold text-xs flex items-center justify-center">
              1
            </span>
            <h4 className="font-display font-bold text-btn-sec text-teak-grey">
              प्रधान लक्षण • Chief Complaints
            </h4>
          </div>
          {openSections.complaints ? <ChevronUp className="w-5 h-5 text-copper-patina" /> : <ChevronDown className="w-5 h-5 text-copper-patina" />}
        </div>
        {openSections.complaints && (
          <div className="mt-3 pt-3 border-t border-copper-border/40">
            <textarea
              rows={2}
              value={chiefComplaints}
              onChange={(e) => setChiefComplaints(e.target.value)}
              className="w-full bg-cream-recess text-teak-grey text-caption p-3 rounded-btn border border-copper-border outline-none focus:border-haritaki-gold shadow-inset-recess"
            />
          </div>
        )}
      </ClayCard>

      {/* Section 2: History of Present Illness (HPI) */}
      <ClayCard className="p-4">
        <div
          onClick={() => toggleSection('hpi')}
          className="flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep font-bold text-xs flex items-center justify-center">
              2
            </span>
            <h4 className="font-display font-bold text-btn-sec text-teak-grey">
              वर्तमान व्याधि इतिहास • History of Present Illness (HPI)
            </h4>
          </div>
          {openSections.hpi ? <ChevronUp className="w-5 h-5 text-copper-patina" /> : <ChevronDown className="w-5 h-5 text-copper-patina" />}
        </div>
        {openSections.hpi && (
          <div className="mt-3 pt-3 border-t border-copper-border/40">
            <textarea
              rows={3}
              value={hpi}
              onChange={(e) => setHpi(e.target.value)}
              className="w-full bg-cream-recess text-teak-grey text-caption p-3 rounded-btn border border-copper-border outline-none focus:border-haritaki-gold shadow-inset-recess"
            />
          </div>
        )}
      </ClayCard>

      {/* Section 3: Ashtavidha Pariksha Summary */}
      <ClayCard className="p-4">
        <div
          onClick={() => toggleSection('pariksha')}
          className="flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep font-bold text-xs flex items-center justify-center">
              3
            </span>
            <h4 className="font-display font-bold text-btn-sec text-teak-grey">
              अष्टविध परीक्षा निष्कर्ष • Ashtavidha Pariksha Findings
            </h4>
          </div>
          {openSections.pariksha ? <ChevronUp className="w-5 h-5 text-copper-patina" /> : <ChevronDown className="w-5 h-5 text-copper-patina" />}
        </div>
        {openSections.pariksha && (
          <div className="mt-3 pt-3 border-t border-copper-border/40 grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
            <div className="bg-cream-recess p-2 rounded-btn"><strong>नाड़ी:</strong> वात-पित्तज (चपला)</div>
            <div className="bg-cream-recess p-2 rounded-btn"><strong>जिह्वा:</strong> साम (हल्की लेपयुक्त)</div>
            <div className="bg-cream-recess p-2 rounded-btn"><strong>मल:</strong> बद्ध (कब्ज)</div>
            <div className="bg-cream-recess p-2 rounded-btn"><strong>मूत्र:</strong> प्राकृत (Clear)</div>
            <div className="bg-cream-recess p-2 rounded-btn"><strong>शब्द:</strong> स्पष्ट (Normal)</div>
            <div className="bg-cream-recess p-2 rounded-btn"><strong>स्पर्श:</strong> उष्ण (हल्का गर्म)</div>
            <div className="bg-cream-recess p-2 rounded-btn"><strong>दृक्:</strong> प्राकृत</div>
            <div className="bg-cream-recess p-2 rounded-btn"><strong>आकृति:</strong> मध्यम</div>
          </div>
        )}
      </ClayCard>

      {/* Section 4: Ayurvedic Diagnosis */}
      <ClayCard className="p-4">
        <div
          onClick={() => toggleSection('diagnosis')}
          className="flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep font-bold text-xs flex items-center justify-center">
              4
            </span>
            <h4 className="font-display font-bold text-btn-sec text-teak-grey">
              आयुर्वेदिक निदान • Ayurvedic Diagnosis (Roganidan)
            </h4>
          </div>
          {openSections.diagnosis ? <ChevronUp className="w-5 h-5 text-copper-patina" /> : <ChevronDown className="w-5 h-5 text-copper-patina" />}
        </div>
        {openSections.diagnosis && (
          <div className="mt-3 pt-3 border-t border-copper-border/40">
            <ClayInput
              label="दोष-दूष्य सम्मूर्च्छना / Vyadhi"
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
            />
          </div>
        )}
      </ClayCard>

      {/* Section 5: Chikitsa Sutra & Prescription Pad */}
      <ClayCard className="p-4">
        <div
          onClick={() => toggleSection('treatment')}
          className="flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep font-bold text-xs flex items-center justify-center">
              5
            </span>
            <h4 className="font-display font-bold text-btn-sec text-teak-grey">
              चिकित्सा सूत्र एवं औषधि पर्ची • Treatment &amp; Prescriptions
            </h4>
          </div>
          {openSections.treatment ? <ChevronUp className="w-5 h-5 text-copper-patina" /> : <ChevronDown className="w-5 h-5 text-copper-patina" />}
        </div>

        {openSections.treatment && (
          <div className="mt-3 pt-3 border-t border-copper-border/40 flex flex-col gap-4">
            {/* Live Herb Normalizer Search Component */}
            <HerbNormalizerSearch onSelectHerb={handleAddHerb} />

            {/* Prescribed Items Table */}
            <div className="flex flex-col gap-2 mt-2">
              <span className="text-xs font-bold text-haritaki-deep uppercase tracking-wider">
                पर्चे में शामिल औषधियां ({prescriptions.length}):
              </span>

              {prescriptions.map((p, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-cream-warm/50 rounded-btn border border-haritaki-gold/40 flex items-center justify-between text-caption"
                >
                  <div>
                    <strong className="font-display font-bold text-teak-grey block">
                      {p.name}
                    </strong>
                    <span className="text-xs text-teak-muted">
                      {p.dosage} &bull; {p.freq} &bull; अनुपान: {p.anupana} &bull; काल: {p.kala} &bull; {p.duration}
                    </span>
                  </div>

                  <button
                    type="button"
                    aria-label={`Remove prescription ${p.name}`}
                    onClick={() => handleRemovePrescription(idx)}
                    className="text-copper-patina hover:text-manjistha-red p-1 rounded transition-all cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </ClayCard>
    </div>
  );
}
