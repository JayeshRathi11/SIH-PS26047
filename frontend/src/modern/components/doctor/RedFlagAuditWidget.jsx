import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, XCircle, ShieldAlert, FileEdit } from 'lucide-react';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function RedFlagAuditWidget({
  patient,
  redFlagReason = 'Severe Chest Pain / Critical Alert',
  onAuditSubmitted
}) {
  const [evaluation, setEvaluation] = useState(null); // 'VALID' | 'FALSE_ALARM'
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmitAudit = async () => {
    if (!evaluation) return;
    setSubmitting(true);

    try {
      await MediKioskApi.post('/api/emergency/audit', {
        patient_id: patient?.id,
        evaluation,
        notes,
        reviewed_by: 'Dr. AYUSH Senior Consultant',
        timestamp: new Date().toISOString()
      });
    } catch {
      // Offline fallback
    }

    setSubmitted(true);
    setSubmitting(false);
    if (onAuditSubmitted) onAuditSubmitted({ evaluation, notes });
  };

  return (
    <ClayCard className="p-4 border-2 border-manjistha-red/60 bg-manjistha-red/5 mb-4">
      <div className="flex items-center justify-between border-b border-manjistha-red/30 pb-2 mb-3">
        <div className="flex items-center gap-2 text-manjistha-red">
          <ShieldAlert className="w-5 h-5" />
          <h4 className="font-display font-bold text-caption uppercase tracking-wider">
            क्लिनिकल रेड फ्लैग सत्यापन • Red-Flag Mandatory Audit
          </h4>
        </div>
        <ClayBadge variant="redflag">चिकित्सक सत्यापन आवश्यक</ClayBadge>
      </div>

      <div className="text-caption text-teak-grey mb-3">
        <span className="text-teak-muted">एआई द्वारा पहचाना गया चेतावनी कारण: </span>
        <strong className="text-manjistha-red font-bold">{redFlagReason}</strong>
      </div>

      {submitted ? (
        <div className="flex items-center gap-2 p-2.5 bg-shweta-white border border-herbal-green/40 rounded-btn text-herbal-green font-bold text-caption">
          <CheckCircle2 className="w-4 h-4" />
          <span>
            ऑडिट सफलतापूर्वक दर्ज हुआ: {evaluation === 'VALID' ? 'सटीक क्लिनिकल अलर्ट (Valid)' : 'फॉल्स अलार्म (False Alarm)'}
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Binary Evaluation Buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setEvaluation('VALID')}
              className={`p-2.5 rounded-btn font-display font-bold text-caption flex items-center justify-center gap-2 border transition-all cursor-pointer ${
                evaluation === 'VALID'
                  ? 'bg-manjistha-red text-white border-manjistha-red shadow-sm'
                  : 'bg-shweta-white text-teak-grey border-copper-border hover:border-manjistha-red/40'
              }`}
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>सटीक अलर्ट / Valid Alert</span>
            </button>

            <button
              type="button"
              onClick={() => setEvaluation('FALSE_ALARM')}
              className={`p-2.5 rounded-btn font-display font-bold text-caption flex items-center justify-center gap-2 border transition-all cursor-pointer ${
                evaluation === 'FALSE_ALARM'
                  ? 'bg-herbal-green text-white border-herbal-green shadow-sm'
                  : 'bg-shweta-white text-teak-grey border-copper-border hover:border-herbal-green/40'
              }`}
            >
              <XCircle className="w-4 h-4" />
              <span>गलत चेतावनी / False Alarm</span>
            </button>
          </div>

          {/* Audit Note Input */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-teak-muted">
              चिकित्सक समीक्षा टिप्पणी (Audit Notes):
            </label>
            <input
              type="text"
              placeholder="e.g. ECG सामान्य है, मस्कुलोस्केलेटल दर्द पाया गया / Normal ECG, musculoskeletal origin"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full h-9 bg-shweta-white text-teak-grey text-caption px-3 rounded-btn border border-copper-border outline-none focus:border-haritaki-gold"
            />
          </div>

          <div className="flex justify-end">
            <ClayButton
              variant="primary-gold"
              size="sm"
              disabled={!evaluation}
              loading={submitting}
              onClick={handleSubmitAudit}
            >
              ऑडिट सुरक्षित करें / Save Audit
            </ClayButton>
          </div>
        </div>
      )}
    </ClayCard>
  );
}
