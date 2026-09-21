import React, { useState, useEffect } from 'react';
import { Printer, Share2, CheckCircle2, RotateCcw, QrCode, User, MapPin, Calendar, Clock, Ticket } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayBadge from '../atoms/ClayBadge';
import SelfCopyModal from '../modals/SelfCopyModal';
import { MediKioskApi } from '../../services/api';

export default function PatientSummaryScreen({ onReset }) {
  const { patient, interview, documents, tokenSlip, setTokenSlip } = useKioskSession();
  const [showSelfCopy, setShowSelfCopy] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Generate queue token via backend if not present
    if (!tokenSlip) {
      setLoading(true);
      const queuePayload = {
        patient_id: patient.id || 1,
        patient_name: patient.name || 'रमेश कुमार / Ramesh Kumar',
        age: patient.age || 48,
        gender: patient.gender || 'Male',
        chief_complaint: interview.chief_complaints?.join(', ') || 'ज्वर एवं संधि शूल',
        department: 'कायचिकित्सा (Kayachikitsa)',
        is_red_flag: !!interview.is_red_flag
      };

      MediKioskApi.post('/api/opd-queue', queuePayload)
        .then((res) => {
          const data = res?.data || {};
          setTokenSlip({
            tokenNumber: data.token_number || 'A-104',
            roomNumber: data.room_number || '12',
            department: data.department || 'कायचिकित्सा (Kayachikitsa)',
            waitTime: data.wait_time_minutes || 15
          });
        })
        .catch(() => {
          setTokenSlip({
            tokenNumber: 'A-104',
            roomNumber: '12',
            department: 'कायचिकित्सा (Kayachikitsa)',
            waitTime: 15
          });
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, []);

  const handlePrint = () => {
    window.print();
  };

  const currentToken = tokenSlip?.tokenNumber || 'A-104';
  const currentRoom = tokenSlip?.roomNumber || '12';
  const currentDept = tokenSlip?.department || 'कायचिकित्सा (Kayachikitsa)';
  const currentWait = tokenSlip?.waitTime || 15;

  return (
    <div className="flex-1 flex flex-col justify-center max-w-4xl mx-auto w-full py-4 select-none">
      {/* Title */}
      <div className="text-center mb-6">
        <ClayBadge variant="success" className="mb-2">
          <CheckCircle2 className="w-4 h-4" /> पंजीकरण पूर्ण • Registration Complete
        </ClayBadge>
        <h2 className="font-display font-extrabold text-heading sm:text-title text-teak-grey">
          आपका ओपीडी परामर्श टोकन तैयार है
        </h2>
        <p className="text-caption text-teak-muted">
          कृपया अपनी टोकन पर्ची प्राप्त करें एवं निर्दिष्ट परामर्श कक्ष के बाहर प्रतीक्षा करें।
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start mb-6">
        {/* Left Column: Physical Token Ticket Representation */}
        <div className="md:col-span-6 flex flex-col items-center">
          <ClayCard elevated className="w-full p-6 border-2 border-haritaki-gold bg-shweta-white shadow-card-elevated flex flex-col items-center text-center relative overflow-hidden">
            {/* Top Institute Header */}
            <span className="text-[11px] font-bold text-haritaki-deep uppercase tracking-widest mb-1">
              अखिल भारतीय आयुर्वेद संस्थान • AIIA NEW DELHI
            </span>
            <span className="text-xs text-teak-muted border-b border-copper-border/40 pb-3 w-full block">
              केंद्रीय ओपीडी पंजीकरण पर्ची (OPD Consultation Slip)
            </span>

            {/* Giant Token Number */}
            <div className="my-5 flex flex-col items-center">
              <span className="text-xs text-teak-muted uppercase tracking-wider font-semibold">
                टोकन संख्या / Token No.
              </span>
              <span className="font-display font-black text-hero text-haritaki-deep tracking-tight my-1">
                {currentToken}
              </span>
              <ClayBadge variant="ayush">प्राथमिकता: सामान्य / Normal</ClayBadge>
            </div>

            {/* Room & Department Box */}
            <div className="w-full bg-cream-warm/70 p-4 rounded-card border border-haritaki-gold/30 text-left flex flex-col gap-2 my-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-teak-muted font-semibold">परामर्श कक्ष:</span>
                <strong className="text-btn-sec font-display text-teak-grey">
                  कक्ष संख्या {currentRoom} (Room {currentRoom})
                </strong>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-teak-muted font-semibold">विभाग:</span>
                <strong className="text-caption text-haritaki-deep font-semibold">
                  {currentDept}
                </strong>
              </div>
              <div className="flex items-center justify-between border-t border-copper-border/40 pt-2 mt-1">
                <span className="text-xs text-teak-muted font-semibold">अनुमानित प्रतीक्षा:</span>
                <span className="text-caption font-bold text-herbal-green flex items-center gap-1 font-mono">
                  <Clock className="w-3.5 h-3.5" /> ~{currentWait} मिनट
                </span>
              </div>
            </div>

            {/* Simulated Receipt QR Code */}
            <div className="mt-4 pt-3 border-t border-dashed border-copper-border w-full flex items-center justify-between text-left">
              <div>
                <span className="text-[11px] text-teak-muted block font-mono">
                  ID: {patient.abha_id || 'ABHA-918765432109'}
                </span>
                <span className="text-[10px] text-teak-muted/70 block">
                  {new Date().toLocaleDateString('hi-IN')} &bull; {new Date().toLocaleTimeString('hi-IN', { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              <div className="w-12 h-12 bg-cream-recess border border-copper-border rounded flex items-center justify-center">
                <QrCode className="w-8 h-8 text-teak-grey" />
              </div>
            </div>
          </ClayCard>
        </div>

        {/* Right Column: Case Summary Details & Actions */}
        <div className="md:col-span-6 flex flex-col gap-4">
          <ClayCard className="p-5 flex flex-col gap-3">
            <h3 className="font-display font-bold text-btn-sec text-teak-grey border-b border-copper-border/40 pb-2">
              पंजीकृत स्वास्थ्य सारांश • Intake Summary
            </h3>

            {/* Patient Info */}
            <div className="text-caption text-teak-grey flex flex-col gap-1.5">
              <div className="flex justify-between">
                <span className="text-teak-muted">रोगी का नाम:</span>
                <strong className="font-display font-bold">{patient.name || 'रमेश कुमार'}</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-teak-muted">आयु / लिंग:</span>
                <span>{patient.age || '48'} वर्ष / {patient.gender || 'Male'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-teak-muted">मोबाइल नंबर:</span>
                <span className="font-mono">{patient.mobile || '9876543210'}</span>
              </div>
            </div>

            {/* Symptoms Summary */}
            <div className="border-t border-copper-border/40 pt-2">
              <span className="text-xs font-bold text-haritaki-deep block mb-1">
                मुख्य लक्षण (Chief Complaints):
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(interview.chief_complaints?.length > 0 ? interview.chief_complaints : ['ज्वर / बुखार', 'संधि शूल']).map((sym, idx) => (
                  <ClayBadge key={idx} variant="ayush">
                    {sym}
                  </ClayBadge>
                ))}
              </div>
            </div>

            {/* AYUSH Prakriti */}
            <div className="border-t border-copper-border/40 pt-2 flex justify-between text-caption">
              <span className="text-teak-muted">प्रकृति (Prakriti):</span>
              <strong className="text-haritaki-deep font-display font-bold">
                {interview.pariksha?.prakriti || 'Vata-Pitta'}
              </strong>
            </div>

            {/* Documents attached */}
            <div className="border-t border-copper-border/40 pt-2 flex justify-between text-caption">
              <span className="text-teak-muted">स्कैन किए गए दस्तावेज:</span>
              <span className="font-bold text-herbal-green">{documents.length} दस्तावेज संलग्न</span>
            </div>
          </ClayCard>

          {/* Action Buttons */}
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <ClayButton
                variant="neutral"
                size="md"
                onClick={handlePrint}
                icon={<Printer className="w-4 h-4" />}
                className="w-full"
              >
                पर्ची प्रिंट करें / Print Slip
              </ClayButton>

              <ClayButton
                variant="neutral"
                size="md"
                onClick={() => setShowSelfCopy(true)}
                icon={<Share2 className="w-4 h-4" />}
                className="w-full"
              >
                डिजिटल कॉपी / Send to Phone
              </ClayButton>
            </div>

            <ClayButton
              variant="primary-gold"
              size="touch"
              onClick={onReset}
              className="w-full shadow-btn-gold"
            >
              <span className="flex items-center justify-center gap-2">
                <RotateCcw className="w-5 h-5" />
                <span>नया पंजीकरण शुरू करें / Finish &amp; New Kiosk Session</span>
              </span>
            </ClayButton>
          </div>
        </div>
      </div>

      {/* Self-Copy Modal */}
      <SelfCopyModal
        isOpen={showSelfCopy}
        onClose={() => setShowSelfCopy(false)}
        defaultMobile={patient.mobile}
        tokenNumber={currentToken}
      />
    </div>
  );
}
