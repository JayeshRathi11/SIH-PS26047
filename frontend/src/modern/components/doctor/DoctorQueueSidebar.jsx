import React, { useState } from 'react';
import { Search, AlertTriangle, Clock, User, ShieldAlert, CheckCircle2 } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayBadge from '../atoms/ClayBadge';

export default function DoctorQueueSidebar({
  queue = [],
  selectedPatientId,
  onSelectPatient,
  className = ''
}) {
  const [filter, setFilter] = useState('ALL'); // 'ALL' | 'RED_FLAG' | 'SENIOR'
  const [searchQuery, setSearchQuery] = useState('');

  const filteredQueue = queue
    .filter((p) => {
      if (filter === 'RED_FLAG') return p.is_red_flag;
      if (filter === 'SENIOR') return p.age >= 65;
      return true;
    })
    .filter((p) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        p.patient_name?.toLowerCase().includes(q) ||
        p.token_number?.toLowerCase().includes(q) ||
        p.chief_complaint?.toLowerCase().includes(q)
      );
    })
    .sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0));

  return (
    <div className={`flex flex-col bg-shweta-white rounded-card border border-copper-border shadow-card overflow-hidden ${className}`}>
      {/* Header & Search */}
      <div className="p-4 bg-topbar-bg border-b border-copper-border/50">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-bold text-btn-sec text-teak-grey">
            ओपीडी कतार • OPD Queue
          </h3>
          <span className="text-xs bg-haritaki-gold/20 text-haritaki-deep font-mono font-bold px-2 py-0.5 rounded-pill">
            {filteredQueue.length} प्रतीक्षा में
          </span>
        </div>

        {/* Search input */}
        <div className="relative flex items-center mb-2">
          <Search className="w-4 h-4 text-copper-patina absolute left-3 pointer-events-none" />
          <input
            type="text"
            placeholder="नाम, टोकन या लक्षण खोजें..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 bg-cream-recess text-teak-grey placeholder:text-teak-muted/60 text-caption rounded-pill pl-9 pr-3 border border-copper-border/60 outline-none focus:border-haritaki-gold shadow-inset-recess"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 pt-1">
          {[
            { id: 'ALL', label: 'सभी / All' },
            { id: 'RED_FLAG', label: '🚨 Red Flag' },
            { id: 'SENIOR', label: 'वरिष्ठ (65+)' }
          ].map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={`px-2.5 py-1 text-[11px] font-bold rounded-pill transition-all cursor-pointer ${
                filter === f.id
                  ? 'bg-haritaki-gold text-white shadow-sm'
                  : 'bg-cream-neutral text-teak-muted border border-copper-border/50 hover:text-teak-grey'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Patient List */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2.5 max-h-[calc(100vh-280px)]">
        {filteredQueue.length === 0 ? (
          <div className="py-8 text-center text-caption text-teak-muted">
            कोई रोगी कतार में नहीं है
          </div>
        ) : (
          filteredQueue.map((item) => {
            const isSelected = selectedPatientId === item.id;
            return (
              <ClayCard
                key={item.id}
                selected={isSelected}
                interactive
                onClick={() => onSelectPatient(item)}
                className={`p-3 transition-all ${
                  item.is_red_flag
                    ? isSelected
                      ? 'border-manjistha-red bg-manjistha-red/10'
                      : 'border-manjistha-red/60 bg-manjistha-red/5'
                    : ''
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-display font-black text-caption text-haritaki-deep font-mono">
                    {item.token_number || `TK-${item.id}`}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {item.is_red_flag && (
                      <span className="text-[10px] font-bold text-white bg-manjistha-red px-2 py-0.5 rounded-pill flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Red Flag
                      </span>
                    )}
                    <span className="text-[11px] font-mono text-teak-muted flex items-center gap-0.5">
                      <Clock className="w-3 h-3" /> {item.wait_time_minutes || 10}m
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-display font-bold text-caption text-teak-grey leading-tight">
                      {item.patient_name}
                    </h4>
                    <span className="text-[11px] text-teak-muted block">
                      {item.age}y &bull; {item.gender}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-teak-muted uppercase block">
                      प्राथमिकता अंक:
                    </span>
                    <strong className="text-caption font-mono text-haritaki-deep">
                      {item.priority_score || 0}
                    </strong>
                  </div>
                </div>

                {item.chief_complaint && (
                  <p className="text-[11px] text-teak-muted/90 mt-1.5 truncate bg-cream-warm/40 px-2 py-0.5 rounded border border-copper-border/30">
                    {item.chief_complaint}
                  </p>
                )}
              </ClayCard>
            );
          })
        )}
      </div>
    </div>
  );
}
