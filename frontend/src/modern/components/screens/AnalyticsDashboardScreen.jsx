import React, { useState, useEffect } from 'react';
import { BarChart3, Users, Clock, AlertTriangle, CheckCircle2, TrendingUp, Download, RefreshCw } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function AnalyticsDashboardScreen() {
  const [metrics, setMetrics] = useState({
    totalPatientsToday: 248,
    avgWaitTimeMinutes: 14.2,
    redFlagCases: 18,
    ocrAccuracyRate: '97.4%',
    deptDistribution: [
      { name: 'कायचिकित्सा (Kayachikitsa)', count: 104, pct: 42 },
      { name: 'पंचकर्म (Panchakarma)', count: 52, pct: 21 },
      { name: 'शल्य तंत्र (Shalya)', count: 38, pct: 15 },
      { name: 'कौमारभृत्य (Pediatrics)', count: 32, pct: 13 },
      { name: 'शालाक्य (ENT & Eye)', count: 22, pct: 9 }
    ],
    symptomDistribution: [
      { name: 'ज्वर / Fever', count: 78 },
      { name: 'संधि शूल / Joint Pain', count: 64 },
      { name: 'कास / Cough', count: 52 },
      { name: 'अम्लपित्त / Acidity', count: 46 },
      { name: 'श्वास कष्ट / Breathlessness', count: 18 }
    ],
    auditAccuracy: {
      validAlerts: 15,
      falseAlarms: 3,
      precision: '83.3%'
    }
  });

  useEffect(() => {
    MediKioskApi.get('/api/analytics/overview')
      .then((res) => {
        if (res?.data) {
          setMetrics((prev) => ({ ...prev, ...res.data }));
        }
      })
      .catch(() => {});
  }, []);

  return (
    <div className="flex-1 flex flex-col max-w-7xl mx-auto w-full py-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <ClayBadge variant="ayush" className="mb-1">
            अस्पताल टेलीमेट्री • Real-time Telemetry
          </ClayBadge>
          <h2 className="font-display font-extrabold text-heading sm:text-title text-teak-grey">
            ओपीडी विश्लेषिकी एवं क्लिनिकल डैशबोर्ड • Analytics Dashboard
          </h2>
          <p className="text-caption text-teak-muted">
            All India Institute of Ayurveda — OPD Footfall &amp; AI Triage Metrics
          </p>
        </div>

        <ClayButton
          variant="neutral"
          size="sm"
          onClick={() => window.print()}
          icon={<Download className="w-4 h-4" />}
        >
          रिपोर्ट डाउनलोड / Export Report
        </ClayButton>
      </div>

      {/* 4 Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <ClayCard className="p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep flex items-center justify-center font-bold">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-teak-muted block font-semibold">आज कुल पंजीकरण / Total Footfall</span>
            <strong className="font-display font-black text-title text-teak-grey">
              {metrics.totalPatientsToday}
            </strong>
          </div>
        </ClayCard>

        <ClayCard className="p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-herbal-green/10 border border-herbal-green/30 text-herbal-green flex items-center justify-center font-bold">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-teak-muted block font-semibold">औसत प्रतीक्षा / Avg. Wait Time</span>
            <strong className="font-display font-black text-title text-herbal-green">
              {metrics.avgWaitTimeMinutes}m
            </strong>
          </div>
        </ClayCard>

        <ClayCard className="p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-manjistha-red/10 border border-manjistha-red/30 text-manjistha-red flex items-center justify-center font-bold">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-teak-muted block font-semibold">रेड फ्लैग मामले / Red Flags</span>
            <strong className="font-display font-black text-title text-manjistha-red">
              {metrics.redFlagCases}
            </strong>
          </div>
        </ClayCard>

        <ClayCard className="p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep flex items-center justify-center font-bold">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-teak-muted block font-semibold">सर्वम ओसीआर सटीकता / OCR Acc.</span>
            <strong className="font-display font-black text-title text-haritaki-deep">
              {metrics.ocrAccuracyRate}
            </strong>
          </div>
        </ClayCard>
      </div>

      {/* Middle Row: Department Distribution + Symptom Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        {/* Department Distribution */}
        <div className="lg:col-span-6">
          <ClayCard className="p-5 flex flex-col gap-4">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey border-b border-copper-border/40 pb-2">
              विभागवार रोगी विभाजन • Department Distribution
            </h3>
            <div className="flex flex-col gap-3">
              {metrics.deptDistribution.map((dept, idx) => (
                <div key={idx} className="flex flex-col gap-1">
                  <div className="flex justify-between text-xs font-semibold text-teak-grey">
                    <span>{dept.name}</span>
                    <span className="font-mono text-haritaki-deep">{dept.count} ({dept.pct}%)</span>
                  </div>
                  <div className="w-full h-2.5 bg-cream-recess rounded-full overflow-hidden border border-copper-border/40">
                    <div
                      className="h-full bg-gradient-to-r from-[#D49E34] to-[#BE8722] rounded-full"
                      style={{ width: `${dept.pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </ClayCard>
        </div>

        {/* Symptom Heatmap */}
        <div className="lg:col-span-6">
          <ClayCard className="p-5 flex flex-col gap-4">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey border-b border-copper-border/40 pb-2">
              मुख्य लक्षण आवृत्ति • Chief Complaint Frequency
            </h3>
            <div className="flex flex-col gap-3">
              {metrics.symptomDistribution.map((sym, idx) => (
                <div key={idx} className="flex items-center justify-between p-2.5 bg-cream-warm/40 rounded-btn border border-copper-border/40 text-caption">
                  <span className="font-display font-bold text-teak-grey">{sym.name}</span>
                  <span className="font-mono font-bold text-haritaki-deep bg-cream-warm px-2.5 py-0.5 rounded-pill border border-haritaki-gold/30">
                    {sym.count} मामले
                  </span>
                </div>
              ))}
            </div>
          </ClayCard>
        </div>
      </div>

      {/* Red Flag Audit Precision Card */}
      <ClayCard className="p-5 border-2 border-haritaki-gold/40">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-manjistha-red" />
            <h3 className="font-display font-bold text-btn-sec text-teak-grey">
              क्लिनिकल रेड फ्लैग डॉक्टर ऑडिट शुद्धता • AI Safety Evaluation
            </h3>
          </div>
          <ClayBadge variant="success">सटीकता दर: {metrics.auditAccuracy.precision}</ClayBadge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
          <div className="bg-cream-recess p-3 rounded-btn border border-copper-border/40">
            <span className="text-xs text-teak-muted block font-semibold">डॉक्टर द्वारा मान्य (Valid Alerts)</span>
            <strong className="font-display font-bold text-heading text-herbal-green">
              {metrics.auditAccuracy.validAlerts}
            </strong>
          </div>
          <div className="bg-cream-recess p-3 rounded-btn border border-copper-border/40">
            <span className="text-xs text-teak-muted block font-semibold">गलत चेतावनी (False Alarms)</span>
            <strong className="font-display font-bold text-heading text-manjistha-red">
              {metrics.auditAccuracy.falseAlarms}
            </strong>
          </div>
          <div className="bg-cream-warm p-3 rounded-btn border border-haritaki-gold/40">
            <span className="text-xs text-haritaki-deep block font-semibold">एआई परिशुद्धता (AI Precision)</span>
            <strong className="font-display font-bold text-heading text-haritaki-deep">
              {metrics.auditAccuracy.precision}
            </strong>
          </div>
        </div>
      </ClayCard>
    </div>
  );
}
