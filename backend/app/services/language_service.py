from typing import Dict, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.clinical_ontology import ClinicalOntologyField
from app.models.language import Language
from app.repositories.interview_repository import (
    InterviewRepository,
    interview_repository,
)
from app.repositories.language_repository import (
    ClinicalOntologyTranslationRepository,
    LanguageRepository,
    language_repository,
    ontology_translation_repository,
)
from app.schemas.language import InterviewLanguageResponse, LanguageResponse


class LanguageService:
    def __init__(
        self,
        lang_repo: LanguageRepository = language_repository,
        trans_repo: ClinicalOntologyTranslationRepository = ontology_translation_repository,
        interview_repo: InterviewRepository = interview_repository,
    ):
        self.lang_repo = lang_repo
        self.trans_repo = trans_repo
        self.interview_repo = interview_repo

    def get_active_languages(self, db: Session) -> List[LanguageResponse]:
        # Ensure default languages exist
        self.lang_repo.seed_default_languages(db)
        languages = self.lang_repo.get_active_languages(db)
        return [LanguageResponse.model_validate(l) for l in languages]

    def validate_active_language(self, db: Session, language_code: str) -> Language:
        self.lang_repo.seed_default_languages(db)
        lang = self.lang_repo.get_by_code(db, language_code)
        if not lang or not lang.is_active:
            active_langs = self.lang_repo.get_active_languages(db)
            active_codes = ", ".join([l.code for l in active_langs])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Language '{language_code}' is not supported or active. Supported languages: {active_codes}",
            )
        return lang

    def get_translations_map(
        self, db: Session, language_code: str
    ) -> Dict[str, Tuple[str, str]]:
        self.trans_repo.seed_default_translations(db)
        target_trans = self.trans_repo.get_translations_for_interview(db, language_code)
        en_trans = (
            self.trans_repo.get_translations_for_interview(db, "en")
            if language_code != "en"
            else target_trans
        )

        translations_map: Dict[str, Tuple[str, str]] = {}
        # Union all field keys
        all_keys = set(target_trans.keys()) | set(en_trans.keys())
        for key in all_keys:
            if key in target_trans:
                translations_map[key] = (
                    target_trans[key].display_name,
                    target_trans[key].description,
                )
            elif key in en_trans:
                translations_map[key] = (
                    en_trans[key].display_name,
                    en_trans[key].description,
                )

        return translations_map

    def get_field_localization(
        self,
        db: Session,
        field_key: str,
        language_code: str,
        fallback_field: ClinicalOntologyField,
    ) -> Tuple[str, str]:
        self.trans_repo.seed_default_translations(db)
        # 1. Try selected language
        trans = self.trans_repo.get_translation(db, field_key, language_code)
        if trans:
            return trans.display_name, trans.description

        # 2. Try English fallback
        if language_code != "en":
            en_trans = self.trans_repo.get_translation(db, field_key, "en")
            if en_trans:
                return en_trans.display_name, en_trans.description

        # 3. Canonical ontology field fallback
        return fallback_field.display_name, fallback_field.description

    def update_interview_language(
        self, db: Session, interview_id: int, language_code: str
    ) -> InterviewLanguageResponse:
        interview = self.interview_repo.get_by_id(db, interview_id)
        if not interview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview with ID {interview_id} not found.",
            )

        lang = self.validate_active_language(db, language_code)

        interview.language_code = lang.code
        interview.preferred_language = lang.code
        db.commit()
        db.refresh(interview)

        return InterviewLanguageResponse(
            interview_id=interview.id,
            language_code=lang.code,
            name=lang.name,
            native_name=lang.native_name,
        )


language_service = LanguageService()
