import React, { useState } from 'react';
import { CheckCircle2, User, Phone, FileText, AlertCircle, Printer, QrCode, ArrowLeft, HeartPulse, Send } from 'lucide-react';
import SelfCopyModal from './SelfCopyModal';

export default function PatientConfirmationStep({
  patient,
  interviewData,
  documentData,
  onEdit,
  onResetKiosk
}) {
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [showSelfCopyModal, setShowSelfCopyModal] = useState(false);
  const [tokenNumber, setTokenNumber] = useState('OPD-' + Math.floor(100 + Math.random() * 900));
  const [isSubmitting, setIsSubmitting] = useState(false);

  const interviewId = interviewData?.id || patient?.interviewId || `int-${Date.now()}`;

  const handleConfirmAndJoinQueue = async () => {
    setIsSubmitting(true);
    try {
      // Post to OPD queue
      await fetch('/api/opd-queue/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patient.id,
          interview_id: interviewId,
          status: 'WAITING',
          is_red_flag: false
        })
      });
    } catch (err) {
      console.warn('Queue dispatch failed or running offline demo:', err);
    } finally {
      setIsSubmitting(false);
      setIsConfirmed(true);
      setShowSelfCopyModal(true);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      <div className="bg-white rounded-2xl shadow-xl border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-ayush-primary to-ayush-primary-dark text-white p-6 sm:p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center border border-white/20">
                <CheckCircle2 className="w-7 h-7 text-ayush-accent" />
              </div>
              <div>
                <h2 className="text-2xl sm:text-3xl font-bold font-serif">
                  विवरण की पुष्टि / Summary & Confirmation
                </h2>
                <p className="text-emerald-100 text-sm mt-1">
                  कृपया डॉक्टर के पास भेजने से पहले अपने विवरण की समीक्षा करें
                </p>
              </div>
            </div>

            {isConfirmed && (
              <div className="bg-ayush-accent text-stone-900 px-4 py-2 rounded-xl text-center font-bold">
                <div className="text-[10px] uppercase tracking-wider">टोकन संख्या</div>
                <div className="text-xl font-mono">{tokenNumber}</div>
              </div>
            )}
          </div>
        </div>

        {/* Confirmation Content */}
        <div className="p-6 sm:p-8 space-y-6">
          {/* Patient Profile Card */}
          <div className="p-4 rounded-xl border border-stone-200 bg-stone-50/60 space-y-3">
            <h3 className="text-sm font-bold text-stone-800 flex items-center gap-2">
              <User className="w-4 h-4 text-ayush-primary" />
              रोगी जनसांख्यिकी / Patient Demographics
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs sm:text-sm">
              <div>
                <span className="text-stone-500 block">नाम / Name:</span>
                <span className="font-semibold text-stone-800">{patient?.name || '--'}</span>
              </div>
              <div>
                <span className="text-stone-500 block">आयु व लिंग / Age & Gender:</span>
                <span className="font-semibold text-stone-800">
                  {patient?.age || '--'} Y • {patient?.gender || '--'}
                </span>
              </div>
              <div>
                <span className="text-stone-500 block">मोबाइल नंबर / Mobile:</span>
                <span className="font-semibold text-stone-800 font-mono">
                  +91 {patient?.phone || '--'}
                </span>
              </div>
              {patient?.emergency_contact_phone && (
                <div className="col-span-2 sm:col-span-1">
                  <span className="text-stone-500 block">आपातकालीन संपर्क / Emergency:</span>
                  <span className="font-semibold text-amber-700 font-mono">
                    +91 {patient.emergency_contact_phone}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Clinical Interview Summary */}
          <div className="p-4 rounded-xl border border-stone-200 bg-stone-50/60 space-y-3">
            <h3 className="text-sm font-bold text-stone-800 flex items-center gap-2">
              <HeartPulse className="w-4 h-4 text-ayush-primary" />
              लक्षण एवं साक्षात्कार सारांश / Clinical Symptoms
            </h3>
            <div className="space-y-2 text-xs sm:text-sm">
              {interviewData?.interviewAnswers && Object.entries(interviewData.interviewAnswers).length > 0 ? (
                Object.entries(interviewData.interviewAnswers).map(([key, val], idx) => (
                  <div key={key} className="bg-white p-3 rounded-lg border border-stone-200">
                    <p className="font-medium text-stone-700 text-xs mb-1">
                      {val.questionHi || `प्रश्न ${idx + 1}`}
                    </p>
                    <p className="font-semibold text-stone-900">{val.answer}</p>
                  </div>
                ))
              ) : (
                <div className="bg-white p-3 rounded-lg border border-stone-200 text-stone-600">
                  लक्षण साक्षात्कार सफलतापूर्वक रिकॉर्ड किया गया।
                </div>
              )}
            </div>
          </div>

          {/* Documents Uploaded */}
          {documentData?.documents && documentData.documents.length > 0 && (
            <div className="p-4 rounded-xl border border-stone-200 bg-stone-50/60 space-y-2">
              <h3 className="text-sm font-bold text-stone-800 flex items-center gap-2">
                <FileText className="w-4 h-4 text-ayush-primary" />
                संलग्न दस्तावेज / Attached Records ({documentData.documents.length})
              </h3>
              <div className="flex flex-wrap gap-2">
                {documentData.documents.map((d) => (
                  <span
                    key={d.id}
                    className="inline-flex items-center gap-1.5 bg-white px-3 py-1.5 rounded-lg border border-stone-200 text-xs font-medium text-stone-700"
                  >
                    <FileText className="w-3.5 h-3.5 text-emerald-600" />
                    {d.name} ({d.type})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Post Confirmation State */}
          {isConfirmed ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 text-center space-y-4">
              <div className="w-14 h-14 rounded-full bg-emerald-100 border border-emerald-300 text-emerald-700 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-emerald-900 font-serif">
                  सफलतापूर्वक कतार में जोड़ा गया / Added to OPD Queue
                </h3>
                <p className="text-sm text-emerald-700 mt-1">
                  आपका टोकन नंबर <strong className="font-mono">{tokenNumber}</strong> है। कृपया प्रतीक्षा कक्ष में बैठें।
                </p>
              </div>

              <div className="flex flex-wrap justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowSelfCopyModal(true)}
                  className="min-h-[48px] px-6 py-2.5 bg-ayush-primary text-white font-semibold rounded-xl shadow hover:bg-ayush-primary-dark transition flex items-center gap-2"
                >
                  <QrCode className="w-5 h-5" />
                  <span>रसीद / QR / SMS प्राप्त करें</span>
                </button>

                <button
                  type="button"
                  onClick={onResetKiosk}
                  className="min-h-[48px] px-6 py-2.5 bg-white border border-stone-300 text-stone-700 font-semibold rounded-xl hover:bg-stone-50 transition"
                >
                  नया पंजीकरण / New Session
                </button>
              </div>
            </div>
          ) : (
            /* Action Buttons Before Confirmation */
            <div className="pt-6 border-t border-stone-200 flex items-center justify-between gap-4">
              <button
                type="button"
                onClick={onEdit}
                className="min-h-[48px] px-6 py-2.5 rounded-xl border border-stone-300 text-stone-700 font-semibold hover:bg-stone-100 transition flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>संशोधन करें / Edit</span>
              </button>

              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleConfirmAndJoinQueue}
                className="min-h-[52px] px-8 py-3 bg-ayush-primary hover:bg-ayush-primary-dark text-white rounded-xl font-bold text-base shadow-lg shadow-ayush-primary/20 flex items-center gap-3 transition-all transform active:scale-95 disabled:opacity-50"
              >
                <CheckCircle2 className="w-5 h-5" />
                <span>{isSubmitting ? 'प्रक्रियाधीन...' : 'पुष्टि करें एवं कतार में जुड़ें / Confirm & Join Queue'}</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Self-Copy Modal */}
      {showSelfCopyModal && (
        <SelfCopyModal
          interviewId={interviewId}
          patientName={patient?.name || 'रोगी / Patient'}
          onClose={() => setShowSelfCopyModal(false)}
        />
      )}
    </div>
  );
}
