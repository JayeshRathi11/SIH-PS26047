"""add_multilingual_support

Revision ID: f8eec2812e08
Revises: cba74366733a
Create Date: 2026-09-13 16:38:48.300896

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8eec2812e08'
down_revision: Union[str, Sequence[str], None] = 'cba74366733a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def upgrade() -> None:
    # 1. Create languages table
    languages_table = op.create_table(
        'languages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('native_name', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_languages_code'), 'languages', ['code'], unique=True)
    op.create_index(op.f('ix_languages_id'), 'languages', ['id'], unique=False)

    # 2. Seed initial languages
    op.bulk_insert(languages_table, DEFAULT_LANGUAGES)

    # 3. Add language_code to interviews with safe data migration
    op.add_column('interviews', sa.Column('language_code', sa.String(length=10), nullable=True))
    op.execute(
        "UPDATE interviews SET language_code = CASE WHEN preferred_language IN ('en', 'hi', 'mr') THEN preferred_language ELSE 'en' END"
    )
    op.alter_column('interviews', 'language_code', nullable=False)
    op.create_foreign_key(
        'fk_interviews_language_code',
        'interviews',
        'languages',
        ['language_code'],
        ['code'],
        ondelete='RESTRICT',
    )
    op.create_index(op.f('ix_interviews_language_code'), 'interviews', ['language_code'], unique=False)

    # 4. Safe migration for existing patients
    op.execute(
        "UPDATE patients SET preferred_language = CASE WHEN preferred_language IN ('en', 'hi', 'mr') THEN preferred_language ELSE 'en' END"
    )

    # 5. Create clinical_ontology_field_translations table
    trans_table = op.create_table(
        'clinical_ontology_field_translations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('field_key', sa.String(length=50), nullable=False),
        sa.Column('language_code', sa.String(length=10), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['field_key'], ['clinical_ontology_fields.field_key'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['language_code'], ['languages.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('field_key', 'language_code', name='uq_field_language_translation'),
    )
    op.create_index(
        op.f('ix_clinical_ontology_field_translations_field_key'),
        'clinical_ontology_field_translations',
        ['field_key'],
        unique=False,
    )
    op.create_index(
        op.f('ix_clinical_ontology_field_translations_language_code'),
        'clinical_ontology_field_translations',
        ['language_code'],
        unique=False,
    )

    # 6. Seed translations for all 10 clinical fields
    op.bulk_insert(trans_table, DEFAULT_TRANSLATIONS)


def downgrade() -> None:
    op.drop_table('clinical_ontology_field_translations')
    op.drop_index(op.f('ix_interviews_language_code'), table_name='interviews')
    op.drop_constraint('fk_interviews_language_code', 'interviews', type_='foreignkey')
    op.drop_column('interviews', 'language_code')
    op.drop_index(op.f('ix_languages_code'), table_name='languages')
    op.drop_index(op.f('ix_languages_id'), table_name='languages')
    op.drop_table('languages')
