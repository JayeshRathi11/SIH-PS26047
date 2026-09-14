"""
Stage 5 NLP Pipeline Orchestrator — Orchestrator Service.

Sequences:
Raw Patient Text
  -> Stage 1: Preprocessing (normalize_text)
  -> Stage 2: Extraction (ClinicalInformationExtractor)
  -> Stage 3: Ontology Mapping (ClinicalOntologyMapper)
  -> Stage 4: Validation & Safety (ClinicalSafetyValidator)
  -> Final Pipeline Result (ClinicalNLPPipelineResult)

Invariants:
- Pure orchestrator; delegates all stage logic to existing stage implementations.
- Strictly deterministic; no direct external AI calls or DB writes.
- Never mutates assertion status (AFFIRMED, DENIED, SUSPECTED).
- Does NOT perform clinical reasoning, diagnosis, or treatment planning.
- Isolates and reports stage failures safely without crashing or losing raw input.
"""

from typing import Optional

from app.nlp.preprocessing import normalize_text
from app.nlp.extraction.schemas import ExtractedClinicalFacts
from app.nlp.extraction.providers import ClinicalFactExtractionProvider
from app.nlp.extraction.service import ClinicalInformationExtractor
from app.nlp.ontology.schemas import ClinicalOntologyMappingResult
from app.nlp.ontology.mapper import ClinicalOntologyMapper
from app.nlp.validation.schemas import (
    ValidationStatus,
    ClinicalValidationResult,
)
from app.nlp.validation.validator import ClinicalSafetyValidator
from app.nlp.pipeline.schemas import (
    PipelineStatus,
    ClinicalNLPPipelineResult,
)


class ClinicalNLPPipeline:
    """
    End-to-end clinical NLP pipeline orchestrator connecting Stages 1 through 4.
    """

    def __init__(
        self,
        extraction_provider: Optional[ClinicalFactExtractionProvider] = None,
        extractor: Optional[ClinicalInformationExtractor] = None,
        ontology_mapper: Optional[ClinicalOntologyMapper] = None,
        validator: Optional[ClinicalSafetyValidator] = None,
    ):
        self.extractor = extractor or ClinicalInformationExtractor(provider=extraction_provider)
        self.ontology_mapper = ontology_mapper or ClinicalOntologyMapper()
        self.validator = validator or ClinicalSafetyValidator()

    def process(
        self,
        text: str,
        language_code: Optional[str] = None,
    ) -> ClinicalNLPPipelineResult:
        """
        Processes raw patient or clinician text through the 4-stage pipeline.

        Args:
            text: Raw input utterance or clinical narration.
            language_code: Optional ISO language code (e.g., 'en', 'hi', 'mr').

        Returns:
            ClinicalNLPPipelineResult containing full trace and gated clinical data.
        """
        raw_text = text if text is not None else ""
        normalized = ""
        extracted: Optional[ExtractedClinicalFacts] = None
        mapped: Optional[ClinicalOntologyMappingResult] = None
        val_result: Optional[ClinicalValidationResult] = None

        # ── Stage 1: Text Preprocessing & Normalization ───────────────────────
        try:
            normalized = normalize_text(raw_text)
        except Exception as err:
            return ClinicalNLPPipelineResult(
                raw_text=raw_text,
                normalized_text="",
                language_code=language_code,
                status=PipelineStatus.STAGE_FAILURE,
                success=False,
                failed_stage="preprocessing",
                error_message=f"Preprocessing error: {str(err)}",
            )

        # ── Stage 2: Clinical Information Extraction ──────────────────────────
        try:
            extracted = self.extractor.extract(normalized, language_code=language_code)
        except Exception as err:
            return ClinicalNLPPipelineResult(
                raw_text=raw_text,
                normalized_text=normalized,
                language_code=language_code,
                status=PipelineStatus.STAGE_FAILURE,
                success=False,
                failed_stage="extraction",
                error_message=f"Extraction error: {str(err)}",
            )

        # ── Stage 3: Clinical Ontology Mapping ────────────────────────────────
        try:
            mapped = self.ontology_mapper.map(extracted)
        except Exception as err:
            return ClinicalNLPPipelineResult(
                raw_text=raw_text,
                normalized_text=normalized,
                language_code=language_code,
                status=PipelineStatus.STAGE_FAILURE,
                success=False,
                failed_stage="ontology_mapping",
                error_message=f"Ontology mapping error: {str(err)}",
                extracted_facts=extracted,
            )

        # ── Stage 4: Validation & Safety Layer ────────────────────────────────
        try:
            val_result = self.validator.validate(mapped)
        except Exception as err:
            return ClinicalNLPPipelineResult(
                raw_text=raw_text,
                normalized_text=normalized,
                language_code=language_code,
                status=PipelineStatus.STAGE_FAILURE,
                success=False,
                failed_stage="validation",
                error_message=f"Validation error: {str(err)}",
                extracted_facts=extracted,
                ontology_mapping=mapped,
            )

        # ── Stage 5: Final Result Construction & Gating ───────────────────────
        if val_result.status == ValidationStatus.VALID:
            pipeline_status = PipelineStatus.VALID
            success = True
            requires_verification = False
            gated_fields = val_result.validated_fields
        elif val_result.status == ValidationStatus.VALID_WITH_WARNINGS:
            pipeline_status = PipelineStatus.VALID_WITH_WARNINGS
            success = True
            requires_verification = True
            gated_fields = val_result.validated_fields
        else:  # ValidationStatus.INVALID
            pipeline_status = PipelineStatus.INVALID
            success = False
            requires_verification = True
            # Never expose invalid information as validated clinical data!
            gated_fields = {}

        return ClinicalNLPPipelineResult(
            raw_text=raw_text,
            normalized_text=normalized,
            language_code=language_code,
            status=pipeline_status,
            success=success,
            requires_human_verification=requires_verification,
            extracted_facts=extracted,
            ontology_mapping=mapped,
            validation_result=val_result,
            validated_fields=gated_fields,
            rejected_items=val_result.rejected_items,
            issues=val_result.issues,
        )


def process_clinical_text(
    text: str,
    language_code: Optional[str] = None,
    extraction_provider: Optional[ClinicalFactExtractionProvider] = None,
) -> ClinicalNLPPipelineResult:
    """
    Convenience function to execute the full 4-stage clinical NLP pipeline.
    """
    pipeline = ClinicalNLPPipeline(extraction_provider=extraction_provider)
    return pipeline.process(text, language_code=language_code)
