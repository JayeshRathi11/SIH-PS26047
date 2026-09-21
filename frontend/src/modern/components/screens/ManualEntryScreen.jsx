import React, { useState } from 'react';
import { User, Phone, MapPin, Calendar, Check, ArrowRight, AlertTriangle } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import ClayCard from '../atoms/ClayCard';
import ClayButton from '../atoms/ClayButton';
import ClayInput from '../atoms/ClayInput';
import ClayKeypad from '../atoms/ClayKeypad';
import ClayBadge from '../atoms/ClayBadge';
import { MediKioskApi } from '../../services/api';

export default function ManualEntryScreen({ onComplete, onBack }) {
  const { language, updatePatient } = useKioskSession();

  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('Male');
  const [mobile, setMobile] = useState('');
  const [district, setDistrict] = useState('South Delhi');
  const [state, setState] = useState('Delhi');

  const [activeKeypadField, setActiveKeypadField] = useState(null); // 'age' | 'mobile' | null
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const handleKeypadPress = (val) => {
    if (activeKeypadField === 'age') {
      if (age.length < 3) setAge((prev) => prev + val);
    } else if (activeKeypadField === 'mobile') {
      if (mobile.length < 10) setMobile((prev) => prev + val);
    }
  };

  const handleKeypadDelete = () => {
    if (activeKeypadField === 'age') {
      setAge((prev) => prev.slice(0, -1));
    } else if (activeKeypadField === 'mobile') {
      setMobile((prev) => prev.slice(0, -1));
    }
  };

  const handleKeypadClear = () => {
    if (activeKeypadField === 'age') setAge('');
    if (activeKeypadField === 'mobile') setMobile('');
  };

  const validate = () => {
    const errs = {};
    if (!name.trim()) errs.name = 'कृपया पूरा नाम दर्ज करें / Please enter name';
    if (!age || parseInt(age, 10) <= 0 || parseInt(age, 10) > 120) {
      errs.age = 'मान्य आयु दर्ज करें / Enter valid age';
    }
    if (!mobile || mobile.length < 10) {
      errs.mobile = '10 अंकों का मोबाइल नंबर दर्ज करें / Enter 10-digit mobile';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setLoading(true);

    const cleanMobile = mobile.trim();
    const formattedPhone = cleanMobile.startsWith('+') ? cleanMobile : (`+91${cleanMobile}`);
    const birthYear = Math.max(1900, new Date().getFullYear() - (parseInt(age, 10) || 30));
    const estimatedDob = `${birthYear}-01-01`;

    const payload = {
      name: name.trim(),
      age: parseInt(age, 10),
      gender,
      mobile,
      district,
      state,
      verification_mode: 'MANUAL'
    };

    const apiPayload = {
      name: name.trim(),
      phone_number: formattedPhone,
      date_of_birth: estimatedDob,
      gender: gender,
      preferred_language: language || 'en'
    };

    try {
      const res = await MediKioskApi.post('/api/patients', apiPayload);
      const saved = res?.data || apiPayload;
      updatePatient({
        id: saved.id || Date.now(),
        ...payload
      });
      onComplete();
    } catch (err) {
      if (err?.isConflict || err?.status === 409) {
        try {
          const lookup = await MediKioskApi.get(`/api/patients/by-phone/${encodeURIComponent(formattedPhone)}`);
          if (lookup?.ok && lookup?.data?.id) {
            updatePatient({
              id: lookup.data.id,
              name: lookup.data.name || name.trim(),
              ...payload
            });
            onComplete();
            return;
          }
        } catch {}
      }
      // Do not use fake Date.now() ID - inform the user of failure
      setErrors((prev) => ({
        ...prev,
        submit: err?.detail || 'पंजीकरण विफल रहा। कृपया विवरण या नेटवर्क जांचें और पुनः प्रयास करें। (Registration failed. Please check details or network and retry.)'
      }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-center max-w-4xl mx-auto w-full py-2">
      {/* Title */}
      <div className="text-center mb-6">
        <ClayBadge variant="ayush" className="mb-2">
          चरण 1 • Step 1
        </ClayBadge>
        <h2 className="font-display font-extrabold text-heading sm:text-title text-teak-grey">
          रोगी विवरण प्रविष्टि • Patient Demographic Entry
        </h2>
        <p className="text-caption text-teak-muted">
          कृपया परामर्श पर्ची के लिए अपना बुनियादी विवरण दर्ज करें।
        </p>
      </div>

      {errors.submit && (
        <div className="mb-4 p-3 bg-manjistha-red/10 border border-manjistha-red/30 rounded-card text-manjistha-red text-caption font-semibold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{errors.submit}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Form Fields Column */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <ClayCard className="p-6 flex flex-col gap-4">
            {/* Full Name */}
            <ClayInput
              label="पूरा नाम / Full Name"
              placeholder="e.g. सीमा देवी / Seema Devi"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={errors.name}
              required
              icon={<User className="w-5 h-5" />}
            />

            {/* Age & Gender Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Age with tactile keypad focus */}
              <ClayInput
                label="आयु / Age (वर्ष / Years)"
                placeholder="e.g. 45"
                type="text"
                value={age}
                onFocus={() => setActiveKeypadField('age')}
                readOnly
                error={errors.age}
                required
                icon={<Calendar className="w-5 h-5" />}
              />

              {/* Gender Selector */}
              <div className="flex flex-col gap-1.5">
                <label className="text-caption font-semibold text-teak-grey">
                  लिंग / Gender <span className="text-manjistha-red text-xs">*</span>
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 'Male', labelHi: 'पुरुष', labelEn: 'Male' },
                    { id: 'Female', labelHi: 'महिला', labelEn: 'Female' },
                    { id: 'Other', labelHi: 'अन्य', labelEn: 'Other' }
                  ].map((g) => (
                    <button
                      key={g.id}
                      type="button"
                      onClick={() => setGender(g.id)}
                      className={`min-h-[52px] rounded-btn font-display font-bold text-caption flex flex-col items-center justify-center transition-all border cursor-pointer ${
                        gender === g.id
                          ? 'bg-cream-warm border-haritaki-gold text-haritaki-deep shadow-btn-gold'
                          : 'bg-cream-neutral border-copper-border text-teak-muted'
                      }`}
                    >
                      <span>{g.labelHi}</span>
                      <span className="text-[10px] font-normal">{g.labelEn}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Mobile Number with keypad focus */}
            <ClayInput
              label="मोबाइल नंबर / Mobile Number"
              placeholder="10 अंकों का नंबर"
              type="text"
              value={mobile}
              onFocus={() => setActiveKeypadField('mobile')}
              readOnly
              error={errors.mobile}
              required
              icon={<Phone className="w-5 h-5" />}
            />

            {/* District & State */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <ClayInput
                label="जिला / District"
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                icon={<MapPin className="w-5 h-5" />}
              />
              <ClayInput
                label="राज्य / State"
                value={state}
                onChange={(e) => setState(e.target.value)}
                icon={<MapPin className="w-5 h-5" />}
              />
            </div>
          </ClayCard>
        </div>

        {/* Right Column: Keypad & Action */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <ClayCard className="p-4">
            <div className="flex items-center justify-between mb-2 px-1">
              <span className="text-caption font-bold text-teak-grey">
                {activeKeypadField === 'age'
                  ? 'आयु दर्ज करें (Age Keypad)'
                  : activeKeypadField === 'mobile'
                  ? 'मोबाइल नंबर दर्ज करें (Mobile Keypad)'
                  : 'टच कीपैड (Touch to Enter)'}
              </span>
              <span className="text-xs text-haritaki-deep bg-cream-warm px-2 py-0.5 rounded-pill border border-haritaki-gold/40">
                {activeKeypadField ? 'सक्रिय / Active' : 'फ़ील्ड चुनें / Tap Input'}
              </span>
            </div>

            <ClayKeypad
              onKeyPress={handleKeypadPress}
              onDelete={handleKeypadDelete}
              onClear={handleKeypadClear}
            />
          </ClayCard>

          <ClayButton
            variant="primary-gold"
            size="touch"
            onClick={handleSubmit}
            loading={loading}
            className="w-full shadow-btn-gold"
          >
            <span className="flex items-center justify-center gap-2">
              <span>सहमति पृष्ठ पर जाएं / Proceed to Consent</span>
              <ArrowRight className="w-5 h-5" />
            </span>
          </ClayButton>
        </div>
      </div>
    </div>
  );
}
