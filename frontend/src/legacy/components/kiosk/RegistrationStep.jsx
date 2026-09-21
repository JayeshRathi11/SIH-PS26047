import React, { useState } from 'react';
import { User, Phone, ShieldCheck, HeartPulse, Globe, ArrowRight, UserCheck } from 'lucide-react';

const LANGUAGES = [
  { code: 'hi', label: 'हिंदी (Hindi)', flag: '🇮🇳' },
  { code: 'en', label: 'English', flag: '🌐' },
  { code: 'mr', label: 'मराठी (Marathi)', flag: '🇮🇳' },
  { code: 'bn', label: 'বাংলা (Bengali)', flag: '🇮🇳' },
  { code: 'ta', label: 'தமிழ் (Tamil)', flag: '🇮🇳' }
];

const GENDERS = [
  { value: 'MALE', label: 'पुरुष / Male' },
  { value: 'FEMALE', label: 'महिला / Female' },
  { value: 'OTHER', label: 'अन्य / Other' }
];

export default function RegistrationStep({ onComplete, initialData = {} }) {
  const [formData, setFormData] = useState({
    name: initialData.name || '',
    age: initialData.age || '',
    gender: initialData.gender || 'FEMALE',
    phone: initialData.phone || '',
    emergency_contact_phone: initialData.emergency_contact_phone || '',
    language: initialData.language || 'hi'
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = () => {
    const errs = {};
    if (!formData.name.trim()) errs.name = 'नाम आवश्यक है / Name is required';
    if (!formData.age || isNaN(formData.age) || formData.age < 1 || formData.age > 125) {
      errs.age = 'कृपया मान्य आयु दर्ज करें (1-125) / Valid age required';
    }
    if (!formData.phone || !/^\d{10}$/.test(formData.phone.replace(/\D/g, ''))) {
      errs.phone = '10 अंकों का मोबाइल नंबर दर्ज करें / 10-digit phone required';
    }
    if (formData.emergency_contact_phone && !/^\d{10}$/.test(formData.emergency_contact_phone.replace(/\D/g, ''))) {
      errs.emergency_contact_phone = '10 अंकों का मान्य आपातकालीन नंबर / 10-digit phone required';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      // Call patient registration endpoint
      const res = await fetch('/api/patients/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name.trim(),
          age: parseInt(formData.age, 10),
          gender: formData.gender,
          phone: formData.phone.trim(),
          emergency_contact_phone: formData.emergency_contact_phone.trim() || null
        })
      });

      if (!res.ok) {
        throw new Error('Registration failed');
      }

      const patient = await res.json();
      onComplete({ ...patient, language: formData.language });
    } catch (err) {
      console.warn('Backend offline or failed, proceeding with local patient state for kiosk flow:', err);
      // Fallback for standalone kiosk demo mode
      onComplete({
        id: 'patient-local-' + Date.now(),
        ...formData,
        age: parseInt(formData.age, 10)
      });
    } finally {
      setIsSubmitting(false);
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
                <HeartPulse className="w-7 h-7 text-ayush-accent" />
              </div>
              <div>
                <h2 className="text-2xl sm:text-3xl font-bold font-serif">
                  रोगी पंजीकरण / Patient Registration
                </h2>
                <p className="text-emerald-100 text-sm mt-1">
                  आयुष स्वास्थ्य कियोस्क • Welcome to MediKiosk
                </p>
              </div>
            </div>
            <div className="hidden sm:flex items-center gap-2 bg-white/10 px-3 py-1.5 rounded-full border border-white/20 text-xs">
              <ShieldCheck className="w-4 h-4 text-emerald-300" />
              <span>DPDP 2023 Compliant</span>
            </div>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 sm:p-8 space-y-6">
          {/* Language Selection */}
          <div>
            <label className="block text-sm font-semibold text-stone-700 mb-2 flex items-center gap-2">
              <Globe className="w-4 h-4 text-ayush-primary" />
              भाषा चुनें / Select Preferred Language
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => setFormData({ ...formData, language: lang.code })}
                  className={`min-h-[48px] px-3 py-2 rounded-xl border text-sm font-medium flex items-center justify-center gap-2 transition-all ${
                    formData.language === lang.code
                      ? 'bg-ayush-primary text-white border-ayush-primary shadow-sm ring-2 ring-ayush-primary/30'
                      : 'bg-stone-50 text-stone-700 border-stone-200 hover:bg-stone-100'
                  }`}
                >
                  <span>{lang.flag}</span>
                  <span>{lang.label.split(' ')[0]}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Patient Name */}
            <div>
              <label className="block text-sm font-semibold text-stone-700 mb-1.5 flex items-center gap-2">
                <User className="w-4 h-4 text-ayush-primary" />
                रोगी का नाम / Full Name *
              </label>
              <input
                type="text"
                placeholder="उदा. राजेश कुमार / e.g. Rajesh Kumar"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className={`w-full min-h-[48px] px-4 py-2.5 rounded-xl border text-base transition-all focus:outline-none focus:ring-2 ${
                  errors.name
                    ? 'border-rose-400 focus:ring-rose-200 bg-rose-50/30'
                    : 'border-stone-300 focus:ring-ayush-primary/30 focus:border-ayush-primary'
                }`}
              />
              {errors.name && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.name}</p>}
            </div>

            {/* Age */}
            <div>
              <label className="block text-sm font-semibold text-stone-700 mb-1.5 flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-ayush-primary" />
                आयु / Age (वर्ष / Years) *
              </label>
              <input
                type="number"
                min="1"
                max="125"
                placeholder="उदा. 45 / e.g. 45"
                value={formData.age}
                onChange={(e) => setFormData({ ...formData, age: e.target.value })}
                className={`w-full min-h-[48px] px-4 py-2.5 rounded-xl border text-base transition-all focus:outline-none focus:ring-2 ${
                  errors.age
                    ? 'border-rose-400 focus:ring-rose-200 bg-rose-50/30'
                    : 'border-stone-300 focus:ring-ayush-primary/30 focus:border-ayush-primary'
                }`}
              />
              {errors.age && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.age}</p>}
            </div>

            {/* Gender */}
            <div className="sm:col-span-2">
              <label className="block text-sm font-semibold text-stone-700 mb-1.5">
                लिंग / Gender *
              </label>
              <div className="grid grid-cols-3 gap-3">
                {GENDERS.map((g) => (
                  <button
                    key={g.value}
                    type="button"
                    onClick={() => setFormData({ ...formData, gender: g.value })}
                    className={`min-h-[48px] px-4 py-2.5 rounded-xl border font-medium text-sm transition-all ${
                      formData.gender === g.value
                        ? 'bg-ayush-primary text-white border-ayush-primary shadow-sm ring-2 ring-ayush-primary/30'
                        : 'bg-stone-50 text-stone-700 border-stone-200 hover:bg-stone-100'
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Phone Number */}
            <div>
              <label className="block text-sm font-semibold text-stone-700 mb-1.5 flex items-center gap-2">
                <Phone className="w-4 h-4 text-ayush-primary" />
                मोबाइल नंबर / Mobile Number *
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400 font-medium text-sm">
                  +91
                </span>
                <input
                  type="tel"
                  maxLength={10}
                  placeholder="9876543210"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value.replace(/\D/g, '') })}
                  className={`w-full min-h-[48px] pl-12 pr-4 py-2.5 rounded-xl border text-base font-mono transition-all focus:outline-none focus:ring-2 ${
                    errors.phone
                      ? 'border-rose-400 focus:ring-rose-200 bg-rose-50/30'
                      : 'border-stone-300 focus:ring-ayush-primary/30 focus:border-ayush-primary'
                  }`}
                />
              </div>
              {errors.phone && <p className="text-xs text-rose-600 mt-1 font-medium">{errors.phone}</p>}
            </div>

            {/* Emergency Contact Phone */}
            <div>
              <label className="block text-sm font-semibold text-stone-700 mb-1.5 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-amber-600" />
                आपातकालीन संपर्क / Emergency Contact (वैकल्पिक)
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400 font-medium text-sm">
                  +91
                </span>
                <input
                  type="tel"
                  maxLength={10}
                  placeholder="8765432109"
                  value={formData.emergency_contact_phone}
                  onChange={(e) => setFormData({ ...formData, emergency_contact_phone: e.target.value.replace(/\D/g, '') })}
                  className={`w-full min-h-[48px] pl-12 pr-4 py-2.5 rounded-xl border text-base font-mono transition-all focus:outline-none focus:ring-2 ${
                    errors.emergency_contact_phone
                      ? 'border-rose-400 focus:ring-rose-200 bg-rose-50/30'
                      : 'border-stone-300 focus:ring-ayush-primary/30 focus:border-ayush-primary'
                  }`}
                />
              </div>
              {errors.emergency_contact_phone && (
                <p className="text-xs text-rose-600 mt-1 font-medium">{errors.emergency_contact_phone}</p>
              )}
            </div>
          </div>

          {/* Action Submit */}
          <div className="pt-4 border-t border-stone-200 flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting}
              className="min-h-[52px] w-full sm:w-auto px-8 py-3 bg-ayush-primary hover:bg-ayush-primary-dark text-white rounded-xl font-bold text-base shadow-lg shadow-ayush-primary/20 flex items-center justify-center gap-3 transition-all transform active:scale-95 disabled:opacity-50"
            >
              <span>आगे बढ़ें / Proceed to Consent</span>
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
