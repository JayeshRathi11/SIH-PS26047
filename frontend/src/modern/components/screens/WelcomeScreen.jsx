import React from 'react';
import { ArrowRight, Sparkles, UserCheck, Stethoscope, FileText, Ticket, HelpCircle } from 'lucide-react';
import { useKioskSession } from '../../context/KioskSessionContext';
import ClayButton from '../atoms/ClayButton';
import ClayCard from '../atoms/ClayCard';

export default function WelcomeScreen({ onBegin }) {
  const { language } = useKioskSession();

  const content = {
    en: {
      sub: "All India Institute of Ayurveda — New Delhi",
      title: "Welcome to AIIA OPD Check-in",
      desc: "Get your OPD consultation token quickly in 4 easy steps. Our Dr. Charaka AI assistant will help you prepare your chief complaints and Ayurvedic health records before seeing the doctor.",
      steps: [
        { num: 1, title: "Identity Check", desc: "Scan ABHA QR code or enter mobile number", icon: UserCheck },
        { num: 2, title: "AI Doctor Interview", desc: "Speak or tap your symptoms in your own language", icon: Stethoscope },
        { num: 3, title: "Records & OCR", desc: "Scan old prescriptions or lab test reports", icon: FileText },
        { num: 4, title: "OPD Queue Token", desc: "Receive consultation room & token slip", icon: Ticket }
      ],
      ctaHeading: "Begin Your Registration",
      ctaSub: "Touch the button below to start",
      btnText: "Begin / प्रारंभ करें",
      helpdesk: "Hospital Sahayak staff available at Helpdesk 1"
    },
    hi: {
      sub: "अखिल भारतीय आयुर्वेद संस्थान — नई दिल्ली",
      title: "AIIA ओपीडी में आपका स्वागत है",
      desc: "केवल 4 आसान चरणों में अपना ओपीडी परामर्श टोकन प्राप्त करें। डॉक्टर से मिलने से पहले हमारा डॉ. चरक एआई सहायक आपकी समस्याओं और स्वास्थ्य रिकॉर्ड को दर्ज करने में मदद करेगा।",
      steps: [
        { num: 1, title: "पहचान सत्यापन", desc: "आभा (ABHA) क्यूआर स्कैन करें या मोबाइल नंबर दर्ज करें", icon: UserCheck },
        { num: 2, title: "एआई डॉक्टर साक्षात्कार", desc: "अपनी भाषा में बोलकर या चुनकर लक्षण बताएं", icon: Stethoscope },
        { num: 3, title: "दस्तावेज व रिपोर्ट", desc: "पुराने पर्चे या लैब रिपोर्ट स्कैन करें", icon: FileText },
        { num: 4, title: "ओपीडी कतार टोकन", desc: "कमरा नंबर और परामर्श टोकन पर्ची प्राप्त करें", icon: Ticket }
      ],
      ctaHeading: "पंजीकरण शुरू करें",
      ctaSub: "शुरू करने के लिए नीचे दिए गए बटन को दबाएं",
      btnText: "प्रारंभ करें / Begin",
      helpdesk: "हेल्पडेस्क 1 पर अस्पताल सहायक कर्मचारी उपलब्ध हैं"
    },
    mr: {
      sub: "अखिल भारतीय आयुर्वेद संस्था — नवी दिल्ली",
      title: "AIIA ओपीडी मध्ये आपले स्वागत आहे",
      desc: "फक्त 4 सोप्या चरणांमध्ये आपले ओपीडी टोकन मिळवा. डॉक्टरांना भेटण्यापूर्वी आमचा डॉ. चरक एआय सहाय्यक आपल्या तक्रारी नोंदविण्यात मदत करेल.",
      steps: [
        { num: 1, title: "ओळख पडताळणी", desc: "आभा क्यूआर कोड स्कॅन करा किंवा मोबाइल नंबर टाका", icon: UserCheck },
        { num: 2, title: "एआई डॉक्टर संवाद", desc: "आपल्या भाषेत लक्षणे सांगा किंवा निवडा", icon: Stethoscope },
        { num: 3, title: "कागदपत्रे आणि अहवाल", desc: "जुनी प्रिस्क्रिप्शन किंवा लॅब रिपोर्ट स्कॅन करा", icon: FileText },
        { num: 4, title: "ओपीडी टोकन", desc: "सल्लागार कक्ष क्रमांक व टोकन स्लिप मिळवा", icon: Ticket }
      ],
      ctaHeading: "नोंदणी सुरू करा",
      ctaSub: "सुरू करण्यासाठी खालील बटण दाबा",
      btnText: "सुरू करा / Begin",
      helpdesk: "मदत कक्ष 1 वर रुग्ण सहाय्यक उपलब्ध आहेत"
    }
  };

  const t = content[language] || content.en;

  return (
    <div className="flex-1 flex flex-col justify-center max-w-5xl mx-auto w-full py-4">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left Column: Welcome Info & 4 Steps */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          <div>
            <span className="inline-block text-caption font-bold text-haritaki-deep bg-cream-warm px-3.5 py-1 rounded-pill border border-haritaki-gold/30 mb-3">
              {t.sub}
            </span>
            <h2 className="font-display font-extrabold text-hero text-teak-grey leading-tight mb-3">
              {t.title}
            </h2>
            <p className="text-body text-teak-muted font-body leading-relaxed">
              {t.desc}
            </p>
          </div>

          {/* 4 Journey Steps Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            {t.steps.map((step) => {
              const IconComponent = step.icon;
              return (
                <ClayCard key={step.num} className="p-4 flex items-start gap-3.5">
                  <div className="w-9 h-9 rounded-full bg-cream-warm border border-haritaki-gold text-haritaki-deep font-display font-bold text-caption flex items-center justify-center flex-shrink-0 shadow-sm">
                    {step.num}
                  </div>
                  <div>
                    <h3 className="font-display font-bold text-btn-sec text-teak-grey mb-1">
                      {step.title}
                    </h3>
                    <p className="text-caption text-teak-muted leading-snug">
                      {step.desc}
                    </p>
                  </div>
                </ClayCard>
              );
            })}
          </div>
        </div>

        {/* Right Column: Interactive Start CTA Card */}
        <div className="lg:col-span-5">
          <ClayCard elevated className="p-8 flex flex-col items-center text-center gap-6 border-2 border-copper-border">
            {/* Pulsing Central Icon */}
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-haritaki-gold/25 to-haritaki-gold/10 border-2 border-haritaki-gold flex items-center justify-center text-haritaki-deep shadow-pill">
              <Sparkles className="w-10 h-10 text-haritaki-gold animate-pulse" />
            </div>

            {/* Active Status Badge */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-pill bg-herbal-green/10 border border-herbal-green/30 text-herbal-green text-caption font-semibold">
              <span className="w-2.5 h-2.5 rounded-full bg-herbal-green animate-ping" />
              <span>AIIA Central OPD Kiosk Active</span>
            </div>

            <div>
              <h3 className="font-display font-bold text-heading text-teak-grey mb-1">
                {t.ctaHeading}
              </h3>
              <p className="text-caption text-teak-muted">
                {t.ctaSub}
              </p>
            </div>

            {/* Main Begin CTA */}
            <ClayButton
              variant="primary-gold"
              size="touch"
              onClick={onBegin}
              className="w-full text-heading shadow-btn-gold py-4"
            >
              <span className="flex items-center justify-center gap-3">
                <span>{t.btnText}</span>
                <ArrowRight className="w-6 h-6 stroke-[2.5]" />
              </span>
            </ClayButton>

            {/* Helpdesk Notice */}
            <div className="flex items-center gap-2 text-caption text-teak-muted pt-2 border-t border-copper-border/40 w-full justify-center">
              <HelpCircle className="w-4 h-4 text-haritaki-deep flex-shrink-0" />
              <span>{t.helpdesk}</span>
            </div>
          </ClayCard>
        </div>
      </div>
    </div>
  );
}
