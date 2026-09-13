"""add_ayush_mode

Revision ID: a4d65305f5fa
Revises: f2b78f26bb93
Create Date: 2026-09-13 16:50:44.784926

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d65305f5fa'
down_revision: Union[str, Sequence[str], None] = 'f2b78f26bb93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AYUSH_ONTOLOGY_FIELDS = [
    # Prakriti
    {
        "field_key": "prakriti_observation",
        "section": "Prakriti",
        "display_name": "Prakriti Observations",
        "description": "Patient-reported observations and physical-mental constitution tendencies for clinical assessment.",
        "required": True,
        "priority": 110,
        "active": True,
    },
    # Vikriti
    {
        "field_key": "vikriti_observation",
        "section": "Vikriti",
        "display_name": "Vikriti Observations",
        "description": "Current physiological and functional disturbance observations reported by patient.",
        "required": True,
        "priority": 120,
        "active": True,
    },
    # Agni
    {
        "field_key": "agni_observation",
        "section": "Agni",
        "display_name": "Digestive and Metabolic Observations",
        "description": "Patient-reported appetite patterns, digestion speed, and post-meal comfort.",
        "required": True,
        "priority": 130,
        "active": True,
    },
    {
        "field_key": "agni_type",
        "section": "Agni",
        "display_name": "Agni State / Type",
        "description": "Reported digestive fire nature (e.g., Vishama, Tikshna, Manda, Sama) as described by patient.",
        "required": False,
        "priority": 135,
        "active": True,
    },
    # Koshtha
    {
        "field_key": "koshtha_observation",
        "section": "Koshtha",
        "display_name": "Bowel and Elimination Observations",
        "description": "Patient-reported bowel movement frequency, regularity, and stool consistency.",
        "required": True,
        "priority": 140,
        "active": True,
    },
    {
        "field_key": "koshtha_type",
        "section": "Koshtha",
        "display_name": "Koshtha Nature / Bowel Tendency",
        "description": "Reported bowel habit tendency (e.g., Krura, Madhyama, Mridu) as described by patient.",
        "required": False,
        "priority": 145,
        "active": True,
    },
    # Dashavidha Pariksha
    {
        "field_key": "dashavidha_prakriti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Prakriti (Body Constitution)",
        "description": "Assessment of physical and mental constitution within Dashavidha Pariksha.",
        "required": False,
        "priority": 150,
        "active": True,
    },
    {
        "field_key": "dashavidha_vikriti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Vikriti (Morbidity/Pathology)",
        "description": "Assessment of disease diathesis and pathological state.",
        "required": False,
        "priority": 151,
        "active": True,
    },
    {
        "field_key": "dashavidha_sara",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Sara (Tissue Essence / Excellence)",
        "description": "Evaluation of structural and functional quality of tissues.",
        "required": False,
        "priority": 152,
        "active": True,
    },
    {
        "field_key": "dashavidha_samhanana",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Samhanana (Body Build / Compactness)",
        "description": "Evaluation of skeletal structure and body symmetry/compactness.",
        "required": False,
        "priority": 153,
        "active": True,
    },
    {
        "field_key": "dashavidha_pramana",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Pramana (Anthropometric Measurements)",
        "description": "Body proportions, height, and physical measurements.",
        "required": False,
        "priority": 154,
        "active": True,
    },
    {
        "field_key": "dashavidha_satmya",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Satmya (Habituation / Adaptability)",
        "description": "Substances, dietary items, and climates well tolerated by the patient.",
        "required": False,
        "priority": 155,
        "active": True,
    },
    {
        "field_key": "dashavidha_satva",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Satva (Mental Strength / Resilience)",
        "description": "Psychological tolerance, mental fortitude, and stress coping capacity.",
        "required": False,
        "priority": 156,
        "active": True,
    },
    {
        "field_key": "dashavidha_ahara_shakti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Ahara Shakti (Digestive Capacity)",
        "description": "Capacity to ingest (Abhyavaharana) and digest (Jarana) food.",
        "required": False,
        "priority": 157,
        "active": True,
    },
    {
        "field_key": "dashavidha_vyayama_shakti",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Vyayama Shakti (Physical Work Capacity)",
        "description": "Endurance, exercise tolerance, and physical work capacity.",
        "required": False,
        "priority": 158,
        "active": True,
    },
    {
        "field_key": "dashavidha_vaya",
        "section": "Dashavidha Pariksha",
        "display_name": "Dashavidha - Vaya (Age / Chronological Stage)",
        "description": "Age category and related metabolic stage of life.",
        "required": False,
        "priority": 159,
        "active": True,
    },
    # Ahara
    {
        "field_key": "ahara_pattern",
        "section": "Ahara",
        "display_name": "Dietary Pattern and Timing",
        "description": "Meal timings, meal frequency, snacking habits, and eating schedule.",
        "required": False,
        "priority": 160,
        "active": True,
    },
    {
        "field_key": "ahara_preferences",
        "section": "Ahara",
        "display_name": "Taste and Food Preferences",
        "description": "Preference for specific tastes (Rasa), temperatures (hot/cold), and food types.",
        "required": False,
        "priority": 165,
        "active": True,
    },
    {
        "field_key": "ahara_restrictions",
        "section": "Ahara",
        "display_name": "Dietary Restrictions and Incompatibilities",
        "description": "Food intolerances, cultural dietary restrictions, or incompatible foods.",
        "required": False,
        "priority": 170,
        "active": True,
    },
    # Vihara
    {
        "field_key": "vihara_activity",
        "section": "Vihara",
        "display_name": "Physical Activity and Lifestyle",
        "description": "Daily physical exercise, posture, occupational routines, and sedentary time.",
        "required": False,
        "priority": 180,
        "active": True,
    },
    {
        "field_key": "sleep_pattern",
        "section": "Vihara",
        "display_name": "Sleep Pattern (Nidra)",
        "description": "Sleep duration, daytime sleeping, quality of rest, and insomnia tendencies.",
        "required": False,
        "priority": 185,
        "active": True,
    },
    {
        "field_key": "daily_routine",
        "section": "Vihara",
        "display_name": "Daily Regimen (Dinacharya)",
        "description": "Waking schedule, relaxation, and daily habit routines.",
        "required": False,
        "priority": 190,
        "active": True,
    },
]

AYUSH_TRANSLATIONS = [
    # 1. prakriti_observation
    {
        "field_key": "prakriti_observation",
        "language_code": "en",
        "display_name": "Prakriti Observations",
        "description": "Patient-reported observations and physical-mental constitution tendencies for clinical assessment.",
    },
    {
        "field_key": "prakriti_observation",
        "language_code": "hi",
        "display_name": "प्रकृति अवलोकन",
        "description": "चिकित्सीय मूल्यांकन हेतु रोगी द्वारा बताई गई शारीरिक और मानसिक प्रकृति की प्रवृत्तियाँ।",
    },
    {
        "field_key": "prakriti_observation",
        "language_code": "mr",
        "display_name": "प्रकृती निरीक्षण",
        "description": "वैद्यकीय मूल्यांकनासाठी रुग्णाने सांगितलेली शारीरिक व मानसिक प्रकृतीची लक्षणे व प्रवृत्ती.",
    },
    # 2. vikriti_observation
    {
        "field_key": "vikriti_observation",
        "language_code": "en",
        "display_name": "Vikriti Observations",
        "description": "Current physiological and functional disturbance observations reported by patient.",
    },
    {
        "field_key": "vikriti_observation",
        "language_code": "hi",
        "display_name": "विकृति अवलोकन",
        "description": "रोगी द्वारा बताए गए वर्तमान शारीरिक और क्रियात्मक दोष असंतुलन के लक्षण।",
    },
    {
        "field_key": "vikriti_observation",
        "language_code": "mr",
        "display_name": "विकृती निरीक्षण",
        "description": "रुग्णाने नोंदवलेली सध्याची शारीरिक आणि कार्यात्मक दोषांची असंतुलन लक्षणे.",
    },
    # 3. agni_observation
    {
        "field_key": "agni_observation",
        "language_code": "en",
        "display_name": "Digestive and Metabolic Observations",
        "description": "Patient-reported appetite patterns, digestion speed, and post-meal comfort.",
    },
    {
        "field_key": "agni_observation",
        "language_code": "hi",
        "display_name": "अग्नि व पाचन अवलोकन",
        "description": "रोगी द्वारा बताई गई भूख की स्थिति, पाचन गति और भोजन के बाद की स्थिति।",
    },
    {
        "field_key": "agni_observation",
        "language_code": "mr",
        "display_name": "अग्नी व पचन निरीक्षण",
        "description": "रुग्णाने नोंदवलेली भूक, पचनाचा वेग आणि जेवणानंतरचे पचन स्वास्थ्य.",
    },
    # 4. agni_type
    {
        "field_key": "agni_type",
        "language_code": "en",
        "display_name": "Agni State / Type",
        "description": "Reported digestive fire nature (e.g., Vishama, Tikshna, Manda, Sama) as described by patient.",
    },
    {
        "field_key": "agni_type",
        "language_code": "hi",
        "display_name": "अग्नि का प्रकार",
        "description": "पाचन अग्नि की प्रकृति (जैसे विषम, तीक्ष्ण, मंद, सम) का विवरण।",
    },
    {
        "field_key": "agni_type",
        "language_code": "mr",
        "display_name": "अग्नीचा प्रकार",
        "description": "पचन अग्नीचे स्वरूप (उदा. विषम, तीक्ष्ण, मंद, सम) चे विवरण.",
    },
    # 5. koshtha_observation
    {
        "field_key": "koshtha_observation",
        "language_code": "en",
        "display_name": "Bowel and Elimination Observations",
        "description": "Patient-reported bowel movement frequency, regularity, and stool consistency.",
    },
    {
        "field_key": "koshtha_observation",
        "language_code": "hi",
        "display_name": "कोष्ठ व मल निष्कासन अवलोकन",
        "description": "शौच की आवृत्ति, नियमितता और मल की प्रकृति संबंधी जानकारी।",
    },
    {
        "field_key": "koshtha_observation",
        "language_code": "mr",
        "display_name": "कोष्ठ व मलप्रवृत्ती निरीक्षण",
        "description": "शौचाची वारंवारता, नियमितता आणि मलाचे स्वरूप यासंबंधी निरीक्षण.",
    },
    # 6. koshtha_type
    {
        "field_key": "koshtha_type",
        "language_code": "en",
        "display_name": "Koshtha Nature / Bowel Tendency",
        "description": "Reported bowel habit tendency (e.g., Krura, Madhyama, Mridu) as described by patient.",
    },
    {
        "field_key": "koshtha_type",
        "language_code": "hi",
        "display_name": "कोष्ठ का प्रकार",
        "description": "कोष्ठ की प्रकृति (जैसे क्रूर, मध्यम, मृदु) का विवरण।",
    },
    {
        "field_key": "koshtha_type",
        "language_code": "mr",
        "display_name": "कोष्ठाचा प्रकार",
        "description": "कोष्ठाचे स्वरूप (उदा. क्रूर, मध्यम, मृदू) चे विवरण.",
    },
    # 7. dashavidha_prakriti
    {
        "field_key": "dashavidha_prakriti",
        "language_code": "en",
        "display_name": "Dashavidha - Prakriti (Body Constitution)",
        "description": "Assessment of physical and mental constitution within Dashavidha Pariksha.",
    },
    {
        "field_key": "dashavidha_prakriti",
        "language_code": "hi",
        "display_name": "दशविध - प्रकृति (शारीरिक संविधान)",
        "description": "दशविध परीक्षा अंतर्गत शारीरिक और मानसिक प्रकृति का मूल्यांकन।",
    },
    {
        "field_key": "dashavidha_prakriti",
        "language_code": "mr",
        "display_name": "दशविध - प्रकृती (शारीरिक ठेवण)",
        "description": "दशविध परीक्षेअंतर्गत शारीरिक आणि मानसिक प्रकृतीचे मूल्यमापन.",
    },
    # 8. dashavidha_vikriti
    {
        "field_key": "dashavidha_vikriti",
        "language_code": "en",
        "display_name": "Dashavidha - Vikriti (Morbidity/Pathology)",
        "description": "Assessment of disease diathesis and pathological state.",
    },
    {
        "field_key": "dashavidha_vikriti",
        "language_code": "hi",
        "display_name": "दशविध - विकृति (रोग स्थिति)",
        "description": "दोष असंतुलन एवं रोग की वर्तमान अवस्था का परीक्षण।",
    },
    {
        "field_key": "dashavidha_vikriti",
        "language_code": "mr",
        "display_name": "दशविध - विकृती (रोग स्थिती)",
        "description": "दोष असंतुलन आणि आजाराच्या सद्यस्थितीचे परीक्षण.",
    },
    # 9. dashavidha_sara
    {
        "field_key": "dashavidha_sara",
        "language_code": "en",
        "display_name": "Dashavidha - Sara (Tissue Essence / Excellence)",
        "description": "Evaluation of structural and functional quality of tissues.",
    },
    {
        "field_key": "dashavidha_sara",
        "language_code": "hi",
        "display_name": "दशविध - सार (धातु श्रेष्ठता)",
        "description": "शारीरिक धातुओं की गुणवत्ता और उत्कृष्टता का परीक्षण।",
    },
    {
        "field_key": "dashavidha_sara",
        "language_code": "mr",
        "display_name": "दशविध - सार (धातूंची शुद्धता व सामर्थ्य)",
        "description": "शारीरिक धातूंची गुणवत्ता आणि बळकटीचे मूल्यमापन.",
    },
    # 10. dashavidha_samhanana
    {
        "field_key": "dashavidha_samhanana",
        "language_code": "en",
        "display_name": "Dashavidha - Samhanana (Body Build / Compactness)",
        "description": "Evaluation of skeletal structure and body symmetry/compactness.",
    },
    {
        "field_key": "dashavidha_samhanana",
        "language_code": "hi",
        "display_name": "दशविध - संहनन (शरीर गठन)",
        "description": "शारीरिक अस्थि संरचना और शरीर की सुदृढ़ता का मूल्यांकन।",
    },
    {
        "field_key": "dashavidha_samhanana",
        "language_code": "mr",
        "display_name": "दशविध - संहनन (शरीराची बांधणी)",
        "description": "हाडांची रचना आणि शरीराच्या सुदृढ बांधणीचे मूल्यमापन.",
    },
    # 11. dashavidha_pramana
    {
        "field_key": "dashavidha_pramana",
        "language_code": "en",
        "display_name": "Dashavidha - Pramana (Anthropometric Measurements)",
        "description": "Body proportions, height, and physical measurements.",
    },
    {
        "field_key": "dashavidha_pramana",
        "language_code": "hi",
        "display_name": "दशविध - प्रमाण (शारीरिक माप)",
        "description": "शारीरिक अनुपात, ऊंचाई और माप का मूल्यांकन।",
    },
    {
        "field_key": "dashavidha_pramana",
        "language_code": "mr",
        "display_name": "दशविध - प्रमाण (शारीरिक मोजमाप)",
        "description": "शारीरिक प्रमाण, उंची आणि शरीर मोजमापांचे मूल्यमापन.",
    },
    # 12. dashavidha_satmya
    {
        "field_key": "dashavidha_satmya",
        "language_code": "en",
        "display_name": "Dashavidha - Satmya (Habituation / Adaptability)",
        "description": "Substances, dietary items, and climates well tolerated by the patient.",
    },
    {
        "field_key": "dashavidha_satmya",
        "language_code": "hi",
        "display_name": "दशविध - सात्म्य (अनुकूलता)",
        "description": "रोगी के अनुकूल आहार, जलवायु और सहनीय पदार्थों की जानकारी।",
    },
    {
        "field_key": "dashavidha_satmya",
        "language_code": "mr",
        "display_name": "दशविध - सात्म्य (अनुकूलता व सवय)",
        "description": "रुग्णाला मानवणारे अन्न, हवामान आणि सवयींचे मूल्यमापन.",
    },
    # 13. dashavidha_satva
    {
        "field_key": "dashavidha_satva",
        "language_code": "en",
        "display_name": "Dashavidha - Satva (Mental Strength / Resilience)",
        "description": "Psychological tolerance, mental fortitude, and stress coping capacity.",
    },
    {
        "field_key": "dashavidha_satva",
        "language_code": "hi",
        "display_name": "दशविध - सत्व (मानसिक बल)",
        "description": "मानसिक शक्ति, सहनशीलता और तनाव सहन करने की क्षमता।",
    },
    {
        "field_key": "dashavidha_satva",
        "language_code": "mr",
        "display_name": "दशविध - सत्व (मानसिक बळ)",
        "description": "मानसिक ताकद, सहनशक्ती आणि तणाव हाताळण्याची क्षमता.",
    },
    # 14. dashavidha_ahara_shakti
    {
        "field_key": "dashavidha_ahara_shakti",
        "language_code": "en",
        "display_name": "Dashavidha - Ahara Shakti (Digestive Capacity)",
        "description": "Capacity to ingest (Abhyavaharana) and digest (Jarana) food.",
    },
    {
        "field_key": "dashavidha_ahara_shakti",
        "language_code": "hi",
        "display_name": "दशविध - आहार शक्ति (भोजन एवं पाचन क्षमता)",
        "description": "आहार ग्रहण करने और पचाने की क्षमता का मूल्यांकन।",
    },
    {
        "field_key": "dashavidha_ahara_shakti",
        "language_code": "mr",
        "display_name": "दशविध - आहार शक्ती (पचन व ग्रहण क्षमता)",
        "description": "अन्न ग्रहण करण्याची आणि ते पचवण्याची क्षमता.",
    },
    # 15. dashavidha_vyayama_shakti
    {
        "field_key": "dashavidha_vyayama_shakti",
        "language_code": "en",
        "display_name": "Dashavidha - Vyayama Shakti (Physical Work Capacity)",
        "description": "Endurance, exercise tolerance, and physical work capacity.",
    },
    {
        "field_key": "dashavidha_vyayama_shakti",
        "language_code": "hi",
        "display_name": "दशविध - व्यायाम शक्ति (कार्य क्षमता)",
        "description": "शारीरिक परिश्रम और व्यायाम सहन करने की क्षमता।",
    },
    {
        "field_key": "dashavidha_vyayama_shakti",
        "language_code": "mr",
        "display_name": "दशविध - व्यायाम शक्ती (शारीरिक क्षमता)",
        "description": "शारीरिक कष्ट आणि व्यायाम करण्याची क्षमता.",
    },
    # 16. dashavidha_vaya
    {
        "field_key": "dashavidha_vaya",
        "language_code": "en",
        "display_name": "Dashavidha - Vaya (Age / Chronological Stage)",
        "description": "Age category and related metabolic stage of life.",
    },
    {
        "field_key": "dashavidha_vaya",
        "language_code": "hi",
        "display_name": "दशविध - वय (आयु अवस्था)",
        "description": "आयु वर्ग और जीवन के अवस्था-आधारित शारीरिक बदलाव।",
    },
    {
        "field_key": "dashavidha_vaya",
        "language_code": "mr",
        "display_name": "दशविध - वय (वयाची अवस्था)",
        "description": "वयाचा टप्पा आणि त्यानुसार शरीरातील बदल.",
    },
    # 17. ahara_pattern
    {
        "field_key": "ahara_pattern",
        "language_code": "en",
        "display_name": "Dietary Pattern and Timing",
        "description": "Meal timings, meal frequency, snacking habits, and eating schedule.",
    },
    {
        "field_key": "ahara_pattern",
        "language_code": "hi",
        "display_name": "आहार समय व आदतें",
        "description": "भोजन का समय, बारंबारता और खान-पान की दिनचर्या।",
    },
    {
        "field_key": "ahara_pattern",
        "language_code": "mr",
        "display_name": "आहार वेळ आणि पद्धत",
        "description": "जेवणाची वेळ, वारंवारता आणि खाण्यापिण्याच्या सवयी.",
    },
    # 18. ahara_preferences
    {
        "field_key": "ahara_preferences",
        "language_code": "en",
        "display_name": "Taste and Food Preferences",
        "description": "Preference for specific tastes (Rasa), temperatures (hot/cold), and food types.",
    },
    {
        "field_key": "ahara_preferences",
        "language_code": "hi",
        "display_name": "रस एवं भोजन पसंद",
        "description": "स्वाद (रस), भोजन के तापमान (गरम/ठंडा) और खाद्य प्राथमिकताओं का विवरण।",
    },
    {
        "field_key": "ahara_preferences",
        "language_code": "mr",
        "display_name": "रस आणि आवडीनिवडी",
        "description": "रुग्णाला आवडणारे चव (रस), उष्ण/शीत अन्न आणि खाद्यपदार्थांची आवड.",
    },
    # 19. ahara_restrictions
    {
        "field_key": "ahara_restrictions",
        "language_code": "en",
        "display_name": "Dietary Restrictions and Incompatibilities",
        "description": "Food intolerances, cultural dietary restrictions, or incompatible foods.",
    },
    {
        "field_key": "ahara_restrictions",
        "language_code": "hi",
        "display_name": "आहार वर्जना एवं असंगत भोजन",
        "description": "भोजन एलर्जी, परहेज या विरुद्ध आहार संबंधी जानकारी।",
    },
    {
        "field_key": "ahara_restrictions",
        "language_code": "mr",
        "display_name": "आहार पथ्य व विरुद्ध अन्न",
        "description": "अन्नाची ॲलर्जी, पथ्ये आणि विरुद्ध अन्नाची माहिती.",
    },
    # 20. vihara_activity
    {
        "field_key": "vihara_activity",
        "language_code": "en",
        "display_name": "Physical Activity and Lifestyle",
        "description": "Daily physical exercise, posture, occupational routines, and sedentary time.",
    },
    {
        "field_key": "vihara_activity",
        "language_code": "hi",
        "display_name": "शारीरिक गतिविधि एवं विहार",
        "description": "दैनिक शारीरिक व्यायाम, बैठने की मुद्रा और कार्यशैली।",
    },
    {
        "field_key": "vihara_activity",
        "language_code": "mr",
        "display_name": "शारीरिक हालचाल आणि विहार",
        "description": "दैनंदिन व्यायाम, कामाचे स्वरूप आणि जीवनशैली.",
    },
    # 21. sleep_pattern
    {
        "field_key": "sleep_pattern",
        "language_code": "en",
        "display_name": "Sleep Pattern (Nidra)",
        "description": "Sleep duration, daytime sleeping, quality of rest, and insomnia tendencies.",
    },
    {
        "field_key": "sleep_pattern",
        "language_code": "hi",
        "display_name": "निद्रा एवं विश्राम",
        "description": "नींद की अवधि, दिन में सोना, नींद की गुणवत्ता और अनिद्रा की स्थिति।",
    },
    {
        "field_key": "sleep_pattern",
        "language_code": "mr",
        "display_name": "झोपेचे स्वरूप (निद्रा)",
        "description": "झोपेचा कालावधी, दिवसा झोपणे, शांत झोप लागते का याबद्दलची माहिती.",
    },
    # 22. daily_routine
    {
        "field_key": "daily_routine",
        "language_code": "en",
        "display_name": "Daily Regimen (Dinacharya)",
        "description": "Waking schedule, relaxation, and daily habit routines.",
    },
    {
        "field_key": "daily_routine",
        "language_code": "hi",
        "display_name": "दिनचर्या",
        "description": "जागने का समय, विश्राम और दैनिक आदतों की दिनचर्या।",
    },
    {
        "field_key": "daily_routine",
        "language_code": "mr",
        "display_name": "दिनचर्या",
        "description": "उठण्याची वेळ, विश्रांती आणि दैनंदिन सवयींचे वेळापत्रक.",
    },
]


def upgrade() -> None:
    # 1. Add mode column to interviews table with default GENERAL
    op.add_column(
        'interviews',
        sa.Column('mode', sa.String(length=20), server_default='GENERAL', nullable=False),
    )
    op.create_index(op.f('ix_interviews_mode'), 'interviews', ['mode'], unique=False)

    # 2. Seed AYUSH ontology fields
    ontology_table = sa.table(
        'clinical_ontology_fields',
        sa.column('field_key', sa.String),
        sa.column('section', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.Text),
        sa.column('required', sa.Boolean),
        sa.column('priority', sa.Integer),
        sa.column('active', sa.Boolean),
    )
    op.bulk_insert(ontology_table, AYUSH_ONTOLOGY_FIELDS)

    # 3. Seed translations for AYUSH fields
    trans_table = sa.table(
        'clinical_ontology_field_translations',
        sa.column('field_key', sa.String),
        sa.column('language_code', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.Text),
    )
    op.bulk_insert(trans_table, AYUSH_TRANSLATIONS)


def downgrade() -> None:
    ayush_keys = [f["field_key"] for f in AYUSH_ONTOLOGY_FIELDS]
    quoted_keys = ", ".join(f"'{k}'" for k in ayush_keys)

    # 1. Delete translations
    op.execute(f"DELETE FROM clinical_ontology_field_translations WHERE field_key IN ({quoted_keys})")

    # 2. Delete ontology fields
    op.execute(f"DELETE FROM clinical_ontology_fields WHERE field_key IN ({quoted_keys})")

    # 3. Drop mode index and column
    op.drop_index(op.f('ix_interviews_mode'), table_name='interviews')
    op.drop_column('interviews', 'mode')
