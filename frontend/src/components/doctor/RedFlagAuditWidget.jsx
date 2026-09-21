import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, XCircle, Send, ShieldAlert } from 'lucide-react';

/**
 * RedFlagAuditWidget
 * Clinician-in-the-loop feedback component for auditing algorithmic red flags.
 * Allows doctor to mark an AI-detected red flag as 'Valid Clinical Alert' or 'False Alarm'
 * and records feedback notes via POST /api/interviews/{interviewId}/red-flags/{redFlagId}/feedback.
 */
export default function RedFlagAuditWidget({
  interviewId,
  redFlags = [],
  onFeedbackSubmitted
}) {
  const [feedbackState, setFeedbackState] = useState({});
  const [submitting, setSubmitting] = useState({});
  const [submitted, setSubmitted] = useState({});

  const handleSelection = (rfId, isValid) => {
    setFeedbackState(prev => ({
      ...prev,
      [rfId]: {
        ...prev[rfId],
        isValid
      }
    }));
  };

  const handleNotesChange = (rfId, notes) => {
    setFeedbackState(prev => ({
      ...prev,
      [rfId]: {
        ...prev[rfId],
        notes
      }
    }));
  };

  const submitFeedback = async (rfId) => {
    const state = feedbackState[rfId];
    if (!state || state.isValid === undefined) return;

    setSubmitting(prev => ({ ...prev, [rfId]: true }));
    try {
      const res = await fetch(`/api/interviews/${interviewId}/red-flags/${rfId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          is_valid: state.isValid,
          feedback_notes: state.notes || ''
        })
      });

      if (res.ok) {
        setSubmitted(prev => ({ ...prev, [rfId]: true }));
        if (onFeedbackSubmitted) {
          onFeedbackSubmitted(rfId, state.isValid, state.notes);
        }
      } else {
        console.error('Failed to submit clinician feedback');
      }
    } catch (err) {
      console.error('Error submitting red flag feedback:', err);
    } finally {
      setSubmitting(prev => ({ ...prev, [rfId]: false }));
    }
  };

  if (!redFlags || redFlags.length === 0) {
    return (
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3 text-emerald-800 text-sm">
        <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
        <span>No algorithmic red flags detected for this patient consultation.</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-rose-800 font-semibold text-sm">
        <ShieldAlert className="w-4 h-4 text-rose-600" />
        <span>Algorithmic Red Flag Audit ({redFlags.length})</span>
      </div>

      <div className="space-y-3">
        {redFlags.map((rf) => {
          const state = feedbackState[rf.id] || {};
          const isDone = submitted[rf.id];
          const isSubmitting = submitting[rf.id];

          return (
            <div
              key={rf.id}
              className={`p-4 rounded-xl border transition-all ${
                isDone
                  ? 'bg-stone-50 border-stone-200 opacity-90'
                  : 'bg-rose-50/60 border-rose-200 shadow-sm'
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <span className="text-sm font-bold text-rose-900">
                    {rf.flag_type || 'Clinical Warning'}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-rose-200 text-rose-800 font-medium">
                    {rf.severity || 'HIGH'}
                  </span>
                </div>
                {rf.detected_at && (
                  <span className="text-xs text-stone-500">
                    {new Date(rf.detected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </div>

              <p className="text-xs text-stone-700 mb-3 bg-white/80 p-2 rounded-lg border border-rose-100">
                {rf.description || rf.message || 'Potential severe medical anomaly detected.'}
              </p>

              {isDone ? (
                <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>
                    Feedback logged: <strong>{state.isValid ? 'Valid Clinical Alert' : 'False Alarm'}</strong>
                    {state.notes ? ` — "${state.notes}"` : ''}
                  </span>
                </div>
              ) : (
                <div className="space-y-2 pt-1 border-t border-rose-100">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-stone-600">Clinician Audit:</span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleSelection(rf.id, true)}
                        className={`min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                          state.isValid === true
                            ? 'bg-rose-600 text-white shadow-sm ring-2 ring-rose-600 ring-offset-1'
                            : 'bg-white text-stone-700 border border-stone-300 hover:bg-rose-50'
                        }`}
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Valid Alert
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSelection(rf.id, false)}
                        className={`min-h-[38px] px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                          state.isValid === false
                            ? 'bg-stone-700 text-white shadow-sm ring-2 ring-stone-700 ring-offset-1'
                            : 'bg-white text-stone-700 border border-stone-300 hover:bg-stone-100'
                        }`}
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        False Alarm
                      </button>
                    </div>
                  </div>

                  {state.isValid !== undefined && (
                    <div className="flex items-center gap-2 mt-2">
                      <input
                        type="text"
                        placeholder="Optional feedback notes for AI audit..."
                        value={state.notes || ''}
                        onChange={(e) => handleNotesChange(rf.id, e.target.value)}
                        className="flex-1 text-xs px-3 py-2 rounded-lg border border-stone-300 focus:outline-none focus:ring-1 focus:ring-rose-500 bg-white"
                      />
                      <button
                        type="button"
                        onClick={() => submitFeedback(rf.id)}
                        disabled={isSubmitting}
                        className="min-h-[38px] px-3 py-2 bg-ayush-primary text-white text-xs font-medium rounded-lg hover:bg-ayush-primary-dark transition flex items-center gap-1 disabled:opacity-50"
                      >
                        <Send className="w-3 h-3" />
                        {isSubmitting ? 'Saving...' : 'Submit'}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
