from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.language import Language, ClinicalOntologyFieldTranslation

DEFAULT_LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English", "is_active": True},
    {"code": "hi", "name": "Hindi", "native_name": "हिन्दी", "is_active": True},
    {"code": "mr", "name": "Marathi", "native_name": "मराठी", "is_active": True},
]

DEFAULT_TRANSLATIONS = [
    # 1. Chief Complaint
    {
        "field_key": "chief_complaint",
        "language_code": "en",
        "display_name": "Primary Symptoms / Chief Complaint",
        "description": "The main medical problem, symptom, or concern that brought the patient to the kiosk.",
    },
    {
        "field_key": "chief_complaint",
        "language_code": "hi",
        "display_name": "मुख्य शिकायत / प्राथमिक लक्षण",
        "description": "मुख्य स्वास्थ्य समस्या, लक्षण या तकलीफ जिसके लिए मरीज कियोस्क पर आया है।",
    },
    {
        "field_key": "chief_complaint",
        "language_code": "mr",
        "display_name": "मुख्य तक्रार / प्राथमिक लक्षणे",
        "description": "मुख्य आरोग्य समस्या, लक्षण किंवा त्रास ज्यासाठी रुग्ण किऑस्कवर आला आहे.",
    },
    # 2. HPI Onset & Duration
    {
        "field_key": "hpi_onset_duration",
        "language_code": "en",
        "display_name": "Onset and Duration",
        "description": "When the symptom started, how long it has been present, and progression over time.",
    },
    {
        "field_key": "hpi_onset_duration",
        "language_code": "hi",
        "display_name": "शुरुआत और अवधि",
        "description": "लक्षण कब शुरू हुआ, कितने समय से है, और समय के साथ कैसे बढ़ या बदल रहा है।",
    },
    {
        "field_key": "hpi_onset_duration",
        "language_code": "mr",
        "display_name": "सुरुवात आणि कालावधी",
        "description": "लक्षणे कधी सुरू झाली, किती दिवसांपासून आहेत आणि वेळेनुसार कशी बदलत आहेत.",
    },
    # 3. HPI Characteristics
    {
        "field_key": "hpi_characteristics",
        "language_code": "en",
        "display_name": "Symptom Severity and Characteristics",
        "description": "Quality, intensity, exact anatomical site, radiation, and aggravating or relieving factors.",
    },
    {
        "field_key": "hpi_characteristics",
        "language_code": "hi",
        "display_name": "लक्षण की तीव्रता और विशेषताएं",
        "description": "दर्द या परेशानी का प्रकार, गंभीरता, सटीक स्थान, और किन कारणों से आराम या बढ़ोतरी होती है।",
    },
    {
        "field_key": "hpi_characteristics",
        "language_code": "mr",
        "display_name": "लक्षण तीव्रता आणि स्वरूप",
        "description": "त्रासाचे स्वरूप, तीव्रता, नेमके ठिकाण आणि कशामुळे आराम मिळतो किंवा त्रास वाढतो.",
    },
    # 4. Past Medical History
    {
        "field_key": "past_medical_history",
        "language_code": "en",
        "display_name": "Past Medical Conditions",
        "description": "Known chronic illnesses (e.g. Hypertension, Diabetes, Asthma, Heart disease, TB).",
    },
    {
        "field_key": "past_medical_history",
        "language_code": "hi",
        "display_name": "पिछला चिकित्सकीय इतिहास",
        "description": "पूर्व-मौजूदा पुरानी बीमारियां (जैसे उच्च रक्तचाप, मधुमेह, दमा, हृदय रोग, टीबी)।",
    },
    {
        "field_key": "past_medical_history",
        "language_code": "mr",
        "display_name": "मागील वैद्यकीय इतिहास",
        "description": "पूर्वीचे जुनाट आजार (जसे की उच्च रक्तदाब, मधुमेह, दमा, हृदयरोग, टीबी).",
    },
    # 5. Past Surgical History
    {
        "field_key": "past_surgical_history",
        "language_code": "en",
        "display_name": "Past Surgeries and Hospitalizations",
        "description": "Previous major surgeries, operations, or hospital admissions.",
    },
    {
        "field_key": "past_surgical_history",
        "language_code": "hi",
        "display_name": "पिछली सर्जरी और अस्पताल में भर्ती",
        "description": "पूर्व में हुआ कोई बड़ा ऑपरेशन, सर्जरी या अस्पताल में भर्ती होने का इतिहास।",
    },
    {
        "field_key": "past_surgical_history",
        "language_code": "mr",
        "display_name": "मागील शस्त्रक्रिया आणि हॉस्पिटलायझेशन",
        "description": "पूर्वी झालेली कोणतीही मोठी शस्त्रक्रिया, ऑपरेशन किंवा रुग्णालयात दाखल झाल्याचा इतिहास.",
    },
    # 6. Current Medications
    {
        "field_key": "current_medications",
        "language_code": "en",
        "display_name": "Current Medications",
        "description": "Prescription medications, OTC drugs, insulin, Ayurvedic or home remedies currently taken.",
    },
    {
        "field_key": "current_medications",
        "language_code": "hi",
        "display_name": "वर्तमान में ली जा रही दवाइयां",
        "description": "वर्तमान में ली जाने वाली डॉक्टर की दवाइयां, बिना पर्चे की दवाइयां, इंसुलिन, आयुर्वेदिक या घरेलू उपचार।",
    },
    {
        "field_key": "current_medications",
        "language_code": "mr",
        "display_name": "सध्या चालू असलेली औषधे",
        "description": "सध्या घेत असलेली डॉक्टरांची औषधे, नेहमीची औषधे, इन्सुलिन, आयुर्वेदिक किंवा घरगुती उपचार.",
    },
    # 7. Allergy History
    {
        "field_key": "allergy_history",
        "language_code": "en",
        "display_name": "Known Allergies",
        "description": "Allergies to medications (e.g. Penicillin, Sulfa), foods, or environmental triggers.",
    },
    {
        "field_key": "allergy_history",
        "language_code": "hi",
        "display_name": "एलर्जी का इतिहास",
        "description": "दवाइयों (जैसे पेनिसिलिन, सल्फा), खाद्य पदार्थों या अन्य चीजों से होने वाली किसी भी प्रकार की एलर्जी।",
    },
    {
        "field_key": "allergy_history",
        "language_code": "mr",
        "display_name": "ॲलर्जीचा इतिहास",
        "description": "औषधे (उदा. पेनिसिलिन, सल्फा), अन्नपदार्थ किंवा इतर घटकांपासून होणारी कोणतीही ॲलर्जी.",
    },
    # 8. Family Medical History
    {
        "field_key": "family_medical_history",
        "language_code": "en",
        "display_name": "Family Medical History",
        "description": "Hereditary or familial health conditions in immediate blood relatives.",
    },
    {
        "field_key": "family_medical_history",
        "language_code": "hi",
        "display_name": "पारिवारिक स्वास्थ्य इतिहास",
        "description": "परिवार के निकटतम रक्त संबंधियों में वंशानुगत या गंभीर बीमारियों का इतिहास।",
    },
    {
        "field_key": "family_medical_history",
        "language_code": "mr",
        "display_name": "कौटुंबिक वैद्यकीय इतिहास",
        "description": "कुटुंबातील जवळच्या नातेवाईकांमधील आनुवंशिक किंवा गंभीर आजारांचा इतिहास.",
    },
    # 9. Personal / Lifestyle History
    {
        "field_key": "personal_lifestyle_history",
        "language_code": "en",
        "display_name": "Personal and Lifestyle Habits",
        "description": "Tobacco/beedi use, alcohol consumption, dietary patterns, and occupational exposures.",
    },
    {
        "field_key": "personal_lifestyle_history",
        "language_code": "hi",
        "display_name": "व्यक्तिगत आदतें और जीवनशैली",
        "description": "तंबाकू/बीड़ी का सेवन, मदिरापान, खान-पान की आदतें और कार्यस्थल से जुड़े जोखिम।",
    },
    {
        "field_key": "personal_lifestyle_history",
        "language_code": "mr",
        "display_name": "वैयक्तिक सवयी आणि जीवनशैली",
        "description": "तंबाखू/बिडीचे सेवन, मद्यपान, आहाराच्या सवयी आणि कामाच्या ठिकाणचे वातावरण.",
    },
    # 10. Review of Systems
    {
        "field_key": "review_of_systems",
        "language_code": "en",
        "display_name": "Systemic Review of Associated Symptoms",
        "description": "General systemic checks including fever, chills, unexplained weight loss, night sweats, or fatigue.",
    },
    {
        "field_key": "review_of_systems",
        "language_code": "hi",
        "display_name": "संबंधित अन्य शारीरिक लक्षण",
        "description": "सामान्य शारीरिक लक्षण जैसे बुखार, कंपकंपी, अकारण वजन घटना, रात में पसीना या अत्यधिक थकान।",
    },
    {
        "field_key": "review_of_systems",
        "language_code": "mr",
        "display_name": "इतर संबंधित शारीरिक लक्षणे",
        "description": "सामान्य शारीरिक लक्षणे जसे की ताप, थंडी वाजणे, अकारण वजन कमी होणे, रात्री घाम येणे किंवा थकवा.",
    },
]


class LanguageRepository:
    def get_active_languages(self, db: Session) -> List[Language]:
        return db.query(Language).filter(Language.is_active == True).order_by(Language.id.asc()).all()

    def get_by_code(self, db: Session, code: str) -> Optional[Language]:
        return db.query(Language).filter(Language.code == code).first()

    def is_valid_active_code(self, db: Session, code: str) -> bool:
        lang = self.get_by_code(db, code)
        return lang is not None and lang.is_active

    def seed_default_languages(self, db: Session) -> None:
        for lang_data in DEFAULT_LANGUAGES:
            existing = self.get_by_code(db, lang_data["code"])
            if not existing:
                db_lang = Language(**lang_data)
                db.add(db_lang)
        db.commit()


class ClinicalOntologyTranslationRepository:
    def get_translation(
        self, db: Session, field_key: str, language_code: str
    ) -> Optional[ClinicalOntologyFieldTranslation]:
        return (
            db.query(ClinicalOntologyFieldTranslation)
            .filter(
                ClinicalOntologyFieldTranslation.field_key == field_key,
                ClinicalOntologyFieldTranslation.language_code == language_code,
            )
            .first()
        )

    def get_translations_for_interview(
        self, db: Session, language_code: str
    ) -> Dict[str, ClinicalOntologyFieldTranslation]:
        translations = (
            db.query(ClinicalOntologyFieldTranslation)
            .filter(ClinicalOntologyFieldTranslation.language_code == language_code)
            .all()
        )
        return {t.field_key: t for t in translations}

    def seed_default_translations(self, db: Session) -> None:
        for t_data in DEFAULT_TRANSLATIONS:
            existing = self.get_translation(db, t_data["field_key"], t_data["language_code"])
            if not existing:
                trans = ClinicalOntologyFieldTranslation(**t_data)
                db.add(trans)
        db.commit()


language_repository = LanguageRepository()
ontology_translation_repository = ClinicalOntologyTranslationRepository()
