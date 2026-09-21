import React, { useState, useEffect } from 'react';
import { FileText, Save, CheckCircle, AlertTriangle, ShieldCheck, Printer, Sparkles, Stethoscope, Pill } from 'lucide-react';
import RedFlagAuditWidget from './RedFlagAuditWidget';

export default function CaseSheetEditor({
  patient,
  interviewId,
  caseSheetData,
  onSaveCaseSheet
}) {
  const [formData, setFormData] = useState({
    chiefComplaints: '',
    historyOfPresentIllness: '',
    ashtavidhaPariksha: {
      nadi: 'Vata-Pitta',
      mutra: 'Normal',
      mala: 'Constipation (Vibandha)',
      jihva: 'Sama (Coated)',
      shabda: 'Normal',
      sparsha: 'Anushna (Normothermic)',
      drik: 'Normal',
      akriti: 'Madhyama'
    },
    pastHistory: '',
    medicationHistory: [],
    allergies: '',
    diagnosis: '',
    treatmentPlan: ''
  });

  const [redFlags, setRedFlags] = useState([]);
  const [discrepancies, setDiscrepancies] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (caseSheetData) {
      setFormData(prev => ({
        ...prev,
        chiefComplaints: caseSheetData.chief_complaints || caseSheetData.chiefComplaints || prev.chiefComplaints,
        historyOfPresentIllness: caseSheetData.hpi || caseSheetData.historyOfPresentIllness || prev.historyOfPresentIllness,
        pastHistory: caseSheetData.past_history || caseSheetData.pastHistory || prev.pastHistory,
        medicationHistory: caseSheetData.medications || caseSheetData.medicationHistory || [
          { name: 'Ashwagandharishta', dose: '15ml BD after meals', afiCode: 'AFI-01:04', namasteCode: 'NAM-AYU-0104' },
          { name: 'Triphala Churna', dose: '3g HS with warm water', afiCode: 'AFI-02:11', namasteCode: 'NAM-AYU-0211' }
        ],
        allergies: caseSheetData.allergies || 'No known drug allergies reported.',
        diagnosis: caseSheetData.diagnosis || 'Vata-Kaphaja Kasa (Sub-acute Bronchitis)',
        treatmentPlan: caseSheetData.treatment_plan || '1. Sitopaladi Churna 3g BD with honey\n2. Kanakasava 15ml BD\n3. Steam inhalation with eucalyptus'
      }));

      if (caseSheetData.red_flags) {
        setRedFlags(caseSheetData.red_flags);
      }
      if (caseSheetData.discrepancies) {
        setDiscrepancies(caseSheetData.discrepancies);
      }
    } else {
      // Default demo mock if empty
      setFormData({
        chiefComplaints: 'Chest tightness, persistent dry cough for 5 days, mild exertion breathlessness.',
        historyOfPresentIllness: 'Patient reports progressive cough starting 5 days ago, worsening at night. Associated with mild substernal tightness on exertion. Denies haemoptysis.',
        ashtavidhaPariksha: {
          nadi: 'Vata-Pitta',
          mutra: 'Normal',
          mala: 'Mild constipation',
          jihva: 'Sama (Mild white coating)',
          shabda: 'Kasa dhwani present',
          sparsha: 'Normothermic',
          drik: 'Normal conjunctiva',
          akriti: 'Madhyama'
        },
        pastHistory: 'Hypertension x 4 years on Amlodipine 5mg OD. No prior surgeries.',
        medicationHistory: [
          { name: 'Amlodipine 5mg OD', type: 'Allopathic' },
          { name: 'Ashwagandharishta', dose: '15ml BD', afiCode: 'AFI-01:04', namasteCode: 'NAM-AYU-0104' }
        ],
        allergies: 'No known drug or food allergies.',
        diagnosis: 'Vata-Kaphaja Kasa (Sub-acute Bronchitis) [ICD-11: CA20 / NAMASTE: KASA-01]',
        treatmentPlan: '1. Sitopaladi Churna 3g BD with honey\n2. Kanakasava 15ml BD with equal water\n3. Continue Amlodipine 5mg OD\n4. Review in 7 days'
      });

      setRedFlags([
        {
          id: 'rf-demo-1',
          flag_type: 'Chest Pain with Exertion',
          severity: 'HIGH',
          description: 'Substernal tightness noted in 50+ age hypertensive patient. Rule out acute coronary event.'
        }
      ]);

      setDiscrepancies([
        {
          sourceA: 'Voice Interview',
          statementA: 'Denies taking blood pressure medications',
          sourceB: 'OCR Prescription (2025)',
          statementB: 'Prescribed Amlodipine 5mg daily',
          severity: 'MODERATE'
        }
      ]);
    }
  }, [caseSheetData]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      if (onSaveCaseSheet) {
        await onSaveCaseSheet(formData);
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to save case sheet:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="flex-1 bg-stone-50 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
      {/* Top Bar / Patient Banner */}
      <div className="bg-white rounded-2xl p-6 border border-stone-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold font-serif text-stone-900">
              {patient?.name || 'Rajesh Kumar'}
            </h2>
            <span className="text-xs font-mono bg-stone-100 text-stone-700 px-2.5 py-1 rounded-full border border-stone-200">
              ID: {patient?.id || 'P-1049'}
            </span>
          </div>
          <p className="text-xs text-stone-500 mt-1">
            {patient?.age || '48'} Years • {patient?.gender || 'Male'} • Phone: +91 {patient?.phone || '9876543210'}
            {patient?.emergency_contact_phone && (
              <span className="text-amber-700 font-medium ml-2">
                • Emergency: +91 {patient.emergency_contact_phone}
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handlePrint}
            className="min-h-[42px] px-4 py-2 border border-stone-300 text-stone-700 rounded-xl hover:bg-stone-100 font-medium text-xs flex items-center gap-2 transition"
          >
            <Printer className="w-4 h-4" />
            Print Case Sheet
          </button>

          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="min-h-[42px] px-5 py-2 bg-ayush-primary hover:bg-ayush-primary-dark text-white rounded-xl font-bold text-xs shadow flex items-center gap-2 transition disabled:opacity-50"
          >
            {saveSuccess ? (
              <>
                <CheckCircle className="w-4 h-4 text-ayush-accent" />
                <span>Saved</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>{isSaving ? 'Saving...' : 'Save & Finalize'}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Multi-Source Contradiction Banner */}
      {discrepancies.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>Multi-Source Contradiction Detected ({discrepancies.length})</span>
          </div>
          <div className="space-y-2">
            {discrepancies.map((d, idx) => (
              <div
                key={idx}
                className="bg-white p-3 rounded-xl border border-amber-200 text-xs text-stone-700 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div>
                  <span className="font-semibold text-rose-700">[{d.sourceA}]:</span> {d.statementA}
                  <span className="mx-2 text-stone-400 font-bold">vs</span>
                  <span className="font-semibold text-blue-700">[{d.sourceB}]:</span> {d.statementB}
                </div>
                <span className="text-[10px] bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded-full shrink-0">
                  {d.severity || 'DISCREPANCY'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clinician Red Flag Audit Widget */}
      <div className="bg-white rounded-2xl p-6 border border-stone-200 shadow-sm">
        <RedFlagAuditWidget
          interviewId={interviewId}
          redFlags={redFlags}
          onFeedbackSubmitted={(rfId, isValid, notes) => {
            console.log('Clinician feedback logged:', rfId, isValid, notes);
          }}
        />
      </div>

      {/* 8-Section AYUSH Clinical Case Sheet Form */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-stone-200 shadow-sm space-y-6">
        <div className="flex items-center gap-2 border-b border-stone-200 pb-3">
          <Stethoscope className="w-5 h-5 text-ayush-primary" />
          <h3 className="text-lg font-bold text-stone-800">
            आयुष क्लिनिकल केस शीट / Standardized AYUSH Case Sheet
          </h3>
        </div>

        {/* Section 1: Chief Complaints */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-1.5">
            1. Chief Complaints (लक्षण)
          </label>
          <textarea
            rows={2}
            value={formData.chiefComplaints}
            onChange={(e) => setFormData({ ...formData, chiefComplaints: e.target.value })}
            className="w-full text-sm p-3 rounded-xl border border-stone-300 focus:outline-none focus:ring-1 focus:ring-ayush-primary"
          />
        </div>

        {/* Section 2: History of Present Illness */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-1.5">
            2. History of Present Illness (HPI)
          </label>
          <textarea
            rows={3}
            value={formData.historyOfPresentIllness}
            onChange={(e) => setFormData({ ...formData, historyOfPresentIllness: e.target.value })}
            className="w-full text-sm p-3 rounded-xl border border-stone-300 focus:outline-none focus:ring-1 focus:ring-ayush-primary"
          />
        </div>

        {/* Section 3: Ashtavidha Pariksha */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-2">
            3. Ashtavidha Pariksha (अष्टविध परीक्षा)
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-stone-50 p-4 rounded-xl border border-stone-200">
            {Object.entries(formData.ashtavidhaPariksha).map(([key, value]) => (
              <div key={key}>
                <span className="text-[11px] font-semibold text-stone-500 capitalize block">
                  {key}
                </span>
                <input
                  type="text"
                  value={value}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      ashtavidhaPariksha: {
                        ...formData.ashtavidhaPariksha,
                        [key]: e.target.value
                      }
                    })
                  }
                  className="w-full text-xs p-2 rounded-lg border border-stone-300 bg-white focus:outline-none focus:ring-1 focus:ring-ayush-primary"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Section 4: Past Medical & Surgical History */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-1.5">
            4. Past Medical & Surgical History
          </label>
          <textarea
            rows={2}
            value={formData.pastHistory}
            onChange={(e) => setFormData({ ...formData, pastHistory: e.target.value })}
            className="w-full text-sm p-3 rounded-xl border border-stone-300 focus:outline-none focus:ring-1 focus:ring-ayush-primary"
          />
        </div>

        {/* Section 5: Medication History with AFI / NAMASTE Badges */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-2">
            5. Medication History (AFI & NAMASTE Normalized)
          </label>
          <div className="space-y-2">
            {formData.medicationHistory.map((med, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 rounded-xl border border-stone-200 bg-stone-50/70 text-xs"
              >
                <div className="flex items-center gap-2">
                  <Pill className="w-4 h-4 text-ayush-primary" />
                  <span className="font-bold text-stone-800">{med.name}</span>
                  {med.dose && <span className="text-stone-500">• {med.dose}</span>}
                </div>
                <div className="flex items-center gap-2">
                  {med.afiCode && (
                    <span className="bg-emerald-100 text-emerald-800 text-[10px] px-2 py-0.5 rounded font-mono font-semibold">
                      {med.afiCode}
                    </span>
                  )}
                  {med.namasteCode && (
                    <span className="bg-blue-100 text-blue-800 text-[10px] px-2 py-0.5 rounded font-mono font-semibold">
                      {med.namasteCode}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 6: Allergies */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-1.5">
            6. Allergies & Adverse Reactions
          </label>
          <input
            type="text"
            value={formData.allergies}
            onChange={(e) => setFormData({ ...formData, allergies: e.target.value })}
            className="w-full text-sm p-2.5 rounded-xl border border-stone-300 focus:outline-none focus:ring-1 focus:ring-ayush-primary"
          />
        </div>

        {/* Section 7: Diagnosis & Differential */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-1.5">
            7. Clinical Diagnosis & Differential (Prakriti / Vikriti / ICD-11)
          </label>
          <input
            type="text"
            value={formData.diagnosis}
            onChange={(e) => setFormData({ ...formData, diagnosis: e.target.value })}
            className="w-full text-sm p-2.5 rounded-xl border border-stone-300 focus:outline-none focus:ring-1 focus:ring-ayush-primary font-semibold"
          />
        </div>

        {/* Section 8: Treatment Plan & Prescription */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-stone-600 mb-1.5">
            8. Treatment Plan & Prescription (Chikitsa Sutra / Rx)
          </label>
          <textarea
            rows={4}
            value={formData.treatmentPlan}
            onChange={(e) => setFormData({ ...formData, treatmentPlan: e.target.value })}
            className="w-full text-sm p-3 rounded-xl border border-stone-300 focus:outline-none focus:ring-1 focus:ring-ayush-primary font-mono"
          />
        </div>
      </div>
    </div>
  );
}
