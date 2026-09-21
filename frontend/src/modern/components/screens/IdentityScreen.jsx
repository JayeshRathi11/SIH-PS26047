import React, { useState } from 'react';
import { QrCode, Phone, User, ShieldCheck, ArrowRight, Sparkles, CheckCircle2 } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayInput from '../atoms/ClayInput';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function IdentityScreen({ onSelectManual, onVerified, onTriggerOtp }) {
  const { language, updatePatient } = useKioskSession();
  const [mobileInput, setMobileInput] = useState('');
  const [abhaInput, setAbhaInput] = useState('');
  const [selectedMethod, setSelectedMethod] = useState('QR'); // 'QR' | 'MOBILE' | 'ABHA'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSimulateQrScan = async () => {
    setLoading(true);
    setError(null);
    try {
      // Simulate ABHA QR parsing
      const mockAbhaPayload = {
        abha_id: '91-8765-4321-0987',
        name: 'रमेश कुमार / Ramesh Kumar',
        age: 48,
        gender: 'Male',
        mobile: '9876543210',
        district: 'South Delhi',
        state: 'Delhi',
        verification_mode: 'ABHA_QR'
      };

      const apiPayload = {
        name: 'रमेश कुमार / Ramesh Kumar',
        phone_number: '+919876543210',
        date_of_birth: '1976-05-15',
        gender: 'Male',
        preferred_language: language || 'hi'
      };

      let patientId = 101;
      try {
        const res = await MediKioskApi.post('/api/patients', apiPayload);
        if (res?.data?.id) patientId = res.data.id;
      } catch (postErr) {
        if (postErr?.isConflict || postErr?.status === 409) {
          try {
            const lookup = await MediKioskApi.get(`/api/patients/by-phone/${encodeURIComponent(apiPayload.phone_number)}`);
            if (lookup?.ok && lookup?.data?.id) patientId = lookup.data.id;
          } catch {}
        }
      }

      updatePatient({
        id: patientId,
        ...mockAbhaPayload
      });

      onVerified();
    } catch (err) {
      // Fallback
      updatePatient({
        id: 101,
        ...mockAbhaPayload
      });
      onVerified();
    } finally {
      setLoading(false);
    }
  };

  const handleSendMobileOtp = () => {
    if (mobileInput.length < 10) {
      setError('कृपया 10 अंकों का मान्य मोबाइल नंबर दर्ज करें / Please enter a valid 10-digit mobile number');
      return;
    }
    setError(null);
    onTriggerOtp(mobileInput, 'MOBILE');
  };

  return (
    <div className="flex-1 flex flex-col justify-center max-w-4xl mx-auto w-full py-4">
      {/* Screen Title */}
      <div className="text-center mb-8">
        <ClayBadge variant="ayush" className="mb-2">
          चरण 1 • Step 1
        </ClayBadge>
        <h2 className="font-display font-extrabold text-heading sm:text-title text-teak-grey">
          पहचान सत्यापन • Identity Verification
        </h2>
        <p className="text-caption sm:text-body text-teak-muted max-w-lg mx-auto mt-1">
          त्वरित पंजीकरण के लिए अपना आभा (ABHA) क्यूआर स्कैन करें या मोबाइल नंबर दर्ज करें।
        </p>
      </div>

      {/* 2 Primary Verification Methods */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Card 1: ABHA QR Code Scan */}
        <ClayCard
          selected={selectedMethod === 'QR'}
          interactive
          onClick={() => setSelectedMethod('QR')}
          className="p-6 flex flex-col items-center text-center justify-between min-h-[340px]"
        >
          <div className="flex flex-col items-center">
            <div className="w-16 h-16 rounded-full bg-cream-warm border-2 border-haritaki-gold text-haritaki-deep flex items-center justify-center mb-4 shadow-sm">
              <QrCode className="w-8 h-8" />
            </div>
            <h3 className="font-display font-bold text-heading text-teak-grey mb-1">
              आभा क्यूआर कोड स्कैन करें
            </h3>
            <p className="text-caption text-teak-muted mb-4">
              Scan ABHA QR with your Ayushman Bharat / Aarogya Setu app
            </p>

            <div className="w-36 h-36 border-2 border-dashed border-haritaki-gold/60 rounded-card flex flex-col items-center justify-center bg-cream-warm/40 p-4 mb-4">
              <QrCode className="w-16 h-16 text-haritaki-deep/60" />
              <span className="text-[11px] text-teak-muted mt-1 font-semibold">
                कैमरा सक्रिय / Scanner Ready
              </span>
            </div>
          </div>

          <ClayButton
            variant="primary-gold"
            size="md"
            loading={loading}
            onClick={(e) => {
              e.stopPropagation();
              handleSimulateQrScan();
            }}
            className="w-full"
          >
            स्कैन सिमुलेशन / Simulate Scan
          </ClayButton>
        </ClayCard>

        {/* Card 2: Mobile Number / ABHA ID */}
        <ClayCard
          selected={selectedMethod === 'MOBILE'}
          interactive
          onClick={() => setSelectedMethod('MOBILE')}
          className="p-6 flex flex-col justify-between min-h-[340px]"
        >
          <div className="flex flex-col">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep flex items-center justify-center flex-shrink-0">
                <Phone className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-display font-bold text-btn-sec text-teak-grey">
                  मोबाइल नंबर दर्ज करें
                </h3>
                <p className="text-caption text-teak-muted">
                  Enter Mobile for OTP Verification
                </p>
              </div>
            </div>

            <ClayInput
              label="मोबाइल नंबर / Mobile Number"
              placeholder="9876543210"
              type="tel"
              maxLength={10}
              value={mobileInput}
              onChange={(e) => setMobileInput(e.target.value.replace(/\D/g, ''))}
              error={error}
              icon={<Phone className="w-5 h-5" />}
              className="mb-4"
            />

            <p className="text-xs text-teak-muted flex items-center gap-1.5 bg-cream-warm/50 p-2.5 rounded-btn border border-copper-border/50">
              <ShieldCheck className="w-4 h-4 text-haritaki-deep flex-shrink-0" />
              <span>आपके मोबाइल पर 4-अंकों का सुरक्षित ओटीपी भेजा जाएगा।</span>
            </p>
          </div>

          <ClayButton
            variant="primary-gold"
            size="md"
            onClick={(e) => {
              e.stopPropagation();
              handleSendMobileOtp();
            }}
            disabled={mobileInput.length < 10}
            className="w-full mt-4"
          >
            ओटीपी प्राप्त करें / Get OTP
          </ClayButton>
        </ClayCard>
      </div>

      {/* Manual Entry Fallback Button */}
      <div className="text-center pt-2">
        <button
          type="button"
          onClick={onSelectManual}
          className="text-btn-sec font-display font-bold text-haritaki-deep hover:text-haritaki-gold underline decoration-haritaki-gold underline-offset-4 cursor-pointer transition-all"
        >
          आभा कार्ड नहीं है? विवरण हाथ से दर्ज करें &rarr; / No ABHA? Enter Manually
        </button>
      </div>
    </div>
  );
}
