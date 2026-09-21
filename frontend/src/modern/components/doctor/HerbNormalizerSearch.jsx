import React, { useState } from 'react';
import { Search, Plus, Leaf, Sparkles, Check } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function HerbNormalizerSearch({ onSelectHerb }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const mockDatabase = [
    {
      sanskrit: 'सुदर्शन वटी (Sudarshan Vati)',
      botanical: 'Swertia chirata & polyherbal formulation',
      afi_code: 'AFI-Vol-I-23:12',
      namaste_code: 'AYU-NAMASTE-3401',
      dosage: '2 tablets',
      anupana: 'कोष्ण जल (Warm Water)',
      kala: 'भोजनोत्तर (After Food)'
    },
    {
      sanskrit: 'अश्वगंधा चूर्ण (Ashwagandha Churna)',
      botanical: 'Withania somnifera (L.) Dunal',
      afi_code: 'AFI-Vol-I-07:05',
      namaste_code: 'AYU-NAMASTE-1104',
      dosage: '3 grams',
      anupana: 'दुग्ध (Warm Milk)',
      kala: 'रात्रौ (Bedtime)'
    },
    {
      sanskrit: 'त्रिफला क्वाथ (Triphala Kwath)',
      botanical: 'Terminalia chebula, T. bellirica, Phyllanthus emblica',
      afi_code: 'AFI-Vol-I-04:09',
      namaste_code: 'AYU-NAMASTE-0842',
      dosage: '20 ml',
      anupana: 'मधु (Honey)',
      kala: 'प्रातः (Morning)'
    },
    {
      sanskrit: 'योगराज गुग्गुलु (Yograj Guggulu)',
      botanical: 'Commiphora mukul & polyherbal',
      afi_code: 'AFI-Vol-I-05:08',
      namaste_code: 'AYU-NAMASTE-2190',
      dosage: '1 tablet',
      anupana: 'रास्नादि क्वाथ (Rasnadi Kwath)',
      kala: 'भोजनोत्तर (After Food)'
    }
  ];

  const handleSearch = async (val) => {
    setQuery(val);
    if (!val.trim()) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      const res = await MediKioskApi.post('/api/ayush/normalize-herb', { query: val });
      if (res?.data?.matches?.length > 0) {
        setResults(res.data.matches);
        setLoading(false);
        return;
      }
    } catch {
      // Offline fallback
    }

    // Filter local mock database
    const filtered = mockDatabase.filter(
      (m) =>
        m.sanskrit.toLowerCase().includes(val.toLowerCase()) ||
        m.botanical.toLowerCase().includes(val.toLowerCase()) ||
        m.afi_code.toLowerCase().includes(val.toLowerCase())
    );
    setResults(filtered);
    setLoading(false);
  };

  return (
    <div className="flex flex-col gap-2 relative">
      <div className="flex items-center gap-2 mb-1">
        <Leaf className="w-4 h-4 text-herbal-green" />
        <span className="text-caption font-bold text-teak-grey">
          AFI एवं NAMASTE मानकीकृत औषधि खोज (Pharmacopeia Normalizer):
        </span>
      </div>

      <div className="relative flex items-center">
        <Search className="w-4 h-4 text-copper-patina absolute left-3 pointer-events-none" />
        <input
          type="text"
          placeholder="औषधि नाम, AFI कोड या वनस्पति नाम खोजें (e.g. Sudarshan, Ashwagandha)..."
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          className="w-full h-10 bg-shweta-white text-teak-grey text-caption rounded-btn pl-9 pr-4 border border-copper-border focus:border-haritaki-gold outline-none shadow-sm"
        />
        {loading && (
          <span className="absolute right-3 w-4 h-4 border-2 border-haritaki-gold border-t-transparent rounded-full animate-spin" />
        )}
      </div>

      {/* Autocomplete Dropdown */}
      {results.length > 0 && (
        <div className="absolute top-16 left-0 right-0 z-30 bg-shweta-white border-2 border-haritaki-gold rounded-card shadow-2xl p-2 flex flex-col gap-2 max-h-60 overflow-y-auto">
          {results.map((item, idx) => (
            <div
              key={idx}
              onClick={() => {
                onSelectHerb(item);
                setQuery('');
                setResults([]);
              }}
              className="p-2.5 rounded-btn hover:bg-cream-warm/70 transition-all cursor-pointer flex items-center justify-between border border-transparent hover:border-haritaki-gold/40"
            >
              <div>
                <strong className="text-caption font-display text-teak-grey block">
                  {item.sanskrit}
                </strong>
                <span className="text-xs text-teak-muted italic block">
                  {item.botanical}
                </span>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] bg-cream-recess text-teak-muted font-mono px-2 py-0.5 rounded">
                    {item.afi_code}
                  </span>
                  <span className="text-[10px] bg-herbal-green/10 text-herbal-green font-mono px-2 py-0.5 rounded font-bold">
                    {item.namaste_code}
                  </span>
                </div>
              </div>

              <button
                type="button"
                className="w-8 h-8 rounded-full bg-haritaki-gold text-white flex items-center justify-center shadow-sm"
                title="प्रिस्क्रिप्शन में जोड़ें"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
